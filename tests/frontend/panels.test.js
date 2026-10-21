'use strict';
// panels.js: run timeline, project files, proposed files (diff / apply), research outline, library, experiments in VS Code.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const SID = fixtures.meta.session;
const RID = fixtures.meta.runs[0];
const P = (h) => h.w.PL.panels;
const btn = (root, label) => [...root.querySelectorAll('button')].find((b) => b.textContent.includes(label));

test('run panel: steps, provider switch, outputs, acceptance, every timeline event, live repaint', async () => {
  let run = (r) => r;
  let events = (e) => e;
  const h = await boot({routes: {
    ['GET /api/runs/' + RID]: () => run(fixtures.get('GET /api/runs/' + RID)),
    [`GET /api/runs/${RID}/events`]: () => events(fixtures.get(`GET /api/runs/${RID}/events`)),
  }});
  await P(h).run(RID);
  assert.strictEqual(h.$('#panel-title').textContent, '/lit lightweight vision transformers for edge devices');
  const body = h.$('#panel-body');
  assert.strictEqual(body.querySelectorAll('ol.timeline')[0].children.length, 3);
  assert.match(body.textContent, /Feynman \(AI research agent\)/);
  assert.match(body.textContent, /trích dẫn khớp thư viện/);  // a result summary that is not already a note
  assert.ok(body.querySelector('select').disabled);  // a finished step keeps its provider
  assert.match(body.textContent, /Đổi provider S1/);
  // outputs open the file viewer
  h.server.on('GET /api/files', () => '# report');
  [...body.querySelectorAll('.list .li')].at(-1).click();
  await h.idle(30);
  assert.strictEqual(h.$('#panel-title').textContent, 'report.md');
  // a run waiting for approval, with a recovery proposal, acceptance verdicts and every event kind
  const step = (id, status, extra = {}) => ({id, label: 'L' + id, provider: 'python', status, attempt: 1, ...extra});
  run = (r) => ({...r, status: 'APPROVAL_PENDING', synthetic: true, reason: 'cần duyệt', next_decision: '', proposal: {text: 'halve batch'},
    steps: [step('S1', 'pending'), step('S2', 'failed', {attempt: 2, resource: 'gpu', active_s: 3.25, error: 'OOM', notes: ['n1'], result: {summary_line: 'n1'}}),
      step('S3', 'running'), step('S4', 'pending', {result: {summary_line: 'only a summary'}})], outputs: [],
    result: {acceptance: [{priority: 'P0', title: 'A', verdict: 'PASS'}, {priority: 'P1', title: 'B', verdict: 'FAIL'}, {priority: 'P1', title: 'C', verdict: 'PARTIAL'}]}});
  const ts = 1792544926;
  events = () => ({events: [
    {type: 'run.created', ts}, {type: 'run.approved', ts}, {type: 'run.restart', ts}, {type: 'run.resumed', ts}, {type: 'step.lost', ts},
    {type: 'step.reattached', ts}, {type: 'step.provider', ts, data: {step: 'S1', old: 'a', new: 'b'}},
    {type: 'run.state', ts, data: {status: 'RUNNING'}}, {type: 'run.state', ts, data: {status: 'ODD', reason: 'why'}},
    {type: 'step.started', ts, data: {step: 'S1', label: 'x', provider: 'p', attempt: 1}}, {type: 'step.completed', ts, data: {step: 'S1'}},
    {type: 'step.completed', ts, data: {step: 'S2', note: 'ok'}}, {type: 'step.failed', ts, data: {step: 'S2', error: 'boom'}},
    {type: 'step.log', ts, data: {message: 'log line'}}, {type: 'run.analysis', ts, data: {proposal: {text: 'try cpu'}}},
    {type: 'run.analysis', ts, data: {}}, {type: 'custom.event', ts},
    {type: 'run.checkpoint', ts, data: {checkpoint: true, user: 'u said', assistant: 'a said'}}]});
  await P(h).run(RID);
  const b2 = h.$('#panel-body');
  assert.match(b2.textContent, /SYNTHETIC/);
  assert.match(b2.textContent, /Đề xuất phục hồi: halve batch/);
  assert.match(b2.textContent, /failed · lần 2 · gpu · 3\.3 s/);
  assert.match(b2.textContent, /only a summary/);
  assert.strictEqual([...b2.querySelectorAll('table .chip')].map((c) => c.className).join(' '), 'chip ok chip err chip warn');
  for (const t of ['Bạn đã duyệt', 'khôi phục', 'Tiếp tục theo quyết định', 'bị mất', 'Dùng lại kết quả', 'Đổi provider S1: a → b',
    'Đang chạy', 'ODD — why', 'Bắt đầu S1', 'Xong S2 — ok', 'Lỗi S2: boom', 'log line', 'Phân tích lỗi → try cpu', 'custom.event', 'u said', 'a said']) {
    assert.ok(b2.textContent.includes(t), t);
  }
  const sel = b2.querySelector('select');
  assert.ok(!sel.disabled);
  sel.value = 'codex';
  sel.dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', `/api/runs/${RID}/provider`).body)), {step: 'S1', provider: 'codex'});
  btn(h.$('#panel-body'), 'Chấp nhận & chạy').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', `/api/runs/${RID}/approve`).length, 1);
  btn(h.$('#panel-body'), 'Huỷ').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ run', 40);
  assert.strictEqual(h.server.calledWith('POST', `/api/runs/${RID}/cancel`).length, 1);
  run = (r) => ({...r, status: 'NEEDS_USER_ACTION', proposal: null, next_decision: 'pick one'});
  await P(h).run(RID);
  assert.match(h.$('#panel-body').textContent, /pick one/);
  btn(h.$('#panel-body'), 'Tiếp tục').click();
  await h.idle(30);
  assert.strictEqual(h.server.last('POST', `/api/runs/${RID}/resume`).body.accept, true);
  // live: run events of this run repaint the panel; others are ignored; closing stops listening
  const n = () => h.server.calledWith('GET', '/api/runs/' + RID).length;
  const before = n();
  h.w.PL.emit({type: 'run.updated', run_id: 'RR-other'});
  h.w.PL.emit({type: 'run.updated', run_id: RID});
  await h.idle(30);
  assert.ok(n() > before);
  run = () => R({detail: 'x'}, 500);
  events = () => R({detail: 'x'}, 500);
  h.w.PL.emit({type: 'run.updated', run_id: RID});
  await h.idle(30);  // a failing refresh keeps the last state
  assert.match(h.$('#panel-body').textContent, /pick one/);
  P(h).close();
  const after = n();
  h.w.PL.emit({type: 'run.updated', run_id: RID});
  await h.idle(30);
  assert.strictEqual(n(), after);
  // a run that does not exist
  await P(h).run('RR-missing');
  assert.match(h.$('#panel-body').textContent, /no fake/);
});

