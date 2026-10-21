'use strict';
// main.js: boot, project switcher, navigation, keyboard shortcuts, the UI ⇄ CLI live bus.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const SID = fixtures.meta.session;
const RID = fixtures.meta.runs[0];

test('boot paints the project, conversations, pending count; header + sidebar controls', async () => {
  const h = await boot({storage: {'pl.side': 'false'}});
  assert.match(h.$('#proj-sub').textContent, /Đề cương cấp 3\/5/);
  assert.ok(h.$('#app').classList.contains('side-collapsed'));
  await h.until(() => h.$('#pending-count').textContent === '4');
  assert.match(h.w.document.title, /PhD Research Lab/);
  assert.ok(h.$$('#threads .thread').length >= 1);
  // sidebar toggle (wide screen) remembers its state; side-open re-opens
  await h.click('#side-toggle');
  assert.ok(!h.$('#app').classList.contains('side-collapsed'));
  assert.strictEqual(h.w.localStorage.getItem('pl.side'), 'true');
  await h.click('#side-toggle');
  await h.click('#side-open');
  assert.ok(!h.$('#app').classList.contains('side-collapsed'));
  // new chat / search
  await h.go('#/chat/' + SID);
  await h.click('#new-chat');
  assert.strictEqual(h.w.location.hash, '#/');
  await h.input('#search', 'ViT');
  await h.until(() => h.server.calls.some((c) => c.path === '/api/chat/sessions' && c.query.q === 'ViT'));
  // panel button toggles the outline panel
  await h.click('#panel-btn', 40);
  assert.strictEqual(h.$('#panel').hidden, false);
  assert.strictEqual(h.$('#panel-title').textContent, 'Đề cương nghiên cứu');
  await h.click('#panel-btn');
  assert.strictEqual(h.$('#panel').hidden, true);
  await h.click('#panel-btn', 40);
  await h.click('#panel-close');
  assert.strictEqual(h.$('#panel').hidden, true);
  assert.deepStrictEqual(h.errors, []);
});

test('narrow screens: the sidebar slides over the page', async () => {
  const h = await boot({media: {'(max-width: 820px)': true}, storage: {'pl.side': 'false'}});
  assert.ok(!h.$('#app').classList.contains('side-collapsed'));  // never collapsed on a phone
  await h.click('#side-open');
  assert.ok(h.$('#app').classList.contains('side-open'));
  await h.click('#side-toggle');
  assert.ok(!h.$('#app').classList.contains('side-open'));
  await h.click('#side-open');
  await h.click('#new-chat');
  assert.ok(!h.$('#app').classList.contains('side-open'));
});

test('navigation buttons open panels, pages and settings', async () => {
  const h = await boot();
  await h.click('.nav[data-go="library"]', 40);
  assert.strictEqual(h.$('#panel-title').textContent, 'Tài liệu');
  await h.click('.nav[data-go="code"]', 40);
  assert.match(h.$('#panel-title').textContent, /VS Code/);
  await h.click('.nav[data-go="settings"]', 40);
  assert.ok(h.$('.settings'));
  h.$('#modal').click();
  await h.click('.nav[data-go="dashboard"]', 60);
  assert.strictEqual(h.w.location.hash, '#/dashboard');
  assert.ok(h.$('.nav[data-go="dashboard"]').classList.contains('active'));
  await h.click('.nav[data-go="review"]', 60);
  assert.strictEqual(h.w.location.hash, '#/review');
});

test('keyboard: Ctrl+Shift+O new chat, "/" opens the skill menu outside inputs', async () => {
  const h = await boot({hash: '#/dashboard'});
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'O', ctrlKey: true, shiftKey: true, cancelable: true}));
  await h.idle(40);
  assert.strictEqual(h.w.location.hash, '#/');
  h.document.activeElement.blur();
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: '/', cancelable: true}));
  await h.idle();
  assert.strictEqual(h.$('#input').value, '/');
  assert.ok(h.$('.menu.slash'));
  h.$('#input').focus();
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: '/', cancelable: true}));  // typing in the box: untouched
  assert.strictEqual(h.$('#input').value, '/');
  await h.go('#/dashboard', 60);
  h.document.activeElement.blur();
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: '/', cancelable: true}));  // no composer on this page
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'x'}));
  await h.go('#/', 60);
  Object.defineProperty(h.document, 'activeElement', {get: () => null, configurable: true});
  h.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: '/', cancelable: true}));
  assert.strictEqual(h.$('#input').value, '/');
  await h.go('#/chat', 60);
  assert.strictEqual(h.w.PL.chat.sid, null);
});

