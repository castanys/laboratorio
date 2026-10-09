#!/usr/bin/env bash
# Builds the public tree in DEST: the tracked files of this repo minus its working files
# (comprueba_privacidad.sh --list), then runs the privacy gate on DEST.
# The public repo gets this tree as fresh commits, never this repo's history.
#   exporta_publico.sh DEST     exit 0 clean · 1 leak found · 2 DEST not empty
set -eu
cd "$(dirname "$0")/.."
dest=${1:?usage: exporta_publico.sh DEST}
if [ -e "$dest" ] && [ -n "$(ls -A "$dest")" ]; then
    echo "exporta_publico: $dest is not empty" >&2
    exit 2
fi
mkdir -p "$dest"
bash scripts/comprueba_privacidad.sh --list | while IFS= read -r f; do
    [ -f "$f" ] || continue
    mkdir -p "$dest/$(dirname "$f")"
    cp -p "$f" "$dest/$f"
done
echo "exporta_publico: $(find "$dest" -type f | wc -l) files in $dest"
bash scripts/comprueba_privacidad.sh "$dest"
