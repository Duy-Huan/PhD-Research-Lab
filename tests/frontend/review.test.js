'use strict';
// review.js: the paper review session — upload, venue settings, reviewers R1–R3 → area chair → issues → quick fixes
// (accept / dismiss) → apply to LaTeX → response letter; every stage streams Server-Sent Events.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const RVID = fixtures.meta.review;
const reviewed = () => {
  const r = fixtures.get('GET /api/review/:id');
  r.state = {
    reviewers: {R1: {persona: 'Methods', recommendation: 'Major revision', score: 5, text: '## R1\nWeak baselines.'},
      R2: {persona: 'Domain', text: 'R2 text'}},
    meta: {decision: 'Major revision', text: 'Chair says'},
    issues: [{id: 'I1', severity: 'critical', title: 'Baselines', location: '§4', problem: 'Missing', fix: 'Add DeiT', status: 'open'},
      {id: 'I2', severity: 'typo', title: 'Typo', location: '§1', problem: 'teh', status: 'done'},
      {id: 'I3', severity: 'weird', title: 'Other', location: '', problem: 'p', status: 'wontfix'},
      {id: 'I4', severity: 'minor', title: 'Dismissed', location: '', problem: 'p', status: 'open'},
      {id: 'I5', severity: 'major', title: 'Not found', location: '', problem: 'p', status: 'open'},
      {id: 'I6', severity: 'major', title: 'Odd', location: '', problem: 'p', status: 'open'}],
    fixes: {I2: {original: 'teh', revised: 'the', status: 'accepted', original_found: true, note: 'spelling'},
      I4: {original: '', plan: 'rewrite', status: 'dismissed'}, I5: {original: 'abc', revised: 'abd', status: 'proposed', original_found: false},
      I6: {original: 'x', revised: '', status: 'strange', original_found: true}},
    response: {text: 'Dear editor'},
  };
  r.meta.source = 'main.tex';
  r.meta.venue = {type: 'journal', quartile: 'Q2', name: 'TPAMI'};
  r.meta.n_reviewers = 2;
  r.meta.pages = 9;
  return r;
};

test('empty review page: drop zone (click, keyboard, drag & drop), upload opens the new review', async () => {
  const h = await boot({hash: '#/review', routes: {'GET /api/review': () => ({reviews: [], active: ''}),
    'POST /api/review/upload': () => ({meta: {id: RVID}}), 'GET /api/review/:id': () => fixtures.get('GET /api/review/:id')}});
  assert.strictEqual(h.$('#title').textContent, 'Phản biện bài báo');
  const drop = h.$('#rv-main .drop');
  assert.ok(drop);
  drop.click();
  drop.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'Enter'}));
  drop.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'a'}));
  await h.drop('#rv-main .drop', ['paper.pdf'], 'dragover');
  assert.ok(h.$('#rv-main .drop').classList.contains('over'));
  h.$('#rv-main .drop').dispatchEvent(new h.w.Event('dragleave'));
  await h.drop('#rv-main .drop', []);
  await h.drop('#rv-main .drop', ['paper.pdf'], 'drop');
  await h.idle(60);
  assert.strictEqual(h.w.location.hash, '#/review/' + RVID);
  assert.match(h.toast(), /Đã tải lên paper.pdf/);
  // the sidebar upload button and a refused upload
  h.server.on('POST /api/review/upload', () => R({detail: 'Too little text'}, 400));
  await h.setFiles(h.$('.review-grid > div:first-child input[type=file]'), ['short.md']);
  await h.idle(30);
  assert.match(h.toast(), /Too little text/);
  await h.setFiles(h.$('.review-grid > div:first-child input[type=file]'), []);
  h.$('.review-grid > div:first-child .btn').click();
});

