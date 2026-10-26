// Owned browser lease. Browser traffic can reach only this run's application origin.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import http from 'node:http';
import readline from 'node:readline';
import { createHash } from 'node:crypto';
const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const options = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const target = new URL(options.url);
if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || !target.port || target.username || target.password) throw Error('Unsafe application origin');
const out = resolve(options.out);
const journey = options.journey || 'settings-language';
if (!['settings-language', 'project-and-chat', 'workflow-operations', 'failure-recovery'].includes(journey)) throw Error('Unsupported UAT journey');
const events = [], mutations = [], blocked = [], navigations = [], configReads = [];
let controlledFault = null;
async function readJSON(path) {
  return new Promise((resolve, reject) => {
    const req = http.get({ hostname: '127.0.0.1', port: Number(target.port), path }, res => {
      let body = ''; res.on('data', chunk => { body += chunk; if (body.length > 20_000_000) req.destroy(Error('Oversized owned state')); });
      res.on('end', () => { try { if (res.statusCode !== 200) throw Error('State verification HTTP ' + res.statusCode); resolve(JSON.parse(body)); } catch (e) { reject(e); } });
    });
    req.setTimeout(10_000, () => req.destroy(Error('State verification timeout'))); req.on('error', reject);
  });
}
const initial = await readJSON('/api/qa/uat-state');
let phase = 'STARTUP';
const proxy = http.createServer((req, res) => {
  let url;
  try { url = req.url.startsWith('/') && req.headers.host === target.host ? new URL(req.url, target.origin) : new URL(req.url); } catch { res.writeHead(400).end(); return; }
  if (url.origin !== target.origin) {
    blocked.push({ method: req.method, origin: url.origin }); res.writeHead(403).end('Origin outside UAT allowlist'); return;
  }
  const headers = { ...req.headers, host: target.host };
  delete headers['proxy-authorization']; delete headers['proxy-connection'];
  const upstream = http.request({ hostname: '127.0.0.1', port: Number(target.port), path: url.pathname + url.search, method: req.method, headers }, response => {
    res.writeHead(response.statusCode, response.headers); response.pipe(res);
  });
  upstream.setTimeout(30_000, () => upstream.destroy(Error('Bounded UAT upstream timeout')));
  upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
  req.pipe(upstream);
});
proxy.on('connect', (req, socket) => { blocked.push({ method: 'CONNECT', host: req.url }); socket.end('HTTP/1.1 403 Forbidden\r\n\r\n'); });
await new Promise(resolve => proxy.listen(0, '127.0.0.1', resolve));
const context = await chromium.launchPersistentContext(join(out, 'browser-profile'), {
  headless: true, permissions: [], acceptDownloads: false, serviceWorkers: 'block',
  proxy: { server: `http://127.0.0.1:${proxy.address().port}`, bypass: '<-loopback>' },
  args: ['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', '--disable-extensions',
    '--disable-background-networking', '--disable-quic', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'],
});
async function emergency(error) {
  console.error(error?.stack || String(error));
  await context.close().catch(() => {}); proxy.closeAllConnections(); proxy.close(); process.exitCode = 1;
}
process.once('uncaughtException', emergency);
process.once('unhandledRejection', emergency);
process.once('SIGTERM', () => emergency('Owned browser terminated'));
await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
const attach = page => {
  page.on('pageerror', e => events.push({ phase, kind: 'pageerror', text: e.message }));
  page.on('framenavigated', frame => { if (frame === page.mainFrame() && frame.url().startsWith(target.origin)) navigations.push({ url: frame.url(), at: Date.now() }); });
  page.on('console', m => {
    if (m.type() !== 'error') return;
    const url = m.location().url, event = { phase, kind: 'console', url, text: m.text().slice(0, 1200) };
    if (url === 'http://example.invalid/uat-canary') event.expected_fault_id = 'UAT-EGRESS-CANARY';
    if (phase === 'EXPECTED_FAULT_INJECTION' && m.text().includes("Access to fetch at 'http://example.invalid/uat-canary'")
        && m.text().includes("from origin '" + target.origin + "'") && m.text().includes('blocked by CORS policy')) {
      event.expected_fault_id = 'UAT-EGRESS-CANARY'; event.fault_url = 'http://example.invalid/uat-canary';
    }
    if (controlledFault && url === target.origin + '/api/config' && /503/.test(m.text())) Object.assign(event, { expected_fault_id: controlledFault.id, path: '/api/config' });
    events.push(event);
  });
  page.on('requestfailed', r => events.push({ phase, kind: 'network', url: r.url(), error: r.failure(),
    ...(r.url() === 'http://example.invalid/uat-canary' ? { expected_fault_id: 'UAT-EGRESS-CANARY' } : {}) }));
};
context.on('page', attach); for (const page of context.pages()) attach(page);
context.on('response', async response => {
  const req = response.request();
  const url = new URL(req.url());
  if (url.origin !== target.origin || !url.pathname.startsWith('/api/')) return;
  if (req.method() === 'POST') {
    let language;
    if (url.pathname === '/api/config') { try { language = req.postDataJSON()?.ui?.language; } catch { /* No arbitrary request body is retained. */ } }
    mutations.push({ path: url.pathname, method: req.method(), language, status: response.status(), at: Date.now() });
  }
  if (req.method() === 'GET' && url.pathname === '/api/config') configReads.push({ status: response.status(), at: Date.now() });
  if (response.status() >= 400) {
    const event = { phase, kind: 'http', path: url.pathname, status: response.status() };
    if (controlledFault && url.pathname === '/api/config' && response.status() === 503 && req.method() === 'GET') event.expected_fault_id = controlledFault.id;
    events.push(event);
  }
});
const page = context.pages()[0] || await context.newPage();
await page.goto(target.origin + '/dist/react.html');
await expect(page.getByRole('button', { name: 'System Settings', exact: true })).toBeVisible();
// This canary demonstrates that browser-origin requests cannot reach arbitrary hosts.
phase = 'EXPECTED_FAULT_INJECTION';
const forbidden = await page.evaluate(async () => { try { return (await fetch('http://example.invalid/uat-canary')).status; } catch { return 'BLOCKED'; } });
if (forbidden !== 'BLOCKED' && forbidden !== 403) throw Error('Browser egress canary failed');
await new Promise(resolve => setTimeout(resolve, 100));
phase = 'EXPLORATION';
if (journey === 'failure-recovery') {
  await context.route(target.origin + '/api/config', async route => {
    if (route.request().method() !== 'GET' || controlledFault) return route.continue();
    controlledFault = { id: 'UAT-CONFIG-503', path: '/api/config', method: 'GET', status: 503,
      at: Date.now(), mode: 'CONTROLLED_BROWSER_NETWORK_FAULT', scientific_or_provider_evidence: false };
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'UAT controlled config interruption' }) });
  });
}
const [port, wsPath] = readFileSync(join(out, 'browser-profile', 'DevToolsActivePort'), 'utf8').trim().split(/\r?\n/);
writeFileSync(join(out, 'browser-lease.json'), JSON.stringify({ cdp_url: `http://127.0.0.1:${port}`, websocket: wsPath, app_origin: target.origin, profile: join(out, 'browser-profile'), personal_profile: false, egress_canary: 'BLOCKED', journey, setup: initial.lease }, null, 2));
console.log('UAT_BROWSER_READY');
const input = readline.createInterface({ input: process.stdin });
for await (const line of input) {
  if (!line.trim()) continue;
  const command = JSON.parse(line);
  if (command.action !== 'finish') continue;
  const current = context.pages().find(p => p.url().startsWith(target.origin)) || page;
  const checks = [];
  const check = (id, passed) => checks.push({ id, passed: passed === true });
  const state = await readJSON('/api/qa/uat-state');
  const settingsVisible = await current.locator('.settings-studio-content').isVisible();
  const vi = mutations.findIndex(m => m.language === 'vi' && m.status === 200);
  const en = mutations.findIndex((m, i) => i > vi && m.language === 'en' && m.status === 200);
  if (journey === 'settings-language') {
    const config = await readJSON('/api/config');
    check('language_vi_then_en', vi >= 0 && en > vi); check('persisted_english', config.ui?.language === 'en'); check('settings_visible', settingsVisible);
  } else if (journey === 'project-and-chat') {
    const session = state.sessions?.find(s => s.turns?.some(t => t.question === 'Return just the result of 13 plus 29. Do not use any tools.'));
    const turn = session?.turns?.at(-1), answer = session?.messages?.find(m => m.id === turn?.answer_id);
    check('owned_project_created', state.in_owned_project === true && mutations.some(m => m.path === '/api/projects' && m.status === 200));
    check('chat_request_observed', mutations.some(m => m.path === `/api/chat/sessions/${session?.id}/turns` && m.status === 200));
    check('completed_local_turn', turn?.status === 'completed' && !turn?.error && answer?.provider === 'app:local' && answer?.model === initial.lease.model);
    check('response_persisted', answer?.content?.trim() === '42' && answer?.status === 'complete');
    const ended = typeof turn?.ended === 'number' ? turn.ended * 1000 : Date.parse(turn?.ended || '');
    check('visible_after_reload', Number.isFinite(ended) && navigations.some(n => n.at > ended)
      && (await current.locator('.msg-card.assistant').last().innerText().catch(() => '')).includes('42'));
    check('isolation_preserved', !state.sessions?.some(s => s.id === initial.lease.sentinel_id));
  } else if (journey === 'workflow-operations') {
    const mission = state.mission, base = `/api/research/topics/${initial.lease.topic_id}/missions/${initial.lease.mission_id}`;
    check('initial_draft', initial.mission?.status === 'draft' && initial.runs?.length === 0 && initial.mission.tasks.every(t => t.payload.attempts === 0));
    check('approval_observed', mutations.some(m => m.path === base + '/approve' && m.status === 200));
    check('review_observed', mutations.some(m => m.path === base + '/review' && m.status === 200));
    check('native_tasks_completed_once', mission?.status === 'completed' && mission.tasks.length === 2 && mission.tasks.every(t => t.status === 'completed' && t.payload.attempts === 1));
    const rawValid = state.raw_artifacts?.length >= 5 && state.raw_artifacts.every(a => {
      const raw = Buffer.from(a.content_base64, 'base64'); return raw.length === a.bytes && createHash('sha256').update(raw).digest('hex') === a.sha256;
    });
    check('native_raw_artifacts', rawValid && state.runs?.length === 1 && state.runs.every(r => r.status === 'completed' && r.mission_id === mission.id && r.protocol_id === initial.lease.protocol_id && r.trials.length === 4 && r.trials.every(t => t.status === 'completed')));
    check('zero_reasoning_calls', mission?.payload.reasoning_calls === 0);
    const card = current.locator('article').filter({ has: current.getByRole('heading', { name: /L3.*Synthetic CPU UAT mission/ }) });
    check('completed_visible', /\bcompleted\b/.test(await card.getByRole('status').innerText().catch(() => '')));
  } else {
    check('exact_controlled_fault', controlledFault?.id === 'UAT-CONFIG-503' && configReads.filter(r => r.status === 503).length === 1);
    check('reload_after_fault', !!controlledFault && navigations.some(n => n.at > controlledFault.at));
    check('successful_config_after_fault', !!controlledFault && configReads.some(r => r.status === 200 && r.at > controlledFault.at));
    check('settings_visible', settingsVisible);
  }
  const confirmation = checks.length && checks.every(c => c.passed) ? 'PASS' : 'UNCONFIRMED';
  await current.screenshot({ path: join(out, 'final.png'), fullPage: true });
  writeFileSync(join(out, 'browser-evidence.json'), JSON.stringify({ journey, source_sha256: options.source_sha256 || 'UNATTESTED', oracle_version: 1,
    confirmation, checks, mutations, events, blocked, navigations, configReads, controlled_fault: controlledFault, initial, state,
    scope: 'Only ' + journey + '; deterministic synthetic setup/control faults are labeled; scientific/provider/autonomy claims require separate qualification' }, null, 2));
  break;
}
input.close(); process.stdin.destroy();
// End only this context's long-lived SSE requests before trace/browser teardown.
await Promise.all(context.pages().map(p => p.goto('about:blank', { waitUntil: 'commit', timeout: 10_000 }).catch(() => {})));
await context.tracing.stop({ path: join(out, 'trace.zip') });
await context.close(); proxy.closeAllConnections(); await new Promise(resolve => proxy.close(resolve));
