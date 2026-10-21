# Friends' site (Cloudflare Pages)

The playtest page, the patch, the changelog and the Ideas box, on Cloudflare Pages like Sonterra's friends' site.
**Rule (same as Sonterra): deploy only when Alex says "ship it".** Pushes to GitHub never go live by themselves.

## Where each file came from

Copied from `apolitakis/sonterra-tactics` (nightly snapshot, read-only), per the scoping doc's phase 0 port table:

| Here | From sonterra-tactics | Changes |
|---|---|---|
| `functions/api/feedback.js` | `hosting/cloudflare/functions/api/feedback.js` | none |
| `feedback.js` | `feedback/widget/feedback.js` | Sonterra's build-time edits baked in (posts to `/api/feedback`, shows on `*.pages.dev`); page is `play`; its link goes to the changelog |
| `export.py` | `hosting/cloudflare/export.py` | inbox defaults to `/mnt/project-files/feedback/inbox` (out of git) |
| `release.py` | `hosting/cloudflare/release.py` | rows record the ROM commit, expansion base and patch checksum instead of page builds |
| `changelog.py`, `changelog.md` | `hosting/cloudflare/changelog.py`, `changelog.md` | retitled; changelog starts fresh |
| `../site/build.sh` | `hosting/cloudflare/build.sh` | rewritten: one page (`/play/`), the patch, a vendored EmulatorJS |

Not copied: `assemble.py` (it unwraps Sonterra's claude.ai pages; this site is built from the repo), `_middleware.js`
and `stats.js` (visitor stats, not in the port table), `feedback/widget/feedback-form.html` (Netlify only) and
`tools/publish/` (it copies claude.ai Artifact pages; the playtest page here is a static page built from git, so there is
nothing to copy between pages).

## Build (dry run)

```sh
make firered -j$(nproc)
CLEAN_ROM=/path/to/your/firered.gba sh site/build.sh out     # version dev-<commit>, no changelog needed
python3 -m http.server -d out/dist 8000                       # open http://localhost:8000/play/?feedback=1
```

The clean ROM is only read to make the patch. It is never committed (`.gitignore` blocks `*.gba`) and never copied
into `out/`.

## One-time setup (not done yet)

- A Pages project name for this site (`PAGES_PROJECT`, default `firered-gen9`) and its KV namespace for the Ideas box
  (`npx wrangler@4 kv namespace create FEEDBACK`, id into `kv-id.txt`).
- `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in the environment, with `api.cloudflare.com` and the new
  `*.pages.dev` host allowed. Sonterra's README "One-time setup" has the token steps.

## Every deploy (on "ship it")

1. Add a `## 0.N · YYYY-MM-DD` section to `changelog.md`.
2. `RELEASE=$(python3 hosting/release.py next) CLEAN_ROM=... sh site/build.sh out`
3. `cd out && npx -y wrangler@4 pages deploy --project-name "$PAGES_PROJECT" --branch main --commit-dirty=true`
4. Check `/play/` live (patch.json shows the release; a ROM patches and boots), then `python3 hosting/release.py append out`.
