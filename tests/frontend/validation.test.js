'use strict';
const test = require('node:test');
const assert = require('node:assert');
const {boot, fixtures} = require('./harness');

test('custom model selection can cancel, add a model, and refresh actual provider catalogs', async () => {
  const cfg = fixtures.get('GET /api/config');
  const h = await boot({routes: {'POST /api/config': () => cfg,
    'POST /api/models/list': () => ({models: ['catalog-new', 'catalog-new']}),
    'POST /api/models/cli/codex': () => ({models: ['codex-reviewed']})}});
  await h.w.PL.settings.open('models');
  await h.idle(25);
  const select = h.$('.sb option[value="__custom__"]').parentElement;
  const original = select.value;
  h.w.PL.prompt = async () => null;
  await h.change(select, '__custom__');
  assert.strictEqual(select.value, original);
  h.w.PL.prompt = async () => 'custom-reviewed';
  await h.change(select, '__custom__');
  assert.strictEqual(select.value, 'custom-reviewed');
  assert.ok(Object.values(h.server.last('POST', '/api/config').body.agent_models).includes('custom-reviewed'));
  await h.clickText('.sb button', '↻ Models');
  assert.strictEqual(h.server.last('POST', '/api/models/list').body.provider, 'anthropic');
  await h.w.PL.settings.open('providers');
  await h.idle(20);
  await h.clickText('.sb button', 'Codex model catalog');
  assert.strictEqual(h.toast(), "1 " + h.w.PL.ui("models (catalog; access checked when chatting)"));
  const token = h.byText('.sb .field', h.w.PL.ui('Deployment token')).querySelector('input');
  token.value = 'test-deployment-token';
  await h.clickText('.sb button', 'Lưu mã truy cập');
  assert.strictEqual(h.server.last('POST', '/api/config').body.openscience.token, 'test-deployment-token');
  assert.strictEqual(token.value, '');
});

test('remote run cards require approval and sync the real task identity', async () => {
  const d = fixtures.get('GET /api/dashboard');
  const rid = 'rc-123456789012';
  const remote = {run_id: rid, experiment_id: 'exp-test', compute_target: 'colab-gpu', status: 'awaiting_approval',
    bundle_sha256: 'sha-test', files: [{path: 'train.py'}], clearml_task_id: '', clearml_url: ''};
  d.compute_runs = [remote];
  const h = await boot({hash: '#/dashboard', routes: {'GET /api/dashboard': () => d,
    [`POST /api/compute/runs/${rid}/approve`]: () => { remote.status = 'approved'; return remote; },
    [`POST /api/compute/runs/${rid}/sync`]: () => ({status: 'awaiting_collection'})}});
  await h.idle(30);
  h.w.PL.confirm = async () => false;
  await h.clickText('.page button', 'Duyệt bundle');
  assert.strictEqual(h.server.last('POST', `/api/compute/runs/${rid}/approve`), undefined);
  h.w.PL.confirm = async () => true;
  await h.clickText('.page button', 'Duyệt bundle', 40);
  assert.ok(h.server.last('POST', `/api/compute/runs/${rid}/approve`));
  assert.ok(h.$(`a[href="/api/compute/runs/${rid}/bundle"]`));
  h.w.PL.prompt = async () => null;
  await h.clickText('.page button', 'Thu kết quả');
  assert.strictEqual(h.server.last('POST', `/api/compute/runs/${rid}/sync`), undefined);
  h.w.PL.prompt = async () => 'actual-task-123';
  await h.clickText('.page button', 'Thu kết quả', 30);
  assert.strictEqual(h.server.last('POST', `/api/compute/runs/${rid}/sync`).body.task_id, 'actual-task-123');
  remote.clearml_task_id = 'saved-task';
  remote.clearml_url = 'http://127.0.0.1:8080/projects/p/experiments/saved-task';
  h.w.PL.emit({type: 'run.updated'});
  await h.idle(550);
  await h.clickText('.page button', 'Thu kết quả', 25);
  assert.strictEqual(h.server.last('POST', `/api/compute/runs/${rid}/sync`).body.task_id, 'saved-task');
});

test('native run recovery, cancellation and questions preserve user intent', async () => {
  const rid = fixtures.meta.runs[0], jid = 'ej-' + '3'.repeat(20), base = `/api/research-engines/jobs/${jid}`;
  let detail = {job: {state: 'admission_unconfirmed', native_run_id: ''}, pending: []};
  const h = await boot({hash: '#/chat/' + fixtures.meta.session, routes: {
    ['GET ' + base]: () => detail, ['POST ' + base + '/recover-admission']: () => ({native_run_id: 'run-test'}),
    ['POST ' + base + '/cancel']: () => ({state: 'cancellation_unconfirmed'}),
    ['POST ' + base + '/decisions']: () => ({status: 'resolved'}), [`POST /api/runs/${rid}/resume`]: () => ({})}});
  await h.idle(30);
  await h.w.PL.engineJob({id: rid}, jid);
  await h.clickText('.dialog button', 'Khôi phục tiếp nhận', 25);
  assert.ok(h.server.last('POST', base + '/recover-admission'));
  detail = {job: {state: 'waiting_decision', native_run_id: 'run-test'}, observation_error: 'connection lost',
    pending: [{id: 'question-1', kind: 'question', questions: [{question: 'Which baseline?'}]}]};
  await h.w.PL.engineJob({id: rid}, jid);
  assert.match(h.$('.dialog').textContent, /Chưa truy cập được môi trường thực thi/);
  await h.clickText('.dialog button', 'Yêu cầu hủy', 25);
  assert.match(h.toast(), /cancellation_unconfirmed/);
  h.w.PL.prompt = async () => null;
  await h.clickText('.dialog button', 'Trả lời', 20);
  assert.strictEqual(h.server.last('POST', base + '/decisions'), undefined);
  h.w.PL.prompt = async () => 'U-Net';
  await h.clickText('.dialog button', 'Trả lời', 25);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', base + '/decisions').body.answers)), [['U-Net']]);
  await h.clickText('.dialog button', 'Từ chối', 25);
  assert.strictEqual(h.server.last('POST', base + '/decisions').body.reply, 'reject');
});
