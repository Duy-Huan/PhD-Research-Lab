'use strict';
// Frontend test harness: the REAL frontend/index.html + every script it loads, in jsdom, against a fake backend that
// replays responses recorded from the real backend (fixtures.json — tools/frontend_fixtures.py).
// Scripts run through vm with their absolute file name, so `node --test --experimental-test-coverage` measures them.
//   const h = await boot({routes: {'POST /api/x': (req) => ({...})}});   h.$('#id').click();   await h.idle();
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM, VirtualConsole} = require('jsdom');
const fixtures = require('./fixtures');

const ROOT = path.resolve(__dirname, '../..');
const FRONT = path.join(ROOT, 'frontend');
const HTML = fs.readFileSync(path.join(FRONT, 'index.html'), 'utf8');
const SCRIPTS = [...HTML.matchAll(/<script src="\/([^"?]+)"><\/script>/g)].map((m) => m[1]);
const SRC = {};
const read = (rel) => (SRC[rel] = SRC[rel] || fs.readFileSync(path.join(FRONT, rel), 'utf8'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const LIVE = [];
require('node:test').afterEach(() => { for (const h of LIVE.splice(0)) h.close(); });

// ---------------------------------------------------------------- fake backend
class Server {
  constructor(routes) {
    this.routes = [];
    this.calls = [];
    this.unmatched = [];
    for (const [k, v] of Object.entries(fixtures.routes())) this.on(k, v);
    for (const [k, v] of Object.entries(routes || {})) this.on(k, v);
  }
  /** "METHOD /path" · "METHOD /path/:param" · "METHOD /path?exact=query" (later routes win). */
  on(key, handler) {
    const [method, full] = key.split(' ');
    const [pat, query] = full.split('?');
    const re = new RegExp('^' + pat.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/:\w+/g, '([^/]+)') + '$');
    this.routes.unshift({method, re, query: query === undefined ? null : query, handler});
    return this;
  }
  find(method, pathname, search) {
    const q = search.replace(/^\?/, '');
    return this.routes.find((r) => r.method === method && r.re.test(pathname) && (r.query === null || r.query === q)) || null;
  }
  calledWith(method, prefix) { return this.calls.filter((c) => c.method === method && c.path.startsWith(prefix)); }
  last(method, prefix) { const c = this.calledWith(method, prefix); return c[c.length - 1]; }
  async handle(url, opts = {}) {
    const u = new URL(url, 'http://127.0.0.1:8765');
    const method = (opts.method || 'GET').toUpperCase();
    let body = opts.body;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch { /* raw text */ } }
    const req = {method, path: u.pathname, query: Object.fromEntries(u.searchParams), body, headers: opts.headers || {}};
    this.calls.push(req);
    const r = this.find(method, u.pathname, u.search);
    if (!r) {
      this.unmatched.push(`${method} ${u.pathname}${u.search}`);
      return method === 'GET' ? resp({status: 404, body: {detail: `no fake for ${method} ${u.pathname}`}}) : resp({body: {}});
    }
    req.params = u.pathname.match(r.re).slice(1);
    let out = typeof r.handler === 'function' ? await r.handler(req) : r.handler;
    if (out instanceof Error) throw out;
    if (!(out && typeof out === 'object' && out.__resp)) out = {body: out};
    return resp(out);
  }
}

// Response stand-in: json / text / streamed body (review stages read Server-Sent Events from fetch)
function resp(o) {
  const status = o.status || 200;
  const isText = typeof o.body === 'string';
  const ct = 'contentType' in o ? o.contentType : o.sse ? 'text/event-stream' : isText ? 'text/plain' : 'application/json';
  const text = isText ? o.body : JSON.stringify(o.body === undefined ? {} : o.body);
  const chunks = o.sse ? o.sse.map((e) => (typeof e === 'string' ? e : `data: ${JSON.stringify(e)}\n\n`)) : null;
  return {
    ok: status < 400, status, statusText: o.statusText || '', headers: {get: (k) => (k.toLowerCase() === 'content-type' ? ct : null)},
    json: async () => JSON.parse(text), text: async () => text,
    body: chunks ? {getReader() {
      let i = 0;
      return {read: async () => (i < chunks.length ? {value: new TextEncoder().encode(chunks[i++]), done: false} : {value: undefined, done: true})};
    }} : null,
  };
}
const R = (body, status = 200, extra = {}) => ({__resp: true, body, status, ...extra});

// ---------------------------------------------------------------- browser APIs jsdom lacks
class FakeES {
  constructor(url) { this.url = url; this.closed = false; FakeES.all.push(this); }
  close() { this.closed = true; }
  open() { if (this.onopen) this.onopen({}); }
  send(obj) { if (this.onmessage) this.onmessage({data: typeof obj === 'string' ? obj : JSON.stringify(obj)}); }
  fail() { if (this.onerror) this.onerror(new Error('es')); }
}
FakeES.all = [];

