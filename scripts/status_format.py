#!/usr/bin/env python3
"""Validate that a STATUS.md follows the common format.

Usage: python3 status_format.py PATH/STATUS.md   (exit 1 and one line per problem)
In a test: `from status_format import check, warnings`.

Format: `GOAL:` first, then `## OPEN (N)`, `## DECISIONS (N)`, `## DONE (N)`, at most 60
lines, numbered lists and never tables. An OPEN item is one line: stable id (`AREA-NN`,
never `#NN`, which GitHub links to a PR), a checkable `wins:`, the part of the GOAL it
serves, and a final `[impact N]` (1-10) with an optional `[origin human|plan|failure|auto]`.
Items without an origin are `auto`: session_pass.py never launches them.
"""
import re
import sys

SECTIONS = ["## OPEN", "## DECISIONS", "## DONE"]
MAX_LINES = 60
MAX_KEPT = 10
MARGIN = 3

HEADER = re.compile(r"^## (?:OPEN|DECISIONS|DONE) \((\d+)")
ITEM = re.compile(r"^(\d+)\. +`([A-Z0-9]{2,}-\d{2,})` +\S")
HASH_ID = re.compile(r"`?#\d+`?")
TABLE_SEPARATOR = re.compile(r"^(?=.*-)(?=.*\|)[\s|:-]+$")
IMPACT = re.compile(r"\[impact (?:10|[1-9])\]")
ORIGIN = re.compile(r"\[origin (?:human|plan|failure|auto)\]")
TRAILING_BRACKETS = re.compile(r"(?:\[[^\[\]]*\]\s*)+$")
BRACKET = re.compile(r"\[[^\[\]]*\]")
WINS = re.compile(r"\bwins: *\S")


def _section_lines(lines, name):
    out, inside = [], False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line.startswith(name)
            continue
        if inside:
            out.append(line)
    return out


def _entries(lines, name):
    return [l for l in _section_lines(lines, name)
            if l.strip() and (l[0].isdigit() or l.startswith("- "))]


def _tail_ok(line):
    """The trailing brackets are exactly one `[impact N]` and at most one `[origin X]`."""
    m = TRAILING_BRACKETS.search(line)
    if not m:
        return False
    kinds = [("impact" if IMPACT.fullmatch(t) else "origin" if ORIGIN.fullmatch(t) else None)
             for t in BRACKET.findall(m.group())]
    return None not in kinds and kinds.count("impact") == 1 and len(set(kinds)) == len(kinds)


def check(text):
    """Reasons why `text` does not follow the format. Empty = fine."""
    problems = []
    lines = text.splitlines()
    if not text.startswith("GOAL:"):
        problems.append("does not start with `GOAL:`: a title or preamble hides what is open")
    present = [s for s in SECTIONS if s in text]
    if missing := [s for s in SECTIONS if s not in text]:
        problems.append(f"missing sections: {', '.join(missing)}")
    order = sorted(present, key=text.index)
    if order != present:
        problems.append("sections out of order: OPEN first, DONE last (it is history)")
    if len(lines) > MAX_LINES:
        problems.append(f"{len(lines)} lines, over {MAX_LINES}")
    if any(TABLE_SEPARATOR.match(l) for l in lines):
        problems.append("uses a table: the format is a numbered list")

    declared = None
    for line in lines:
        if line.startswith("## OPEN"):
            m = HEADER.match(line)
            if m:
                declared = int(m.group(1))
            else:
                problems.append(f"`{line}` has no `(N)` counter")
    items = _entries(lines, "## OPEN")
    if declared is not None and declared != len(items):
        problems.append(f"OPEN says ({declared}) and has {len(items)} items: update the counter")

    ids = []
    for n, line in enumerate(items, 1):
        m = ITEM.match(line)
        if not m:
            problems.append(f"item {n} has no `N.` plus a stable id in backticks (`AREA-01`)")
            if HASH_ID.search(line):
                problems.append(f"item {n} uses `#NN` as id: GitHub links it to a PR; use `AREA-NN`")
            continue
        if int(m.group(1)) != n:
            problems.append(f"item {n} numbered {m.group(1)}: renumber")
        ids.append(m.group(2))
        name = m.group(2)
        if not WINS.search(line):
            problems.append(f"item `{name}` has no checkable `wins:`")
        if "GOAL:" not in line:
            problems.append(f"item `{name}` does not say which part of the GOAL it serves")
        if not _tail_ok(line):
            problems.append(f"item `{name}` must end in `[impact 1-10]` and at most one "
                            "`[origin human|plan|failure|auto]`")
    if repeated := {i for i in ids if ids.count(i) > 1}:
        problems.append(f"repeated ids: {', '.join(sorted(repeated))}")
    return problems


def warnings(text):
    """Things to fix soon that do not break anything yet."""
    out = []
    lines = text.splitlines()
    if MAX_LINES - MARGIN <= len(lines) <= MAX_LINES:
        out.append(f"{len(lines)} lines of {MAX_LINES}: archive to HISTORICO.md now")
    for name, label in (("## DECISIONS", "DECISIONS"), ("## DONE", "DONE")):
        n = len(_entries(lines, name))
        if n > MAX_KEPT:
            out.append(f"{label} has {n} entries and the cap is {MAX_KEPT}: move the oldest "
                       "to HISTORICO.md")
    return out


def main(argv):
    if len(argv) != 2:
        print(f"usage: {argv[0]} PATH/STATUS.md", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        text = f.read()
    problems = check(text)
    for p in problems:
        print(f"- {p}")
    for w in warnings(text):
        print(f"- WARNING: {w}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
