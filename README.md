# laboratorio

**Keep unattended Claude Code sessions from eating your weekly subscription quota, and get a WhatsApp message when one needs you.** The share of the quota you leave to sessions is spread over the 7 days of the week; when today's cap is reached, nothing launches until tomorrow. As an extra, a session can finish its own pull request: it works on one item of a `STATUS.md` and merges only when CI is green. Free and open; no service, no account, no telemetry.

[Leer en español](README.es.md)

## Why a cap on the quota, not on dollars

`claude --max-budget-usd` counts API dollars. On a Pro or Max plan it has stopped runs that cost nothing (claude-code issue #85400) while the weekly bar keeps filling, and that bar is what actually ends your week early. The cap here works on the percentage your plan shows, so it protects the thing you run out of.

## What you get

- **Weekly cap** (`scripts/weekly_cap.py`): `100 - reserve` percent of the weekly quota is left to sessions (the reserve is yours for working by hand) and spread by days, plus a small margin for a busier day. Exit 0 if there is room to launch, 1 with the reason if not. It reads the weekly percentage and the renewal time that `/usage` shows, with the login `claude` already keeps (no other credential; the token is never printed or stored); exit 2 if it cannot read them.
- **WhatsApp alerts** (`scripts/notify_whatsapp.py`): any gateway that accepts `POST /send {"recipient", "message"}`. Exit 0 only when the gateway confirms the send, so a silent failure cannot pass for a delivered alert.
- **Extra: sessions that finish their PR**
  - **Passes** (`scripts/session_pass.py`): one pass = one item. It picks the first OPEN item that someone asked for (`[origin human|plan|failure]`), checks the weekly cap, runs `claude -p` in its own git worktree with a USD ceiling, and reports `DONE` / `ASK` / `BLOCKED`. Items without an origin are never launched: sessions that invent and score their own work are where unattended spend goes.
  - **One-call close** (`scripts/session_close.py`): push, open the PR, move the item from OPEN to DONE in `STATUS.md`, wait for CI, squash-merge. Idempotent: after a red CI, fix and run it again with the same arguments. It never merges with a red check, or with no checks on a repo that has workflows.
  - **`pre-push` guard** (`hooks/pre-push`): main/master cannot be updated or deleted on the remote. Branch and PR only. Works without a paid GitHub plan.
  - **`STATUS.md` format** (`scripts/status_format.py`): one-line items with a stable id, a checkable `wins:` and an `[impact N]`, capped at 60 lines. Fits one screen, so a session reads what is open without scrolling.

## Install

```sh
git clone https://github.com/castanys/laboratorio ~/laboratorio
claude plugin marketplace add ~/laboratorio
claude plugin install laboratorio@laboratorio
```

The clone is where the scripts live, at a path that does not change between versions (cron and the git hook point at it); the plugin adds the `/laboratorio:*` commands. Update with `git -C ~/laboratorio pull && claude plugin marketplace update laboratorio`.

## Use

**Cap.** The week's percentage and renewal time come from the same endpoint `/usage` uses, fetched with a token you hand over yourself: the plugin never reads your machine's credential store. The token is the OAuth token of your `claude` login. When you enable the plugin, Claude Code asks for it (`usage_token`, kept in its secure store and passed to the plugin's processes as `CLAUDE_PLUGIN_OPTION_USAGE_TOKEN`). From cron, give it a command of yours that prints the current one (it rotates, so not a pasted copy):

```sh
python3 ~/laboratorio/scripts/weekly_cap.py --token-cmd 'your-command-that-prints-it' && echo "room to launch"
```

It prints the week's percentage, today's cap and the renewal time. Defaults: `--reserve 15` (kept for you), `--margin 5`; `--pct 42 --renews 2026-10-11T18:00:00+00:00` overrides the reading. Put it in front of whatever launches your sessions (cron, a script, `session_pass.py`).

**WhatsApp.** Set `WHATSAPP_API_URL` and `WHATSAPP_RECIPIENT` in the environment or a `.env` outside git (there is no default URL on purpose), then `python3 ~/laboratorio/scripts/notify_whatsapp.py "text"`.

**Extra: sessions that finish their PR.** In the repo you want to protect, `bash ~/laboratorio/scripts/install_hooks.sh` (it prints the one `git config core.hooksPath …` line it runs; undo with `git config --unset core.hooksPath`). Start from the `STATUS.md` shape that `status_format.py` validates:

```
GOAL: one sentence
## OPEN (1)
1. `APP-01` wins: `make test` exits 0 on the new parser; serves GOAL: ship v1 [impact 7] [origin human]
## DECISIONS (0)
## DONE (0)
```

- `python3 ~/laboratorio/scripts/session_pass.py REPO --token-cmd 'your-command-that-prints-it'` runs one pass if the weekly cap allows (and none if the quota cannot be read).
- `/laboratorio:close ITEM-ID "feat: title"` closes the task you just finished.
- `/laboratorio:check-status` validates `STATUS.md`.

## Develop

`bash .claude/test.sh` runs the suite; `bash scripts/comprueba_privacidad.sh` is the privacy gate (exit 1 on a home-directory path, an email, a phone number, a token or a term in `.privacy-deny`). Requires `git`, `gh`, `python3 >= 3.9`, `claude`.

MIT licensed.
