'use strict';
// core.js: DOM builder, API client, live streams, bus, Markdown, toast/dialogs, formatting, routing, storage.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R} = require('./harness');

test('h() builds elements: classes, id, attributes, events, html/text/dataset, children', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  let clicked = 0;
  const el = PL.h('button.a.b#x', {onclick: () => clicked++, title: 't', 'aria-hidden': true, hidden: false, skip: null, dataset: {k: 'v'}},
    'text', [PL.h('i'), null, false], 3);
  assert.strictEqual(el.tagName, 'BUTTON');
  assert.strictEqual(el.className, 'a b');
  assert.strictEqual(el.id, 'x');
  assert.strictEqual(el.getAttribute('aria-hidden'), '');
  assert.ok(!el.hasAttribute('hidden') && !el.hasAttribute('skip'));
  assert.strictEqual(el.dataset.k, 'v');
  assert.strictEqual(el.textContent, 'text3');
  el.click();
  assert.strictEqual(clicked, 1);
  assert.strictEqual(PL.h('.only').tagName, 'DIV');
  assert.strictEqual(PL.h('span.dot.').outerHTML, '<span class="dot"></span>');  // an empty modifier class
  assert.strictEqual(PL.h('span.').className, '');
  assert.strictEqual(PL.h('p', {html: '<b>x</b>'}).innerHTML, '<b>x</b>');
  assert.strictEqual(PL.h('p', {text: '<b>'}).innerHTML, '&lt;b&gt;');
  assert.strictEqual(PL.h('???').tagName, 'DIV');  // a bad spec still gives an element
  assert.strictEqual(PL.esc(null), '');
  assert.strictEqual(PL.esc(`<a href="x">'&`), '&lt;a href=&quot;x&quot;&gt;&#39;&amp;');
  assert.match(PL.icon('nope'), /d=""/);
  const host = PL.h('div', {html: '<span data-i="plus"></span><span data-i="x"><svg></svg></span>'});
  PL.paintIcons(host);
  PL.paintIcons(host);  // idempotent
  assert.strictEqual(host.querySelectorAll('svg').length, 2);
  assert.strictEqual(PL.$$('svg', host).length, 2);
  assert.ok(PL.$$('body').length === 1 && PL.$('svg', host));
});

test('api(): JSON, text, FormData, errors, offline banner, abort', async () => {
  let fail = null;
  const h = await boot({noBoot: true, routes: {
    'GET /t/json': () => ({a: 1}),
    'GET /t/text': () => 'plain',
    'GET /t/detail': () => R({detail: {message: 'bad thing'}}, 400),
    'GET /t/detailobj': () => R({detail: {code: 7}}, 422),
    'GET /t/nodetail': () => R('', 500, {statusText: 'Server Error'}),
    'GET /t/str': () => R({detail: 'plain detail'}, 409),
    'GET /t/noct': () => R('', 500, {contentType: null}),
    'POST /t/form': (req) => ({isForm: req.body instanceof h.w.FormData}),
  }});
  const PL = h.w.PL;
  assert.deepStrictEqual(await PL.get('/t/json'), {a: 1});
  assert.strictEqual(await PL.get('/t/text'), 'plain');
  await assert.rejects(PL.get('/t/detail'), /bad thing/);
  await assert.rejects(PL.get('/t/detailobj'), /"code":7/);
  await assert.rejects(PL.get('/t/nodetail'), /Server Error/);
  await assert.rejects(PL.get('/t/noct'), /Lỗi/);
  await assert.rejects(PL.get('/t/str'), (e) => e.status === 409 && e.message === 'plain detail' && e instanceof PL.ApiError);
  assert.deepStrictEqual(await PL.upload('/t/form', [new h.w.File(['x'], 'a.txt')]), {isForm: true});
  const put = await PL.put('/t/put', {x: 1});
  assert.deepStrictEqual(put, {});
  assert.deepStrictEqual(h.server.last('PUT', '/t/put').body, {x: 1});
  await PL.del('/t/del');
  await PL.post('/t/post');
  await PL.post('/t/post2', {y: 2});
  assert.strictEqual(h.server.last('POST', '/t/post2').body.y, 2);
  assert.deepStrictEqual(h.server.calls.find((c) => c.path === '/t/post').body, {});
  // network failure → offline banner, then back online
  h.w.fetch = async () => { throw fail; };
  fail = new Error('down');
  await assert.rejects(PL.get('/t/json'), (e) => e.status === 0);
  assert.strictEqual(h.$('#offline').hidden, false);
  fail = Object.assign(new Error('aborted'), {name: 'AbortError'});
  await assert.rejects(PL.api('GET', '/t/json', undefined, {signal: {}}), /aborted/);
  h.w.fetch = (u, o) => h.server.handle(u, o);
  await PL.get('/t/json');
  assert.strictEqual(h.$('#offline').hidden, true);
  // safe(): ok message / error toast
  assert.strictEqual(await PL.safe(async () => 5, 'done'), 5);
  assert.strictEqual(h.toast(), 'done');
  assert.strictEqual(await PL.safe(async () => { throw new Error('nope'); }), undefined);
  assert.strictEqual(h.toast(), 'nope');
  await PL.safe(async () => { throw 'raw'; });  // eslint-disable-line no-throw-literal
  assert.strictEqual(h.toast(), 'raw');
  PL.online(true);  // no change → no-op
  h.$('#offline').remove();
  PL.online(false);  // banner missing: still fine
});

