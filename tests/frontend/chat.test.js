'use strict';
// chat.js: conversation list, messages, proposals (Accept / Reject), run cards, live events, composer, "/" skills,
// attachments, the model + reasoning picker, send / stop / retry, remember / pin.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const SID = fixtures.meta.session;
const RID = fixtures.meta.runs[0];
const now = () => Date.now() / 1000;

/** a page on the recorded conversation; `mut(session)` edits the conversation each time it is fetched */
async function chat(opt = {}) {
  const st = {mut: opt.mut || null, run: opt.run || null};
  const routes = {
    'GET /api/chat/sessions/:id': (req) => {
      if (req.params[0] !== SID && !opt.anyId) return R({detail: 'Session not found'}, 404);
      const s = fixtures.get('GET /api/chat/sessions/:id');
      if (st.mut) st.mut(s);
      return s;
    },
    ...(st.run ? {['GET /api/runs/' + RID]: () => st.run(fixtures.get('GET /api/runs/' + RID))} : {}),
    ...(opt.routes || {}),
  };
  const h = await boot({...opt, routes, hash: opt.hash === undefined ? '#/chat/' + SID : opt.hash});
  h.st = st;
  await h.idle(30);
  return h;
}
const card = (h, apId) => h.$(`.card[data-ap="${apId}"]`);
const sse = (h) => h.ES.all.filter((e) => e.url.includes('/stream') && !e.url.startsWith('/api/events')).at(-1);

test('research run in chat exposes source cards that save to the library without leaving the conversation', async () => {
  const source = {id: 'paper-1', title: 'Real paper', source: 'arxiv', url: 'https://arxiv.org/abs/1'};
  const h = await chat({run: (r) => ({...r, steps: r.steps.map((s, i) => i ? s : {...s, result: {sources: [source]}})}),
    routes: {'POST /api/library/save': () => ({pdf_saved: false})}});
  await h.until(() => h.$('.card.run details'));
  assert.match(h.$('.card.run details summary').textContent, /1 nguồn tìm được/);
  const det = h.$('.card.run details');  // source cards are built when the list is opened
  det.open = true;
  det.dispatchEvent(new h.w.Event('toggle'));
  det.dispatchEvent(new h.w.Event('toggle'));
  await h.until(() => h.$('.card.run .paper'));
  assert.strictEqual(h.$$('.card.run .paper').length, 1);
  h.$('.card.run .paper button').click();
  await h.idle(20);
  assert.strictEqual(h.server.last('POST', '/api/library/save').body.source.id, 'paper-1');
  assert.match(h.$('.card.run .paper').textContent, /Đã lưu thông tin bài báo/);
  assert.strictEqual(h.w.PL.chat.sid, SID);
});

test('conversation list: groups by age, badges, running spinner, keyboard, empty state', async () => {
  const day = 86400;
  const list = [
    {id: SID, title: 'Today', updated: now(), pending_approvals: 2, status: 'running'},
    {id: 'as-0000000002', title: 'This week', updated: now() - 3 * day},
    {id: 'as-0000000003', title: '', updated: now() - 30 * day},
  ];
  let sessions = list;
  const h = await chat({anyId: true, routes: {'GET /api/chat/sessions': () => ({sessions})}});
  assert.deepStrictEqual(h.$$('#threads .tgroup').map((x) => x.textContent), ['Hôm nay', '7 ngày qua', new Intl.DateTimeFormat('vi-VN', {month:'long',year:'numeric'}).format(new Date((Date.now()/1000 - 30*86400)*1000))]);
  assert.strictEqual(h.$('#threads .badge').textContent, '2');
  assert.ok(h.$('#threads .thread.active .spin'));
  assert.strictEqual(h.$$('#threads .thread .t')[2].textContent, 'Cuộc trò chuyện');
  h.$$('#threads .thread')[1].dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'Enter'}));
  await h.idle();
  assert.strictEqual(h.w.location.hash, '#/chat/as-0000000002');
  h.$$('#threads .thread')[1].dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'a'}));
  h.$$('#threads .thread')[0].click();
  await h.idle();
  assert.strictEqual(h.w.location.hash, '#/chat/' + SID);
  sessions = [];
  await h.w.PL.chat.loadList();
  assert.strictEqual(h.$('#threads').textContent, 'Chưa có cuộc trò chuyện');
  h.$('#threads').remove();
  await h.w.PL.chat.loadList();
  h.$('#search').remove();
  await h.w.PL.chat.loadList();
});

test('thread menu: rename, archive, delete (cancel / confirm), on the open and on another conversation', async () => {
  const other = {id: 'as-0000000009', title: 'Other', updated: now()};
  const h = await chat({routes: {'GET /api/chat/sessions': () => ({sessions: [{id: SID, title: 'Open', updated: now()}, other]})}});
  const more = (i) => h.$$('#threads .thread .more')[i];
  const pick = async (i, label) => { more(i).click(); await h.idle(); await h.clickText('.menu.pop .mi', label); };
  await pick(0, 'Đổi tên');
  await h.clickText('.dialog-f button', 'Huỷ', 20);
  assert.strictEqual(h.server.calledWith('PUT', '/api/chat/sessions/').length, 0);
  await pick(0, 'Đổi tên');
  h.$('#modal input').value = 'Renamed';
  await h.clickText('.dialog-f button', 'Lưu', 30);
  assert.strictEqual(h.server.last('PUT', '/api/chat/sessions/' + SID).body.title, 'Renamed');
  await pick(1, 'Lưu trữ');
  await h.idle(20);
  assert.strictEqual(h.server.last('PUT', '/api/chat/sessions/as-0000000009').body.archived, true);
  assert.strictEqual(h.w.location.hash, '#/chat/' + SID);
  await pick(0, 'Lưu trữ');
  await h.idle(30);
  assert.strictEqual(h.w.location.hash, '#/');
  await h.go('#/chat/' + SID, 40);
  await pick(1, 'Xoá');
  await h.clickText('.dialog-f button', 'Huỷ', 20);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/chat/sessions/').length, 0);
  await pick(1, 'Xoá');
  await h.clickText('.dialog-f button', 'Xoá', 30);
  assert.deepStrictEqual(h.server.last('DELETE', '/api/chat/sessions/').query, {confirm: 'as-0000000009'});
  await pick(0, 'Xoá');
  await h.clickText('.dialog-f button', 'Xoá', 40);
  assert.strictEqual(h.w.location.hash, '#/');
});

