#!/usr/bin/env python3
"""Release numbers for the friends' site (ported from sonterra-tactics hosting/cloudflare/release.py).

  python3 hosting/release.py next [patch]   # the next number: last release with the minor bumped (or the patch, for a fix-only ship)
  python3 hosting/release.py check 0.2.0    # site/build.sh runs this: well formed and newer than every release in releases.json
  python3 hosting/release.py append OUT     # after the deploy is verified live: adds this ship's row from OUT/dist/play/patch/patch.json

releases.json maps each release to the ROM build it shipped (commit, expansion base, patch checksum). Only append after
a deploy has gone live and been checked; a dry run never touches it.
"""
import json, os, re, sys, time

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "releases.json")
FORM = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def load():
    try:
        return json.load(open(FILE, encoding="utf-8"))
    except FileNotFoundError:
        return {"releases": []}


def key(r):
    return tuple(int(x) for x in FORM.match(r).groups())


def last():
    rels = [r["release"] for r in load()["releases"]]
    return max(rels, key=key) if rels else "0.0.0"


def check(rel):
    if not FORM.match(rel or ""):
        sys.exit(f"Set RELEASE to the release being shipped, MAJOR.MINOR.PATCH (next: {next_release()}; "
                 f"a fix-only ship: {next_release(True)}). See hosting/README.md.")
    if key(rel) <= key(last()):
        sys.exit(f"RELEASE {rel} is not newer than the last release {last()} in releases.json (next: {next_release()})")
    print(f"release {rel} (last was {last()})")


def next_release(patch=False):
    a, b, c = key(last())
    return f"{a}.{b}.{c + 1}" if patch else f"{a}.{b + 1}.0"


def append(out):
    m = json.load(open(os.path.join(out, "dist", "play", "patch", "patch.json"), encoding="utf-8"))
    check(m["version"])
    data = load()
    data["releases"].append({
        "release": m["version"], "shipped": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
        "commit": m.get("commit", ""), "base": m.get("base", ""),
        "patches": {p["source"]: p["targetCrc"] for p in m["patches"]},
    })
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, FILE)
    print(f"appended {m['version']} to releases.json")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["next"]:
        print(next_release(a[1:] == ["patch"]))
    elif a[:1] == ["check"] and len(a) <= 2:
        check(a[1] if len(a) == 2 else "")
    elif a[:1] == ["append"] and len(a) == 2:
        append(a[1])
    else:
        sys.exit(__doc__)
