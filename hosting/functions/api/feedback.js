// Cloudflare Pages Function: POST /api/feedback
// Replaces Netlify Forms for the "Ideas?" tab (feedback/widget/feedback.js).
// Stores each submission in the FEEDBACK KV namespace as sub:<time>-<rand>;
// export.py pulls them into feedback/inbox/. Same fields as the Netlify form.

const LIMITS = { name: 30, message: 1000, minMessage: 8, maxLinks: 1, perIpPerDay: 20 };
const FIELDS = { page: 20, path: 80, version: 20, screen: 20 };
const CATS = ['idea', 'bug', 'balance', 'other'];
const KEEP_SECONDS = 60 * 60 * 24 * 365;

function clean(s, n) {
  return String(s || '').replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '').trim().slice(0, n);
}

function reply(status, text) {
  return new Response(text, { status, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
}

async function ipKey(request) {
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  const day = new Date().toISOString().slice(0, 10);
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(ip + day));
  const hex = [...new Uint8Array(hash)].slice(0, 8).map(b => b.toString(16).padStart(2, '0')).join('');
  return 'rl:' + day + ':' + hex;  // hashed, so no raw IPs are stored
}

export async function onRequestPost({ request, env }) {
  if (!env.FEEDBACK) return reply(503, 'Feedback storage is not set up.');
  const type = request.headers.get('content-type') || '';
  if (!type.includes('application/x-www-form-urlencoded')) return reply(415, 'Unsupported.');
  const raw = await request.text();
  if (raw.length > 8000) return reply(413, 'Too long.');
  const f = new URLSearchParams(raw);

  if (f.get('bot-field')) return reply(200, 'Thanks!');  // honeypot: pretend success

  const message = clean(f.get('message'), LIMITS.message + 1);
  const name = clean(f.get('name'), LIMITS.name + 1);
  if (message.length < LIMITS.minMessage) return reply(400, 'Too short.');
  if (message.length > LIMITS.message || name.length > LIMITS.name) return reply(400, 'Too long.');
  if ((message.match(/https?:\/\/|www\./gi) || []).length > LIMITS.maxLinks) return reply(400, 'Too many links.');

  const rl = await ipKey(request);
  const used = parseInt(await env.FEEDBACK.get(rl) || '0', 10);
  if (used >= LIMITS.perIpPerDay) return reply(429, 'Daily limit reached.');
  await env.FEEDBACK.put(rl, String(used + 1), { expirationTtl: 60 * 60 * 48 });

  const at = new Date().toISOString();
  const id = at.replace(/[-:.TZ]/g, '') + '-' + crypto.randomUUID().slice(0, 8);
  const sub = { id, at, name, message, category: CATS.includes(f.get('category')) ? f.get('category') : 'other' };
  for (const [k, n] of Object.entries(FIELDS)) sub[k] = clean(f.get(k), n);
  await env.FEEDBACK.put('sub:' + id, JSON.stringify(sub), { expirationTtl: KEEP_SECONDS });
  return reply(200, 'Thanks!');
}

export function onRequest() {
  return reply(405, 'POST only.');
}
