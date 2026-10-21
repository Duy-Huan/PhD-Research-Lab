'use strict';
// dashboard.js: the minimal tracking page (goal, current step, status, next decision, pending work, pins, recent runs)
// and its "advanced" section (hardware guard, GPU / VRAM, providers, acceptance evidence, research state).
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const RID = fixtures.meta.runs[0];
const SID = fixtures.meta.session;
const dash = (extra) => ({...fixtures.get('GET /api/dashboard'), ...extra});

test('tiles, pending work, recent runs; tiles and rows open the right place', async () => {
  const h = await boot({hash: '#/dashboard'});
  assert.strictEqual(h.$('#title').textContent, 'Theo dõi');
  assert.strictEqual(h.$('.page h1').textContent, 'Default project');
  const tiles = h.$$('.tile');
  assert.match(tiles[0].textContent, /Đề cương cấp 3\/5 · Chủ đề \+ định hướng/);
  assert.match(tiles[1].textContent, /Không có run nào đang chạy/);
  assert.match(tiles[2].textContent, /chờ bạn duyệt/);
  assert.match(h.$('.page').textContent, /Cần bạn duyệt \(4\)/);
  assert.match(h.$('.page').textContent, /Ghi research gap/);  // the action name is shown in words
  assert.match(h.$('.page').textContent, /Chưa có\. Kết quả của run/);
  const det = h.$('details.adv');
  det.open = true;
  det.dispatchEvent(new h.w.Event('toggle'));
  await h.idle(40);
  assert.match(det.textContent, /Nghiệm thu AI Research OS · 20\d\d-/);
  tiles[0].click();
  await h.idle(40);
  assert.strictEqual(h.$('#panel-title').textContent, 'Đề cương nghiên cứu');
  h.$('.page table tr:nth-child(2)').click();
  await h.idle(40);
  assert.match(h.$('#panel-title').textContent, /\/lit/);
  // pending: memory proposals open the review list; approvals open their conversation
  h.$$('.page .panelbox .li').find((x) => x.textContent.includes('đề xuất ghi nhớ')).click();
  await h.idle(40);
  assert.strictEqual(h.$('#panel-title').textContent, 'Đề xuất ghi nhớ');
  h.$$('.page .panelbox .li').find((x) => x.textContent.includes('Ghi research gap')).click();
  await h.idle(60);
  assert.strictEqual(h.w.location.hash, '#/chat/' + SID);
});

