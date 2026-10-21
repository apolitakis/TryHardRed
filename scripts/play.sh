#!/bin/sh
# Play the latest TryHardRed build in mGBA on your own computer (macOS or Linux), no uploading.
#
#   sh scripts/play.sh /path/to/firered.gba   # first time: remembers your clean FireRed (USA 1.0) ROM
#   sh scripts/play.sh                         # after that: fetch the newest patch if there is one, patch, launch
#
# Everything lives in ~/.tryhardred: your clean ROM, the patched game (always the same file name, so mGBA keeps
# using the same save file across updates) and the last patch. Needs python3 and curl; launches mGBA if installed
# (https://mgba.io), otherwise prints where the patched ROM is so you can open it in any emulator.
# PATCH_URL picks another build (default: the playtest preview).
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
HOME_DIR=${TRYHARDRED_HOME:-$HOME/.tryhardred}
PATCH_URL=${PATCH_URL:-https://playtest.tryhardred.pages.dev/play/patch}
mkdir -p "$HOME_DIR"
CLEAN="$HOME_DIR/firered-clean.gba"
GAME="$HOME_DIR/tryhardred.gba"

if [ $# -ge 1 ]; then
  cp "$1" "$CLEAN"
  echo "Remembered your ROM in $CLEAN"
fi
[ -f "$CLEAN" ] || { echo "First run: sh scripts/play.sh /path/to/your/firered.gba" >&2; exit 1; }

# Newest patch, only downloaded when the build changed.
if curl -fsS "$PATCH_URL/patch.json" -o "$HOME_DIR/patch.json.new"; then
  NEW=$(python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); print(m["version"], m["patches"][0]["file"])' "$HOME_DIR/patch.json.new")
  OLD=$(cat "$HOME_DIR/version" 2>/dev/null || true)
  if [ "$NEW" != "$OLD" ] || [ ! -f "$GAME" ]; then
    FILE=${NEW#* }
    echo "Downloading build ${NEW% *}…"
    curl -fsS "$PATCH_URL/$FILE" -o "$HOME_DIR/patch.bps"
    python3 "$HERE/tools/patch/bps.py" apply "$CLEAN" "$HOME_DIR/patch.bps" "$GAME.new"
    mv "$GAME.new" "$GAME"
    echo "$NEW" > "$HOME_DIR/version"
  else
    echo "Already on the newest build (${NEW% *})."
  fi
  rm -f "$HOME_DIR/patch.json.new"
else
  [ -f "$GAME" ] || { echo "Couldn't download the patch from $PATCH_URL" >&2; exit 1; }
  echo "Offline: playing the last build you downloaded."
fi

if [ "$(uname)" = Darwin ] && open -Ra mGBA 2>/dev/null; then
  open -a mGBA "$GAME"
elif command -v mgba-qt >/dev/null 2>&1; then
  mgba-qt "$GAME" >/dev/null 2>&1 &
elif command -v flatpak >/dev/null 2>&1 && flatpak info io.mgba.mGBA >/dev/null 2>&1; then
  flatpak run io.mgba.mGBA "$GAME" >/dev/null 2>&1 &
else
  echo "Patched game: $GAME (install mGBA from https://mgba.io to launch it automatically)"
fi
