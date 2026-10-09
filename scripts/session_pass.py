#!/usr/bin/env python3
"""One pass = one item: launch `claude -p` on the first launchable OPEN item of a repo.

Launchable means the item carries `[origin human]`, `[origin plan]` or `[origin failure]`
(an item without origin is `auto` and never launched: sessions inventing and scoring their
own work is where unattended spend goes) and does not wait for a date (`(since YYYY-MM-DD)`).
Before launching it checks the weekly cap (weekly_cap.py, which reads the quota with the
token you hand over through --token-cmd or the plugin's usage_token option, unless --pct and
--renews are given; unreadable means no launch); each pass runs in its own git worktree from
origin/main with a USD ceiling. The session ends with a last line `DONE: …`, `ASK [kind]: …`
or `BLOCKED: …`; anything but DONE is sent to WhatsApp (notify_whatsapp.py) if it is
configured.

Usage: session_pass.py [REPO] [--token-cmd CMD] [--pct N --renews ISO]
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notify_whatsapp  # noqa: E402
import status_format  # noqa: E402
import weekly_cap  # noqa: E402

Item = namedtuple("Item", "id line")
LAUNCHABLE = re.compile(r"\[origin (human|plan|failure)\]")
SINCE = re.compile(r"\(since (\d{4}-\d{2}-\d{2})\)")
VERDICT = re.compile(r"^(DONE|ASK|BLOCKED)\b")
PROMPT = ("Task: item {id} of STATUS.md. Branch from origin/main, write a failing test first, "
          "make `bash .claude/test.sh` pass, close with session_close.py. If it cannot advance "
          "until a date, finish with `wait until YYYY-MM-DD`. End with one last line: "
          "`DONE: PR #n merged.`, `ASK [kind]: …` or `BLOCKED: …`.\n\nItem: {line}")


def pick_item(status, today=None):
    today = today or dt.date.today().isoformat()
    for line in status_format._entries(status.splitlines(), "## OPEN"):
        m = status_format.ITEM.match(line)
        if not m or not LAUNCHABLE.search(line):
            continue
        since = SINCE.search(line)
        if since and since.group(1) > today:
            continue
        return Item(m.group(2), line)
    return None


def build_command(prompt, model="sonnet", budget=8):
    return ["claude", "-p", prompt, "--model", model, "--max-budget-usd", str(budget),
            "--permission-mode", "bypassPermissions"]


def verdict(output):
    last = [l.strip() for l in output.strip().splitlines() if l.strip()][-1:] or [""]
    m = VERDICT.match(last[0])
    return m.group(1) if m else "NONE"


def launch(item, repo, model="sonnet", budget=8):
    """Run the session in a fresh worktree and return its output."""
    branch = f"pass/{item.id.lower()}"
    tree = os.path.join(repo, ".worktrees", branch.replace("/", "-"))
    subprocess.run(["git", "fetch", "origin", "main"], cwd=repo, capture_output=True)
    subprocess.run(["git", "worktree", "add", "-B", branch, tree, "origin/main"],
                   cwd=repo, capture_output=True, check=True)
    r = subprocess.run(build_command(PROMPT.format(id=item.id, line=item.line), model, budget),
                       cwd=tree, capture_output=True, text=True)
    return r.stdout


def _notify(text):
    url, recipient = notify_whatsapp.config()
    notify_whatsapp.send(text, url, recipient)


def run_pass(repo, usage=None, launch=launch, notify=_notify, today=None):
    """Returns "paused: …", "idle", or the verdict of the session. `usage` None means the
    quota could not be read: nothing is launched."""
    reason = weekly_cap.UNREADABLE if usage is None else weekly_cap.pause_reason(usage)
    if reason:
        notify(f"laboratorio: {reason}")
        return f"paused: {reason}"
    with open(os.path.join(repo, "STATUS.md"), encoding="utf-8") as f:
        item = pick_item(f.read(), today)
    if item is None:
        return "idle"
    output = launch(item, repo)
    result = verdict(output)
    if result != "DONE":
        last = output.strip().splitlines()[-1:] or [""]
        notify(f"laboratorio {item.id}: {result} - {last[0]}")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("repo", nargs="?", default=".")
    p.add_argument("--token-cmd", help="command that prints the usage token")
    p.add_argument("--pct", type=float)
    p.add_argument("--renews")
    a = p.parse_args(argv)
    handed = weekly_cap.token_from_cmd(a.token_cmd)
    usage = ({"seven_day": (a.pct, a.renews)} if a.pct is not None and a.renews
             else weekly_cap.read_usage(token=handed))
    print(run_pass(os.path.abspath(a.repo), usage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