test('a running project: current step, run in pending work, pins with their menu, statuses', async () => {
  const pins = [{id: 'PIN-1', title: 'Best acc', kind: 'result', body: 'acc 0.91', status: 'verified'},
    {id: 'PIN-2', title: 'Note', kind: 'note', body: 'x', status: 'approved'}, {id: 'PIN-3', title: 'P', kind: 'note', body: '', status: 'pinned'},
    {id: 'PIN-4', title: 'Q', kind: 'note', body: '', status: 'odd'}];
  let d = dash({status: 'running', goal: '', outline_level: 0, outline_label: '', next_decision: '',
    current: {run: RID, title: 'Run T', step: 'Train', provider: 'python', progress: '2/4'},
    pending: [{kind: 'run', id: RID, title: 'Run needs you', status: 'NEEDS_USER_ACTION', text: ''}, {kind: 'odd', id: 'x', title: 'Y'}],
    pins, recent_runs: [{...fixtures.get('GET /api/dashboard').recent_runs[0], synthetic: true}]});
  const h = await boot({hash: '#/dashboard', routes: {'GET /api/dashboard': () => d}});
  const tiles = h.$$('.tile');
  assert.match(tiles[0].textContent, /Chưa có — bắt đầu bằng \/outline/);
  assert.match(tiles[0].textContent, /Đề cương cấp 0\/5$/);
  assert.match(tiles[1].textContent, /Train.*python · 2\/4/);
  assert.match(tiles[2].textContent, /đang chạy/);
  assert.match(tiles[3].textContent, /Không có gì cần bạn quyết định/);
  assert.match(h.$('.page').textContent, /SYNTHETIC/);
  assert.match(h.$('.page').textContent, /Cần bạn quyết định/);
  assert.deepStrictEqual(h.$$('.page .li .chip').slice(-4).map((c) => c.textContent), ['đã kiểm chứng', 'đã duyệt', 'đã ghim', 'odd']);
  tiles[1].click();
  await h.idle(40);
  assert.strictEqual(h.$('#panel-title').textContent, '/lit lightweight vision transformers for edge devices');
  h.$$('.page .panelbox .li')[0].click();
  await h.idle(40);
  assert.match(h.$('#panel-title').textContent, /\/lit/);
  // pin menu
  const pinMenu = async (label) => { h.$$('.page .li button.icon')[0].click(); await h.idle(); await h.clickText('.menu.pop .mi', label, 20); };
  await pinMenu('Đánh dấu đã duyệt');
  assert.strictEqual(h.server.last('PUT', '/api/pins/PIN-1').body.status, 'approved');
  await pinMenu('Đánh dấu đã kiểm chứng');
  assert.strictEqual(h.server.last('PUT', '/api/pins/PIN-1').body.status, 'verified');
  await pinMenu('Bỏ ghim');
  assert.strictEqual(h.server.calledWith('DELETE', '/api/pins/PIN-1').length, 1);
  // other statuses
  d = dash({status: 'idle', pending: [], recent_runs: []});
  h.w.PL.emit({type: 'run.updated'});
  await h.idle(40);
  assert.match(h.$$('.tile')[2].textContent, /rảnh/);
  assert.strictEqual(h.$('.page table'), null);
  d = dash({status: 'something'});
  h.w.PL.emit({type: 'aiws.message'});
  h.w.PL.emit({type: 'outline.updated'});
  await h.idle(40);
  assert.match(h.$$('.tile')[2].textContent, /something/);
});

test('advanced details: guard slots, GPU, models in VRAM, providers, acceptance, research state, unload', async () => {
  const adv = {...fixtures.get('GET /api/dashboard?advanced=1')};
  adv.resources.gpu.held_by = ['RR-1:S2'];
  adv.gpus.push({name: '', vram_total_mb: 0});
  adv.local_models = {ollama: ['qwen'], lmstudio: [], online: true};
  const h = await boot({hash: '#/dashboard', routes: {'GET /api/dashboard?advanced=1': () => adv,
    'GET /api/acceptance': () => ({...fixtures.get('GET /api/acceptance'), generated: '', gaps: undefined,
      criteria: [{priority: 'P0', title: 'a', verdict: 'PASS', evidence: 'e'}, {priority: 'P1', title: 'b', verdict: 'FAIL', evidence: ''},
        {priority: 'P1', title: 'c', verdict: 'PARTIAL', evidence: ''}]})}});
  const det = h.$('details.adv');
  det.open = true;
  det.dispatchEvent(new h.w.Event('toggle'));
  await h.idle(40);
  const t = det.textContent;
  for (const s of ['RR-1:S2', 'RTX 3060', '1030 / 12288 MB', '41°C', 'GPU', '? °C'.replace(' ', ''), 'Trong VRAM: ollama: qwen', 'Feynman', 'NOT_CONFIGURED',
    '1 quyết định', '1 giả thuyết']) assert.ok(t.includes(s), s);
  assert.ok(!t.includes('Nghiệm thu AI Research OS ·'));
  assert.strictEqual([...det.querySelectorAll('table')[1].querySelectorAll('.chip')].map((c) => c.className).join(' '), 'chip ok chip err chip warn');
  assert.ok(det.querySelectorAll('.li .dot.ok').length >= 1);
  assert.ok(det.querySelectorAll('.li .dot.warn').length >= 1);
  await h.clickText('details.adv button', 'Unload tất cả', 20);
  assert.strictEqual(h.server.last('POST', '/api/models/unload').body.engine, 'all');
  await h.clickText('details.adv button', 'Đề xuất ghi nhớ đang chờ', 40);
  assert.strictEqual(h.$('#panel-title').textContent, 'Đề xuất ghi nhớ');
  det.dispatchEvent(new h.w.Event('toggle'));  // loaded once
  det.open = false;
  det.dispatchEvent(new h.w.Event('toggle'));
  await h.idle(20);
  assert.strictEqual(h.server.calledWith('GET', '/api/acceptance').length, 1);
});

