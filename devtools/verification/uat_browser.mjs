// Owned browser lease. Browser traffic can reach only this run's application origin.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import http from 'node:http';
import readline from 'node:readline';
const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const options = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const target = new URL(options.url);
if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || !target.port || target.username || target.password) throw Error('Unsafe application origin');
const out = resolve(options.out);
const events = [], mutations = [], blocked = [];
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
  page.on('console', m => { if (m.type() === 'error') events.push({ phase, kind: 'console', text: m.text().slice(0, 1200) }); });
  page.on('requestfailed', r => events.push({ phase, kind: 'network', url: new URL(r.url()).pathname, error: r.failure() }));
};
context.on('page', attach); for (const page of context.pages()) attach(page);
context.on('response', async response => {
  const req = response.request();
  if (req.url() === target.origin + '/api/config' && req.method() === 'POST') {
    try { const language = req.postDataJSON()?.ui?.language; if (language) mutations.push({ language, status: response.status() }); } catch { /* Unrelated config fields are not copied. */ }
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
const [port, wsPath] = readFileSync(join(out, 'browser-profile', 'DevToolsActivePort'), 'utf8').trim().split(/\r?\n/);
writeFileSync(join(out, 'browser-lease.json'), JSON.stringify({ cdp_url: `http://127.0.0.1:${port}`, websocket: wsPath, app_origin: target.origin, profile: join(out, 'browser-profile'), personal_profile: false, egress_canary: 'BLOCKED' }, null, 2));
console.log('UAT_BROWSER_READY');
const input = readline.createInterface({ input: process.stdin });
for await (const line of input) {
  if (!line.trim()) continue;
  const command = JSON.parse(line);
  if (command.action !== 'finish') continue;
  let confirmation = 'UNCONFIRMED';
  const current = context.pages().find(p => p.url().startsWith(target.origin)) || page;
  const vi = mutations.findIndex(m => m.language === 'vi' && m.status === 200);
  const en = mutations.findIndex((m, i) => i > vi && m.language === 'en' && m.status === 200);
  const config = await new Promise((resolve, reject) => {
    const req = http.get({ hostname: '127.0.0.1', port: Number(target.port), path: '/api/config' }, res => {
      let body = ''; res.on('data', chunk => { body += chunk; });
      res.on('end', () => { try { if (res.statusCode !== 200) throw Error('Config verification HTTP ' + res.statusCode); resolve(JSON.parse(body)); } catch (e) { reject(e); } });
    });
    req.setTimeout(10_000, () => req.destroy(Error('Config verification timeout'))); req.on('error', reject);
  });
  if (vi >= 0 && en > vi && config.ui?.language === 'en' && await current.locator('.settings-studio-content').isVisible()) confirmation = 'PASS';
  await current.screenshot({ path: join(out, 'final.png'), fullPage: true });
  writeFileSync(join(out, 'browser-evidence.json'), JSON.stringify({ confirmation, mutations, events, blocked,
    scope: 'Settings navigation and observed VI -> EN backend persistence only; other personas are not qualified' }, null, 2));
  break;
}
input.close(); process.stdin.destroy();
await context.tracing.stop({ path: join(out, 'trace.zip') });
await context.close(); proxy.closeAllConnections(); await new Promise(resolve => proxy.close(resolve));
