// Friends' feedback tab. Self-contained drop-in: <script src="feedback.js" defer></script>
// Ported from sonterra-tactics feedback/widget/feedback.js with the edits Sonterra's build.sh made at build time:
// posts to /api/feedback (hosting/functions/api/feedback.js) and only shows on *.pages.dev (or with ?feedback=1).
(function () {
  'use strict';
  if (window.__feedbackTab) return;
  window.__feedbackTab = true;

  var qs = new URLSearchParams(location.search);
  var forced = qs.get('feedback') === '1';
  if (!forced && !/\.pages\.dev$/.test(location.hostname)) return;

  var LIMITS = { name: 30, message: 1000, minMessage: 8, maxLinks: 1,
    cooldownMs: 60 * 1000, perDay: 10, minOpenMs: 3000 };
  var CATS = [['idea', 'Idea'], ['bug', 'Bug'], ['balance', 'Balance'], ['other', 'Other']];
  var KEY = 'pt-feedback-log';
  var ENDPOINT = window.FEEDBACK_ENDPOINT || '/api/feedback';
  var PAGE = window.FEEDBACK_PAGE ||
    'play';

  function store(fn) { try { return fn(window.localStorage); } catch (e) { return null; } }
  function log() {
    var raw = store(function (s) { return s.getItem(KEY); });
    var now = Date.now(), arr = [];
    try { arr = JSON.parse(raw) || []; } catch (e) {}
    return arr.filter(function (t) { return now - t < 864e5; });
  }
  function remember() {
    var arr = log(); arr.push(Date.now());
    store(function (s) { s.setItem(KEY, JSON.stringify(arr)); });
  }

  var css = '' +
    '#fbk-tab{position:fixed;right:0;top:50%;transform:translateY(-50%);z-index:2147483000;' +
    'writing-mode:vertical-rl;background:#2f5d8a;color:#fff;border:2px solid #10233a;border-right:0;' +
    'border-radius:8px 0 0 8px;padding:12px 6px;font:600 13px/1 system-ui,sans-serif;cursor:pointer;' +
    'letter-spacing:.06em;box-shadow:-2px 2px 0 rgba(0,0,0,.25)}' +
    '#fbk-tab:hover{background:#3a74ab}' +
    // Touch screens: a small pill on the top edge, so it never covers the pad's A button.
    '@media (pointer:coarse){#fbk-tab{top:0;right:auto;left:50%;transform:translateX(-50%);writing-mode:horizontal-tb;' +
      'border:2px solid #10233a;border-top:0;border-radius:0 0 8px 8px;padding:4px 10px;' +
      'padding-top:max(4px,env(safe-area-inset-top));font-size:11px;opacity:.8;box-shadow:0 2px 0 rgba(0,0,0,.25)}}' +
    '#fbk-tab.fbk-hidden{display:none!important}' +
    '#fbk-panel{position:fixed;right:0;top:0;bottom:0;width:min(340px,100vw);z-index:2147483001;' +
    'background:#1f2436;color:#e8ecf4;border-left:2px solid #3a4260;box-shadow:-6px 0 18px rgba(0,0,0,.3);' +
    'font:14px/1.4 system-ui,sans-serif;display:flex;flex-direction:column;transform:translateX(105%);' +
    'transition:transform .18s ease}' +
    '#fbk-panel.open{transform:none}' +
    '#fbk-panel .fbk-head{display:flex!important;align-items:center;justify-content:space-between;padding:12px 14px;' +
    'background:#2a3047;color:#f4c84a;font-weight:700;border-bottom:2px solid #3a4260}' +
    '#fbk-panel .fbk-head button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1}' +
    '#fbk-panel form{padding:14px;display:flex;flex-direction:column;gap:10px;overflow:auto}' +
    '#fbk-panel label{font-size:12px;font-weight:600;color:#aab3c8}' +
    '#fbk-panel input,#fbk-panel textarea,#fbk-panel select{width:100%;box-sizing:border-box;font:inherit;' +
    'padding:7px 8px;border:2px solid #3a4260;border-radius:6px;background:#2a3047;color:#e8ecf4}' +
    '#fbk-panel textarea{min-height:150px;resize:vertical}' +
    '#fbk-panel .fbk-cats{display:flex;gap:6px;flex-wrap:wrap}' +
    '#fbk-panel .fbk-cats button{flex:1;padding:6px 4px;border:2px solid #3a4260;border-radius:6px;' +
    'background:#2a3047;cursor:pointer;font:600 12px system-ui,sans-serif;color:#e8ecf4}' +
    '#fbk-panel .fbk-cats button[aria-pressed=true]{background:#2f5d8a;border-color:#10233a;color:#fff}' +
    '#fbk-panel .fbk-count{font-size:11px;color:#8891a8;text-align:right;margin-top:-6px}' +
    '#fbk-panel .fbk-send{padding:9px;border:2px solid #10233a;border-radius:6px;background:#e0542e;' +
    'color:#fff;font-weight:700;cursor:pointer}' +
    '#fbk-panel .fbk-send:disabled{opacity:.5;cursor:default}' +
    '#fbk-panel .fbk-msg{font-size:13px;min-height:1.4em}' +
    '#fbk-panel .fbk-msg.err{color:#ff7b6b}#fbk-panel .fbk-msg.ok{color:#5fd38d}' +
    '#fbk-panel .fbk-hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}' +
    '#fbk-panel .fbk-faq{font-size:12px;color:#f4c84a}' +
    '#fbk-panel .fbk-note{font-size:11px;color:#8891a8}';

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === 'text') n.textContent = attrs[k]; else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { n.appendChild(c); });
    return n;
  }

  function mount() {
    document.head.appendChild(el('style', { text: css }));
    var tab = el('button', { id: 'fbk-tab', type: 'button', text: 'Ideas?', title: 'Send feedback' });
    var cat = 'idea';
    var catBtns = CATS.map(function (c) {
      var b = el('button', { type: 'button', 'aria-pressed': String(c[0] === cat), text: c[1] });
      b.onclick = function () {
        cat = c[0];
        catBtns.forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      };
      return b;
    });
    var name = el('input', { name: 'name', maxlength: LIMITS.name, autocomplete: 'nickname', placeholder: 'So we know who to thank' });
    var msg = el('textarea', { name: 'message', maxlength: LIMITS.message, placeholder: 'What should change, what felt off, what would be cool...' });
    var count = el('div', { class: 'fbk-count', text: '0 / ' + LIMITS.message });
    var hp = el('input', { name: 'bot-field', tabindex: '-1', autocomplete: 'off' });
    var status = el('div', { class: 'fbk-msg', role: 'status' });
    var faq = el('a', { href: window.FEEDBACK_FAQ || '/changelog/', target: '_blank', rel: 'noopener', class: 'fbk-faq', text: "See what's new first" });
    faq.style.display = 'none';
    // Show the link only once the FAQ page is actually deployed.
    fetch(faq.href, { method: 'HEAD' }).then(function (r) { if (r.ok) faq.style.display = ''; }).catch(function () {});
    var send = el('button', { type: 'submit', class: 'fbk-send', text: 'Send' });
    var close = el('button', { type: 'button', 'aria-label': 'Close', text: '×' });
    var form = el('form', { name: 'feedback', novalidate: '' }, [
      el('div', { class: 'fbk-hp', 'aria-hidden': 'true' }, [el('label', { text: 'Leave this empty' }), hp]),
      faq,
      el('label', { text: 'Your name (optional)' }), name,
      el('label', { text: 'Kind' }), el('div', { class: 'fbk-cats' }, catBtns),
      el('label', { text: 'Your idea' }), msg, count,
      send, status,
      el('div', { class: 'fbk-note', text: 'Everything sent here gets read together later. Please keep it friendly.' })
    ]);
    var panel = el('aside', { id: 'fbk-panel', 'aria-label': 'Feedback' }, [
      // A div, not <header>: the game's focus mode hides every <header> on the page.
      el('div', { class: 'fbk-head' }, [el('span', { text: 'Send an idea' }), close]), form
    ]);
    document.body.appendChild(tab);
    document.body.appendChild(panel);

    var openedAt = 0;
    function setOpen(on) {
      panel.classList.toggle('open', on);
      tab.style.display = on ? 'none' : '';
      if (on) { openedAt = Date.now(); setTimeout(function () { msg.focus(); }, 50); }
    }
    tab.onclick = function () { setOpen(true); };
    // Pages with their own menu (pad, game Start menu) can open the panel and hide the tab:
    //   window.openFeedback()  /  window.FEEDBACK_HIDE_TAB = true (before load) or window.hideFeedbackTab(true)
    window.openFeedback = function () { setOpen(true); };
    window.hideFeedbackTab = function (on) { tab.classList.toggle('fbk-hidden', on !== false); };
    if (window.FEEDBACK_HIDE_TAB) window.hideFeedbackTab(true);
    close.onclick = function () { setOpen(false); };
    // Keep game/simulator hotkeys from firing while typing.
    panel.addEventListener('keydown', function (e) {
      e.stopPropagation();
      if (e.key === 'Escape') setOpen(false);
    });
    panel.addEventListener('keyup', function (e) { e.stopPropagation(); });
    msg.addEventListener('input', function () { count.textContent = msg.value.length + ' / ' + LIMITS.message; });

    function say(text, kind) { status.textContent = text; status.className = 'fbk-msg ' + (kind || ''); }

    form.onsubmit = function (e) {
      e.preventDefault();
      var text = msg.value.trim(), who = name.value.trim();
      if (hp.value) { say('Thanks!', 'ok'); return; }               // bot: pretend success
      if (Date.now() - openedAt < LIMITS.minOpenMs) { say('Take a second to write it out.', 'err'); return; }
      if (text.length < LIMITS.minMessage) { say('A little more detail, please.', 'err'); return; }
      if (text.length > LIMITS.message || who.length > LIMITS.name) { say('That is too long.', 'err'); return; }
      if ((text.match(/https?:\/\/|www\./gi) || []).length > LIMITS.maxLinks) { say('Please leave out the links.', 'err'); return; }
      var recent = log();
      if (recent.length >= LIMITS.perDay) { say('That is the limit for today. Thank you for all of it!', 'err'); return; }
      var last = recent[recent.length - 1];
      if (last && Date.now() - last < LIMITS.cooldownMs) {
        say('Give it ' + Math.ceil((LIMITS.cooldownMs - (Date.now() - last)) / 1000) + 's before the next one.', 'err');
        return;
      }
      var body = new URLSearchParams({
        'form-name': 'feedback', 'bot-field': '', name: who, category: cat, message: text,
        page: PAGE, path: location.pathname + location.hash, version: String(window.FEEDBACK_VERSION || ''),
        screen: window.innerWidth + 'x' + window.innerHeight
      });
      send.disabled = true; say('Sending...');
      fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString() })
        .then(function (r) {
          if (!r.ok) throw new Error(r.status);
          remember(); msg.value = ''; count.textContent = '0 / ' + LIMITS.message;
          say('Got it, thank you!', 'ok');
        })
        .catch(function () { say('Could not send right now. Try again in a bit.', 'err'); })
        .then(function () { send.disabled = false; });
    };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
