#!/usr/bin/env python3
"""Pull friends' feedback from Cloudflare KV into review files (ported from sonterra-tactics hosting/cloudflare/export.py).

  python3 export.py            # writes feedback/inbox/feedback-<date>.md and merges feedback/inbox/all.json
  python3 export.py --delete   # afterwards, delete the exported submissions from KV

Needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in the environment, api.cloudflare.com
reachable, and the namespace id in kv-id.txt next to this file. Never prints the token.
"""
import argparse, datetime, json, os, re, sys, urllib.parse, urllib.request
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
# Friends' notes stay out of git: they go to the project's shared folder unless FEEDBACK_INBOX says otherwise.
INBOX = os.environ.get('FEEDBACK_INBOX', '/mnt/project-files/feedback/inbox')
API = 'https://api.cloudflare.com/client/v4'
CATS = OrderedDict([('bug', 'Bugs'), ('balance', 'Balance'), ('idea', 'Ideas'), ('other', 'Other')])


def ns_url():
    acct = os.environ.get('CLOUDFLARE_ACCOUNT_ID')
    if not os.environ.get('CLOUDFLARE_API_TOKEN') or not acct:
        sys.exit('CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set.')
    with open(os.path.join(HERE, 'kv-id.txt')) as f:
        return '%s/accounts/%s/storage/kv/namespaces/%s' % (API, acct, f.read().strip())


def call(url, method='GET', body=None, raw=False):
    headers = {'Authorization': 'Bearer ' + os.environ['CLOUDFLARE_API_TOKEN']}
    data = None
    if body is not None:
        data = json.dumps(body).encode(); headers['Content-Type'] = 'application/json'
    with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers)) as r:
        out = r.read()
    return out.decode() if raw else json.loads(out)


def fetch_all(base):
    keys, cursor = [], ''
    while True:
        q = '?prefix=sub:&limit=1000' + ('&cursor=' + urllib.parse.quote(cursor) if cursor else '')
        res = call(base + '/keys' + q)
        keys += [k['name'] for k in res['result']]
        cursor = (res.get('result_info') or {}).get('cursor') or ''
        if not cursor:
            break
    subs = []
    for k in keys:
        try:
            subs.append(json.loads(call(base + '/values/' + urllib.parse.quote(k, safe=''), raw=True)))
        except ValueError:
            pass
    return keys, subs


def clean(s, n):
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', str(s or '')).strip()[:n]


def row(d):
    return {
        'id': clean(d.get('id'), 40), 'at': clean(d.get('at'), 16).replace('T', ' '),
        'name': clean(d.get('name'), 30) or 'anonymous',
        'category': d.get('category') if d.get('category') in CATS else 'other',
        'page': clean(d.get('page'), 20), 'path': clean(d.get('path'), 80),
        'version': clean(d.get('version'), 20), 'screen': clean(d.get('screen'), 20),
        'message': clean(d.get('message'), 1000),
    }


def write(rows):
    rows.sort(key=lambda r: r['at'])
    seen, uniq = set(), []
    for r in rows:  # drop exact duplicates (same text from the same name), keep the first
        k = (r['name'].lower(), re.sub(r'\s+', ' ', r['message'].lower()))
        if k not in seen:
            seen.add(k); uniq.append(r)
    os.makedirs(INBOX, exist_ok=True)
    allp = os.path.join(INBOX, 'all.json')
    old = json.load(open(allp)) if os.path.exists(allp) else []
    have = {r['id'] for r in old}
    with open(allp, 'w') as f:
        json.dump(old + [r for r in uniq if r['id'] not in have], f, indent=1)

    today = datetime.date.today().isoformat()
    lines = ["# Friends' feedback, exported %s" % today, '',
             '%d submissions (%d duplicates dropped), from Cloudflare.' % (len(uniq), len(rows) - len(uniq)), '']
    for cat, title in CATS.items():
        items = [r for r in uniq if r['category'] == cat]
        if items:
            lines += ['## %s (%d)' % (title, len(items)), '']
            for r in items:
                meta = ' · '.join(x for x in [r['name'], r['at'], r['page'], r['version']] if x)
                quoted = '\n'.join('> ' + l for l in r['message'].splitlines()) or '> (empty)'
                lines += ['- [ ] **%s**' % meta, '', quoted, '']
    out = os.path.join(INBOX, 'feedback-%s.md' % today)
    if os.path.exists(out):  # don't overwrite an earlier export from the same day
        out = out[:-3] + '-cf.md'
    with open(out, 'w') as f:
        f.write('\n'.join(lines))
    return out, allp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--delete', action='store_true')
    args = ap.parse_args()
    base = ns_url()
    keys, subs = fetch_all(base)
    out, allp = write([row(s) for s in subs])
    print('wrote', os.path.normpath(out), 'and', os.path.normpath(allp), '(%d submissions)' % len(subs))
    if args.delete and keys:
        for i in range(0, len(keys), 1000):
            call(base + '/bulk/delete', 'POST', keys[i:i + 1000])
        print('deleted %d submissions from KV' % len(keys))


if __name__ == '__main__':
    main()