test('file viewer: PDF, image, Markdown, CSV with a note, JSON, broken JSON, text, errors', async () => {
  const files = {'a.md': '# Title', 'b.csv': '# SYNTHETIC data\nx,y\n1,2\n\n', 'c.json': '{"a":1}', 'd.json': '{bad', 'e.txt': 'plain', 'f.csv': 'h\n1'};
  const h = await boot({routes: {'GET /api/files': (req) => (files[req.query.path] !== undefined ? files[req.query.path] : R('missing file', 404))}});
  await P(h).file('runs/x/paper.pdf');
  assert.ok(h.$('#panel-body iframe').src.includes('paper.pdf'));
  assert.ok(h.$('#panel-actions a').href.includes('download=1'));
  await P(h).file('fig.PNG');
  assert.ok(h.$('#panel-body img'));
  await P(h).file('a.md');
  assert.strictEqual(h.$('#panel-body h1').textContent, 'Title');
  await P(h).file('b.csv');
  assert.match(h.$('#panel-body .chip').textContent, /SYNTHETIC data/);
  assert.strictEqual(h.$$('#panel-body th').length, 2);
  await P(h).file('f.csv');
  assert.strictEqual(h.$('#panel-body .chip'), null);
  await P(h).file('c.json');
  assert.match(h.$('#panel-body pre').textContent, /"a": 1/);
  await P(h).file('d.json');
  assert.strictEqual(h.$('#panel-body pre').textContent, '{bad');
  await P(h).file('e.txt');
  assert.strictEqual(h.$('#panel-body pre').textContent, 'plain');
  await P(h).file('noext');
  await P(h).file('trailing.');
  assert.match(h.$('#panel-body').textContent, /missing file/);
  h.w.fetch = async () => { throw new Error('offline'); };
  await P(h).file('e.txt');
  assert.match(h.$('#panel-body').textContent, /offline/);
});