test('PL.menu: headers, hints, tags, disabled and danger items, above the anchor, outside click', async () => {
  const h = await chat({hash: ''});
  let ran = 0;
  const anchor = h.$('#proj-btn');
  const m = h.w.PL.menu(anchor, [{header: 'H'}, {label: 'A', hint: 'hint', tag: 'tag', run: () => ran++}, {label: 'B', disabled: true},
    {label: 'C', danger: true}], {above: true});
  assert.strictEqual(m.querySelector('.mh').textContent, 'H');
  assert.ok(m.querySelector('.tag'));
  assert.ok(m.querySelectorAll('.mi')[1].disabled);
  m.querySelectorAll('.mi')[2].click();  // an item without run()
  assert.strictEqual(h.$('.menu.pop'), null);
  const m2 = h.w.PL.menu(anchor, [{label: 'A', run: () => ran++}]);
  await h.idle();
  m2.dispatchEvent(new h.w.MouseEvent('mousedown', {bubbles: true}));  // inside: stays
  assert.ok(m2.isConnected);
  m2.querySelector('.mi').click();
  assert.strictEqual(ran, 1);
});

test('home screen: outline starter for an empty project, current run, pending work, no project name', async () => {
  const h = await chat({hash: '', routes: {
    'GET /api/outline': () => ({level: 0, level_label: '', keywords: [], attachments: []}),
    'GET /api/dashboard': () => ({...fixtures.get('GET /api/dashboard'), current: {title: 'Run X', run: RID}}),
  }});
  assert.strictEqual(h.$('.hello h1').textContent, 'Bắt đầu một nghiên cứu');
  assert.ok(h.$('.outline-card'));
  assert.match(h.$('.state-line').textContent, /Run X/);
  await h.clickText('.state-line button', 'việc chờ');
  await h.idle(30);
  assert.strictEqual(h.w.location.hash, '#/dashboard');
  const h2 = await chat({hash: '', routes: {
    'GET /api/outline': () => R({detail: 'x'}, 500), 'GET /api/dashboard': () => ({...fixtures.get('GET /api/dashboard'), pending: []}),
    'GET /api/config': () => ({...fixtures.get('GET /api/config'), project: {name: '', data_dir: 'x'}}),
  }});
  assert.strictEqual(h2.$('.state-line'), null);
  assert.strictEqual(h2.$('.hello p').textContent, '');
  const h3 = await chat({hash: '', routes: {'GET /api/dashboard': () => R({detail: 'x'}, 500), 'GET /api/outline': () => ({level: 2, level_label: 'L', attachments: [{}]})}});
  assert.strictEqual(h3.$('.outline-card'), null);
  await h3.clickText('.starter', '/gap');
  assert.strictEqual(h3.$('#input').value, '/gap ');
});

test('opening a conversation: messages, proposals, memory card, run card; missing conversation', async () => {
  const h = await chat();
  assert.strictEqual(h.$('#title').textContent, 'Khoảng trống nghiên cứu ViT gọn nhẹ');
  assert.strictEqual(h.$$('.msg.user').length, 3);
  assert.match(h.$('.msg.ai .who').textContent, /Research agent|Smart router/);
  assert.match(h.$('.activity').textContent, /Đã dùng công cụ research_search_memory \(tự động, chỉ đọc\)/);
  assert.ok(card(h, 'ap-15b0cb8e').classList.contains('pending'));
  assert.match(card(h, 'ap-32450735').textContent, /\/idea/);
  assert.ok(h.$$('.card.pending').some((c) => /Đề xuất ghi nhớ.*Câu hỏi mở/.test(c.textContent)));
  await h.until(() => h.$('.card.run .steps'));
  assert.match(h.$('.card.run').textContent, /3 bước/);
  // a run output opens in the side panel
  h.server.on('GET /api/files', () => '# Report');
  h.$$('.card.run button.chip').find((b) => b.textContent === 'report.md').click();
  await h.idle(40);
  assert.strictEqual(h.$('#panel-title').textContent, 'report.md');
  await h.clickText('.card.run .btn', 'Chi tiết', 40);
  assert.strictEqual(h.$('#panel-title').textContent, '/lit lightweight vision transformers for edge devices');
  // a conversation that does not exist
  await h.go('#/chat/as-ffffffffff', 40);
  assert.strictEqual(h.w.location.hash, '#/');
  assert.match(h.toast(), /not found/);
});