test('a new review: settings, start reviewing (streamed stages), tabs before any report', async () => {
  let stageFail = null;
  const sse = (req) => {
    if (stageFail === 'http') return R({detail: 'model offline'}, 502);
    if (stageFail === 'httpnodetail') return R({}, 500, {statusText: 'Bad Gateway'});
    if (stageFail === 'httpnojson') return R('<html>', 500, {statusText: 'Proxy', contentType: 'text/html'});
    if (stageFail === 'meta' && req.body.stage === 'meta') return {__resp: true, sse: [{type: 'error', detail: 'chair offline'}]};
    if (stageFail === 'event') return {__resp: true, sse: [{type: 'start'}, {type: 'error', detail: 'quota'}]};
    return {__resp: true, sse: [{type: 'start'}, 'data: {bad json\n\n', {type: 'delta', text: 'Reading '}, {type: 'delta', text: 'paper'}, {type: 'done', ok: true}]};
  };
  const h = await boot({hash: '#/review/' + RVID, routes: {'POST /api/review/:id/stage': sse}});
  assert.match(h.$('#rv-main').textContent, /Lightweight ViT on the edge/);
  assert.match(h.$('#rv-main').textContent, /\? trang · 1k ký tự/);
  assert.ok(h.$('.review-grid .thread.active'));
  assert.match(h.$('#rv-body').textContent, /Chưa có báo cáo/);
  // settings
  const sels = h.$$('#rv-main select');
  sels[0].value = 'journal';
  h.$$('#rv-main select')[2].value = '2';
  h.$('#rv-main input.input').value = 'CVPR';
  await h.clickText('#rv-main button', 'Lưu cài đặt', 40);
  const put = h.server.last('PUT', `/api/review/${RVID}/settings`).body;
  assert.deepStrictEqual(JSON.parse(JSON.stringify(put)), {venue: {type: 'journal', scale: 'icore', rank: 'A', quartile: 'Q1', name: 'CVPR'}, n_reviewers: 2});
  // tabs without content
  for (const [tab, text] of [['Chủ tịch', /Chưa có ý kiến/], ['Vấn đề', /Chưa có danh sách/], ['Thư phản hồi', /được soạn từ các vấn đề/]]) {
    await h.clickText('.rv-tabs button', tab);
    assert.match(h.$('#rv-body').textContent, text);
  }
  // the whole review: R1..R3 → chair → issues
  h.byText('#rv-main button', 'Bắt đầu phản biện').click();
  await h.w.PL.review.runAll();  // already running: does nothing
  await h.until(() => h.toast().includes('Phản biện xong'));
  const stages = h.server.calledWith('POST', `/api/review/${RVID}/stage`).map((c) => c.body.stage + (c.body.idx || ''));
  assert.deepStrictEqual(stages, ['reviewer1', 'reviewer2', 'reviewer3', 'meta', 'issues']);
  assert.strictEqual(h.server.calledWith('POST', `/api/review/${RVID}/stage`)[0].body.fresh, true);
  // failures stop the pipeline and show why
  for (const [mode, msg] of [['http', /model offline/], ['httpnodetail', /Bad Gateway/], ['httpnojson', /Proxy/], ['event', /quota/]]) {
    stageFail = mode;
    await h.clickText('#rv-main button', 'Bắt đầu phản biện', 60);
    assert.match(h.toast(), msg);
    assert.strictEqual(h.$('#rv-prog').textContent, '');
  }
  stageFail = null;
  await h.clickText('.rv-tabs button', 'Chủ tịch');
  stageFail = 'meta';
  await h.w.PL.review.runAll();  // the reviewers succeed, the chair stage fails
  assert.match(h.toast(), /chair offline/);
  assert.strictEqual(h.server.calledWith('POST', `/api/review/${RVID}/stage`).filter((c) => c.body.stage === 'issues').length, 1);
  // the response letter
  stageFail = null;
  await h.clickText('.rv-tabs button', 'Thư phản hồi');
  await h.clickText('#rv-body button', 'Soạn thư phản hồi', 60);
  assert.strictEqual(h.server.last('POST', `/api/review/${RVID}/stage`).body.stage, 'response');
});

