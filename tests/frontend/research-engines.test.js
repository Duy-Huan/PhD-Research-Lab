'use strict';
const test = require('node:test');
const assert = require('node:assert');
const {boot, fixtures} = require('./harness');

test('engine settings remain separate from models; search and model qualification updates', async () => {
  const cfg = fixtures.get('GET /api/config');
  cfg.openscience = {enabled: false, has_token: true, qualified_tasks: ['review']};
  const h = await boot({routes: {'GET /api/config': () => cfg, 'POST /api/config': () => cfg}});
  await h.w.PL.settings.open('providers');
  await h.idle(25);
  const field = (text) => h.byText('.sb .field', h.w.PL.ui(text)).querySelector('input,select');
  const modes = field('Research engine mode');
  assert.deepStrictEqual([...modes.options].map((x) => x.value), ['auto', 'feynman', 'openscience', 'collaborative']);
  modes.value = 'collaborative';
  modes.dispatchEvent(new h.w.Event('change'));
  await h.idle(20);
  assert.strictEqual(h.server.last('POST', '/api/config').body.research_providers.engine_mode, 'collaborative');
  const model = field('OpenScience model ID');
  model.value = 'reviewed-model';
  model.dispatchEvent(new h.w.Event('change'));
  await h.idle(20);
  const update = h.server.last('POST', '/api/config').body.openscience;
  assert.strictEqual(update.model_id, 'reviewed-model');
  assert.strictEqual(update.qualified_tasks.length, 0);
  assert.strictEqual(field('Deployment token').value, '');
  const search = h.$('.settings-search');
  search.value = 'OpenScience';
  search.dispatchEvent(new h.w.Event('input'));
  await h.idle(20);
  assert.strictEqual(h.$('.settings nav .nav.active').dataset.k, 'providers');
});

test('native permission UI permits once/reject and resumes the existing run', async () => {
  const rid = fixtures.meta.runs[0], jid = 'ej-' + '1'.repeat(20);
  const base = `/api/research-engines/jobs/${jid}`;
  const h = await boot({hash: '#/chat/' + fixtures.meta.session, routes: {
    ['GET ' + base]: () => ({job: {state: 'waiting_decision', native_run_id: 'run_native'}, pending: [
      {id: 'per_native', kind: 'permission', permission: 'bash', patterns: ['python analysis.py'], metadata: {}}]}),
    ['POST ' + base + '/decisions']: () => ({state: 'applied'}),
    [`POST /api/runs/${rid}/resume`]: () => ({}),
  }});
  await h.idle(30);
  await h.w.PL.engineJob({id: rid}, jid);
  const buttons = h.$$('.dialog button').map((b) => b.textContent).join('|');
  assert.doesNotMatch(buttons, /always|project grant|session grant/);
  await h.clickText('.dialog button', 'Cho phép một lần', 25);
  assert.strictEqual(h.server.last('POST', base + '/decisions').body.reply, 'once');
  assert.strictEqual(h.server.last('POST', base + '/decisions').body.request_id, 'per_native');
  assert.strictEqual(h.server.last('POST', `/api/runs/${rid}/resume`).body.accept, false);
});

test('uncertain decision never automatically resumes the workflow', async () => {
  const rid = fixtures.meta.runs[0], jid = 'ej-' + '2'.repeat(20);
  const base = `/api/research-engines/jobs/${jid}`;
  const h = await boot({hash: '#/chat/' + fixtures.meta.session, routes: {
    ['GET ' + base]: () => ({job: {state: 'waiting_decision', native_run_id: 'run_native'}, pending: [{id: 'p', kind: 'permission', permission: 'read'}]}),
    ['POST ' + base + '/decisions']: () => ({state: 'indeterminate'}),
  }});
  await h.idle(30);
  await h.w.PL.engineJob({id: rid}, jid);
  await h.clickText('.dialog button', 'Cho phép một lần', 25);
  assert.match(h.toast(), /chưa xác định/);
  assert.strictEqual(h.server.last('POST', `/api/runs/${rid}/resume`), undefined);
});
