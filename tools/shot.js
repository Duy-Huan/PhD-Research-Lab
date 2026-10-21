// Screenshot of the running app in headless Edge (dev tool):
//   node tools/shot.js URL out.png [width] [height] [jsBeforeShot]
// Console errors and uncaught exceptions of the page are printed (a blank screen always has a reason).
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const [url, out, w = '1440', h = '900', js = ''] = process.argv.slice(2);
const exe = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const port = 9300 + Math.floor(Math.random() * 500);
const p = spawn(exe, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`, `--window-size=${w},${h}`, '--user-data-dir=' + require('os').tmpdir() + '/shot' + port, 'about:blank']);
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  let ws;
  for (let i = 0; i < 50 && !ws; i++) {
    try { const t = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); ws = t.find(x => x.type === 'page').webSocketDebuggerUrl; } catch { await sleep(200); }
  }
  const sock = new WebSocket(ws); let id = 0; const wait = {};
  sock.onmessage = m => {
    const d = JSON.parse(m.data);
    if (wait[d.id]) { wait[d.id](d.result); delete wait[d.id]; }
    if (d.method === 'Runtime.exceptionThrown') console.log('EXCEPTION', JSON.stringify(d.params.exceptionDetails).slice(0, 800));
    if (d.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(d.params.type)) console.log('CONSOLE', d.params.type, JSON.stringify(d.params.args.map(a => a.value || a.description)).slice(0, 500));
    if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error') console.log('LOG', d.params.entry.text, d.params.entry.url || '');
  };
  await new Promise(r => sock.onopen = r);
  const call = (method, params = {}) => new Promise(r => { wait[++id] = r; sock.send(JSON.stringify({id, method, params})); });
  await call('Runtime.enable');
  await call('Log.enable');
  await call('Page.navigate', {url});
  await sleep(3500);
  if (js) { const r = await call('Runtime.evaluate', {expression: js, awaitPromise: true}); if (r && r.exceptionDetails) console.log('EVAL', JSON.stringify(r.exceptionDetails).slice(0, 500)); await sleep(1500); }
  const r = await call('Page.captureScreenshot', {format: 'png'});
  fs.writeFileSync(out, Buffer.from(r.data, 'base64'));
  sock.close(); p.kill();
  process.exit(0);
})();
