#!/bin/sh
# Build the friends' site: the playtest page, a vendored EmulatorJS (mGBA core), the .bps patch, the changelog
# and the feedback endpoint. Layout follows sonterra-tactics hosting/cloudflare/build.sh.
#   CLEAN_ROM=/path/to/firered-usa-1.0.gba [RELEASE=0.1.0] [ROM=pokefirered.gba] sh site/build.sh [OUT]
# OUT (default: out/) gets dist/ (the site), functions/ (the feedback endpoint) and wrangler.toml.
# Deploy from OUT, only on Alex's "ship it":  npx wrangler@4 pages deploy --project-name "$PAGES_PROJECT" --branch main
# Without RELEASE it's a dry run: the version reads like "dev-1a2b3c4" and no changelog section is needed.
# The clean ROM is only read to diff against; it never lands in OUT.
set -eu
cd "$(dirname "$0")/.."
OUT=${1:-out}
D=$OUT/dist
ROM=${ROM:-pokefirered.gba}
EJS_VERSION=4.2.3
SOURCE_LABEL=${SOURCE_LABEL:-"FireRed (USA) 1.0"}
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
BASE=$(git describe --tags --abbrev=0 --match 'expansion/*' 2>/dev/null || echo unknown)

[ -n "${CLEAN_ROM:-}" ] && [ -f "$CLEAN_ROM" ] || { echo "Set CLEAN_ROM to your clean FireRed ROM" >&2; exit 1; }
[ -f "$ROM" ] || { echo "$ROM not found: run 'make firered' first" >&2; exit 1; }
if [ -n "${RELEASE:-}" ]; then
  python3 hosting/release.py check "$RELEASE" >&2
  REL_CL=$(echo "$RELEASE" | sed 's/\.0$//')
  grep -q "^## $REL_CL · " hosting/changelog.md || { echo "hosting/changelog.md has no '## $REL_CL · DATE' section" >&2; exit 1; }
  VERSION=$RELEASE
else
  VERSION=dev-$COMMIT
fi

rm -rf "$D" "$OUT/functions"
mkdir -p "$D/play/patch" "$D/changelog"
cp site/play/index.html site/play/bps.js site/play/play.js "$D/play/"
printf '/ /play/ 302\n' > "$D/_redirects"

# EmulatorJS from npm, pinned, so the page needs no third-party CDN.
TMP=$(mktemp -d)
( cd "$TMP" && npm pack --silent "@emulatorjs/emulatorjs@$EJS_VERSION" "@emulatorjs/core-mgba@$EJS_VERSION" >/dev/null )
mkdir -p "$TMP/ejs" "$TMP/core"
tar -xzf "$TMP"/emulatorjs-emulatorjs-*.tgz -C "$TMP/ejs"
tar -xzf "$TMP"/emulatorjs-core-mgba-*.tgz -C "$TMP/core"
mkdir -p "$D/play/emulatorjs"
cp -r "$TMP/ejs/package/data" "$D/play/emulatorjs/data"
cp "$TMP/ejs/package/LICENSE" "$D/play/emulatorjs/LICENSE"
cp "$TMP"/core/package/mgba-wasm.data "$TMP"/core/package/mgba-legacy-wasm.data "$D/play/emulatorjs/data/cores/"
mkdir -p "$D/play/emulatorjs/data/cores/reports"
cp "$TMP/core/package/reports/mgba.json" "$D/play/emulatorjs/data/cores/reports/"
rm -rf "$TMP"

# The patch, and the manifest the page reads to match a ROM to it.
python3 tools/patch/bps.py make "$CLEAN_ROM" "$ROM" "$D/play/patch/tryhardred.bps"
python3 - "$CLEAN_ROM" "$ROM" "$D/play/patch" "$VERSION" "$SOURCE_LABEL" "$COMMIT" "$BASE" <<'PY'
import json, os, sys, zlib, datetime
clean, rom, out, version, label, commit, base = sys.argv[1:]
c = open(clean, "rb").read()
t = open(rom, "rb").read()
json.dump({
    "version": version, "built": datetime.date.today().isoformat(), "commit": commit, "base": base,
    "patches": [{
        "source": label, "sourceSize": len(c), "sourceCrc": f"{zlib.crc32(c):08x}",
        "targetCrc": f"{zlib.crc32(t):08x}", "file": "tryhardred.bps",
    }],
}, open(os.path.join(out, "patch.json"), "w"), indent=2)
PY

# Changelog at /changelog/, and the Ideas tab on both pages (shows on *.pages.dev, or with ?feedback=1).
python3 hosting/changelog.py "$D/changelog/index.html" --back /play/
for d in "$D/play" "$D/changelog"; do
  cp hosting/feedback.js "$d/"
  sed -i "s#</body>#<script>window.FEEDBACK_VERSION='$VERSION';</script><script src=\"feedback.js\" defer></script>\n</body>#" "$d/index.html"
done

cp -r hosting/functions "$OUT/functions"
{
  echo "name = \"${PAGES_PROJECT:-tryhardred}\""
  echo 'pages_build_output_dir = "dist"'
  echo 'compatibility_date = "2026-10-01"'
  if [ -s hosting/kv-id.txt ]; then
    echo; echo '[[kv_namespaces]]'; echo 'binding = "FEEDBACK"'; echo "id = \"$(tr -d ' \n' < hosting/kv-id.txt)\""
  fi
} > "$OUT/wrangler.toml"

echo "version $VERSION, files: $(find "$D" -type f | wc -l), size: $(du -sh "$D" | cut -f1)"
echo "$OUT"