test('stream(): resume cursor, hello, timeout reconnect, bad JSON, errors with backoff, close', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  const got = [];
  let opened = 0, errs = 0;
  const s = PL.stream('/s?x=1', (e) => got.push(e.type), {onOpen: () => opened++, onError: () => errs++});
  const es = h.ES.all.at(-1);
  assert.strictEqual(es.url, '/s?x=1&after=0');
  es.open();
  es.send({type: 'hello', seq: 7});
  assert.strictEqual(s.after, 7);
  es.send({type: 'a', seq: 9});
  es.send('{bad');
  es.send({type: 'b'});
  es.send({type: 'stream.timeout'});
  assert.ok(es.closed);
  const es2 = h.ES.all.at(-1);
  assert.strictEqual(es2.url, '/s?x=1&after=9');
  es2.fail();
  assert.strictEqual(errs, 1);
  await h.idle(10);
  const es3 = h.ES.all.at(-1);
  assert.notStrictEqual(es3, es2);
  es3.send({type: 'hello', seq: 3});  // a later hello never moves the cursor back
  assert.strictEqual(s.after, 9);
  for (let i = 0; i < 6; i++) { h.ES.all.at(-1).fail(); await h.idle(5); }  // backoff grows and is capped
  h.ES.all.at(-1).fail();
  s.close();  // the pending reconnect finds the stream closed
  await h.idle(10);
  s.close();
  h.ES.all.at(-1).fail();
  await h.idle(10);
  const n = h.ES.all.length;
  await h.idle(10);
  assert.strictEqual(h.ES.all.length, n);  // closed: no reconnect
  assert.deepStrictEqual(got, ['hello', 'a', 'b', 'hello']);
  assert.strictEqual(opened, 1);
  const plain = PL.stream('/p', () => {});
  h.ES.all.at(-1).open();
  h.ES.all.at(-1).fail();
  plain.close();
  plain.close();
});

test('bus: prefix subscriptions, unsubscribe, a failing listener never breaks the others; live dot', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  const seen = [];
  const off = PL.on('run.', (e) => seen.push('run:' + e.type));
  PL.on('', (e) => seen.push('all:' + e.type));
  PL.on('run.', () => { throw new Error('boom'); });
  PL.emit({type: 'run.updated'});
  PL.emit({});
  off();
  PL.emit({type: 'run.done'});
  assert.deepStrictEqual(seen, ['run:run.updated', 'all:run.updated', 'all:undefined', 'all:run.done']);
  const bus = PL.startBus();
  const es = h.ES.all.at(-1);
  es.open();
  assert.strictEqual(h.$('#live').className, 'dot live');
  es.send({type: 'hello', seq: 1});
  es.send({type: 'x.y', seq: 2});
  assert.strictEqual(seen.at(-1), 'all:x.y');
  es.fail();
  assert.strictEqual(h.$('#live').className, 'dot warn');
  bus.close();
  h.$('#live').remove();
  const b2 = PL.startBus();
  h.ES.all.at(-1).open();
  h.ES.all.at(-1).fail();
  b2.close();
});

