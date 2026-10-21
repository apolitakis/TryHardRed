#!/usr/bin/env python3
"""Render changelog.md as a standalone page (ported from sonterra-tactics hosting/cloudflare/changelog.py).
   python3 changelog.py OUT.html [--back URL]   --back adds a "Back" link (the site passes /play/).
No external files: fonts fall back to the system's, so the page works anywhere (claude.ai page, zip, the site)."""
import html, re, sys
from pathlib import Path

def render(md, back=None):
    out, open_ul = [], False
    for line in md.splitlines():
        if line.startswith('<!--') or line.startswith('# ') or not line.strip() or line.strip().endswith('-->'):
            continue
        m = re.match(r'## (\S+) · (\S+)', line)
        if m:
            if open_ul: out.append('</ul></section>')
            out.append(f'<section><h2>Version {html.escape(m[1])}<small>{html.escape(m[2])}</small></h2><ul>')
            open_ul = True
        elif line.startswith('- builds:'):
            out.append(f'<li class="b">Builds: {html.escape(line[9:].strip())}</li>')
        elif line.startswith('- '):
            out.append(f'<li>{html.escape(line[2:])}</li>')
    if open_ul: out.append('</ul></section>')
    nav = f'<a class="back" href="{html.escape(back)}">Back</a>' if back else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>What's new · FireRed Gen 9</title><meta name="robots" content="noindex">
<style>
:root {{ --ground:#1b1f2e; --panel:#262c41; --line:#424b6b; --ink:#ece9f5; --muted:#a3a8c3; --gold:#f2c14e; color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--ground); color:var(--ink); font:16px/1.45 "Atkinson Hyperlegible", system-ui, sans-serif; padding:32px 16px; }}
main {{ max-width:640px; margin:0 auto; display:grid; gap:16px; }}
h1 {{ font:700 30px/1.1 "Pixelify Sans","Courier New",monospace; margin:0; }} h1 span {{ color:var(--gold); }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 16px; }}
h2 {{ font:700 20px "Pixelify Sans","Courier New",monospace; color:var(--gold); margin:0 0 6px; display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; }}
h2 small {{ font:13px "Atkinson Hyperlegible", system-ui, sans-serif; color:var(--muted); }}
ul {{ margin:0; padding-left:20px; display:grid; gap:4px; }}
li.b {{ list-style:none; margin-left:-20px; color:var(--muted); font-size:12px; margin-top:4px; }}
a {{ color:var(--gold); }} .back {{ font-size:14px; }}
</style></head>
<body><main>
{nav}
<h1>What's <span>new</span></h1>
{chr(10).join(out)}
</main></body></html>
'''

if __name__ == '__main__':
    a = sys.argv[1:]
    back = a[a.index('--back') + 1] if '--back' in a else None
    Path(a[0]).write_text(render((Path(__file__).parent / 'changelog.md').read_text(), back))