test('project menu: switch, new project (validation, failure, success), open existing, outline, reveal', async () => {
  const other = {name: 'Second', data_dir: 'D:/p2'};
  let failCreate = true;
  const h = await boot({routes: {
    'GET /api/projects': () => ({projects: [...fixtures.get('GET /api/projects').projects, other]}),
    'POST /api/projects': () => (failCreate ? R({detail: 'exists'}, 409) : {project: other}),
  }});
  const menu = async () => { await h.click('#proj-btn'); return h.$$('.menu.pop .mi'); };
  let items = await menu();
  assert.ok(items[0].textContent.includes('đang mở'));
  items[0].click();  // the open project: nothing to do
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', '/api/projects/activate').length, 0);
  items = await menu();
  items[1].click();
  await h.until(() => h.server.calledWith('POST', '/api/projects/activate').length === 1);
  assert.strictEqual(h.server.last('POST', '/api/projects/activate').body.data_dir, 'D:/p2');
  // new project
  (await menu()).find((b) => b.textContent.includes('Dự án mới')).click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Tạo dự án');
  assert.strictEqual(h.$('#modal').hidden, false);  // a name is required
  h.$$('#modal input')[0].value = 'New one';
  await h.clickText('.dialog-f button', 'Tạo dự án', 30);
  assert.strictEqual(h.$('#modal').hidden, false);  // server refused: stays open
  assert.match(h.toast(), /exists/);
  failCreate = false;
  h.$$('#modal input')[1].value = 'D:/p3';
  await h.clickText('.dialog-f button', 'Tạo dự án', 40);
  assert.strictEqual(h.$('#modal').hidden, true);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', '/api/projects').body)), {name: 'New one', data_dir: 'D:/p3'});
  (await menu()).find((b) => b.textContent.includes('Dự án mới')).click();
  await h.idle();
  h.$$('#modal input')[0].value = 'No dir';
  await h.clickText('.dialog-f button', 'Tạo dự án', 40);
  assert.strictEqual(h.server.last('POST', '/api/projects').body.data_dir, undefined);
  // open an existing folder (cancel, then a path)
  (await menu()).find((b) => b.textContent.includes('Mở dự án có sẵn')).click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ');
  (await menu()).find((b) => b.textContent.includes('Mở dự án có sẵn')).click();
  await h.idle();
  h.$('#modal input').value = 'D:/existing';
  await h.clickText('.dialog-f button', 'Lưu', 40);
  assert.strictEqual(h.server.last('POST', '/api/projects/open').body.data_dir, 'D:/existing');
  (await menu()).find((b) => b.textContent.includes('Đề cương')).click();
  await h.idle(40);
  assert.strictEqual(h.$('#panel-title').textContent, 'Đề cương nghiên cứu');
  (await menu()).find((b) => b.textContent.includes('Mở thư mục')).click();
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', '/api/projects/reveal').length, 1);
  // the menu closes on an outside click
  await h.click('#proj-btn');
  await h.idle();
  h.document.body.dispatchEvent(new h.w.MouseEvent('mousedown', {bubbles: true}));
  assert.strictEqual(h.$('.menu.pop'), null);
});

test('live bus: conversation, run, project, outline and config events refresh the right parts', async () => {
  const h = await boot({hash: '#/chat/' + SID});
  const bus = h.ES.all.find((e) => e.url.startsWith('/api/events/stream'));
  const n = (p) => h.server.calledWith('GET', p).length;
  const before = {list: n('/api/chat/sessions'), dash: n('/api/dashboard'), run: n('/api/runs/' + RID), cfg: n('/api/config'), models: n('/api/models')};
  h.w.PL.chat.sse.close();
  h.w.PL.chat.sse = null;  // the open conversation without its own stream: the bus refreshes it
  bus.send({type: 'aiws.approval_required', session_id: SID, seq: 5});
  bus.send({type: 'aiws.message', session_id: 'other', seq: 6});
  bus.send({type: 'run.updated', run_id: RID, seq: 7});
  bus.send({type: 'run.created', seq: 8});
  bus.send({type: 'outline.updated', seq: 9});
  bus.send({type: 'config.saved', seq: 10});
  await h.idle(60);
  assert.ok(n('/api/chat/sessions') > before.list);
  assert.ok(n('/api/dashboard') > before.dash);
  assert.ok(n('/api/runs/' + RID) > before.run);
  assert.ok(n('/api/config') > before.cfg);
  assert.ok(n('/api/models') > before.models);
  bus.send({type: 'project.switched', seq: 11});
  await h.idle(60);
  assert.strictEqual(h.w.location.hash, '#/');
});

test('boot survives a failing backend; restores the last run panel; dashboard down → no count', async () => {
  const h = await boot({storage: {'pl.panel': JSON.stringify({kind: 'run', arg: RID})}, routes: {
    'GET /api/config': () => R({detail: 'config broken'}, 500),
    'GET /api/dashboard': () => R({detail: 'x'}, 500),
  }});
  assert.match(h.toast(), /config broken/);
  await h.until(() => h.$('#panel-title').textContent.includes('/lit'));
  assert.strictEqual(h.$('#pending-count').textContent, '');
  const h2 = await boot({routes: {'GET /api/outline': () => R({detail: 'x'}, 500)}});
  assert.strictEqual(h2.$('#proj-sub').textContent, 'Chưa có đề cương');
  const h3 = await boot({routes: {'GET /api/outline': () => ({level: 0, keywords: []})}});
  assert.strictEqual(h3.$('#proj-sub').textContent, 'Chưa có đề cương');
  h3.w.PL.paintPending(0);
  h3.$('#pending-count').remove();
  h3.w.PL.paintPending(2);
  h3.$('#title').remove();
  h3.$('#crumb').remove();
  h3.w.PL.setTitle('', '');
  assert.strictEqual(h3.w.document.title, 'PhD Research Lab');
});

test('the page boots itself: right away, or on DOMContentLoaded while still loading', async () => {
  const h = await boot({noBoot: true, before: (w) => {
    w.PL_NO_BOOT = false;
    Object.defineProperty(w.document, 'readyState', {value: 'complete', configurable: true});
  }});
  await h.until(() => h.$('#proj-name').textContent.includes('Default'));
  const h2 = await boot({noBoot: true, before: (w) => {
    w.PL_NO_BOOT = false;
    Object.defineProperty(w.document, 'readyState', {value: 'loading', configurable: true});
  }});
  await h2.until(() => h2.$('#proj-name').textContent.includes('Default'));
});
