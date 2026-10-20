// Frontend unit tests (node:test, no dependencies): node --test --experimental-test-coverage tests/frontend
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../../frontend/app/wfcore.js');

test('state classes and terminal states', () => {
  assert.equal(C.stateClass('SUCCEEDED'), 'ok');
  assert.equal(C.stateClass('WAITING_FOR_APPROVAL'), 'warn');
  assert.equal(C.stateClass('BUDGET_EXCEEDED'), 'err');
  assert.equal(C.stateClass('nonsense'), '');
  assert.equal(C.stateClass('toString'), '');  // no prototype leakage
  assert.ok(C.isTerminal('CANCELLED'));
  assert.ok(!C.isTerminal('PAUSED'));
});

test('labels', () => {
  assert.equal(C.policyLabel('unload_after_task'), 'Load → task → unload');
  assert.equal(C.policyLabel('custom'), 'custom');
  assert.equal(C.policyLabel(''), '—');
  assert.equal(C.labelClass('MEASURED'), 'ok');
  assert.equal(C.labelClass('AI_SUGGESTION'), 'ai');
  assert.equal(C.labelClass('X'), '');
});

test('formatting', () => {
  assert.equal(C.fmtDuration(null), '—');
  assert.equal(C.fmtDuration(-1), '—');
  assert.equal(C.fmtDuration(Infinity), '—');
  assert.equal(C.fmtDuration(0.25), '250 ms');
  assert.equal(C.fmtDuration(4.25), '4.3 s');
  assert.equal(C.fmtDuration(42), '42 s');
  assert.equal(C.fmtDuration(120), '2 min');
  assert.equal(C.fmtDuration(125), '2 min 5 s');
  assert.equal(C.fmtDuration(3 * 3600 + 120), '3 h 2 min');
  assert.equal(C.fmtMB(undefined), '—');
  assert.equal(C.fmtMB(512.4), '512 MB');
  assert.equal(C.fmtMB(4096), '4.0 GB');
  assert.equal(C.fmtNum(3), '3');
  assert.equal(C.fmtNum(0.123456789), '0.12346');
  assert.equal(C.fmtNum(0.00001234), '1.234e-5');
  assert.equal(C.fmtNum(12345678.9), '1.235e+7');
  assert.equal(C.fmtNum(0), '0');
  assert.equal(C.fmtNum(0.5), '0.5');
  assert.equal(C.fmtNum(NaN), 'NaN');
  assert.equal(C.fmtNum(null), '—');
  assert.equal(C.fmtNum('adam'), 'adam');
  assert.equal(C.vramPct(null, 100), null);
  assert.equal(C.vramPct(50, 0), null);
  assert.equal(C.vramPct(9000, 12288), 73);
  assert.equal(C.vramPct(20000, 12288), 100);
});

test('release labels describe what happens next', () => {
  assert.equal(C.releaseLabel(null), '');
  assert.equal(C.releaseLabel({leases: 2}), 'in use (2)');
  assert.equal(C.releaseLabel({leases: 0, owner: 'external', policy: ''}), 'loaded outside PhD-Lab — kept');
  assert.match(C.releaseLabel({leases: 0, owner: 'external', policy: 'idle_unload'}), /yours/);
  assert.equal(C.releaseLabel({leases: 0, owner: 'lifecycle', policy: 'keep_loaded', release_in_s: null}), 'kept loaded');
  assert.equal(C.releaseLabel({leases: 0, owner: 'lifecycle', policy: 'idle_unload'}), 'kept');
  assert.equal(C.releaseLabel({leases: 0, owner: 'lifecycle', policy: 'unload_after_task', release_in_s: 12}), 'releases in 12 s');
});

test('progress and durations', () => {
  assert.deepEqual(C.progress({steps: []}), {done: 0, total: 0, pct: 0});
  assert.deepEqual(C.progress(null), {done: 0, total: 0, pct: 0});
  const run = {steps: [{status: 'SUCCEEDED'}, {status: 'SKIPPED'}, {status: 'RUNNING'}, {status: 'PENDING'}]};
  assert.deepEqual(C.progress(run), {done: 2, total: 4, pct: 50});
  assert.equal(C.stepDuration(null), null);
  assert.equal(C.stepDuration({started: 10, ended: 12.5}), 2.5);
  assert.equal(C.stepDuration({started: 10}, 15), 5);
  assert.ok(C.stepDuration({started: Date.now() / 1000 - 1}) >= 0.9);
});