test('message variants: cancelled, partial, other providers + model, unknown provider, actions', async () => {
  const h = await chat({mut: (s) => {
    s.messages[1].content = '';
    s.messages[1].status = 'cancelled';
    s.messages[6].provider = 'cli:codex';
    s.messages[6].model = 'gpt-5';
    s.messages[6].status = 'partial';
    s.messages.push({id: 'm-x1', role: 'assistant', content: 'odd', provider: 'web:x', ts: s.messages[6].ts + 1, turn_id: 't-x'});
    s.messages.push({id: 'm-x2', role: 'assistant', content: 'none', provider: '', ts: s.messages[6].ts + 2, turn_id: 't-y'});
  }});
  await h.w.PL.chat.loadModels();
  await h.w.PL.chat.refresh();
  const ai = h.$$('.msg.ai');
  assert.match(ai[0].textContent, /đã dừng/);
  const codex = ai.find((m) => m.textContent.includes('gpt-5'));
  assert.match(codex.textContent, /Codex/);
  assert.match(codex.textContent, /chưa đầy đủ/);
  assert.ok(ai.some((m) => m.querySelector('.who').textContent.includes('web:x')));
  assert.ok(ai.at(-1).querySelector('.who').textContent.includes('Tác nhân nghiên cứu'));
  // copy / retry / remember / pin
  const acts = (m) => [...m.querySelectorAll('.msg-actions button')];
  acts(ai[0])[0].click();
  await h.idle();
  assert.strictEqual(h.w.__clip, '');
  acts(ai[0])[1].click();
  await h.idle(20);
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/retry`).length, 1);
  assert.strictEqual(acts(ai.at(-1)).length, 7);  // copy, retry, note, export, remember, pin
  acts(h.$$('.msg.ai')[1]).find((b) => b.title.includes('Ghi nhớ')).click();
  await h.idle();
  h.$('#modal select').value = 'finding';
  await h.clickText('.dialog-f button', 'Lưu', 30);
  const mem = h.server.last('POST', `/api/chat/sessions/${SID}/memory`).body;
  assert.strictEqual(mem.type, 'finding');
  assert.strictEqual(mem.save, true);
  acts(h.$$('.msg.ai')[1]).find((b) => b.title.includes('Ghim vào kết quả')).click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ', 20);
  assert.strictEqual(h.server.calledWith('POST', '/api/pins').length, 0);
  acts(h.$$('.msg.ai')[1]).find((b) => b.title.includes('Ghim vào kết quả')).click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Lưu', 30);
  const pin = h.server.last('POST', '/api/pins').body;
  assert.strictEqual(pin.provenance.session_id, SID);
  // the phdlab assistant has no "retry"
  const phd = h.$$('.msg.ai').find((m) => m.querySelector('.who').textContent.startsWith('PhD Lab'));
  assert.strictEqual(acts(phd).length, 6);
});

test('proposal bodies for every action kind, results, verdict chips', async () => {
  const base = (id, name, args, extra = {}) => ({id, turn_id: 't-z', kind: 'action', name, args, status: 'pending', created: 1, ...extra});
  const h = await chat({mut: (s) => {
    s.approvals = [
      {...s.approvals[0], decided_by: 'researcher'},
      {...s.approvals[0], id: 'ap-f', status: 'failed', decided_by: ''},
      {...s.approvals[0], id: 'ap-t', status: 'pending'},
      base('ap-ws', 'write_section', {section: 'Intro', text: 'Hello'}),
      base('ap-wsn', 'write_section', {section: 'Empty'}),
      base('ap-uo', 'update_outline', {keywords: 'a, b', topic: '', proposal: 'P', extra_key: 'E'}),
      base('ap-cc', 'commit_code', {message: 'msg', files: ['a.py']}),
      base('ap-cc2', 'commit_code', {message: 'msg2'}),
      base('ap-hy', 'create_hypothesis', {title: 'T only'}),
      base('ap-nt', 'add_note', {body: 'note body'}),
      base('ap-js', 'odd_action', {n: 1}),
      base('ap-sr', 'start_run', {skill: 'lit'}, {status: 'executed', result: {run: RID}}),
      base('ap-pn', 'pin_result', {title: 'x'}, {status: 'executed', result: {pin: 'PIN-1'}}),
      base('ap-ex', 'add_decision', {text: 'd'}, {status: 'executed', result: {}}),
      base('ap-er', 'add_decision', {text: 'd'}, {status: 'failed', result: {error: 'refused'}}),
      base('ap-tx', 'add_decision', {text: 'd'}, {status: 'rejected', result: {text: 'note'}}),
      base('ap-ap', 'add_decision', {text: 'd'}, {status: 'approved'}),
      base('ap-dn', 'add_decision', {text: 'd'}, {status: 'denied'}),
      base('ap-cn', 'add_decision', {text: 'd'}, {status: 'cancelled'}),
      base('ap-ww', 'add_decision', {text: 'd'}, {status: 'weird'}),
      base('ap-art', 'apply', {}, {kind: 'apply_artifact'}),
      {...base('ap-late', 'add_note', {text: 'late'}), turn_id: '', created: 0},
    ];
  }});
  assert.match(h.$$('.activity')[0].textContent, /^Đã dùng công cụ research_search_memory$/);
  assert.match(h.$$('.activity')[1].textContent, /Không dùng được/);
  assert.match(card(h, 'ap-t').textContent, /Dùng công cụ: research_search_memory/);
  assert.match(card(h, 'ap-ws').querySelector('.preview-box').textContent, /Hello/);
  assert.strictEqual(card(h, 'ap-wsn').querySelector('.preview-box').textContent, '');
  const dl = card(h, 'ap-uo').querySelector('dl').textContent;
  assert.ok(dl.includes('Từ khoá') && dl.includes('Đề cương') && dl.includes('extra_key') && !dl.includes('Chủ đề'));
  assert.match(card(h, 'ap-cc').textContent, /a\.py/);
  assert.match(card(h, 'ap-hy').textContent, /T only/);
  assert.match(card(h, 'ap-nt').textContent, /note body/);
  assert.match(card(h, 'ap-js').querySelector('pre').textContent, /"n": 1/);
  await h.until(() => card(h, 'ap-sr').querySelector('.card.run .steps'));
  assert.match(card(h, 'ap-pn').textContent, /Đã ghim PIN-1/);
  assert.match(card(h, 'ap-er').textContent, /refused/);
  assert.match(card(h, 'ap-tx').textContent, /note/);
  const chips = ['ap-ex', 'ap-er', 'ap-tx', 'ap-ap', 'ap-dn', 'ap-cn', 'ap-ww'].map((id) => card(h, id).querySelector('.card-h .chip').textContent);
  assert.deepStrictEqual(chips, ['đã chấp nhận', 'lỗi', 'đã bỏ qua', 'đã chấp nhận', 'bị chặn', 'đã huỷ', 'weird']);
  assert.strictEqual(card(h, 'ap-art'), null);
  assert.ok(card(h, 'ap-late'));
});

test('Accept / Reject a proposal (ok, failed, server error); memory proposals', async () => {
  let reply = {status: 'executed'};
  const h = await chat({routes: {'POST /api/chat/sessions/:id/approvals/:ap': () => reply}});
  const btn = (id, label) => [...card(h, id).querySelectorAll('button')].find((b) => b.textContent.includes(label));
  btn('ap-15b0cb8e', 'Chấp nhận').click();
  assert.ok(btn('ap-15b0cb8e', 'Bỏ qua').disabled);
  await h.idle(30);
  assert.strictEqual(h.toast(), 'Đã chấp nhận');
  assert.strictEqual(h.server.last('POST', `/api/chat/sessions/${SID}/approvals/ap-15b0cb8e`).body.decision, 'approve');
  btn('ap-48894aa8', 'Bỏ qua').click();
  await h.idle(30);
  assert.strictEqual(h.toast(), 'Đã bỏ qua');
  reply = {status: 'failed', result: {error: 'nope'}};
  btn('ap-32450735', 'Chấp nhận').click();
  await h.idle(30);
  assert.match(h.toast(), /Không thực hiện được: nope/);
  reply = {status: 'failed'};
  btn('ap-32450735', 'Chấp nhận').click();
  await h.idle(30);
  assert.match(h.toast(), /Không thực hiện được: $/);
  reply = R({detail: 'gone'}, 404);
  btn('ap-32450735', 'Chấp nhận').click();
  await h.idle(30);
  assert.strictEqual(h.toast(), 'gone');
  h.w.PL.chat.refresh = async () => {};
  // memory card
  const mem = () => h.$$('.card').find((c) => c.textContent.includes('Đề xuất ghi nhớ'));
  [...mem().querySelectorAll('button')].find((b) => b.textContent === 'Chấp nhận').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/memory/candidates/CAND-001/approve').length, 1);
  [...mem().querySelectorAll('button')].find((b) => b.textContent === 'Bỏ qua').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/memory/candidates/CAND-001/reject').length, 1);
});

test('memory and artifact cards: every status, conflicts, view / reject / apply', async () => {
  const mi = (id, status, extra = {}) => ({id, status, type: 'decision', text: 'T ' + id, message_ids: [], conflicts: 0, ...extra});
  const h = await chat({mut: (s) => {
    s.memory_items = [mi('C1', 'duplicate', {conflicts: 2}), mi('C2', 'approved'), mi('C3', 'rejected'), mi('C4', 'odd', {type: 'zzz'})];
    s.artifacts = [{id: 'af-1', turn_id: 't-8fffee5e', path: 'src/a.py', status: 'collected'},
      {id: 'af-2', turn_id: '', created: 5, path: 'b.py', status: 'applied'}, {id: 'af-3', path: 'c.py', status: 'rejected'},
      {id: 'af-4', path: 'd.py', status: 'other'}];
  }, routes: {'GET /api/chat/sessions/:id/artifacts/:a/diff': () => ({exists: true, diff: '+x', target_sha256: 'abc'})}});
  const text = h.$('#msgs').textContent;
  for (const t of ['có thể trùng', 'Mâu thuẫn với 2', 'đã lưu', 'đã bỏ qua', 'odd', 'zzz', 'đã áp dụng', 'other']) assert.ok(text.includes(t), t);
  const art = h.$$('.card').find((c) => c.textContent.includes('src/a.py'));
  [...art.querySelectorAll('button')].find((b) => b.textContent.includes('Xem')).click();
  await h.idle(40);
  assert.strictEqual(h.$('#panel-title').textContent, 'src/a.py');
  [...art.querySelectorAll('button')].find((b) => b.textContent === 'Bỏ qua').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/artifacts/af-1/reject`).length, 1);
  [...h.$$('.card').find((c) => c.textContent.includes('src/a.py')).querySelectorAll('button')].find((b) => b.textContent.includes('Áp dụng')).click();
  await h.idle(40);
  assert.ok(h.$('#panel-body pre'));
});