test('md()/rich(): hidden action blocks, math, code copy + lazy highlight, links, fallbacks', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  const src = 'Hi [x](https://e.org) $a+b$ and $$\\sum$$ and \\[x^2\\]\n\n```python\nprint(1)\n```\n\n```phdlab-action\n{"a":1}\n```';
  const el = PL.rich(PL.h('div'), src);
  assert.ok(!el.textContent.includes('"a":1'));
  assert.strictEqual(el.querySelector('a').target, '_blank');
  assert.strictEqual(el.querySelectorAll('.math').length, 3);
  assert.strictEqual(el.querySelectorAll('.math.display').length, 2);
  // the lazily loaded KaTeX / highlight.js scripts: simulate their load
  const scripts = () => [...h.document.head.querySelectorAll('script')];
  assert.ok(scripts().some((s) => s.src.includes('katex')));
  let rendered = 0, lit = 0;
  h.w.katex = {render: (tex, m) => { rendered++; if (tex === 'x^2') throw new Error('bad tex'); }};
  h.w.hljs = {highlightElement: () => { lit++; throw new Error('no lang'); }};
  scripts().forEach((s) => s.onload());
  await h.idle();
  assert.strictEqual(rendered, 3);
  assert.strictEqual(lit, 1);
  el.querySelector('.copy-code').click();
  await h.idle();
  assert.strictEqual(h.w.__clip.trim(), 'print(1)');
  // second render reuses the loaded promise; a failed load renders nothing
  PL.rich(PL.h('div'), '$q$ ```js\nx\n```');
  delete h.w.katex;
  PL.rich(PL.h('div'), '$z$\n\n```\ny\n```');
  await h.idle();
  const bad = PL.load('/vendor/missing.js');
  scripts().at(-1).onerror();
  assert.strictEqual(await bad, false);
  // dark theme picks the dark highlight stylesheet (explicit theme and system preference)
  const h2 = await boot({noBoot: true, media: {'(prefers-color-scheme: dark)': true}});
  h2.w.PL.rich(h2.w.PL.h('div'), '```\nx\n```');
  assert.ok([...h2.document.head.querySelectorAll('link')].some((l) => l.href.includes('github-dark')));
  const h3 = await boot({noBoot: true});
  h3.document.documentElement.dataset.theme = 'dark';
  h3.w.PL.rich(h3.w.PL.h('div'), '```\nx\n```');
  assert.ok([...h3.document.head.querySelectorAll('link')].some((l) => l.href.includes('github-dark')));
  // without marked / DOMPurify: escaped text
  delete h.w.marked;
  assert.strictEqual(PL.md('a\nb'), 'a<br>b');
  delete h.w.DOMPurify;
  assert.strictEqual(PL.md('<b>'), '&lt;b&gt;');
  assert.strictEqual(PL.md(null), '');
});

test('copy(): clipboard ok, failure, no clipboard', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  PL.copy('a');
  await h.idle();
  assert.strictEqual(h.toast(), 'Đã sao chép');
  h.w.navigator.clipboard.writeText = async () => { throw new Error('denied'); };
  PL.copy('b');
  await h.idle();
  assert.match(h.toast(), /Không sao chép/);
  Object.defineProperty(h.w.navigator, 'clipboard', {value: undefined, configurable: true});
  h.$('#toast').textContent = '';
  PL.copy('c');
  assert.strictEqual(h.toast(), 'Đã sao chép');
});