test('advanced details when everything is unavailable', async () => {
  const h = await boot({hash: '#/dashboard', routes: {'GET /api/dashboard?advanced=1': () => R({}, 500),
    'GET /api/acceptance': () => R({}, 500), 'GET /api/research': () => R({}, 500),
    'GET /api/dashboard': () => dash({current: {run: RID, title: 'Only a title', progress: '0/2'}})}});
  assert.match(h.$$('.tile')[1].textContent, /Only a title · 0\/2/);
  const det = h.$('details.adv');
  det.open = true;
  det.dispatchEvent(new h.w.Event('toggle'));
  await h.idle(40);
  assert.match(det.textContent, /Không đọc được GPU/);
  assert.match(det.textContent, /Không có mô hình local nào trong VRAM/);
  assert.ok(!det.textContent.includes('Nghiệm thu'));
  assert.ok(!det.textContent.includes('Trạng thái nghiên cứu'));
});

test('memory proposals panel: accept, dismiss, none, unavailable', async () => {
  let cands = [{id: 'CAND-1', payload: {text: 'Remember this'}}, {id: 'CAND-2', payload: {}}, {id: 'CAND-3'}];
  const h = await boot({hash: '#/dashboard', routes: {'GET /api/memory/candidates': () => ({candidates: cands})}});
  h.$$('.page .panelbox .li').find((x) => x.textContent.includes('đề xuất ghi nhớ')).click();
  await h.idle(40);
  assert.strictEqual(h.$$('#panel-body .card').length, 3);
  await h.clickText('#panel-body .card .btn', 'Chấp nhận', 30);
  assert.strictEqual(h.server.calledWith('POST', '/api/memory/candidates/CAND-1/approve').length, 1);
  assert.strictEqual(h.$$('#panel-body .card').length, 2);
  await h.clickText('#panel-body .card .btn', 'Bỏ qua', 30);
  assert.strictEqual(h.server.calledWith('POST', '/api/memory/candidates/CAND-2/reject').length, 1);
  cands = [];
  h.$$('.page .panelbox .li').find((x) => x.textContent.includes('đề xuất ghi nhớ')).click();
  await h.idle(40);
  assert.match(h.$('#panel-body').textContent, /Không có đề xuất nào/);
  h.server.on('GET /api/memory/candidates', () => R({}, 500));
  h.$$('.page .panelbox .li').find((x) => x.textContent.includes('đề xuất ghi nhớ')).click();
  await h.idle(40);
  assert.match(h.$('#panel-body').textContent, /Không có đề xuất nào/);
});

test('dashboard error, leaving the page stops live refreshes, reopening replaces the listeners', async () => {
  let fail = true;
  const h = await boot({hash: '#/dashboard', routes: {'GET /api/dashboard': () => (fail ? R({detail: 'state unreadable'}, 500) : fixtures.get('GET /api/dashboard'))}});
  assert.strictEqual(h.$('.page .err-line').textContent, 'state unreadable');
  fail = false;
  await h.go('#/review', 60);
  await h.go('#/dashboard', 60);
  await h.go('#/', 60);
  const n = h.server.calledWith('GET', '/api/dashboard').length;
  h.w.PL.emit({type: 'run.updated'});
  await h.idle(40);
  assert.ok(h.server.calledWith('GET', '/api/dashboard').length <= n + 1);  // only the pending counter, not the page
  // the chat stream of an open conversation is closed when the dashboard opens
  await h.go('#/chat/' + SID, 60);
  const es = h.ES.all.filter((e) => e.url.includes(`/api/chat/sessions/${SID}/stream`)).at(-1);
  await h.go('#/dashboard', 60);
  assert.ok(es.closed);
  assert.strictEqual(h.w.PL.chat.sid, null);
});
