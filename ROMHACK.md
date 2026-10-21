# TryHardRed (FireRed Gen 9)

FireRed as it is (same Kanto, story, maps and trainers) with Gen 9 battle mechanics and trainer AI that plays like a
decent human. Built on [pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion)'s FireRed target.
Scope, phases and decisions: the scoping doc (Claude Doc "FireRed Gen 9 romhack: scoping").

## Build

```sh
sh scripts/setup-toolchain.sh        # ARM toolchain, libpng, Python (Ubuntu/Debian)
make firered -j$(nproc)              # -> pokefirered.gba
make check BUILD=firered TEST=1 -j$(nproc)   # expansion's headless test suite, FireRed target
```

Switching between the Emerald and FireRed builds needs a `make clean` (expansion's FRLG guide,
`docs/tutorials/how_to_frlg.md`).

## Never commit a ROM

No `.gba` goes into git: not a clean FireRed ROM, not a build, not a patched copy (`.gitignore` blocks them; the only
tracked `.gba` files are upstream's small multiboot images in `data/`). Friends get a `.bps` patch and apply it to their
own FireRed (USA) ROM, in the browser or with any BPS patcher.

```sh
python3 tools/patch/bps.py make  CLEAN.gba pokefirered.gba tryhardred.bps
python3 tools/patch/bps.py apply CLEAN.gba tryhardred.bps patched.gba
python3 tools/patch/selftest.py      # no ROM needed
```

## Layout (ours, on top of expansion)

| Path | What |
|---|---|
| `scripts/setup-toolchain.sh` | toolchain install, for CI and cloud sessions |
| `.github/workflows/romhack-ci.yml` | builds the ROM, runs `make check` on FireRed, checks the patch tools (upstream's workflows are removed) |
| `tools/patch/` | BPS make/apply (`bps.py`) and its self-test |
| `site/play/` | the playtest page: your own ROM + the patch, played in EmulatorJS (mGBA core), saves kept in the browser |
| `site/build.sh` | builds the site into `out/` (see `hosting/README.md`) |
| `hosting/` | Cloudflare Pages pieces ported from Sonterra: feedback box, release numbers, changelog |

## Upstream

`upstream` is rh-hideout/pokeemerald-expansion. This repo started at tag `expansion/1.17.1` with its full history, so a
newer release merges in with `git fetch upstream tag expansion/X.Y.Z && git merge expansion/X.Y.Z`. We stay pinned to one
release at a time (scoping doc, question 1).