test('a reviewed manuscript: reports, chair, issues with fixes (accept / dismiss / propose), apply, downloads, delete', async () => {
  let rv = reviewed();
  let apply = {applied: ['I2'], not_found: ['I5']};
  const h = await boot({hash: '#/review/' + RVID, routes: {
    'GET /api/review/:id': () => rv, 'POST /api/review/:id/apply': () => apply,
    'POST /api/review/:id/fix': () => ({__resp: true, sse: [{type: 'done'}]}),
  }});
  assert.match(h.$('#rv-main').textContent, /9 trang/);
  assert.match(h.$$('#rv-main label span')[1].textContent, /Hạng tạp chí/);
  assert.match(h.$('#rv-body').textContent, /Methods.*Major revision.*Điểm 5/);
  assert.ok(h.$('#rv-body h2'));
  assert.ok(h.$$('#rv-main button').some((b) => b.textContent.includes('Phản biện lại')));
  assert.deepStrictEqual(h.$$('.rv-tabs button').map((b) => b.textContent), ['Reviewer 1', 'Reviewer 2', 'Chủ tịch', 'Vấn đề (6)', 'Thư phản hồi']);
  await h.clickText('.rv-tabs button', 'Reviewer 2');
  assert.strictEqual(h.$('#rv-body .chip'), null);
  await h.clickText('.rv-tabs button', 'Chủ tịch');
  assert.match(h.$('#rv-body').textContent, /Major revision.*Chair says/);
  await h.clickText('.rv-tabs button', 'Thư phản hồi');
  assert.match(h.$('#rv-body').textContent, /Dear editor/);
  await h.clickText('.rv-tabs button', 'Vấn đề');
  const issues = h.$$('#rv-body .issue');
  assert.strictEqual(issues.length, 6);
  assert.deepStrictEqual(issues.map((x) => x.querySelector('.chip').className), ['chip err', 'chip', 'chip', 'chip info', 'chip warn', 'chip warn']);
  assert.match(issues[0].textContent, /Gợi ý: Add DeiT/);
  assert.match(issues[1].textContent, /spelling.*đã chấp nhận/s);
  assert.match(issues[3].textContent, /\(không trích được đoạn gốc\).*rewrite.*đã bỏ qua/s);
  assert.match(issues[4].textContent, /không khớp nguyên văn/);
  assert.match(issues[5].textContent, /strange/);
  // status select, accept / dismiss a fix, propose a fix for an issue without one
  const sel = issues[0].querySelector('select');
  sel.value = 'wontfix';
  sel.dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.strictEqual(h.server.last('PUT', `/api/review/${RVID}/issue/I1`).body.status, 'wontfix');
  [...h.$$('#rv-body .issue')[4].querySelectorAll('button')].find((b) => b.textContent === 'Chấp nhận sửa').click();
  await h.idle(30);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('PUT', `/api/review/${RVID}/issue/I5`).body)), {fix_status: 'accepted', status: 'done'});
  [...h.$$('#rv-body .issue')[4].querySelectorAll('button')].find((b) => b.textContent === 'Bỏ qua').click();
  await h.idle(30);
  assert.strictEqual(h.server.last('PUT', `/api/review/${RVID}/issue/I5`).body.fix_status, 'dismissed');
  [...h.$$('#rv-body .issue')[0].querySelectorAll('button')].find((b) => b.textContent.includes('Đề xuất sửa')).click();
  await h.idle(60);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', `/api/review/${RVID}/fix`).body)), {issue_id: 'I1'});
  // apply accepted fixes to the LaTeX source
  await h.clickText('#rv-main button', 'Áp dụng sửa đã chấp nhận', 40);
  assert.match(h.toast(), /Đã áp dụng 1 sửa → source_revised.tex · 1 không khớp/);
  apply = {};
  await h.clickText('#rv-main button', 'Áp dụng sửa đã chấp nhận', 40);
  assert.strictEqual(h.toast(), 'Đã áp dụng 0 sửa → source_revised.tex');
  apply = R({detail: 'no source'}, 409);
  await h.clickText('#rv-main button', 'Áp dụng sửa đã chấp nhận', 40);
  assert.strictEqual(h.toast(), 'no source');
  assert.ok(h.$$('#rv-main a').some((a) => a.href.endsWith('/download/response')));
  assert.ok(h.$$('#rv-main a').some((a) => a.href.endsWith('/download/source')));
  // delete (cancel, then confirm)
  await h.clickText('#rv-main button', 'Xoá');
  await h.clickText('.dialog-f button', 'Huỷ', 20);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/review/').length, 0);
  await h.clickText('#rv-main button', 'Xoá');
  await h.clickText('.dialog-f button', 'Xoá', 60);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/review/' + RVID).length, 1);
  assert.strictEqual(h.w.location.hash, '#/review');
  // without a LaTeX source: attach one (accepted / none chosen)
  rv = fixtures.get('GET /api/review/:id');
  delete rv.meta.venue;
  delete rv.meta.n_reviewers;
  delete rv.meta.title;
  delete rv.meta.chars;
  rv.state.reviewers = {R1: {text: 'no persona'}};
  rv.state.meta = {text: 'no decision'};
  h.server.on('GET /api/review', () => ({reviews: [{id: RVID, file: 'f.md', n_issues: 3, decision: 'Accept', updated: '2026-10-21T01:00:00'}], active: 'gone'}));
  await h.go('#/review/' + RVID, 60);
  assert.match(h.$('.review-grid .thread').textContent, /f\.md.*Accept · 3 vấn đề · 2026-10-21/);
  assert.strictEqual(h.$$('.rv-tabs button').length, 6);
  assert.match(h.$('#rv-main b.grow').textContent, /vit-edge\.md/);
  assert.match(h.$('#rv-main').textContent, /0k ký tự/);
  await h.clickText('.rv-tabs button', 'Reviewer 1');
  assert.strictEqual(h.$('#rv-body b').textContent, '');
  await h.clickText('.rv-tabs button', 'Chủ tịch');
  assert.strictEqual(h.$('#rv-body .chip'), null);
  h.server.on('POST /api/review/:id/stage', () => ({__resp: true, sse: [{type: 'done'}]}));
  await h.w.PL.review.runAll();
  assert.strictEqual(h.server.calledWith('POST', `/api/review/${RVID}/stage`).length, 5);
  await h.clickText('#rv-main button', 'Đính kèm mã nguồn LaTeX');
  await h.setFiles(h.$$('#rv-main input[type=file]').at(-1), ['main.tex']);
  await h.idle(40);
  assert.strictEqual(h.server.calledWith('POST', `/api/review/${RVID}/source`).length, 1);
  await h.setFiles(h.$$('#rv-main input[type=file]').at(-1), []);
  h.server.on('POST /api/review/:id/source', () => R({detail: 'not tex'}, 400));
  await h.setFiles(h.$$('#rv-main input[type=file]').at(-1), ['x.txt']);
  await h.idle(30);
  assert.match(h.toast(), /not tex/);
  h.$('.review-grid .thread').click();
  await h.idle(40);
});

test('review list without an active review; a review that cannot be loaded; leaving a chat for the review page', async () => {
  const h = await boot({hash: '#/chat/' + fixtures.meta.session, routes: {
    'GET /api/review': () => ({reviews: [{id: 'r1', title: 'T1'}, {id: 'r2', title: 'T2'}], active: ''}),
    'GET /api/review/:id': () => R({detail: 'review missing'}, 404),
  }});
  await h.go('#/review', 60);
  assert.strictEqual(h.w.PL.review.rid, 'r1');
  assert.match(h.toast(), /review missing/);
  assert.strictEqual(h.$('#rv-main').textContent, '');
  h.server.on('GET /api/review', () => R({}, 500));
  await h.go('#/review/x', 60);
  assert.ok(h.$('#rv-main'));
  h.$('#rv-main').remove();
  h.w.PL.review.data = reviewed();
  await h.w.PL.review.runAll();  // painting without the page is a no-op
});
