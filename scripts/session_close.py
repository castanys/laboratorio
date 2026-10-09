#!/usr/bin/env python3
"""Close a task in one call: push, PR, STATUS.md, CI, merge.

One call of paperwork costs as much as one of work (each call re-reads the whole context),
so the ceremony is a single idempotent script: after a red CI, fix and run it again with the
same arguments.

The barrier is the PR's CI: with any check not green, or no checks at all on a repo that has
workflows, nothing is merged. The item moves from OPEN to DONE in STATUS.md with its PR
number; DONE and DECISIONS keep the last 10 and the rest goes to HISTORICO.md.

Usage: session_close.py ID --title "type: text" --body FILE --done "what was closed"
       [--decision "text"] [--tag vX.Y]
The last line printed is `DONE: PR #n merged.` (`, tag vX.Y.`) or `NOT CLOSED: reason`.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

KEEP = 10
GREEN = {"SUCCESS", "PASS", "NEUTRAL", "SKIPPED"}
PROTECTED = ("main", "master", "HEAD", "")
PR_URL = re.compile(r"/pull/(\d+)")
CHECK_RETRIES = 8
SECONDS_BETWEEN = 15


class CannotClose(Exception):
    pass


def _run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _section(lines, name):
    """(start, end) line range of the `## name` section, body only; None if absent."""
    for i, line in enumerate(lines):
        if line.startswith("## " + name):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            return i, j
    return None


def _renumber_header(header, n):
    return re.sub(r"\(\d+\)", f"({n})", header, count=1)


def close_item(text, id_, done, pr, today, decision=None):
    """(new STATUS.md, text to append to HISTORICO.md). Raises CannotClose."""
    lines = text.splitlines()
    span = _section(lines, "OPEN")
    if span is None:
        raise CannotClose("STATUS.md has no OPEN section")
    start, end = span
    body = lines[start + 1:end]
    idx = next((k for k, l in enumerate(body) if f"`{id_}`" in l and re.match(r"\d+\. ", l)), None)
    if idx is None:
        raise CannotClose(f"`{id_}` is not in OPEN")
    del body[idx]
    items = [l for l in body if re.match(r"\d+\. ", l)]
    n = 0
    renumbered = []
    for l in body:
        if re.match(r"\d+\. ", l):
            n += 1
            l = re.sub(r"^\d+\.", f"{n}.", l)
        renumbered.append(l)
    lines[start:end] = [_renumber_header(lines[start], len(items))] + renumbered

    history = []
    if decision:
        lines = _append(lines, "DECISIONS", f"- {today}: {decision}", history, dash=True)
    lines = _append(lines, "DONE", f"0. `{id_}` {done} (PR #{pr}, {today})", history, dash=False)
    return "\n".join(lines) + "\n", "".join(l + "\n" for l in history)


def _append(lines, name, entry, history, dash):
    span = _section(lines, name)
    if span is None:
        raise CannotClose(f"STATUS.md has no {name} section")
    start, end = span
    body = [l for l in lines[start + 1:end] if l.strip()]
    pattern = r"- " if dash else r"\d+\. "
    kept = [l for l in body if re.match(pattern, l)]
    other = [l for l in body if not re.match(pattern, l)]
    if dash:
        kept.append(entry)
    else:
        kept.insert(0, entry)  # newest first in DONE
    while len(kept) > KEEP:
        history.append(kept.pop(0) if dash else kept.pop())
    if not dash:
        kept = [re.sub(r"^\d+\.", f"{i}.", l) for i, l in enumerate(kept, 1)]
    lines[start:end] = [_renumber_header(lines[start], len(kept))] + other + kept
    return lines


def _principal(run, cwd):
    return "main" if any(run(["git", "rev-parse", "--verify", "--quiet", ref], cwd)[0] == 0
                         for ref in ("main", "origin/main")) else "master"


def _checks(run, cwd, n):
    code, out = run(["gh", "pr", "view", str(n), "--json", "statusCheckRollup"], cwd)
    try:
        rollup = json.loads(out)["statusCheckRollup"] if code == 0 else None
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(rollup, list):
        return None
    latest = {}
    for c in rollup:  # a new commit cancels the running one: only the last run of each counts
        key = (c.get("workflowName") or "", c.get("name") or "")
        if key not in latest or str(c.get("startedAt") or "9999") >= str(latest[key].get("startedAt") or "9999"):
            latest[key] = c
    return [{"name": k[1], "state": "PENDING" if str(c.get("status") or "COMPLETED").upper() != "COMPLETED"
             else c.get("conclusion") or c.get("state") or "PENDING"} for k, c in latest.items()]


def _open_pr(run, cwd, branch, title, body, id_):
    code, ahead = run(["git", "rev-list", "--count", f"origin/{_principal(run, cwd)}..HEAD"], cwd)
    if code == 0 and ahead.strip() == "0":
        run(["git", "commit", "--allow-empty", "-m", f"{title.split(':', 1)[0]}: open {id_}"], cwd)
    code, out = run(["git", "push", "-u", "origin", branch], cwd)
    if code != 0:
        raise CannotClose("push failed:\n" + out[-800:])
    code, out = run(["gh", "pr", "view", "--json", "number,state"], cwd)
    try:
        pr = json.loads(out) if code == 0 else {}
    except ValueError:
        pr = {}
    if pr.get("state") == "OPEN" and isinstance(pr.get("number"), int):
        return pr["number"]
    code, out = run(["gh", "pr", "create", "--title", title, "--body", body], cwd)
    m = PR_URL.search(out)
    if code != 0 or not m:
        raise CannotClose("could not open the PR:\n" + out[-800:])
    return int(m.group(1))


def _wait_for_ci(run, cwd, n, sleep):
    has_ci = os.path.isdir(os.path.join(cwd, ".github", "workflows"))
    for _ in range(CHECK_RETRIES):
        run(["gh", "pr", "checks", str(n), "--watch"], cwd)
        checks = _checks(run, cwd, n)
        if checks is None:
            raise CannotClose(f"could not read the CI of PR #{n}: no CI status, no merge")
        if checks or not has_ci:
            break
        sleep(SECONDS_BETWEEN)
    else:
        raise CannotClose(f"PR #{n} has no checks and the repo has CI: not merging without a "
                          "green light; run again when GitHub registers them")
    red = [c for c in checks if str(c["state"]).upper() not in GREEN]
    if red:
        raise CannotClose("the CI is not green (" + ", ".join(f"{c['name']}: {c['state']}" for c in red)
                          + "). Failures: gh run view --log-failed. Fix and run again with the same arguments.")


def close(cwd, id_, title, body, done, decision=None, tag=None, run=_run, today=None,
          sleep=time.sleep):
    today = today or datetime.date.today().isoformat()
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)[1].strip()
    if branch in PROTECTED:
        raise CannotClose(f"you are on `{branch}`: close from the task's branch")
    path = os.path.join(cwd, "STATUS.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    already = re.search(rf"^\d+\. `{re.escape(id_)}` .*\(PR #(\d+),", text, re.M)
    n = _open_pr(run, cwd, branch, title, body, id_)
    if not already:
        new, history = close_item(text, id_, done, n, today, decision)
        written = [path]
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        if history:
            hpath = os.path.join(cwd, "HISTORICO.md")
            old = open(hpath, encoding="utf-8").read() if os.path.exists(hpath) else ""
            with open(hpath, "w", encoding="utf-8") as f:
                f.write(old + history)
            written.append(hpath)
        run(["git", "add", *written], cwd)
        code, out = run(["git", "commit", "-m", f"{title.split(':', 1)[0]}: close {id_} in STATUS.md"], cwd)
        if code != 0:
            raise CannotClose("the closing commit failed:\n" + out[-800:])
        code, out = run(["git", "push", "origin", branch], cwd)
        if code != 0:
            raise CannotClose("push failed:\n" + out[-800:])
    _wait_for_ci(run, cwd, n, sleep)
    code, out = run(["gh", "pr", "merge", str(n), "--squash", "--delete-branch"], cwd)
    if code != 0 and "failed to delete remote branch" not in out:
        state = run(["gh", "pr", "view", str(n), "--json", "state"], cwd)[1]
        if '"MERGED"' not in state:
            raise CannotClose("the merge failed:\n" + out[-800:])
    if tag:
        main_ref = "origin/" + _principal(run, cwd)
        run(["git", "fetch", "origin", main_ref[7:]], cwd)
        for cmd in (["git", "tag", tag, main_ref], ["git", "push", "origin", tag]):
            code, out = run(cmd, cwd)
            if code != 0:
                raise CannotClose(f"PR #{n} merged, but `{' '.join(cmd)}` failed:\n" + out[-800:])
        return f"DONE: PR #{n} merged, tag {tag}."
    return f"DONE: PR #{n} merged."


def main(argv=None):
    p = argparse.ArgumentParser(description="Close a task in one call.")
    p.add_argument("id")
    p.add_argument("--title", required=True)
    p.add_argument("--body", required=True, help="file with the PR description")
    p.add_argument("--done", required=True)
    p.add_argument("--decision")
    p.add_argument("--tag")
    a = p.parse_args(argv)
    try:
        with open(a.body, encoding="utf-8") as f:
            body = f.read()
        print(close(os.getcwd(), a.id, a.title, body, a.done, a.decision, a.tag))
    except (CannotClose, OSError) as e:
        print(f"NOT CLOSED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