/** A page with the app booted. opt: routes, hash, storage {k: v}, media {query: bool}, before(w, server), noBoot. */
async function boot(opt = {}) {
  FakeES.all = [];
  const vc = new VirtualConsole();
  const errors = [];
  vc.on('jsdomError', (e) => errors.push(String((e && (e.stack || e.message)) || e)));
  const dom = new JSDOM(HTML.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, ''),
    {url: 'http://127.0.0.1:8765/' + (opt.hash || ''), runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: vc});
  const w = dom.window;
  const server = new Server(opt.routes);
  w.fetch = (u, o) => server.handle(u, o);
  w.EventSource = FakeES;
  const media = opt.media || {};
  w.matchMedia = (q) => ({matches: !!media[q], media: q});
  w.Element.prototype.scrollIntoView = function () {};
  w.TextDecoder = TextDecoder;
  w.TextEncoder = TextEncoder;
  // every timer fires (almost) immediately: debounces, toasts and reconnects run without waiting for wall-clock time
  const st = w.setTimeout.bind(w);
  w.setTimeout = (fn, ms, ...a) => st(fn, ms ? 1 : 0, ...a);
  Object.defineProperty(w.navigator, 'clipboard', {value: {writeText: async (t) => { w.__clip = t; }}, configurable: true});
  for (const [k, v] of Object.entries(opt.storage || {})) w.localStorage.setItem(k, v);
  w.PL_NO_BOOT = true;
  if (opt.before) opt.before(w, server);
  const ctx = dom.getInternalVMContext();
  for (const rel of SCRIPTS) vm.runInContext(read(rel), ctx, {filename: path.join(FRONT, rel)});
  const h = {
    dom, w, document: w.document, server, errors, R, ES: FakeES, fx: fixtures,
    $: (s) => w.document.querySelector(s), $$: (s) => [...w.document.querySelectorAll(s)],
    idle: (ms = 15) => sleep(ms),
    until: async (fn, ms = 2000) => {
      const end = Date.now() + ms;
      while (Date.now() < end) { try { if (await fn()) return true; } catch { /* not yet */ } await sleep(5); }
      throw new Error('until(): condition not met: ' + fn.toString().slice(0, 160));
    },
    el: (sel) => { const e = typeof sel === 'string' ? w.document.querySelector(sel) : sel; if (!e) throw new Error('no element ' + sel); return e; },
    click: async (sel, ms = 15) => { const e = h.el(sel); e.click(); await sleep(ms); return e; },
    /** the first element matching sel whose text contains `text` */
    byText: (sel, text) => { const e = [...w.document.querySelectorAll(sel)].find((x) => x.textContent.includes(text)); if (!e) throw new Error(`no ${sel} with "${text}"`); return e; },
    clickText: async (sel, text, ms = 15) => { h.byText(sel, text).click(); await sleep(ms); },
    input: async (sel, value, ev = 'input') => { const e = h.el(sel); e.value = value; e.dispatchEvent(new w.Event(ev, {bubbles: true})); await sleep(10); return e; },
    change: (sel, value) => h.input(sel, value, 'change'),
    key: async (sel, key, extra = {}) => { h.el(sel).dispatchEvent(new w.KeyboardEvent('keydown', {key, bubbles: true, cancelable: true, ...extra})); await sleep(10); },
    /** dispatch an event carrying files (drop / change on an <input type=file>) */
    files: (names) => names.map((n) => new w.File(['x'.repeat(10)], n, {type: n.endsWith('.pdf') ? 'application/pdf' : 'text/plain'})),
    setFiles: async (input, names) => { Object.defineProperty(input, 'files', {value: h.files(names), configurable: true}); input.dispatchEvent(new w.Event('change')); await sleep(15); },
    drop: async (sel, names, type = 'drop') => { const e = new w.Event(type, {bubbles: true, cancelable: true}); Object.defineProperty(e, 'dataTransfer', {value: {files: h.files(names)}}); h.el(sel).dispatchEvent(e); await sleep(15); },
    toast: () => w.document.querySelector('#toast').textContent,
    go: async (hash, ms = 30) => { w.location.hash = hash; await sleep(ms); },
    run: (code) => vm.runInContext(code, ctx),
    close: () => { try { w.close(); } catch { /* ignore */ } },
  };
  LIVE.push(h);
  if (!opt.noBoot) { await w.PL.boot(); await sleep(opt.settle === undefined ? 30 : opt.settle); }
  return h;
}

module.exports = {boot, R, FakeES, sleep, ROOT, FRONT, SCRIPTS, fixtures};
