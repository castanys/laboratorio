---
description: Close the current task in one call (push, PR, STATUS.md, CI, merge)
argument-hint: ITEM-ID "type: title"
---
Close item `$1` of STATUS.md. Write a 5-line PR body (what / why / how it was tested / risks / item closed) to a scratch file, then run, in the foreground:

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session_close.py $1 --title "<type: title>" --body <FILE> --done "<what was closed>"`

If it prints `NOT CLOSED: …`, fix what it says and run it again with the same arguments. Your last line is the one it prints (`DONE: PR #n merged.`).