test('run cards: every status, recovery proposal, approve / cancel / retry / resume; gone run', async () => {
  let run = (r) => r;
  const h = await chat({run: (r) => run(r)});
  const runCard = () => h.$('.card.run');
  const show = async (fn) => { run = fn; await h.w.PL.chat.refreshRun(RID); await h.idle(); return runCard(); };
  let c = await show((r) => ({...r, status: 'RUNNING', synthetic: true}));
  assert.match(c.textContent, /Báo cáo · phdlab/);
  assert.match(c.textContent, /SYNTHETIC/);
  c = await show((r) => ({...r, status: 'BLOCKED', current: 'nope'}));
  assert.match(c.querySelector('.row').textContent, / · /);
  c = await show((r) => ({...r, status: 'CANCELLED'}));
  assert.ok(!c.textContent.includes('Dừng'));
  c = await show((r) => ({...r, status: 'COMPLETED', outputs: []}));
  assert.strictEqual(c.querySelectorAll('button.chip').length, 0);
  c = await show((r) => ({...r, status: 'FAILED', reason: 'OOM'}));
  assert.match(c.textContent, /OOM/);
  c = await show((r) => ({...r, status: 'FAILED', reason: ''}));
  [...c.querySelectorAll('button')].find((b) => b.textContent === 'Dừng').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ', 20);  // keep the run
  assert.strictEqual(h.server.calledWith('POST', `/api/runs/${RID}/cancel`).length, 0);
  [...runCard().querySelectorAll('button')].find((b) => b.textContent === 'Dừng').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ run', 30);
  assert.strictEqual(h.server.calledWith('POST', `/api/runs/${RID}/cancel`).length, 1);
  assert.strictEqual(h.toast(), 'Đã huỷ');
  c = await show((r) => ({...r, status: 'APPROVAL_PENDING'}));
  assert.ok(c.classList.contains('pending'));
  [...c.querySelectorAll('button')].find((b) => b.textContent.includes('Chấp nhận & chạy')).click();
  await h.idle(20);
  assert.strictEqual(h.toast(), 'Đã duyệt — run bắt đầu');
  c = await show((r) => ({...r, status: 'NEEDS_USER_ACTION', proposal: {text: 'halve batch', patch: {batch: 16}}}));
  assert.match(c.querySelector('.preview-box').textContent, /halve batch/);
  [...c.querySelectorAll('button')].find((b) => b.textContent.includes('Áp dụng đề xuất')).click();
  await h.idle(20);
  assert.strictEqual(h.server.last('POST', `/api/runs/${RID}/resume`).body.accept, true);
  c = await show((r) => ({...r, status: 'NEEDS_USER_ACTION', proposal: {text: '', patch: {}}, next_decision: 'decide'}));
  assert.match(c.querySelector('.preview-box').textContent, /decide/);
  assert.ok(![...c.querySelectorAll('button')].some((b) => b.textContent.includes('Áp dụng đề xuất')));
  [...c.querySelectorAll('button')].find((b) => b.textContent === 'Thử lại').click();
  await h.idle(20);
  assert.strictEqual(h.server.last('POST', `/api/runs/${RID}/resume`).body.accept, false);
  c = await show((r) => ({...r, status: 'NEEDS_USER_ACTION', proposal: null, next_decision: ''}));
  assert.strictEqual(c.querySelector('.preview-box'), null);
  [...c.querySelectorAll('button')].find((b) => b.textContent === 'Huỷ run').click();
  await h.idle();
  c = await show((r) => ({...r, status: 'APPROVAL_PENDING'}));
  h.$('#modal').click();
  [...c.querySelectorAll('button')].find((b) => b.textContent === 'Huỷ').click();
  await h.idle();
  h.$('#modal').click();
  // a run that is gone; refreshing a run with no card on screen; a refresh that fails
  run = () => R({detail: 'x'}, 404);
  await h.w.PL.chat.refreshRun(RID);
  await h.w.PL.chat.refreshRun('RR-none');
  await h.w.PL.chat.refresh();
  await h.until(() => h.$('.card.run').textContent.includes('không còn'));
});