test('toast / modal / confirm / prompt', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  PL.toast('x', 'err');
  assert.match(h.$('#toast').className, /err/);
  await h.idle(10);
  assert.strictEqual(h.$('#toast').className, '');
  // modal: string body, actions (one keeps it open), Escape, backdrop, onClose
  let closed = 0, keep = true;
  PL.modal({title: 'T', body: '<input id="mi">', wide: true, onClose: () => closed++,
    actions: [{label: 'Keep', kind: 'accent', onClick: () => (keep ? false : undefined)}, {label: 'Plain'}]});
  assert.strictEqual(h.$('#modal').hidden, false);
  assert.ok(h.$('.dialog.wide'));
  await h.clickText('.dialog-f button', 'Keep');
  assert.strictEqual(h.$('#modal').hidden, false);
  keep = false;
  await h.clickText('.dialog-f button', 'Keep');
  assert.strictEqual(h.$('#modal').hidden, true);
  assert.strictEqual(closed, 1);
  PL.modal({title: 'E', body: PL.h('p', {}, 'x'), raw: true});
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'a'}));
  assert.strictEqual(h.$('#modal').hidden, false);
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'Escape'}));
  assert.strictEqual(h.$('#modal').hidden, true);
  PL.modal({body: 'x'});
  h.$('#modal .dialog').click();
  assert.strictEqual(h.$('#modal').hidden, false);
  h.$('#modal').click();
  assert.strictEqual(h.$('#modal').hidden, true);
  // confirm
  let c = PL.confirm('Sure?');
  await h.clickText('.dialog-f button', 'Đồng ý');
  assert.strictEqual(await c, true);
  c = PL.confirm('Sure?', 'Xoá');
  await h.clickText('.dialog-f button', 'Huỷ');
  assert.strictEqual(await c, false);
  // prompt: Save, Cancel, Enter key, other key
  let p = PL.prompt('T', 'L', ' v ');
  await h.clickText('.dialog-f button', 'Lưu');
  assert.strictEqual(await p, 'v');
  p = PL.prompt('T', 'L');
  await h.clickText('.dialog-f button', 'Huỷ');
  assert.strictEqual(await p, null);
  p = PL.prompt('T', 'L', 'enter');
  await h.key('#modal input', 'a');
  await h.key('#modal input', 'Enter');
  assert.strictEqual(await p, 'enter');
  assert.strictEqual(h.$('#modal').hidden, true);
  h.$('#toast').remove();
  PL.toast('no toast element');
});

test('formatting: ago, size, status chips', async () => {
  const h = await boot({noBoot: true});
  const PL = h.w.PL;
  const now = Date.now() / 1000;
  assert.strictEqual(PL.ago(0), '');
  assert.strictEqual(PL.ago(now - 5), 'vừa xong');
  assert.match(PL.ago(now - 120), /phút/);
  assert.match(PL.ago(now - 7200), /giờ/);
  assert.match(PL.ago(now - 2 * 86400), /ngày/);
  assert.match(PL.ago(now - 30 * 86400), /\d/);
  assert.strictEqual(PL.size(2e6), '2.0 MB');
  assert.strictEqual(PL.size(2500), '3 KB');
  assert.strictEqual(PL.size(0), '0 B');
  assert.strictEqual(PL.size(undefined), '0 B');
  assert.strictEqual(PL.statusChip('RUNNING').textContent, 'Đang chạy');
  assert.strictEqual(PL.statusChip('ODD').textContent, 'ODD');
});

test('routing and storage', async () => {
  const h = await boot({noBoot: true, hash: '#/zzz/a%20b'});
  const PL = h.w.PL;
  const hit = [];
  PL.route('', (...a) => hit.push(['home', ...a]));
  PL.route('x', (...a) => hit.push(['x', ...a]));
  PL.dispatch();
  PL.go('#/x/1');
  await h.idle();
  PL.go('#/x/1');  // same hash → dispatch directly
  h.w.location.hash = '';
  await h.idle();
  assert.deepStrictEqual(hit, [['home', 'a b'], ['x', '1'], ['x', '1'], ['home']]);
  PL.store.set('k', {a: 1});
  assert.strictEqual(JSON.stringify(PL.store.get('k')), '{"a":1}');
  assert.strictEqual(PL.store.get('missing', 3), 3);
  h.w.localStorage.setItem('pl.bad', '{');
  assert.strictEqual(PL.store.get('bad', 'd'), 'd');
  Object.defineProperty(h.w, 'localStorage', {get() { throw new Error('private'); }});
  PL.store.set('k', 1);
  assert.strictEqual(PL.store.get('k', 9), 9);
});