test('trial rows, Pareto flags and sorting', () => {
  const study = {trials: [{number: 1, state: 'COMPLETE', params: {x: 1}, values: {loss: 0.3}, duration_s: 1},
                          {number: 2, state: 'FAIL', error: 'oom'},
                          {number: 3, state: 'COMPLETE', params: {x: 2}, values: {loss: 0.1}}]};
  const rows = C.trialRows(study, [{number: 3}, {trial: 1}]);
  assert.deepEqual(rows.map(r => r.pareto), [true, false, true]);
  assert.equal(rows[1].error, 'oom');
  assert.deepEqual(C.trialRows(null, null), []);
  assert.deepEqual(C.sortRows(rows, 'loss', 'minimize').map(r => r.number), [3, 1, 2]);
  assert.deepEqual(C.sortRows(rows, 'loss', 'maximize').map(r => r.number), [1, 3, 2]);
  const noVals = [{number: 5, values: {}}, {number: 4, values: {}}];
  assert.deepEqual(C.sortRows(noVals, 'loss', 'minimize').map(r => r.number), [4, 5]);
  assert.deepEqual(C.sortRows([{number: 1, values: {}}, {number: 2, values: {loss: 1}}], 'loss', 'minimize').map(r => r.number), [2, 1]);
});

test('JSON fields, step modes and overrides', () => {
  assert.deepEqual(C.parseJSON(''), {ok: true, value: null});
  assert.deepEqual(C.parseJSON('{"a":1}'), {ok: true, value: {a: 1}});
  assert.equal(C.parseJSON('{').ok, false);
  assert.equal(C.defaultStepMode('bounded', 'human', 'low'), 'manual');
  assert.equal(C.defaultStepMode('bounded', 'execution', 'high'), 'automatic');
  assert.equal(C.defaultStepMode('manual', 'execution', 'high'), 'manual');
  assert.equal(C.defaultStepMode('manual', 'deterministic', 'low'), 'assisted');
  assert.equal(C.defaultStepMode('assisted', 'execution', 'high'), 'manual');
  assert.equal(C.defaultStepMode('assisted', 'agent', 'low'), 'assisted');
  assert.equal(C.defaultStepMode('assisted', 'deterministic', 'low'), 'automatic');
  const tpl = {execution_mode: 'assisted'};
  assert.deepEqual(C.buildOverrides(tpl, {execution_mode: 'assisted', step_modes: {a: ''}, budgets: {max_trials: '', x: 'abc'}, approvals: {}}), {});
  assert.deepEqual(C.buildOverrides(tpl, {execution_mode: 'bounded', step_modes: {a: 'manual'}, budgets: {max_trials: '5'},
                                          approvals: {before_training: 'required'}}),
                   {execution_mode: 'bounded', step_modes: {a: 'manual'}, budgets: {max_trials: 5}, approvals: {before_training: 'required'}});
  assert.deepEqual(C.buildOverrides(tpl, {}), {});
  assert.equal(C.shouldPoll(true, true), true);
  assert.equal(C.shouldPoll(false, true), false);
});

test('browser build registers window.WFCORE', () => {
  const src = fs.readFileSync(path.join(__dirname, '../../frontend/app/wfcore.js'), 'utf8');
  const ctx = {self: {}};
  vm.runInNewContext(src, ctx, {filename: path.join(__dirname, '../../frontend/app/wfcore.js')});
  assert.equal(typeof ctx.self.WFCORE.fmtMB, 'function');
});

test('every app script parses', () => {
  const dir = path.join(__dirname, '../../frontend/app');
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.js'))) {
    assert.doesNotThrow(() => new vm.Script(fs.readFileSync(path.join(dir, f), 'utf8'), {filename: f}), f);
  }
});