test('live events: streaming text, activity, tool use, run updates, completion and failure', async () => {
  let turns = null;
  const h = await chat({mut: (s) => { if (turns) s.turns = turns; }});
  const es = sse(h);
  assert.ok(es.url.includes('after=58'));
  const T = 't-live';
  turns = [{id: T, status: 'running'}];
  es.send({type: 'turn.started', turn_id: T});
  await h.idle(30);
  assert.ok(h.$('.msg.live .typing'));
  assert.ok(h.$('#send').classList.contains('stop'));
  es.send({type: 'context.compiled', turn_id: T, data: {sources: 4, tokens: 900}});
  es.send({type: 'status.updated', turn_id: T, data: {intent: 'gap'}});
  es.send({type: 'status.updated', data: {}});
  es.send({type: 'tool.started', turn_id: T, data: {tool: 'web_search'}});
  es.send({type: 'tool.started', data: {}});
  es.send({type: 'tool.started', turn_id: T, data: {}});
  es.send({type: 'message.delta', turn_id: T, data: {text: 'Hello **world**'}});
  assert.match(h.$('.msg.live .prose').innerHTML, /<strong>world<\/strong>/);
  es.send({type: 'message.delta', turn_id: T, data: {}});
  es.send({type: 'run.updated', data: {run_id: RID}});
  es.send({type: 'something.else'});
  es.send({type: 'message.delta', turn_id: 't-unknown', data: {text: 'x'}});  // no live node yet → refresh
  await h.idle(30);
  turns = [{id: T, status: 'waiting_approval'}];
  es.send({type: 'tool.approval_required', turn_id: T});
  await h.idle(30);
  assert.match(h.$('.msg.live .activity').textContent, /chờ bạn duyệt công cụ/);
  turns = [{id: T, status: 'awaiting_launch'}];
  es.send({type: 'session.updated'});
  await h.idle(30);
  assert.match(h.$('.msg.live .activity').textContent, /Chế độ thủ công/);
  await h.clickText('.msg.live .btn', 'Gửi cho mô hình', 20);
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/turns/${T}/launch`).length, 1);
  turns = [{id: T, status: 'running'}];
  es.send({type: 'turn.started', turn_id: T});
  await h.idle(30);
  es.send({type: 'tool.started', turn_id: T, data: {tool: 'x'}});
  es.send({type: 'turn.started', turn_id: T});  // re-render keeps the activity line
  await h.idle(30);
  assert.match(h.$('.msg.live .activity').textContent, /Đang dùng công cụ x/);
  turns = [{id: T, status: 'failed'}];
  es.send({type: 'turn.failed', turn_id: T, data: {message: 'model offline'}});
  await h.idle(30);
  assert.match(h.toast(), /Lỗi: model offline/);
  es.send({type: 'turn.failed', turn_id: T});
  await h.idle(30);
  assert.strictEqual(h.$('.msg.live'), null);
  assert.ok(!h.$('#send').classList.contains('stop'));
});

test('stop a running answer; stop with nothing running', async () => {
  let turns = [{id: 't-r', status: 'queued'}];
  const h = await chat({mut: (s) => { s.turns = turns; }});
  assert.ok(h.$('#send').classList.contains('stop'));
  await h.click('#send', 30);
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/turns/t-r/cancel`).length, 1);
  turns = [];
  await h.w.PL.chat.refresh();
  h.w.PL.chat.busy = true;
  await h.click('#send', 30);
  assert.strictEqual(h.server.calledWith('POST', '/api/chat/sessions/' + SID + '/turns/').length, 1);
  // retry while busy does nothing
  h.w.PL.chat.busy = true;
  [...h.$$('.msg.ai')[0].querySelectorAll('.msg-actions button')][1].click();
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/retry`).length, 0);
});

test('composer: send, Enter / Shift+Enter, composing, busy, attachments (upload, failure, pending, remove, + library)', async () => {
  let failUpload = false;
  const h = await chat({routes: {'POST /api/chat/attachments': () => (failUpload ? R({detail: 'too big'}, 413) : {id: 'att1', kind: 'pdf', chars: 10})}});
  const send = h.$('#send');
  assert.ok(send.disabled);
  await h.input('#input', 'hello');
  assert.ok(!send.disabled);
  await h.key('#input', 'Enter', {shiftKey: true});
  await h.key('#input', 'Enter', {isComposing: true});
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/turns`).length, 0);
  await h.key('#input', 'Enter');
  await h.idle(30);
  assert.strictEqual(h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body.text, 'hello');
  assert.strictEqual(h.$('#input').value, '');
  h.w.PL.chat.busy = true;
  await h.input('#input', 'queued');
  await h.key('#input', 'Enter');
  assert.strictEqual(h.server.calledWith('POST', `/api/chat/sessions/${SID}/turns`).length, 1);
  h.w.PL.chat.busy = false;
  // attachments: file picker, paste, drop
  const fileInput = h.$('.composer input[type=file]');
  await h.setFiles(fileInput, ['paper.pdf']);
  await h.idle(20);
  assert.ok(h.$('.att').textContent.includes('paper.pdf'));
  await h.clickText('.att button', '＋TV', 20);
  assert.strictEqual(h.server.calledWith('POST', '/api/library/upload').length, 1);
  const paste = new h.w.Event('paste', {cancelable: true});
  paste.clipboardData = {files: h.files(['notes.md'])};
  h.$('#input').dispatchEvent(paste);
  const paste2 = new h.w.Event('paste');
  paste2.clipboardData = {files: []};
  h.$('#input').dispatchEvent(paste2);
  h.$('#input').dispatchEvent(new h.w.Event('paste'));
  await h.idle(20);
  await h.drop('#thread', ['data.csv'], 'dragover');
  await h.drop('#thread', ['data.csv']);
  const empty = new h.w.Event('drop', {cancelable: true});
  h.$('#thread').dispatchEvent(empty);
  await h.idle(20);
  assert.deepStrictEqual(h.$$('.att .n').map((x) => x.textContent), ['paper.pdf', 'notes.md', 'data.csv']);
  failUpload = true;
  await h.setFiles(fileInput, ['huge.bin']);
  await h.idle(20);
  assert.match(h.toast(), /huge.bin: too big/);
  [...h.$$('.att')[2].querySelectorAll('button')].at(-1).click();
  assert.strictEqual(h.$$('.att').length, 2);
  // a pending upload blocks sending
  h.w.PL.chat.atts.push({id: '', name: 'slow.pdf', pending: true});
  h.w.PL.chat.addFiles([]);
  await h.w.PL.chat.open(SID);
  await h.idle(30);
  assert.ok(h.$$('.att')[2].querySelector('.spin'));
  await h.input('#input', 'with files');
  await h.click('#send');
  assert.match(h.toast(), /Đợi file tải lên xong/);
  h.w.PL.chat.atts.pop();
  await h.input('#input', '');
  await h.click('#send', 30);
  const body = h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body;
  assert.match(body.text, /Hãy đọc các file đính kèm/);
  assert.match(body.text, /📎 paper.pdf/);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(body.overrides.sources)), ['att:att1', 'att:att1']);
  // nothing to send
  await h.w.PL.chat.submit('   ');
  // a refused turn keeps the text in the box
  h.server.on('POST /api/chat/sessions/:id/turns', () => R({detail: 'busy'}, 409));
  await h.input('#input', 'again');
  await h.click('#send', 30);
  assert.strictEqual(h.$('#input').value, 'again');
  assert.match(h.toast(), /busy/);
  h.server.on('POST /api/chat/sessions/:id/turns', () => { h.$('#input').value = 'typed meanwhile'; return R({detail: 'busy'}, 409); });
  await h.w.PL.chat.submit('other');
  assert.strictEqual(h.$('#input').value, 'typed meanwhile');
});