test('proposed file: diff, reject, apply (ok / refused), read-only when decided, diff error', async () => {
  let apply = {applied: true};
  const h = await boot({hash: '#/chat/' + SID, routes: {
    'GET /api/chat/sessions/:id/artifacts/:a/diff': (req) => (req.params[1] === 'af-bad' ? R({detail: 'no diff'}, 404) : {exists: req.params[1] === 'af-1', diff: '+line', target_sha256: 'sha'}),
    'POST /api/chat/sessions/:id/artifacts/:a/apply': () => apply,
  }});
  await P(h).artifact(SID, {id: 'af-1', path: 'src/a.py', status: 'collected'});
  assert.match(h.$('#panel-body').textContent, /So sánh với file hiện có/);
  btn(h.$('#panel-body'), 'Bỏ qua').click();
  await h.idle(30);
  assert.strictEqual(h.$('#panel').hidden, true);
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/artifacts/af-1/reject`).length, 1);
  await P(h).artifact(SID, {id: 'af-2', path: 'new.py', status: 'collected'}, true);
  assert.match(h.$('#panel-body').textContent, /File mới/);
  apply = R({detail: 'changed on disk'}, 409);
  btn(h.$('#panel-body'), 'Chấp nhận & áp dụng').click();
  await h.idle(30);
  assert.strictEqual(h.$('#panel').hidden, false);
  assert.match(h.toast(), /changed on disk/);
  apply = {applied: true};
  btn(h.$('#panel-body'), 'Chấp nhận & áp dụng').click();
  await h.idle(30);
  assert.strictEqual(h.$('#panel').hidden, true);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', `/api/chat/sessions/${SID}/artifacts/af-2/apply`).body)), {target: 'new.py', expected_sha: 'sha'});
  await P(h).artifact(SID, {id: 'af-3', path: 'done.py', status: 'applied'});
  assert.strictEqual(btn(h.$('#panel-body'), 'Bỏ qua'), undefined);
  await P(h).artifact(SID, {id: 'af-bad', path: 'x.py', status: 'collected'});
  assert.match(h.$('#panel-body .err-line').textContent, /no diff/);
});

test('outline starter: levels, required text, save → AI proposes the next level, attach a proposal file', async () => {
  let put = {};
  const h = await boot({routes: {
    'GET /api/outline': () => ({level: 0, level_label: '', keywords: [], attachments: []}),
    'PUT /api/outline': () => put, 'POST /api/outline/attach': () => ({name: 'proposal.docx'}),
  }});
  const card = h.$('.outline-card');
  const levels = card.querySelectorAll('.level');
  assert.strictEqual(levels.length, 5);
  levels[4].click();
  assert.strictEqual(card.querySelector('textarea').rows, 8);
  assert.ok(card.querySelectorAll('.level')[4].classList.contains('on'));
  card.querySelectorAll('.level')[1].click();
  assert.strictEqual(card.querySelector('textarea').rows, 3);
  btn(card, 'Lưu & để AI').click();
  await h.idle();
  assert.strictEqual(h.server.calledWith('PUT', '/api/outline').length, 0);
  card.querySelector('textarea').value = 'ViT on edge';
  put = R({detail: 'bad'}, 400);
  btn(card, 'Lưu & để AI').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/chat/sessions').length, 0);
  put = {level: 2};
  h.server.on('POST /api/chat/sessions', () => ({id: SID}));
  btn(card, 'Lưu & để AI').click();
  await h.idle(60);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('PUT', '/api/outline').body)), {topic: 'ViT on edge'});
  assert.match(h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body.text, /^\/outline Mình đã có chủ đề/);
  // attach a proposal file (none chosen → nothing)
  await h.go('#/', 40);
  btn(h.$('.outline-card'), 'Đính kèm đề cương').click();
  const fi = h.$('.outline-card input[type=file]');
  await h.setFiles(fi, []);
  await h.setFiles(fi, ['proposal.docx']);
  await h.idle(60);
  assert.match(h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body.text, /đính kèm đề cương "proposal.docx"/);
});

test('outline panel: fields, save, AI proposes, attachments, restore versions, load error', async () => {
  const o = {...fixtures.get('GET /api/outline'), attachments: [{id: 'oa1', name: 'p.pdf', kind: 'pdf', chars: 1200}],
    versions: [{ts: 1, by: 'researcher', reason: 'first'}, {ts: 2, by: 'ai', reason: ''}]};
  let fail = false;
  const h = await boot({routes: {'GET /api/outline': () => (fail ? R({detail: 'outline broken'}, 500) : o),
    'POST /api/outline/attach': () => ({name: 'more.md'}), 'POST /api/chat/sessions': () => ({id: SID})}});
  await P(h).outline();
  const body = h.$('#panel-body');
  assert.match(body.textContent, /Cấp 3\/5/);
  assert.strictEqual(body.querySelector('input.input').value, 'lightweight ViT, edge devices, token pruning, distillation');
  body.querySelectorAll('textarea')[2].value = 'Method text';
  btn(body, 'Lưu').click();
  await h.idle(40);
  assert.strictEqual(h.server.last('PUT', '/api/outline').body.method, 'Method text');
  btn(h.$('#panel-body'), 'Khôi phục').click();
  await h.idle(40);
  assert.strictEqual(h.server.last('POST', '/api/outline/restore').body.index, 1);
  assert.match(h.$('#panel-body .list:last-child .li .t').textContent, /^ai$/);  // a version without a reason shows who made it
  h.$('#panel-body .li button.icon').click();
  await h.idle(40);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/outline/attach/oa1').length, 1);
  await h.setFiles(h.$('#panel-body input[type=file]'), ['more.md']);
  await h.idle(60);
  assert.match(h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body.text, /more\.md/);
  btn(h.$('#panel-body'), 'Đính kèm file').click();
  btn(h.$('#panel-body'), 'AI đề xuất cấp tiếp').click();
  await h.idle(60);
  assert.match(h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body.text, /Hãy đề xuất cấp tiếp theo/);
  h.server.on('PUT /api/outline', () => R({detail: 'no'}, 400));
  btn(h.$('#panel-body'), 'Lưu').click();
  await h.idle(30);
  o.level_label = '';
  delete o.versions;
  o.keywords = undefined;
  delete o.attachments;
  await P(h).outline();
  assert.match(h.$('#panel-body').textContent, /chưa có/);
  fail = true;
  await P(h).outline();
  assert.strictEqual(h.$('#panel-body').textContent, 'outline broken');
});

test('library: list, include toggle, open, delete (cancel / confirm), upload by click and drop, error', async () => {
  const refs = [{file: 'smith2024.pdf', key: 'smith2024', title: 'Token pruning', authors: ['A', 'B', 'C', 'D'], year: '2024', venue: 'CVPR', include: true},
    {file: 'x.pdf', key: 'x2020', include: false}];
  let fail = false;
  const h = await boot({routes: {'GET /api/library': () => (fail ? R({detail: 'library offline'}, 500) : {references: refs})}});
  await P(h).library();
  const body = h.$('#panel-body');
  assert.match(body.textContent, /2 tài liệu/);
  assert.match(body.textContent, /A, B, C · 2024 · CVPR/);
  assert.match(body.textContent, /x2020/);
  const boxes = body.querySelectorAll('input[type=checkbox]');
  assert.ok(boxes[0].checked && !boxes[1].checked);
  boxes[1].checked = true;
  boxes[1].dispatchEvent(new h.w.Event('change'));
  await h.idle(20);
  assert.strictEqual(h.server.last('PUT', '/api/library/x.pdf').body.include, true);
  body.querySelector('.li .m').click();
  assert.ok(h.$('#panel-body iframe').src.includes('/api/library/file/smith2024.pdf'));
  await P(h).library();
  h.$('#panel-body .li button.icon').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ', 20);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/library/').length, 0);
  h.$('#panel-body .li button.icon').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Xoá', 40);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/library/smith2024.pdf').length, 1);
  const drop = h.$('#panel-body .drop');
  drop.click();
  await h.drop('#panel-body .drop', ['a.pdf'], 'dragover');
  assert.ok(h.$('#panel-body .drop').classList.contains('over'));
  h.$('#panel-body .drop').dispatchEvent(new h.w.Event('dragleave'));
  assert.ok(!h.$('#panel-body .drop').classList.contains('over'));
  await h.drop('#panel-body .drop', ['a.pdf', 'b.pdf']);
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/library/upload').length, 1);
  await h.setFiles(h.$('#panel-body input[type=file]'), ['c.pdf']);
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/library/upload').length, 2);
  h.server.on('POST /api/library/upload', () => R({detail: 'not a pdf'}, 400));
  await h.setFiles(h.$('#panel-body input[type=file]'), ['c.txt']);
  await h.idle(30);
  assert.match(h.toast(), /not a pdf/);
  fail = true;
  await P(h).library();
  assert.match(h.$('#panel-body').textContent, /0 tài liệu/);
});

test('experiments: code projects, open in VS Code, new project, sync back, jobs with metrics, stop', async () => {
  let jobs = [{id: 'j1', cmd: 'python a.py', status: 'running', mode: 'local', metrics: {}}, {id: 'j2', status: 'failed'},
    {id: 'j3', cmd: 'x', status: 'done', mode: 'docker', metrics: {acc: 0.9, loss: 0.1, f1: 0.8, extra: 1}}, {id: 'j4', cmd: 'q', status: 'queued'}];
  let projects = [{name: 'main', active: true}, {name: 'exp2', active: false}];
  let sync = {proposals: 2};
  const h = await boot({hash: '#/chat/' + SID, routes: {
    'GET /api/code': () => ({projects}), 'GET /api/jobs': () => ({jobs}), 'POST /api/code/sync': () => sync,
    'POST /api/chat/sessions': () => ({id: 'as-0000000077'}),
  }});
  await P(h).code();
  const body = h.$('#panel-body');
  assert.deepStrictEqual([...body.querySelectorAll('.li .dot')].map((d) => d.className), ['dot warn', 'dot err', 'dot ok', 'dot']);
  assert.match(body.textContent, /acc=0\.9, loss=0\.1, f1=0\.8/);
  assert.match(body.textContent, /không có metrics/);
  btn(body, 'Dừng').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/jobs/j1/stop').length, 1);
  btn(h.$('#panel-body'), 'Mở trong VS Code').click();
  await h.idle(20);
  assert.strictEqual(h.toast(), 'Đã mở VS Code');
  const sel = h.$('#panel-body select');
  sel.value = 'exp2';
  sel.dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.strictEqual(h.server.last('POST', '/api/code/open').body.name, 'exp2');
  // a new code project (cancel, then a name)
  h.$('#panel-body select').value = '__new';
  h.$('#panel-body select').dispatchEvent(new h.w.Event('change'));
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ', 30);
  assert.strictEqual(h.server.calledWith('POST', '/api/code').filter((c) => c.path === '/api/code').length, 0);
  h.$('#panel-body select').value = '__new';
  h.$('#panel-body select').dispatchEvent(new h.w.Event('change'));
  await h.idle();
  await h.clickText('.dialog-f button', 'Lưu', 30);
  assert.strictEqual(h.server.calls.filter((c) => c.method === 'POST' && c.path === '/api/code').at(-1).body.name, 'exp1');
  // sync back into the open conversation
  btn(h.$('#panel-body'), 'Đồng bộ kết quả về').click();
  await h.idle(40);
  assert.strictEqual(h.server.last('POST', '/api/code/sync').body.session_id, SID);
  assert.match(h.toast(), /2 đề xuất/);
  sync = {proposals: 0};
  await P(h).code();
  btn(h.$('#panel-body'), 'Đồng bộ kết quả về').click();
  await h.idle(40);
  assert.strictEqual(h.toast(), 'Không có gì mới');
  sync = R({detail: 'no code project'}, 409);
  await P(h).code();
  btn(h.$('#panel-body'), 'Đồng bộ kết quả về').click();
  await h.idle(40);
  // from the home screen a conversation is created first (and creation may fail)
  sync = {proposals: 1};
  await h.go('#/', 40);
  await P(h).code();
  btn(h.$('#panel-body'), 'Đồng bộ kết quả về').click();
  await h.idle(60);
  assert.strictEqual(h.server.last('POST', '/api/code/sync').body.session_id, 'as-0000000077');
  await h.go('#/', 40);
  h.server.on('POST /api/chat/sessions', () => R({detail: 'x'}, 500));
  await P(h).code();
  const n = h.server.calledWith('POST', '/api/code/sync').length;
  btn(h.$('#panel-body'), 'Đồng bộ kết quả về').click();
  await h.idle(40);
  assert.strictEqual(h.server.calledWith('POST', '/api/code/sync').length, n);
  // no code project yet, no jobs; backend errors
  projects = [];
  jobs = [];
  await P(h).code();
  assert.strictEqual(h.$('#panel-body select').value, '');
  assert.ok(btn(h.$('#panel-body'), 'Mở trong VS Code').disabled);
  assert.match(h.$('#panel-body').textContent, /Chưa có lần chạy nào/);
  h.server.on('GET /api/code', () => R({}, 500));
  h.server.on('GET /api/jobs', () => R({}, 500));
  h.server.on('POST /api/code', () => R({detail: 'bad name'}, 400));
  await P(h).code();
  h.$('#panel-body select').value = '__new';
  h.$('#panel-body select').dispatchEvent(new h.w.Event('change'));
  await h.idle();
  await h.clickText('.dialog-f button', 'Lưu', 30);
  assert.match(h.toast(), /bad name/);
  h.server.on('GET /api/code', () => ({}));
  await P(h).code();
  assert.strictEqual(h.$('#panel-body select').value, '');
});

test('Lit discovery: multi-source search, provider errors, verified journal data and one-click save', async () => {
  const source = {id: 'p1', kind: 'paper', source: 'IEEE', title: '<img onerror=alert(1)> A paper', authors: ['A'], year: 2025,
    venue: 'Journal', url: 'https://ieeexplore.ieee.org/document/1', pdf_url: 'https://example.org/p.pdf', doi: '10.1/p', citations: 0,
    journal_ranking: {source: 'OpenAlex', source_url: 'https://openalex.org/S1', h_index: 50, two_year_mean_citedness: 3.2, note: 'Not an SJR quartile'}};
  const h = await boot({routes: {'POST /api/search': () => ({sources: [source], errors: {arxiv: 'timeout'}}),
    'POST /api/library/save': () => ({entry: {file: 'p.pdf'}, pdf_saved: true})}});
  await P(h).library();
  await h.clickText('#panel-body button', 'Tìm paper & web');
  await h.input('#panel-body input[type=search]', 'token pruning');
  await h.input('#panel-body input[type=number]', '2023');
  await h.click('#panel-body button[type=submit]');
  const req = h.server.last('POST', '/api/search');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(req.body)), {query: 'token pruning', mode: 'both', year_from: 2023});
  assert.match(h.$('.lit-results').textContent, /arxiv: timeout/);
  assert.match(h.$('.paper').textContent, /h-index 50/);
  assert.match(h.$('.paper').textContent, /Trích dẫn TB 2 năm 3\.20/);
  assert.match(h.$('.paper').textContent, /0 trích dẫn/);
  assert.strictEqual(h.$('.paper img'), null); // provider text is displayed as text
  assert.ok(h.$$('#panel-body a').some((a) => a.href.startsWith('https://scholar.google.com/')));
  await h.clickText('.paper button', 'Lưu vào thư viện');
  assert.strictEqual(h.server.last('POST', '/api/library/save').body.source.doi, '10.1/p');
  assert.ok(h.$('.paper button').disabled);
  assert.match(h.$('.paper').textContent, /Đã lưu cả PDF/);
  assert.deepStrictEqual(h.errors, []);
});

test('Lit handles empty results, search faults, unsafe URLs and save retry without inventing quartiles', async () => {
  const h = await boot({routes: {'POST /api/search': () => ({sources: [], errors: ['IEEE unavailable']})}});
  await P(h).literature('a query');
  await h.idle(20);
  assert.match(h.$('.lit-results').textContent, /Chưa tìm thấy/);
  assert.match(h.$('.lit-results').textContent, /IEEE unavailable/);
  h.server.on('POST /api/search', () => R({detail: 'search offline'}, 503));
  await h.click('#panel-body button[type=submit]');
  assert.match(h.$('.lit-results').textContent, /search offline/);
  assert.ok(!h.$('#panel-body button[type=submit]').disabled);
  const article = P(h).paperCard({title: 'Closed paper', url: 'javascript:alert(1)', pdf_url: 'file:///secret'});
  h.$('#panel-body').append(article);
  assert.strictEqual(article.querySelector('a'), null);
  assert.match(article.textContent, /Chưa có dữ liệu xếp hạng xác thực/);
  assert.ok(!article.textContent.includes('Q1'));
  h.server.on('POST /api/library/save', () => R({detail: 'disk full'}, 500));
  article.querySelector('button').click();
  await h.idle(20);
  assert.match(article.textContent, /disk full/);
  assert.ok(!article.querySelector('button').disabled);
  h.server.on('POST /api/library/save', () => ({already_saved: true, pdf_saved: false, warning: 'Publisher has no open PDF'}));
  article.querySelector('button').click();
  await h.idle(20);
  assert.match(article.textContent, /Đã có trong thư viện/);
  assert.match(article.textContent, /Publisher has no open PDF/);
  const upgrade = P(h).paperCard({title: 'Closed paper', url: 'https://example.org/paper'});
  h.$('#panel-body').append(upgrade);
  h.server.on('POST /api/library/save', () => ({already_saved: true, pdf_saved: true, upgraded: true}));
  upgrade.querySelector('button').click();
  await h.idle(20);
  assert.match(upgrade.textContent, /Đã bổ sung PDF vào thư viện/);
  assert.match(upgrade.textContent, /Đã lưu cả PDF/);
});

test('metadata-only library records open details and research runs retain saveable sources', async () => {
  const source = {id: 's', title: 'Closed paper', url: 'https://doi.org/10.1/x', journal_ranking: {quartile: 'Q2', sjr: 1.4, year: 2024, source: 'Verified dataset', categories: 'Computer Science (Q2); Signal Processing (Q3)'}};
  const h = await boot({routes: {'GET /api/library': () => ({references: [{...source, file: 'p.paper.json', source_url: source.url, pdf_available: false}]}),
    ['GET /api/runs/' + RID]: () => ({...fixtures.get('GET /api/runs/' + RID), result: {sources: [source]},
      steps: [{id: 's', provider: 'app', label: 'Research', status: 'done', result: {sources: [source, null]}}]})}});
  await P(h).library();
  assert.match(h.$('#panel-body').textContent, /Thông tin bài báo/);
  h.$('#panel-body .li .m').click();
  assert.strictEqual(h.$('#panel-body iframe'), null);
  assert.match(h.$('#panel-body').textContent, /Best quartile Q2 · SJR 1.4 \(2024\)/);
  assert.match(h.$('#panel-body').textContent, /Nhóm ngành: Computer Science \(Q2\); Signal Processing \(Q3\)/);
  assert.strictEqual(h.$('#panel-body a').href, source.url);
  await P(h).run(RID);
  assert.strictEqual(h.$$('#panel-body .paper').length, 1);
  assert.strictEqual(h.$('#panel-body .paper button').textContent, 'Lưu vào thư viện');
});

test('Lit source availability and validation: sparse responses, direct search links and source provenance', async () => {
  const h = await boot({routes: {'POST /api/search': () => ({sources: null, errors: [{provider: 'IEEE', error: 'key missing'}],
    provider_status: {google_scholar: 'requires_serpapi_key'}, search_links: {ieee: 'https://ieeexplore.ieee.org/search?q=x', google_scholar: 'https://scholar.google.com/scholar?q=x'}})}});
  await P(h).literature();
  const form = h.$('#panel-body form');
  form.dispatchEvent(new h.w.Event('submit', {cancelable: true}));
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', '/api/search').length, 0);
  await h.input('#panel-body input[type=search]', 'a query');
  await h.input('#panel-body input[type=number]', '1000');
  form.dispatchEvent(new h.w.Event('submit', {cancelable: true}));
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', '/api/search').length, 0);
  await h.input('#panel-body input[type=number]', '');
  await h.click('#panel-body button[type=submit]');
  assert.match(h.$('.lit-results').textContent, /Google Scholar chưa được truy vấn/);
  assert.ok(h.$$('#panel-body a').some((a) => a.href === 'https://scholar.google.com/scholar?q=x'));
  assert.match(h.$('.lit-results').textContent, /key missing/);
  h.server.on('POST /api/search', () => ({}));
  await h.click('#panel-body button[type=submit]');
  assert.match(h.$('.lit-results').textContent, /0 kết quả/);
  await h.clickText('#panel-body button', 'Cấu hình nguồn tìm kiếm');
  assert.ok(h.$('.settings'));
  h.$('#modal').click();
  await h.clickText('#panel-actions button', 'Thư viện');
  assert.strictEqual(h.$('#panel-title').textContent, 'Tài liệu');
  assert.strictEqual(P(h).runSources({}).length, 0);
  assert.strictEqual(P(h).runSources({steps: [{}, {result: {sources: [{id: 'only-id'}, {}, 'bad', null]}}]}).length, 1);
  const card = P(h).paperCard({kind: 'web', url: 'https://example.org', snippet: 'A source snippet',
    journal_ranking: {source: 'SCImago', quartile: 'Q1', source_url: 'https://scimagojr.com/', lookup_url: 'https://scimagojr.com/journalrank.php',
      openalex_metrics: {source: 'OpenAlex', source_url: 'https://openalex.org/S1'}}});
  assert.strictEqual(card.querySelector('.kind').textContent, 'Web');
  assert.match(card.textContent, /A source snippet/);
  assert.match(card.textContent, /h-index \/ trích dẫn: OpenAlex/);
  assert.match(card.textContent, /Tra SJR \/ quartile/);
  assert.ok(P(h).paperCard({}).textContent.includes('Nguồn tài liệu'));
  P(h).reference({file: 'plain.pdf'});
  assert.ok(h.$('#panel-body iframe'));
  P(h).reference({file: 'record.paper.json', abstract: 'An abstract', url: 'https://example.org'});
  assert.match(h.$('#panel-body').textContent, /An abstract/);
  P(h).reference({snippet: 'A snippet', url: 'https://example.org'});
  assert.match(h.$('#panel-body').textContent, /A snippet/);
});
