#!/usr/bin/env bash
# No absolute paths.
set -e
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && . .venv/bin/activate
PY=$(command -v python || command -v python3)
"$PY" -m pytest -q -x --tb=short