test('a first message creates the conversation (with the model chosen beforehand)', async () => {
  const h = await chat({hash: '', anyId: true, routes: {'POST /api/chat/sessions': () => ({id: SID})}});
  await h.input('#input', 'new question');
  await h.click('#send', 60);
  const created = () => h.server.calls.filter((c) => c.method === 'POST' && c.path === '/api/chat/sessions').at(-1).body;
  assert.deepStrictEqual(JSON.parse(JSON.stringify(created())), {});
  assert.strictEqual(h.w.location.hash, '#/chat/' + SID);
  assert.strictEqual(h.server.last('POST', `/api/chat/sessions/${SID}/turns`).body.text, 'new question');
  await h.go('#/', 40);
  await h.w.PL.chat.setSetting('provider', 'cli:codex');
  await h.w.PL.chat.setSetting('reasoning', '');
  assert.match(h.$('#model').textContent, /Codex/);
  await h.input('#input', 'second');
  await h.click('#send', 60);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(created())), {settings: {provider: 'cli:codex'}});
});

test('"/" skill menu: filter by name, alias and title, categories, keyboard, pick with the mouse', async () => {
  const h = await chat({hash: ''});
  await h.input('#input', '/');
  const items = () => h.$$('.menu.slash .mi');
  assert.strictEqual(items().length, 18);
  assert.deepStrictEqual(h.$$('.menu.slash .mh').map((x) => x.textContent), ['Nghiên cứu', 'Thí nghiệm', 'Viết bài', 'Hệ thống']);
  assert.ok(items()[0].textContent.includes('chạy nền'));
  assert.ok(items().find((x) => x.textContent.includes('/code')).textContent.includes('cần duyệt'));
  await h.input('#input', '/try');  // alias of /idea
  assert.deepStrictEqual(items().map((x) => x.querySelector('.c').textContent), ['/idea']);
  await h.input('#input', '/quan');  // title match ("Tổng quan tài liệu")
  assert.ok(items().length >= 1);
  await h.input('#input', '/zzzz');
  assert.strictEqual(h.$('.menu.slash'), null);
  await h.input('#input', '/');
  await h.input('#input', 'plain text');  // no longer a command: the menu closes
  assert.strictEqual(h.$('.menu.slash'), null);
  await h.input('#input', '/');
  await h.key('#input', 'ArrowDown');
  await h.key('#input', 'ArrowDown');
  await h.key('#input', 'ArrowUp');
  assert.ok(items()[1].classList.contains('sel'));
  await h.key('#input', 'Tab');
  assert.strictEqual(h.$('#input').value, '/deepresearch ');
  assert.strictEqual(h.$('.menu.slash'), null);
  await h.input('#input', '/');
  await h.key('#input', 'ArrowUp');
  await h.key('#input', 'ArrowUp');  // wraps around to the last skill
  await h.key('#input', 'Enter');
  assert.strictEqual(h.$('#input').value, '/status ');
  await h.input('#input', '/l');
  items()[0].dispatchEvent(new h.w.MouseEvent('mousedown', {cancelable: true}));
  assert.strictEqual(h.$('#input').value, '/lit ');
  await h.input('#input', '/');
  await h.key('#input', 'Escape');
  assert.strictEqual(h.$('.menu.slash'), null);
  await h.clickText('.composer .bar button', '', 10);  // the paper clip opens the file picker
  h.$$('.composer .bar button.icon')[1].click();  // the ✦ button types "/"
  await h.idle();
  assert.ok(h.$('.menu.slash'));
  h.w.PL.chat.skills = [];
  await h.input('#input', '/');
  assert.strictEqual(h.$('.menu.slash'), null);
  h.w.PL.chat.skills = [{name: 'mine', aliases: [], title: 'Mine', description: 'd', category: 'custom', mode: 'chat'}];
  await h.input('#input', '/');
  assert.strictEqual(h.$('.menu.slash .mh').textContent, 'custom');
});

