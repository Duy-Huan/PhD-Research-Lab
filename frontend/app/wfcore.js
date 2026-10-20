/* PhD Research Lab v4.1 — pure helpers shared by the lifecycle and workflow views (no DOM access, so they are unit
   tested with `node --test tests/frontend`). Browser: window.WFCORE · Node: module.exports. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WFCORE = api;
})(typeof self !== 'undefined' ? self : this, function () {
  const RUN_CLS = {SUCCEEDED: 'ok', RUNNING: 'run', WAITING_FOR_APPROVAL: 'warn', PAUSED: 'warn', READY: '', CREATED: '',
                   VALIDATING: '', FAILED: 'err', CANCELLED: 'err', BUDGET_EXCEEDED: 'err', PENDING: '', SKIPPED: 'muted'};
  const TERMINAL = ['SUCCEEDED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED'];
  const POLICY = {unload_after_task: 'Load → task → unload', keep_loaded: 'Keep loaded', idle_unload: 'Unload when idle'};
  const LABEL_CLS = {MEASURED: 'ok', ESTIMATED: 'warn', SYNTHETIC: 'muted', UNAVAILABLE: 'err', AI_SUGGESTION: 'ai',
                     AI_INTERPRETATION: 'ai'};

  function stateClass(s) { return Object.prototype.hasOwnProperty.call(RUN_CLS, s) ? RUN_CLS[s] : ''; }
  function isTerminal(s) { return TERMINAL.indexOf(s) >= 0; }
  function policyLabel(p) { return POLICY[p] || p || '—'; }
  function labelClass(l) { return LABEL_CLS[l] || ''; }

  function fmtDuration(s) {
    if (s === null || s === undefined || !isFinite(s) || s < 0) return '—';
    if (s < 1) return Math.round(s * 1000) + ' ms';
    if (s < 60) return (s < 10 ? s.toFixed(1) : Math.round(s)) + ' s';
    const m = Math.floor(s / 60), r = Math.round(s % 60);
    if (m < 60) return m + ' min' + (r ? ' ' + r + ' s' : '');
    const h = Math.floor(m / 60);
    return h + ' h ' + (m % 60) + ' min';
  }

  function fmtMB(mb) {
    if (mb === null || mb === undefined || !isFinite(mb)) return '—';
    return mb >= 1024 ? (mb / 1024).toFixed(1) + ' GB' : Math.round(mb) + ' MB';
  }

  function fmtNum(v) {
    if (typeof v !== 'number' || !isFinite(v)) return v === null || v === undefined ? '—' : String(v);
    if (Number.isInteger(v)) return String(v);
    const a = Math.abs(v);
    if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(3);
    return String(Number(v.toPrecision(5)));
  }

  function vramPct(used, total) {
    if (!total || used === null || used === undefined) return null;
    return Math.max(0, Math.min(100, Math.round(used / total * 100)));
  }

  /* What happens next with a resident model / tracked resource (one line for the UI). */
  function releaseLabel(row) {
    if (!row) return '';
    if (row.leases > 0) return 'in use (' + row.leases + ')';
    if (row.owner === 'external' && !row.policy) return 'loaded outside PhD-Lab — kept';
    if (row.owner === 'external') return 'yours (loaded before PhD-Lab needed it) — kept';
    if (row.release_in_s === null || row.release_in_s === undefined) return row.policy === 'keep_loaded' ? 'kept loaded' : 'kept';
    return 'releases in ' + fmtDuration(row.release_in_s);
  }

  function progress(run) {
    const steps = (run && run.steps) || [];
    const done = steps.filter(s => ['SUCCEEDED', 'FAILED', 'SKIPPED', 'CANCELLED'].indexOf(s.status) >= 0).length;
    return {done: done, total: steps.length, pct: steps.length ? Math.round(done / steps.length * 100) : 0};
  }

  function stepDuration(st, now) {
    if (!st || !st.started) return null;
    return ((st.ended || now || Date.now() / 1000) - st.started);
  }

  /* Trials of a study → rows for the table; Pareto members flagged. */
  function trialRows(study, pareto) {
    const inFront = new Set((pareto || []).map(t => t.number !== undefined ? t.number : t.trial));
    return ((study && study.trials) || []).map(t => ({number: t.number, state: t.state, params: t.params || {},
      values: t.values || {}, pareto: inFront.has(t.number), duration_s: t.duration_s, error: t.error || ''}));
  }

  function sortRows(rows, metric, direction) {
    const sign = direction === 'maximize' ? -1 : 1;
    return rows.slice().sort((a, b) => {
      const x = a.values[metric], y = b.values[metric];
      const fx = typeof x === 'number' && isFinite(x), fy = typeof y === 'number' && isFinite(y);
      if (fx && fy) return sign * (x - y);
      if (fx) return -1;
      if (fy) return 1;
      return a.number - b.number;
    });
  }

  function parseJSON(text) {
    const t = (text || '').trim();
    if (!t) return {ok: true, value: null};
    try { return {ok: true, value: JSON.parse(t)}; } catch (e) { return {ok: false, error: e.message}; }
  }

  /* Effective autonomy of a step (mirror of backend schema.default_step_mode, for the builder preview). */
  function defaultStepMode(execMode, kind, risk) {
    if (kind === 'human') return 'manual';
    if (execMode === 'bounded') return 'automatic';
    if (execMode === 'manual') return risk === 'high' ? 'manual' : 'assisted';
    if (risk === 'high') return 'manual';
    return kind === 'agent' ? 'assisted' : 'automatic';
  }

  /* Overrides object for POST /api/workflows/runs from the builder state. */
  function buildOverrides(tpl, state) {
    const ov = {};
    if (state.execution_mode && state.execution_mode !== tpl.execution_mode) ov.execution_mode = state.execution_mode;
    const modes = {};
    Object.keys(state.step_modes || {}).forEach(k => { if (state.step_modes[k]) modes[k] = state.step_modes[k]; });
    if (Object.keys(modes).length) ov.step_modes = modes;
    const b = {};
    Object.keys(state.budgets || {}).forEach(k => {
      const v = state.budgets[k];
      if (v !== '' && v !== null && v !== undefined && isFinite(+v)) b[k] = +v;
    });
    if (Object.keys(b).length) ov.budgets = b;
    if (state.approvals && Object.keys(state.approvals).length) ov.approvals = Object.assign({}, state.approvals);
    return ov;
  }

  function shouldPoll(visible, tabOn) { return !!(visible && tabOn); }

  return {stateClass, isTerminal, policyLabel, labelClass, fmtDuration, fmtMB, fmtNum, vramPct, releaseLabel, progress,
          stepDuration, trialRows, sortRows, parseJSON, defaultStepMode, buildOverrides, shouldPoll, POLICY};
});
