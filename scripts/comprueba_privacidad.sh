#!/usr/bin/env bash
# Privacy gate for what gets published: exits 1 if it finds a path under a home directory,
# an email, a phone number, a token or a term from .privacy-deny; 0 otherwise.
# Prints only file:line and the kind of leak, never the matched text.
#   comprueba_privacidad.sh          tracked + untracked-not-ignored files, minus INTERNAL
#   comprueba_privacidad.sh DIR      every file under DIR
#   comprueba_privacidad.sh --list   the tracked files that get published (tracked minus INTERNAL)
# This script is published but never scanned: its own patterns would match themselves.
set -u
cd "$(dirname "$0")/.."
here=$(pwd)

# Working files of the repo itself: never part of the published plugin.
INTERNAL='^(STATUS\.md|HISTORICO\.md|DEMANDA\.md|CLAUDE\.md|ERRORES_REPORTADOS\.md|LECCIONES\.md|pcc\.yml|\.privacy-deny|\.claude/settings[^/]*|\.git/)'
SELF='^scripts/comprueba_privacidad\.sh$'

if [ "${1:-}" = --list ]; then
    git ls-files | grep -Ev "$INTERNAL" | sort
    exit 0
elif [ $# -ge 1 ]; then
    root=$(cd "$1" && pwd)
    files=$(cd "$root" && find . -type f -not -path './.git/*' | sed 's|^\./||' | grep -Ev "$SELF" | sort)
else
    root=$here
    files=$(git ls-files -co --exclude-standard | grep -Ev "$INTERNAL|$SELF" | sort)
fi

declare -A PATTERNS=(
    [home-path]='/home/|/Users/[A-Za-z]|C:\\Users\\'
    [email]='[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}'
    [phone]='\+[0-9]{1,3}[ .-]?[0-9]{2,4}([ .-]?[0-9]{2,4}){2,}|(^|[^0-9])[6-9][0-9]{2}[ .-]?[0-9]{3}[ .-]?[0-9]{3}([^0-9]|$)|(^|[^0-9A-Za-z])[0-9]{9,15}([^0-9A-Za-z]|$)'
    [token]='gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[Bb]earer [A-Za-z0-9._-]{20,}|(token|secret|passw(or)?d|api[_-]?key)[A-Za-z_]*[ ]*[=:][ ]*["'"'"']?[A-Za-z0-9_./+-]{16,}'
)
# Emails that are not personal: documentation domains, git over ssh, bot addresses.
ALLOWED_EMAIL='@(example\.(com|org|net)|users\.noreply\.github\.com|anthropic\.com)$|^git@github\.com$'

found=0
report() { echo "$1:$2: $3"; found=1; }

deny=()
if [ -f "$here/.privacy-deny" ]; then
    while IFS= read -r term; do
        case "$term" in ''|'#'*) ;; *) deny+=("$term") ;; esac
    done < "$here/.privacy-deny"
fi

while IFS= read -r f; do
    [ -n "$f" ] || continue
    path="$root/$f"
    [ -f "$path" ] || continue
    grep -qI . "$path" 2>/dev/null || continue   # skip binary and empty files
    for kind in "${!PATTERNS[@]}"; do
        while IFS= read -r hit; do
            n=${hit%%:*}; text=${hit#*:}
            if [ "$kind" = email ]; then
                # only the emails that are not on the allowed list count
                echo "$text" | grep -oE "${PATTERNS[email]}" | grep -qEv "$ALLOWED_EMAIL" || continue
            fi
            report "$f" "$n" "$kind"
        done < <(grep -nIE -- "${PATTERNS[$kind]}" "$path" 2>/dev/null)
    done
    for term in "${deny[@]+"${deny[@]}"}"; do
        while IFS= read -r hit; do
            report "$f" "${hit%%:*}" "denied-term"
        done < <(grep -nIiF -- "$term" "$path" 2>/dev/null)
    done
done <<< "$files"

if [ "$found" -eq 0 ]; then
    echo "privacy check: clean ($(echo "$files" | grep -c .) files)"
fi
exit "$found"