test('model + reasoning picker: groups, filter, unavailable models, choose model and level, notes, close', async () => {
  let note = {notes: [{setting: 'reasoning', note: 'mapped to effort'}]};
  const h = await chat({routes: {'GET /api/chat/sessions/:id/effective': () => note}});
  const open = async () => { await h.click('#model'); return h.$('.menu.picker'); };
  let pop = await open();
  assert.deepStrictEqual([...pop.querySelectorAll('.plist .mh')].map((x) => x.textContent), ['Trên máy này', 'API đám mây', 'CLI (gói đăng ký của bạn)']);
  assert.match(pop.querySelector('.mi.sel').textContent, /Tự động/);
  const anth = [...pop.querySelectorAll('.plist .mi')].find((x) => x.textContent.includes('Anthropic'));
  assert.ok(anth.disabled);
  assert.match(anth.textContent, /chưa có API key/);
  assert.match([...pop.querySelectorAll('.plist .mi')].find((x) => x.textContent.includes('Claude Code')).textContent, /\S/);
  const filter = pop.querySelector('.filter');
  filter.value = 'codex';
  filter.dispatchEvent(new h.w.Event('input'));
  assert.strictEqual(pop.querySelectorAll('.plist .mi').length, 1);
  filter.value = 'nothing-matches';
  filter.dispatchEvent(new h.w.Event('input'));
  assert.match(pop.querySelector('.plist').textContent, /Không có mô hình phù hợp/);
  filter.value = '';
  filter.dispatchEvent(new h.w.Event('input'));
  [...pop.querySelectorAll('.plist .mi')].find((x) => x.textContent.includes('Codex')).click();
  await h.idle(30);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('PUT', '/api/chat/sessions/' + SID).body)), {settings: {provider: 'cli:codex'}});
  // reasoning submenu (left of the picker when there is room, otherwise right)
  pop = await open();
  const rect = h.w.Element.prototype.getBoundingClientRect;
  h.w.Element.prototype.getBoundingClientRect = function () { return {left: 400, right: 700, top: 300, bottom: 320, width: 300, height: 20}; };
  pop.querySelector('.mi.reason').click();
  h.w.Element.prototype.getBoundingClientRect = rect;
  let sub = h.$('.menu.sub');
  assert.ok(sub);
  assert.ok([...sub.querySelectorAll('.mi')].find((x) => x.textContent === 'Tắt').disabled === false);
  pop.querySelector('.mi.reason').click();  // re-open replaces the submenu
  sub = h.$('.menu.sub');
  sub.dispatchEvent(new h.w.MouseEvent('mousedown', {bubbles: true}));  // clicks inside the submenu keep the picker
  assert.ok(pop.isConnected);
  [...sub.querySelectorAll('.mi')].find((x) => x.textContent === 'Cao').click();
  await h.idle(40);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('PUT', '/api/chat/sessions/' + SID).body)), {settings: {reasoning: 'high'}});
  assert.strictEqual(h.toast(), 'mapped to effort');
  note = {notes: []};
  await h.w.PL.chat.setSetting('reasoning', 'low');
  h.server.on('GET /api/chat/sessions/:id/effective', () => R({}, 500));
  await h.w.PL.chat.setSetting('reasoning', 'medium');
  await h.w.PL.chat.setSetting('reasoning', '');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('PUT', '/api/chat/sessions/' + SID).body)), {settings_reset: ['reasoning']});
  // a chosen level shows on the button
  h.st.mut = (s) => { s.settings = {provider: 'cli:gemini_cli', reasoning: 'high'}; };
  await h.w.PL.chat.refresh();
  h.w.PL.chat.setSetting = h.w.PL.chat.setSetting;
  await h.w.PL.chat.loadModels();
  assert.match(h.$('#model').textContent, /Cao/);
  pop = await open();
  assert.match(pop.querySelector('.mi.reason').textContent, /không có điều khiển tư duy/);
  pop.querySelector('.mi.reason').click();
  assert.ok([...h.$('.menu.sub').querySelectorAll('.mi')].find((x) => x.textContent === 'Cao').disabled);
  [...h.$('.menu.sub').querySelectorAll('.mi')][0].click();  // "auto"
  await h.idle(30);
  // close: Escape, outside click; the settings shortcut
  pop = await open();
  pop.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'a', bubbles: true}));
  pop.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  assert.strictEqual(h.$('.menu.picker'), null);
  pop = await open();
  await h.idle();
  h.document.body.dispatchEvent(new h.w.MouseEvent('mousedown', {bubbles: true}));
  assert.strictEqual(h.$('.menu.picker'), null);
  pop = await open();
  [...pop.querySelectorAll('.mi')].at(-1).click();
  await h.idle(40);
  assert.ok(h.$('.settings'));
  h.$('#modal').click();
  // choosing "auto" resets the provider
  pop = await open();
  [...pop.querySelectorAll('.plist .mi')].find((x) => x.textContent.includes('Tự động')).click();
  await h.idle(30);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('PUT', '/api/chat/sessions/' + SID).body)), {settings_reset: ['provider']});
});

