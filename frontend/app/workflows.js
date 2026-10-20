/* PhD Research Lab v4.1 — 🧭 Workflows: templates (manual / assisted / bounded / custom), per-step autonomy, budgets,
   approval gates, live run timeline (SSE), approvals (approve / edit / revise / reject / provide result), pause / resume /
   cancel, HPO trials with the Pareto front, export. The page opens no stream while it is hidden. */
(() => {
  const T = s => I18N.tr(s);
  const C = window.WFCORE;
  const W = {tpls: [], types: {}, features: {}, engines: null, sel: null, run: null, es: null, seq: 0, timer: null, studies: {}};
  const root = () => $('#tab-workflows');
  const MODES = [['manual', 'Manual'], ['assisted', 'Assisted'], ['bounded', 'Bounded automation'], ['custom', 'Custom']];
  const STEP_MODES = [['', 'default'], ['automatic', 'automatic'], ['assisted', 'assisted (review result)'], ['manual', 'manual (you start it)']];
  const MODE_HELP = {
    manual: 'You control every important transition: each result is reviewed, consequential steps wait for you.',
    assisted: 'Recommended: the harness plans and does low-risk work; you approve proposals and consequential steps.',
    bounded: 'Runs a predefined workflow within hard limits (trials, cycles, runtime) and stops at configured gates.',
    custom: 'You choose the autonomy of every step (manual, assisted, automatic).'};

  function build() {
    root().innerHTML = `<div class="v3sec wf">
      <h2>🧭 ${T('Workflows')}</h2>
      <p class="lead">${T('Automate repetitive execution, not scientific responsibility. Pick a workflow, choose how much autonomy it gets, set hard budgets — every consequential step waits for your decision.')}</p>
      <div id="wf-engines" class="status"></div>
      <div class="wf-grid">
        <aside class="wf-side">
          <div class="card"><h4>${T('Templates')}</h4><div id="wf-tpls"><span class="spin"></span></div></div>
          <div class="card" style="margin-top:12px"><h4 class="row"><span>${T('Runs')}</span><button class="btn small" id="wf-runs-refresh" style="flex:0">↻</button></h4><div id="wf-runs"></div></div>
        </aside>
        <section class="wf-main" id="wf-main"><div class="card"><p class="status">${T('Choose a template on the left, or open a run.')}</p></div></section>
      </div></div>`;
    $('#wf-runs-refresh').onclick = loadRuns;
  }

  async function load() {
    try {
      const [t, a] = await Promise.all([api('/api/workflows/templates'), api('/api/model/adapters')]);
      W.tpls = t.templates; W.features = t.features; W.engines = a.engines;
      W.types = Object.fromEntries(t.step_types.map(s => [s.name, s]));
    } catch (e) { $('#wf-tpls').innerHTML = `<p class="status">⚠ ${esc(e.message)}</p>`; return; }
    const en = W.engines;
    $('#wf-engines').innerHTML = `HPO: Optuna ${en.optuna.usable ? '<span class="badge ok">' + esc(en.optuna.version) + '</span>' : '<span class="badge">' + T('not installed — builtin random/grid') + '</span>'}
      · Ray Tune <span class="badge">${esc(T(en.ray.installed ? 'installed, not validated' : 'not installed'))}</span>
      · ${T('local sequential runner')} <span class="badge ok">${T('ready')}</span>`;
    $('#wf-tpls').innerHTML = W.tpls.map((t, i) => `<button class="wf-tpl" data-tpl="${i}"><b>${esc(T(t.name))}</b>
        <span class="status" style="margin:0">${esc(T(t.execution_mode))} · ${t.steps.length} ${T('steps')}${t.builtin ? '' : ' · ' + T('mine')}</span></button>`).join('');
    $$('#wf-tpls [data-tpl]').forEach(b => b.onclick = () => showTemplate(W.tpls[+b.dataset.tpl]));
    loadRuns();
  }

  async function loadRuns() {
    try {
      const r = await api('/api/workflows/runs?limit=30');
      $('#wf-runs').innerHTML = r.runs.length ? r.runs.map(x => `<button class="wf-run" data-run="${esc(x.id)}">
          <span class="badge ${C.stateClass(x.status)}">${esc(T(x.status))}</span> <b>${esc(T(x.name || x.workflow_id))}</b>
          <span class="status" style="margin:0">${x.steps_done}/${x.steps} · ${new Date(x.created * 1000).toLocaleString()}${x.parent ? ' · ' + T('nested') : ''}</span></button>`).join('')
        : `<p class="status">${T('No runs yet.')}</p>`;
      $$('#wf-runs [data-run]').forEach(b => b.onclick = () => openRun(b.dataset.run));
    } catch (e) { $('#wf-runs').innerHTML = `<p class="status">⚠ ${esc(e.message)}</p>`; }
  }

  // ---------------------------------------------------------------- template builder
  function showTemplate(t) {
    closeStream();
    W.sel = {tpl: t, state: {execution_mode: t.execution_mode, step_modes: {}, budgets: {}, approvals: {}}};
    const inputs = Object.fromEntries(Object.entries(t.inputs || {}).map(([k, v]) => [k, v.default !== undefined ? v.default : (v.type === 'string' ? '' : null)]));
    $('#wf-main').innerHTML = `<div class="card">
      <h3 style="margin:0 0 4px">${esc(T(t.name))} <span class="status">v${t.version} · <code>${esc(t.id)}</code></span></h3>
      <p class="status">${esc(T(t.description || ''))}</p>
      <label>${T('Execution mode')}</label>
      <div class="seg2 wf-modes">${MODES.map(([k, l]) => `<button data-mode="${k}" class="${k === t.execution_mode ? 'on' : ''}">${T(l)}</button>`).join('')}</div>
      <p class="status" id="wf-mode-help">${T(MODE_HELP[t.execution_mode])}</p>
      <h4>${T('Steps')}</h4>
      <table class="dtable"><thead><tr><th>#</th><th>${T('Step')}</th><th>${T('Type')}</th><th>${T('Risk')}</th><th>${T('Autonomy')}</th></tr></thead>
        <tbody>${t.steps.map((s, i) => { const ty = W.types[s.type] || {}; return `<tr><td>${i + 1}</td><td>${esc(T(s.label))}</td><td><code>${esc(s.type)}</code></td>
          <td><span class="badge ${ty.risk === 'high' ? 'warn' : ''}">${esc(T(ty.risk || ''))}</span></td>
          <td>${ty.kind === 'human' ? `<span class="badge">${T('you decide')}</span>` : `<select data-smode="${esc(s.id)}">${STEP_MODES.map(([k, l]) => `<option value="${k}" ${s.mode === k && k ? 'selected' : ''}>${T(l)}</option>`).join('')}</select>
            <span class="status" data-eff="${esc(s.id)}" style="margin:0"></span>`}</td></tr>`; }).join('')}</tbody></table>
      <h4>${T('Budgets (hard limits)')}</h4>
      <div class="wf-budgets">${[['max_trials', 'Max trials'], ['max_workflow_cycles', 'Max cycles'], ['max_parallel_trials', 'Parallel trials'],
        ['max_runtime_minutes', 'Max runtime (min)'], ['max_gpu_memory_gb', 'Max GPU memory (GB)'], ['max_agent_calls', 'Max agent calls']]
        .map(([k, l]) => `<label>${T(l)}<input type="number" min="0" data-budget="${k}" placeholder="${esc(String((t.budgets || {})[k] ?? ''))}"></label>`).join('')}</div>
      <p class="status">${T('On a single consumer GPU keep one parallel trial: training trials always run one at a time.')}</p>
      <h4>${T('Approval gates')}</h4>
      ${[['before_training', 'Before training / expensive compute'], ['before_parallel_gpu_trials', 'Before parallel GPU trials'],
        ['before_research_state_writeback', 'Before proposing research-state updates'], ['before_conclusion', 'Before accepting AI conclusions']]
        .map(([k, l]) => `<label class="chk"><input type="checkbox" data-appr="${k}" ${((t.approvals || {})[k] || 'required') === 'required' ? 'checked' : ''}> ${T(l)}</label>`).join('')}
      <h4>${T('Inputs')} <span class="status">JSON</span></h4>
      <textarea id="wf-inputs" rows="8" class="mono" spellcheck="false">${esc(JSON.stringify(inputs, null, 2))}</textarea>
      <div class="status" id="wf-val"></div>
      <div class="row" style="gap:8px;margin-top:10px;flex-wrap:wrap"><span style="flex:1"></span>
        <button class="btn" id="wf-export" style="flex:0">⤓ ${T('Export JSON')}</button>
        <button class="btn" id="wf-validate" style="flex:0">${T('Validate')}</button>
        <button class="btn primary" id="wf-start" style="flex:0">▶ ${T('Start run')}</button></div></div>`;
    $$('#wf-main [data-mode]').forEach(b => b.onclick = () => {
      W.sel.state.execution_mode = b.dataset.mode;
      $$('#wf-main [data-mode]').forEach(x => x.classList.toggle('on', x === b));
      $('#wf-mode-help').textContent = T(MODE_HELP[b.dataset.mode]);
      effModes();
    });
    $$('#wf-main [data-smode]').forEach(s => s.onchange = () => { W.sel.state.step_modes[s.dataset.smode] = s.value; effModes(); });
    effModes();
    $('#wf-validate').onclick = e => busy(e.target, validate);
    $('#wf-start').onclick = e => busy(e.target, startRun);
    $('#wf-export').onclick = () => download(`${t.id}-v${t.version}.json`, JSON.stringify(t, null, 2));
  }

  function effModes() {
    const t = W.sel.tpl, st = W.sel.state;
    t.steps.forEach(s => {
      const el = $(`[data-eff="${s.id}"]`), ty = W.types[s.type] || {};
      if (!el) return;
      const m = st.step_modes[s.id] || s.mode || C.defaultStepMode(st.execution_mode, ty.kind, ty.risk);
      el.textContent = st.step_modes[s.id] ? '' : '→ ' + T(m);
    });
  }

  function collect() {
    const st = W.sel.state;
    $$('#wf-main [data-budget]').forEach(i => { st.budgets[i.dataset.budget] = i.value; });
    $$('#wf-main [data-appr]').forEach(i => { st.approvals[i.dataset.appr] = i.checked ? 'required' : 'not_required'; });
    const inp = C.parseJSON($('#wf-inputs').value);
    if (!inp.ok) throw new Error(T('Inputs are not valid JSON') + ': ' + inp.error);
    return {inputs: inp.value || {}, overrides: C.buildOverrides(W.sel.tpl, st)};
  }

  async function validate() {
    const {overrides} = collect();
    const full = await api('/api/workflows/templates/' + W.sel.tpl.id + '?version=' + W.sel.tpl.version);
    if (overrides.execution_mode) full.execution_mode = overrides.execution_mode;
    full.budgets = {...(full.budgets || {}), ...(overrides.budgets || {})};
    full.approvals = {...(full.approvals || {}), ...(overrides.approvals || {})};
    (full.steps || []).forEach(s => { if ((overrides.step_modes || {})[s.id]) s.mode = overrides.step_modes[s.id]; });
    const r = await api('/api/workflows/validate', {method: 'POST', body: {definition: full}});
    $('#wf-val').innerHTML = r.valid ? `<span class="badge ok">${T('valid')}</span>` : r.errors.map(x => `<div>⚠ ${esc(x)}</div>`).join('');
  }

  async function startRun() {
    const {inputs, overrides} = collect();
    const r = await api('/api/workflows/runs', {method: 'POST', body: {workflow_id: W.sel.tpl.id, version: W.sel.tpl.version, inputs, overrides, start: true}});
    toast(T('Workflow started'), 'ok');
    loadRuns();
    openRun(r.id);
  }

  // ---------------------------------------------------------------- run view
  async function openRun(id) {
    closeStream();
    W.seq = 0;
    try { W.run = await api('/api/workflows/runs/' + id); } catch (e) { return toast(e.message, 'err'); }
    paintRun();
    if (!C.isTerminal(W.run.status)) stream(id);
  }

  function stream(id) {
    if (!window.EventSource) return poll(id);
    W.es = new EventSource(`/api/workflows/runs/${id}/stream?after=${W.seq}`);
    W.es.onmessage = ev => {
      let e; try { e = JSON.parse(ev.data); } catch { return; }
      if (e.type === 'end') { closeStream(); refreshRun(); return; }
      W.seq = Math.max(W.seq, e.seq || 0);
      addEvent(e);
      scheduleRefresh();
    };
    W.es.onerror = () => { closeStream(); setTimeout(() => W.run && !C.isTerminal(W.run.status) && $('#tab-workflows.on') && stream(W.run.id), 3000); };
  }
  function poll(id) { W.timer = setInterval(() => refreshRun(), 2000); }
  function closeStream() { if (W.es) { W.es.close(); W.es = null; } clearInterval(W.timer); W.timer = null; clearTimeout(W.deb); }
  function scheduleRefresh() { clearTimeout(W.deb); W.deb = setTimeout(refreshRun, 250); }  // one fetch per burst of events

  async function refreshRun() {
    if (!W.run) return;
    try { W.run = await api('/api/workflows/runs/' + W.run.id); } catch { return; }
    paintRun(true);
    if (C.isTerminal(W.run.status)) { closeStream(); loadRuns(); }
  }

  function paintRun(keepLog) {
    const r = W.run, pr = C.progress(r), bl = r.budget_left || {};
    const log = keepLog && $('#wf-log') ? $('#wf-log').innerHTML : '';
    $('#wf-main').innerHTML = `<div class="card">
      <div class="row" style="gap:8px;flex-wrap:wrap"><h3 style="margin:0;flex:1">${esc(T(r.name || r.workflow_id))} <span class="status">${esc(r.id)} · ${esc(T(r.execution_mode))}${r.parent ? ' · ' + T('nested in') + ' <a href="#" data-open="' + esc(r.parent.run_id) + '">' + esc(r.parent.run_id) + '</a>' : ''}</span></h3>
        <span class="badge ${C.stateClass(r.status)}">${esc(T(r.status))}</span>
        ${!C.isTerminal(r.status) && r.status !== 'PAUSED' ? `<button class="btn small" data-act="pause">⏸ ${T('Pause')}</button>` : ''}
        ${r.status === 'PAUSED' || r.status === 'READY' ? `<button class="btn small" data-act="resume">▶ ${T('Resume')}</button>` : ''}
        ${!C.isTerminal(r.status) ? `<button class="btn small danger" data-act="cancel">■ ${T('Cancel')}</button>` : ''}
        <button class="btn small" data-act="export">⤓ ${T('Export')}</button></div>
      <div class="bar"><i style="width:${pr.pct}%"></i></div>
      <div class="status">${pr.done}/${pr.total} ${T('steps')} · ${T('budget left')}: ${T('trials')} ${bl.trials ?? '∞'} · ${T('cycles')} ${bl.cycles ?? '∞'} · ${T('agent calls')} ${bl.agent_calls ?? '∞'} · ${T('runtime')} ${bl.runtime_min ?? '∞'} min
        ${r.recovered ? ' · ⚠ ' + T('recovered after an app restart — check the steps and resume') : ''}</div>
      ${r.error ? `<div class="status err">⚠ ${esc(r.error)}</div>` : ''}</div>
      ${approvalsHTML(r)}
      <div class="card" style="margin-top:12px"><h4>${T('Timeline')}</h4><ol class="wf-steps">${r.steps.map(stepHTML).join('')}</ol></div>
      <div id="wf-trials"></div>
      ${Object.keys(r.outputs || {}).length ? `<details class="card" style="margin-top:12px" open><summary><b>${T('Outputs')}</b></summary><pre class="wf-json">${esc(JSON.stringify(r.outputs, null, 2))}</pre></details>` : ''}
      <details class="card" style="margin-top:12px"><summary><b>${T('Events')}</b></summary><div id="wf-log" class="wf-log">${log}</div></details>`;
    bindRun();
    const study = r.steps.map(s => s.output && s.output.study_id).find(Boolean);
    if (study) trials(study);
  }

  function approvalsHTML(r) {
    const local = r.steps.filter(s => s.status === 'WAITING_FOR_APPROVAL');
    const nested = (r.pending_approvals || []).filter(p => p.run_id !== r.id);
    if (!local.length && !nested.length) return '';
    return `<div class="card wf-appr" style="margin-top:12px"><h4>🛂 ${T('Waiting for your decision')}</h4>
      ${nested.map(p => `<p class="status">${T('Nested run')} <a href="#" data-open="${esc(p.run_id)}">${esc(p.run_id)}</a>: ${esc(T(p.label))}</p>`).join('')}
      ${local.map(s => { const a = s.approval || {}, ty = W.types[s.type] || {}; return `<div class="wf-gate" data-gate="${esc(s.id)}">
        <b>${esc(T(s.label))}</b> <span class="badge ${a.risk === 'high' ? 'warn' : ''}">${esc(T(a.phase === 'after' ? 'review result' : a.phase === 'input' ? 'your input' : 'before running'))}</span>
        <div class="status">${esc(T(a.reason || ''))}${a.question ? ' — ' + esc(T(a.question)) : ''}</div>
        ${a.phase === 'before' && a.planned_params ? `<label>${T('Planned parameters (edit before approving)')}</label><textarea rows="6" class="mono" data-pp>${esc(JSON.stringify(a.planned_params, null, 2))}</textarea>` : ''}
        ${a.phase === 'after' ? `<label>${T('Result (edit before accepting)')}</label><textarea rows="8" class="mono" data-out>${esc(JSON.stringify(s.output, null, 2))}</textarea>${(s.warnings || []).length ? `<div class="status err">${s.warnings.map(esc).join('<br>')}</div>` : ''}` : ''}
        ${a.phase === 'input' && a.show ? `<pre class="wf-json">${esc(JSON.stringify(a.show, null, 2)).slice(0, 6000)}</pre>` : ''}
        ${s.type === 'human.input' ? `<label>${T('Your values')} (JSON)</label><textarea rows="4" class="mono" data-vals>${esc(JSON.stringify(Object.fromEntries(Object.keys(a.fields || {}).map(k => [k, ''])), null, 2))}</textarea>` : ''}
        ${a.budget_left ? `<div class="status">${T('budget left')}: ${esc(JSON.stringify(a.budget_left))}</div>` : ''}
        <label>${T('Note')}</label><input type="text" data-note placeholder="${esc(T('reason, feedback for a revision…'))}">
        <div class="row" style="gap:6px;margin-top:8px;flex-wrap:wrap"><span style="flex:1"></span>
          ${ty.kind === 'agent' && a.phase === 'after' ? `<button class="btn small" data-dec="revise">↻ ${T('Revise with my note')}</button>` : ''}
          ${a.phase === 'before' ? `<button class="btn small" data-dec="provide">✍ ${T('I did it myself (provide result)')}</button>` : ''}
          <button class="btn small danger" data-dec="reject">✕ ${T('Reject')}</button>
          <button class="btn small primary" data-dec="approve">✓ ${T(s.type === 'human.input' ? 'Submit' : a.phase === 'before' ? 'Approve & run' : 'Approve')}</button></div></div>`; }).join('')}</div>`;
  }

  function stepHTML(s) {
    const d = C.stepDuration(s);
    const out = s.output ? JSON.stringify(s.output, null, 2) : '';
    return `<li class="wf-step ${C.stateClass(s.status)}"><div class="row" style="gap:8px">
        <span class="badge ${C.stateClass(s.status)}">${esc(T(s.status))}</span><b style="flex:1">${esc(T(s.label))}</b>
        <code class="status" style="margin:0">${esc(s.type)}</code><span class="status" style="margin:0">${esc(T(s.mode))} · ${C.fmtDuration(d)}${s.attempts > 1 ? ' · ' + s.attempts + '×' : ''}${s.provided_by ? ' · ' + T('provided by you') : ''}</span></div>
      ${s.error ? `<div class="status err">${esc(s.error)}</div>` : ''}
      ${(s.checkpoint || {}).child_run_id || (s.checkpoint || {}).child ? `<div class="status">${T('nested run')}: <a href="#" data-open="${esc((s.checkpoint.child_run_id || s.checkpoint.child))}">${esc(s.checkpoint.child_run_id || s.checkpoint.child)}</a></div>` : ''}
      ${out ? `<details><summary class="status">${T('output')}${s.output.label ? ' · ' + esc(s.output.label) : ''}</summary><pre class="wf-json">${esc(out.slice(0, 20000))}</pre></details>` : ''}</li>`;
  }

  function bindRun() {
    $$('#wf-main [data-act]').forEach(b => b.onclick = () => busy(b, async () => {
      if (b.dataset.act === 'export') {
        const x = await api(`/api/workflows/runs/${W.run.id}/export`);
        return download(`${W.run.id}.json`, JSON.stringify(x, null, 2));
      }
      if (b.dataset.act === 'cancel' && !confirm(T('Cancel this run? Running steps and sandbox jobs are stopped.'))) return;
      W.run = await api(`/api/workflows/runs/${W.run.id}/${b.dataset.act}`, {method: 'POST'});
      paintRun(true);
      if (b.dataset.act === 'resume' && !W.es) stream(W.run.id);
    }, '…'));
    $$('#wf-main [data-open]').forEach(a => a.onclick = e => { e.preventDefault(); openRun(a.dataset.open); });
    $$('#wf-main [data-gate]').forEach(g => g.querySelectorAll('[data-dec]').forEach(b => b.onclick = () => busy(b, async () => {
      const body = {decision: b.dataset.dec, note: g.querySelector('[data-note]').value};
      const pp = g.querySelector('[data-pp]'), out = g.querySelector('[data-out]'), vals = g.querySelector('[data-vals]');
      if (pp && b.dataset.dec === 'approve') {
        const p = C.parseJSON(pp.value); if (!p.ok) throw new Error(T('Parameters are not valid JSON'));
        const step = W.run.steps.find(s => s.id === g.dataset.gate), orig = JSON.stringify((step.approval || {}).planned_params);
        if (JSON.stringify(p.value) !== orig) body.params_patch = p.value;
      }
      if (out && b.dataset.dec === 'approve') {
        const p = C.parseJSON(out.value); if (!p.ok) throw new Error(T('Result is not valid JSON'));
        const step = W.run.steps.find(s => s.id === g.dataset.gate);
        if (JSON.stringify(p.value) !== JSON.stringify(step.output)) body.output = p.value;
      }
      if (b.dataset.dec === 'provide') {
        const v = prompt(T('Result of the step (JSON)'), '{}'); if (v === null) return;
        const p = C.parseJSON(v); if (!p.ok) throw new Error(T('Result is not valid JSON'));
        body.output = p.value || {};
      }
      if (vals) { const p = C.parseJSON(vals.value); if (!p.ok) throw new Error(T('Values are not valid JSON')); body.values = p.value || {}; }
      W.run = await api(`/api/workflows/runs/${W.run.id}/steps/${g.dataset.gate}/decision`, {method: 'POST', body});
      paintRun(true);
      if (!W.es && !C.isTerminal(W.run.status)) stream(W.run.id);
    }, '…')));
  }

  async function trials(studyId) {
    let st;
    try { st = await api('/api/workflows/studies/' + studyId); } catch { return; }
    const objs = st.objectives || [], sum = st.summary || {};
    const rows = C.sortRows(C.trialRows(st, sum.pareto), objs[0].name, objs[0].direction);
    const pnames = [...new Set(rows.flatMap(r => Object.keys(r.params)))];
    $('#wf-trials').innerHTML = `<div class="card" style="margin-top:12px"><h4>🎛 ${T('Study')} <code>${esc(st.id)}</code>
        <span class="status">${esc(st.engine || '')} · ${esc(st.sampler_effective || '')} · ${sum.n_complete}/${sum.n_trials} ${T('complete')} · ${sum.n_pruned} ${T('pruned')} · ${sum.n_failed} ${T('failed')}</span>
        ${sum.measurement ? `<span class="badge ${C.labelClass(sum.measurement)}">${esc(sum.measurement)}</span>` : ''}</h4>
      <p class="status">${esc(T(sum.caveat || ''))} ${objs.length > 1 ? '★ = ' + T('Pareto front (non-dominated)') : ''}</p>
      <div class="wf-tablewrap"><table class="dtable"><thead><tr><th>#</th><th>${T('state')}</th>${objs.map(o => `<th>${esc(o.name)} ${o.direction === 'maximize' ? '↑' : '↓'}</th>`).join('')}${pnames.map(p => `<th>${esc(p)}</th>`).join('')}<th>s</th></tr></thead>
      <tbody>${rows.slice(0, 200).map(r => `<tr class="${r.pareto ? 'wf-pareto' : ''}"><td>${r.pareto && objs.length > 1 ? '★ ' : ''}${r.number}</td><td><span class="badge ${r.state === 'COMPLETE' ? 'ok' : r.state === 'FAIL' ? 'err' : ''}" title="${esc(r.error)}">${esc(r.state)}</span></td>
        ${objs.map(o => `<td>${C.fmtNum(r.values[o.name])}</td>`).join('')}${pnames.map(p => `<td>${C.fmtNum(r.params[p])}</td>`).join('')}<td>${C.fmtNum(r.duration_s)}</td></tr>`).join('')}</tbody></table></div></div>`;
  }

  function addEvent(e) {
    const log = $('#wf-log');
    if (!log) return;
    log.insertAdjacentHTML('afterbegin', `<div><span class="status">${new Date(e.ts * 1000).toLocaleTimeString()}</span> <b>${esc(e.type)}</b> ${esc(e.step_id || '')} ${e.error ? '⚠ ' + esc(String(e.error).slice(0, 200)) : ''}${e.trial ? ' #' + e.trial : ''}</div>`);
    while (log.children.length > 200) log.lastChild.remove();
  }

  function download(name, text) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], {type: 'application/json'}));
    a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function init() {
    if (!root().dataset.built) { build(); root().dataset.built = '1'; }
    load();
    if (W.run && !C.isTerminal(W.run.status) && !W.es) stream(W.run.id);
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'workflows') init(); else closeStream(); });
  window.WORKFLOWS = {init, openRun};
})();
