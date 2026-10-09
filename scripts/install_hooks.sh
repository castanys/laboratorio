#!/usr/bin/env bash
# Activate the pre-push guard (main/master cannot be pushed to or deleted) in the current repo.
# It prints what it changes first; undo with `git config --unset core.hooksPath`.
set -e
here=$(cd "$(dirname "$0")/.." && pwd)
echo "git config core.hooksPath $here/hooks   (repo: $(git rev-parse --show-toplevel))"
git config core.hooksPath "$here/hooks"