test('model picker before the model list arrived; models unavailable; skills unavailable', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const h = await chat({routes: {'GET /api/models': async () => { await gate; return fixtures.get('GET /api/models'); }}});
  h.w.PL.chat.models = null;
  await h.click('#model');
  assert.match(h.$('.menu.picker .plist').textContent, /Đang tải danh sách mô hình/);
  release();
  await h.idle(30);
  assert.ok(h.$('.menu.picker .plist .mi'));
  h.$('.menu.picker').remove();
  h.w.PL.chat.models = null;
  await h.click('#model');
  h.$('.menu.picker').remove();  // closed before the list arrived
  await h.idle(30);
  const h2 = await chat({routes: {'GET /api/models': () => R({}, 500), 'GET /api/skills': () => R({}, 500)}});
  assert.strictEqual(h2.w.PL.chat.models, null);
  assert.deepStrictEqual([...h2.w.PL.chat.skills], []);
  assert.match(h2.$('#model').textContent, /Tự động/);
  h2.$('#model').remove();
  await h2.w.PL.chat.loadModels();
  h2.$('#send').remove();
  h2.w.PL.chat.refresh();
  await h2.idle(30);
  h2.$('#input').remove();
  h2.w.PL.chat.setInput('x');
});

test('scrolling: follows new content only when the reader is near the bottom', async () => {
  const h = await chat();
  const t = h.$('#thread');
  Object.defineProperty(t, 'scrollHeight', {value: 5000, configurable: true});
  Object.defineProperty(t, 'clientHeight', {value: 500, configurable: true});
  t.scrollTop = 0;
  await h.w.PL.chat.refresh();
  assert.strictEqual(t.scrollTop, 0);  // reading older messages: stays put
  t.scrollTop = 4450;
  await h.w.PL.chat.refresh();
  assert.strictEqual(t.scrollTop, 5000);
  h.st.mut = (s) => { s.messages = []; };
  await h.w.PL.chat.refresh();
  await h.idle(30);
  assert.ok(h.$('.hello'));
});

test('sparse records: missing optional fields never break the page; every completion event refreshes', async () => {
  const h = await chat({mut: (s) => {
    delete s.last_seq;
    delete s.memory_items;
    delete s.artifacts;
    delete s.settings;
    s.title = '';
    s.approvals = [{id: 'ap-n', kind: 'action', name: 'add_note', status: 'pending', created: 1}];
    s.messages.push({id: 'm-e', role: 'assistant', content: '', status: 'complete', provider: 'app:auto', ts: 1e12});
  }, run: (r) => ({...r, status: 'RUNNING', steps: r.steps.map((x, i) => (i ? x : {...x, status: undefined}))})});
  assert.ok(sse(h).url.endsWith('after=0'));
  assert.ok(card(h, 'ap-n'));
  await h.until(() => h.$('.card.run .steps i.pending'));
  const es = sse(h);
  const types = ['message.completed', 'turn.completed', 'turn.cancelled', 'action.approval_required', 'memory.candidate', 'memory.saved',
    'action.completed', 'action.failed', 'artifact.discovered', 'artifact.updated'];
  for (const type of types) { es.send({type}); await h.idle(5); }
  await h.idle(20);
  // pin with an untitled conversation
  [...h.$$('.msg.ai')[1].querySelectorAll('.msg-actions button')].find((b) => b.title.includes('Ghim vào kết quả')).click();
  await h.idle();
  assert.strictEqual(h.$('#modal input').value, '');
  h.$('#modal').click();
  h.st.mut = (s) => {
    delete s.turns;
    s.memory_items = [{id: 'C9', status: 'pending', type: 'note', text: 'x', conflicts: 0}];
    s.artifacts = [{id: 'af', path: 'p.py', status: 'collected'}];
    s.settings = {};
  };
  await h.w.PL.chat.refresh();
  assert.ok(h.$$('.card').some((c) => c.textContent.includes('p.py')));
  h.$('#send').click();  // stop with no turns at all
  await h.idle(20);
  // the effective settings without notes
  h.server.on('GET /api/chat/sessions/:id/effective', () => ({}));
  await h.w.PL.chat.setSetting('reasoning', 'low');
  // the open conversation disappears → refresh keeps what is on screen
  h.st.mut = () => { throw new Error('gone'); };
  h.server.on('GET /api/chat/sessions/:id', () => R({detail: 'gone'}, 404));
  await h.w.PL.chat.refresh();
  h.w.PL.chat.sid = null;
  await h.w.PL.chat.refresh();
  // a live answer in a conversation without settings; stop before the conversation loaded
  h.server.on('GET /api/chat/sessions/:id', () => { const x = fixtures.get('GET /api/chat/sessions/:id'); delete x.settings; x.turns = [{id: 't-q', status: 'running'}]; return x; });
  h.w.PL.chat.sid = SID;
  await h.w.PL.chat.refresh();
  assert.ok(h.$('.msg.live'));
  h.w.PL.chat.s = null;
  h.$('#send').click();
  await h.idle(20);
  // helpers without their elements
  h.w.PL.chat.addFiles(undefined);
  h.$('#send').remove();
  h.w.PL.chat.setInput('x');
  h.$('#atts').remove();
  await h.w.PL.chat.addFiles(h.files(['late.txt']));
  h.$('#composer-wrap').remove();
  h.w.PL.chat.busy = false;
  h.w.PL.chat.setInput('x');
});

test('home screen without a project (configuration unavailable); outline without attachments', async () => {
  const h = await chat({hash: '', routes: {'GET /api/config': () => R({detail: 'x'}, 500),
    'GET /api/outline': () => ({level: 0, level_label: ''})}});
  assert.strictEqual(h.$('.hello p').textContent, '');
  assert.ok(h.$('.outline-card'));
});
