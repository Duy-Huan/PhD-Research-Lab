/* PhD Research Lab v3.2 — 🧭 Research Control Center: dashboard, research timeline (hypothesis → experiment → result →
   decision), workspace hand-off (VS Code / Dev Container / Jupyter), integration status, Codex runs, hardware policy,
   provenance inspector, Context-Memory inspector and dataset connectors.
   Everything shown comes from the backend; unavailable integrations are labelled as such — nothing is simulated. */
(() => {
  const T = s => I18N.tr(s);
  const S = {inited: false, sub: 'dash', integ: null, dash: null, ws: null, timer: null, codexTimer: null};
  const root = () => $('#tab-control');
  const led = st => `<span class="led ${st === 'available' ? 'ok' : st === 'disabled' || st === 'unconfigured' ? 'warn' : 'err'}"></span>`;
  const chip = (t, cls = '') => `<span class="ccchip ${cls}">${esc(t)}</span>`;
  const fmt = v => typeof v === 'number' ? (Math.abs(v) >= 1000 || Number.isInteger(v) ? String(v) : v.toPrecision(4)) : esc(v ?? '–');
  const when = ts => ts ? esc(String(ts).replace('T', ' ').slice(0, 16)) : '';
  const empty = msg => `<div class="status">${esc(T(msg))}</div>`;
  const SUBS = [['dash', '🏠 Dashboard'], ['timeline', '🧭 Research timeline'], ['workspace', '💻 Workspace'], ['integrations', '🔌 Integrations'],
    ['codex', '🤖 Codex'], ['resources', '⚙ Resources'], ['provenance', '🛡 Provenance'], ['memory', '🧠 Memory inspector'], ['datasets', '🧬 Datasets']];

  function build() {
    root().innerHTML = `<div class="v3sec">
      <div class="row" style="align-items:flex-start;flex-wrap:wrap;gap:10px;margin-bottom:8px">
        <div style="flex:1;min-width:280px"><h2 style="margin:0 0 4px">🧭 ${T('Research Control Center')}</h2>
          <p class="lead" style="margin:0">${T('The research control plane: hypotheses, experiments and their evidence, and hand-offs to VS Code, Docker, Jupyter, ClearML and Codex. Each integration shows its real status.')}</p></div>
        <div style="flex:0 0 auto"><button class="btn small" id="cc-refresh">↻ ${T('Refresh')}</button></div></div>
      <div class="ccnav">${SUBS.map(([k, l]) => `<button data-sub="${k}" class="${k === S.sub ? 'on' : ''}">${T(l)}</button>`).join('')}</div>
      <div id="cc-body"></div></div>`;
    root().querySelectorAll('.ccnav button').forEach(b => b.onclick = () => show(b.dataset.sub));
    $('#cc-refresh').onclick = () => { S.integ = null; show(S.sub, true); };
  }

  function show(sub, force) {
    S.sub = sub;
    root().querySelectorAll('.ccnav button').forEach(b => b.classList.toggle('on', b.dataset.sub === sub));
    try { localStorage.setItem('cc_sub', sub); } catch {}
    // each view renders into its own box: a slow earlier view that finishes late writes into a detached box, never over this one
    const body = document.createElement('div');
    $('#cc-body').replaceChildren(body);
    body.innerHTML = '<div class="status"><span class="spin"></span>' + T('Loading…') + '</div>';
    ({dash: renderDash, timeline: renderTimeline, workspace: renderWorkspace, integrations: renderIntegrations, codex: renderCodex,
      resources: renderResources, provenance: renderProvenance, memory: renderMemory, datasets: renderDatasets}[sub])(body, force)
      .catch(e => { body.innerHTML = `<div class="card"><b>⚠ ${esc(e.message)}</b></div>`; });
  }

  async function integrations(force) {
    if (!S.integ || force) S.integ = (await api('/api/integrations' + (force ? '?force=1' : ''))).integrations;
    return S.integ;
  }

  // ------------------------------------------------------------------ dashboard
  async function renderDash(body) {
    const d = await api('/api/dashboard'); S.dash = d;
    const g = d.gpu;
    const hyp = d.hypotheses.filter(h => ['testing', 'proposed'].includes(h.status));
    const best = Object.entries(d.best_metrics || {});
    body.innerHTML = `<div class="dgrid">
      <div class="dcard"><h5>📚 ${T('Project')}</h5><div class="big">${esc(d.project.name)}</div>
        <div class="status" style="margin:0">${(d.goals || []).map(g => esc(g.slice(0, 160))).join('<br>') || T('No research goal yet — generate a plan in Lit2Plan.')}</div></div>
      <div class="dcard"><h5>🧪 ${T('Current hypotheses')}</h5>${hyp.length ? hyp.slice(0, 4).map(h => `<div class="ccline">${chip(h.id, 'id')} ${chip(h.status, h.status)} ${esc(h.text.slice(0, 120))}</div>`).join('') : empty('No open hypothesis.')}
        <div class="status">${d.hypotheses_total} ${T('in Research Memory')}</div></div>
      <div class="dcard"><h5>🚀 ${T('Active experiments')}</h5>${d.active_jobs.length ? d.active_jobs.map(j => `<div class="ccline">▶ <code>${esc(j.cmd.slice(0, 60))}</code> · ${esc(j.mode)} · ${Math.round(j.duration || 0)} s</div>`).join('') : empty('Nothing running.')}
        ${d.experiments.length ? `<div class="status">${T('Latest records')}: ${d.experiments.slice(0, 3).map(e => esc(e.id + ' ' + (e.verdict || 'open'))).join(' · ')}</div>` : ''}</div>
      <div class="dcard"><h5>🏆 ${T('Best results')}</h5>${best.length ? `<div class="kv">${best.slice(0, 8).map(([k, v]) => `<span>${esc(k)}</span><span>${fmt(v.value)} <span class="status">(${esc(v.direction)}, run ${esc(String(v.run).slice(-9))})</span></span>`).join('')}</div>` : empty('No successful run with metrics yet.')}</div>
      <div class="dcard"><h5>💥 ${T('Failures')}</h5>${(d.failures.length || d.failed_runs.length) ? d.failures.slice(0, 3).map(f => `<div class="ccline">${chip(f.id, 'id')} ${esc(f.text.slice(0, 100))}</div>`).join('') + d.failed_runs.slice(0, 3).map(r => `<div class="ccline">✗ run ${esc(r.id.slice(-9))} <code>${esc((r.cmd || '').slice(0, 50))}</code></div>`).join('') : empty('No recorded failure.')}</div>
      <div class="dcard"><h5>🎮 GPU ${d.gpu_busy ? chip(T('busy — local LLMs off the GPU'), 'testing') : ''}</h5>${g ? `<div class="kv"><span>GPU</span><span>${esc(g.name)}</span><span>VRAM</span><span>${Math.round(g.vram_used_mb || 0)} / ${Math.round(g.vram_total_mb || 0)} MB</span><span>${T('Load')}</span><span>${fmt(g.util_pct)} %</span><span>${T('Temp')}</span><span>${fmt(g.temp_c)} °C</span></div>` : empty('No NVIDIA GPU detected (CPU only).')}</div>
      <div class="dcard"><h5>🧠 ${T('Context Memory')}</h5><div class="kv"><span>${T('Short-term')}</span><span>${d.memory.tier1_tokens.toLocaleString()} / ${d.memory.high.toLocaleString()} ${T('tokens')}</span>
        <span>${T('Episodes')}</span><span>${d.memory.episodes}</span><span>${T('Last compression')}</span><span>${when(d.memory.last_summary) || '–'}</span></div></div>
      <div class="dcard"><h5>🔌 ${T('Integrations')}</h5><div id="cc-dash-integ"><span class="spin"></span></div></div>
      </div>
      <div class="card dsec"><h4>🧭 ${T('Latest research events')} <button class="btn small" data-go="timeline" style="margin-left:auto">${T('Open timeline')} →</button></h4>${timelineHtml(d.timeline.slice().reverse())}</div>`;
    body.querySelector('[data-go]').onclick = () => show('timeline');
    integrations().then(list => {
      const el = $('#cc-dash-integ'); if (!el) return;
      el.innerHTML = list.map(s => `<div class="ccline" title="${esc(s.detail)}">${led(s.state)} ${esc(s.label)} <span class="status" style="margin:0">${esc(T(s.state))}</span></div>`).join('');
    }).catch(e => { const el = $('#cc-dash-integ'); if (el) el.textContent = e.message; });
  }

  // ------------------------------------------------------------------ research timeline
  const KIND_ICON = {hypothesis: '🧪', experiment: '🔬', failure: '💥', decision: '🔒'};
  function timelineHtml(events) {
    if (!events.length) return empty('No research events yet. Add a hypothesis (or generate a plan in Lit2Plan), then record experiments against it.');
    return `<div class="cctl">${events.map(e => `<div class="cctl-ev ${e.kind}">
      <div class="cctl-dot">${KIND_ICON[e.kind] || '•'}</div>
      <div class="cctl-main"><div class="ccline">${chip(e.id, 'id')} ${chip(e.status || '', e.status || '')} <b>${esc(e.title)}</b> <span class="status" style="margin:0">${when(e.ts)}</span></div>
        ${(e.links || []).length ? `<div class="ccline">${e.links.map(l => chip(l, 'link')).join(' ')}${e.clearml_url ? ` <a href="${esc(e.clearml_url)}" target="_blank" rel="noopener">${T('Open in ClearML')} ↗</a>` : ''}</div>` : ''}
        ${e.metrics && Object.keys(e.metrics).length ? `<div class="status" style="margin:2px 0">${Object.entries(e.metrics).slice(0, 6).map(([k, v]) => `${esc(k)}=${fmt(v)}`).join(' · ')}</div>` : ''}
        ${e.detail ? Object.entries(e.detail).map(([k, v]) => `<div class="ccdetail"><span>${esc(T(k.replace('_', ' ')))}</span> ${esc(v)}</div>`).join('') : ''}
      </div></div>`).join('')}</div>`;
  }

  async function renderTimeline(body) {
    const [tl, rs, runs] = await Promise.all([api('/api/research/timeline'), api('/api/research'), api('/api/sandbox/runs')]);
    const hypOpts = rs.hypotheses.map(h => `<option value="${esc(h.id)}">${esc(h.id)} · ${esc(h.text.slice(0, 70))}</option>`).join('');
    const runOpts = runs.runs.slice(0, 40).map(r => `<option value="${esc(r.id)}">${esc(r.id)} · ${esc(r.status)} · ${esc((r.cmd || '').slice(0, 40))}</option>`).join('');
    body.innerHTML = `<div class="cxgrid" style="grid-template-columns:minmax(0,1.5fr) minmax(320px,1fr)">
      <div class="card"><h4>🧭 ${T('Research timeline')} <span class="status" style="margin:0">${T('paper/finding → hypothesis → experiment → result/failure → interpretation → decision → next experiment')}</span></h4>${timelineHtml(tl.events.slice().reverse())}</div>
      <div>
        <div class="card"><h4>🧪 ${T('New hypothesis')}</h4><textarea id="cc-hyp" rows="3" placeholder="${esc(T('A falsifiable statement, e.g. Spectral attention improves PSNR on Pavia by ≥ 0.5 dB'))}"></textarea>
          <div class="row" style="margin-top:6px"><button class="btn primary small" id="cc-hyp-add" style="flex:0">＋ ${T('Add')}</button></div>
          ${rs.hypotheses.length ? `<table class="dtable" style="margin-top:8px">${rs.hypotheses.map(h => `<tr><td class="mono">${esc(h.id)}</td><td>${esc(h.text.slice(0, 110))}</td><td><select data-hstatus="${esc(h.id)}">${['proposed', 'testing', 'supported', 'refuted', 'inconclusive', 'abandoned'].map(s => `<option ${s === h.status ? 'selected' : ''}>${s}</option>`).join('')}</select></td></tr>`).join('')}</table>` : ''}</div>
        <div class="card dsec"><h4>🔬 ${T('Record an experiment')}</h4>
          <p class="status" style="margin-top:0">${T('Links the run (git commit, environment, measured metrics are copied from the run record) and the ClearML task to a hypothesis, with your interpretation. Numbers are never typed by an AI here.')}</p>
          <div class="dform">
            <div style="grid-column:1/-1"><label>${T('Title')}</label><input type="text" id="cc-e-title"></div>
            <div><label>${T('Hypothesis')}</label><select id="cc-e-hyp"><option value="">—</option>${hypOpts}</select></div>
            <div><label>${T('Run')}</label><select id="cc-e-run"><option value="">—</option>${runOpts}</select></div>
            <div><label>${T('ClearML task id')}</label><input type="text" id="cc-e-task" placeholder="${T('optional')}"></div>
            <div><label>${T('Dataset version')}</label><input type="text" id="cc-e-ds"></div>
            <div><label>${T('Verdict')}</label><select id="cc-e-verdict"><option value="">${T('open')}</option><option>supports</option><option>refutes</option><option>inconclusive</option></select></div>
          </div>
          ${['observation', 'interpretation', 'decision', 'conclusion', 'next_action'].map(k => `<label>${T(k.replace('_', ' '))}</label><textarea id="cc-e-${k}" rows="2"></textarea>`).join('')}
          <div class="row" style="margin-top:8px"><button class="btn primary" id="cc-e-add" style="flex:0">💾 ${T('Save record')}</button><button class="btn" id="cc-f-add" style="flex:0">💥 ${T('Save as validated failure')}</button></div></div>
      </div></div>`;
    $('#cc-hyp-add').onclick = e => busy(e.target, async () => { await api('/api/research/hypotheses', {method: 'POST', body: {text: $('#cc-hyp').value}}); toast(T('Hypothesis added'), 'ok'); show('timeline'); });
    body.querySelectorAll('[data-hstatus]').forEach(s => s.onchange = () => api(`/api/research/hypotheses/${s.dataset.hstatus}`, {method: 'PUT', body: {status: s.value}}).then(() => toast(T('Saved'), 'ok')).catch(e => toast(e.message, 'err')));
    const val = id => $('#' + id).value.trim();
    $('#cc-e-add').onclick = e => busy(e.target, async () => {
      const b = {title: val('cc-e-title'), hypothesis_id: val('cc-e-hyp'), run_id: val('cc-e-run'), clearml_task_id: val('cc-e-task'),
        dataset_version: val('cc-e-ds'), verdict: val('cc-e-verdict')};
      ['observation', 'interpretation', 'decision', 'conclusion', 'next_action'].forEach(k => b[k] = val('cc-e-' + k));
      const r = await api('/api/research/experiments', {method: 'POST', body: b}); toast(`${r.id} ${T('saved')}`, 'ok'); show('timeline');
    });
    $('#cc-f-add').onclick = e => busy(e.target, async () => {
      const r = await api('/api/research/failures', {method: 'POST', body: {text: val('cc-e-title') || val('cc-e-observation'), hypothesis_id: val('cc-e-hyp'),
        run_id: val('cc-e-run'), reason: val('cc-e-interpretation')}}); toast(`${r.id} ${T('saved')}`, 'ok'); show('timeline');
    });
  }

  // ------------------------------------------------------------------ workspace
  async function renderWorkspace(body) {
    const [w, opts] = await Promise.all([api('/api/workspace'), api('/api/workspace/environment/options')]);
    S.ws = w;
    const vs = w.vscode, g = w.git || {};
    const devOk = vs.ok && vs.extra && vs.extra.dev_containers_ext;
    body.innerHTML = `<div class="cxgrid" style="grid-template-columns:minmax(0,1fr) minmax(320px,1fr)">
      <div>
        <div class="card"><h4>💻 ${T('Code workspace')} ${led(vs.state)} <span class="status" style="margin:0">VS Code ${esc(vs.version || T(vs.state))}</span></h4>
          <div class="kv ccv"><span>${T('Folder')}</span><code>${esc(w.targets.code)}</code><span>Git</span><span>${g.sha ? `${esc(g.branch)} · <code>${esc(g.short)}</code>${g.dirty ? ' · ' + chip(T('uncommitted changes'), 'testing') : ''}` : T('not a git repository yet (Workspace & Runs → Source Control → Initialize)')}</span>
            ${g.remote ? `<span>Remote</span><code>${esc(g.remote)}</code>` : ''}</div>
          <div class="row" style="flex-wrap:wrap;gap:6px;margin-top:10px">
            <button class="btn primary" id="cc-open" ${vs.ok ? '' : 'disabled'} style="flex:0">🚀 ${T('Open in VS Code')}</button>
            <button class="btn" id="cc-open-dc" ${devOk && w.devcontainer ? '' : 'disabled'} style="flex:0" title="${esc(devOk ? (w.devcontainer ? '' : T('Generate the environment first')) : T('Needs VS Code + the Dev Containers extension'))}">🐳 ${T('Open in Dev Container')}</button>
            <a class="btn" href="${esc(w.deep_links.code)}" style="flex:0;text-decoration:none" title="${T('Browser hand-off via the vscode:// link')}">🔗 vscode://</a>
            <button class="btn" id="cc-open-term" ${vs.ok ? '' : 'disabled'} style="flex:0" title="${T('The terminal is VS Code’s integrated terminal (Ctrl+`)')}">⌨ ${T('Open Terminal (VS Code)')}</button></div>
          ${vs.ok ? '' : `<ul class="ccsetup">${(vs.setup || []).map(s => `<li>${esc(s)}</li>`).join('')}</ul>`}
          ${vs.ok && !devOk ? `<div class="status">${T('Dev Containers extension not installed')}: <code>code --install-extension ms-vscode-remote.remote-containers</code></div>` : ''}
          ${vs.ok ? `<div class="status">${vs.extra && vs.extra.codex_ext ? '✓ ' + T('Codex extension installed (openai.chatgpt)') : T('Codex extension not installed') + ' — 💻 Workspace & Runs → ⤓ ' + T('Install Codex extension')}</div>` : ''}</div>
        <div class="card dsec"><h4>📓 Jupyter ${led(w.jupyter.state)}</h4><div class="status" style="margin-top:0">${esc(w.jupyter.detail)}</div>
          ${w.jupyter.ok ? `<div class="row" style="gap:6px;margin-top:8px"><button class="btn" id="cc-jup" style="flex:0">▶ ${T('Open Jupyter')}</button><button class="btn small" id="cc-jup-stop" style="flex:0">■ ${T('Stop')}</button></div>` : `<ul class="ccsetup">${(w.jupyter.setup || []).map(s => `<li>${esc(s)}</li>`).join('')}</ul>`}</div>
      </div>
      <div class="card"><h4>🧰 ${T('Environment Manager')} ${w.devcontainer ? chip('.devcontainer ✓', 'supported') : ''}</h4>
        <p class="status" style="margin-top:0">${T('Generates .devcontainer/Dockerfile + devcontainer.json with the hardware caps of this machine')} (${opts.policy.sandbox_memory_gb} GB RAM · ${opts.policy.sandbox_cpus} CPUs · GPU passthrough). ${T('The runs folder is mounted at /runs.')}</p>
        <div class="dform">
          <div><label class="chk"><input type="checkbox" id="cc-env-gpu" checked> 🎮 GPU (CUDA)</label></div>
          <div><label>PyTorch · CUDA</label><select id="cc-env-img">${opts.gpu_images.map(i => `<option value="${esc(i.torch)}|${esc(i.cuda)}">torch ${esc(i.torch)} · CUDA ${esc(i.cuda)}</option>`).join('')}</select></div>
          <div><label>Python (CPU)</label><select id="cc-env-py">${opts.python_versions.map(v => `<option ${v === '3.11' ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
          <div style="grid-column:1/-1"><label>${T('Datasets folder (mounted read-only at /datasets, optional)')}</label><input type="text" id="cc-env-ds" placeholder="D:/datasets/pavia"></div></div>
        <div class="row" style="gap:6px;margin-top:10px"><button class="btn" id="cc-env-prev" style="flex:0">👁 ${T('Preview')}</button><button class="btn primary" id="cc-env-write" style="flex:0">💾 ${T('Write files')}</button></div>
        <pre class="joblog" id="cc-env-out" hidden></pre></div></div>`;
    const spec = () => { const [torch, cuda] = $('#cc-env-img').value.split('|'); return {gpu: $('#cc-env-gpu').checked, torch, cuda, python: $('#cc-env-py').value, datasets_dir: $('#cc-env-ds').value.trim()}; };
    const open = (mode) => async e => busy(e.target, async () => { const r = await api('/api/workspace/open', {method: 'POST', body: {target: 'code', mode}}); toast(r.note, 'ok'); });
    if ($('#cc-open')) $('#cc-open').onclick = open('folder');
    if ($('#cc-open-term')) $('#cc-open-term').onclick = open('folder');
    if ($('#cc-open-dc')) $('#cc-open-dc').onclick = open('devcontainer');
    $('#cc-env-prev').onclick = e => busy(e.target, async () => { const r = await api('/api/workspace/environment/preview', {method: 'POST', body: {spec: spec()}});
      const o = $('#cc-env-out'); o.hidden = false; o.textContent = Object.entries(r.files).map(([k, v]) => `# ${k}\n${v}`).join('\n'); });
    $('#cc-env-write').onclick = e => busy(e.target, async () => {
      let r;
      try { r = await api('/api/workspace/environment', {method: 'POST', body: {spec: spec()}}); }
      catch (err) { if (!/Already exists/.test(err.message) || !confirm(err.message + '\n\n' + T('Overwrite?'))) throw err;
        r = await api('/api/workspace/environment', {method: 'POST', body: {spec: spec(), overwrite: true}}); }
      toast(`${T('Written')}: ${r.written.join(', ')}`, 'ok'); show('workspace');
    });
    if ($('#cc-jup')) $('#cc-jup').onclick = e => busy(e.target, async () => { const r = await api('/api/jupyter/launch', {method: 'POST', body: {target: 'code'}}); window.open(r.url, '_blank', 'noopener'); });
    if ($('#cc-jup-stop')) $('#cc-jup-stop').onclick = e => busy(e.target, async () => { await api('/api/jupyter/stop', {method: 'POST'}); toast(T('Jupyter stopped'), 'ok'); show('workspace'); });
  }

  // ------------------------------------------------------------------ integrations (+ ClearML / Codex settings)
  async function renderIntegrations(body, force) {
    const [list, cfg, runs] = await Promise.all([integrations(force), api('/api/config'), api('/api/sandbox/runs')]);
    const cm = cfg.clearml, cx = cfg.codex;
    const clearOk = list.some(s => s.name === 'clearml' && s.ok);
    body.innerHTML = `<div class="card"><h4>🔌 ${T('Integration status')} <span class="status" style="margin:0">${T('probed just now — available means the tool answered')}</span></h4>
      <table class="dtable"><tr><th></th><th>${T('Integration')}</th><th>${T('State')}</th><th>${T('Detail')}</th><th>${T('Setup')}</th></tr>
      ${list.map(s => `<tr><td>${led(s.state)}</td><td><b>${esc(s.label)}</b>${s.version ? `<div class="status" style="margin:0">${esc(s.version)}</div>` : ''}</td><td>${esc(T(s.state))}</td><td>${esc(s.detail)}</td>
        <td>${s.ok ? '' : (s.setup || []).map(x => `<div class="status" style="margin:0">• ${esc(x)}</div>`).join('')}</td></tr>`).join('')}</table></div>
      <div class="cxgrid" style="grid-template-columns:1fr 1fr">
      <div class="card dsec"><h4>📈 ClearML</h4>
        <div class="dform"><div><label class="chk"><input type="checkbox" id="cm-en" ${cm.enabled ? 'checked' : ''}> ${T('Enabled')}</label></div>
          <div><label>API host</label><input type="text" id="cm-api" value="${esc(cm.api_host)}" placeholder="http://localhost:8008"></div>
          <div><label>Web host</label><input type="text" id="cm-web" value="${esc(cm.web_host)}" placeholder="http://localhost:8080"></div>
          <div><label>Files host</label><input type="text" id="cm-files" value="${esc(cm.files_host)}" placeholder="http://localhost:8081"></div>
          <div><label>Access key</label><input type="password" id="cm-ak" value="${esc(cm.access_key)}"></div>
          <div><label>Secret key</label><input type="password" id="cm-sk" value="${esc(cm.secret_key)}"></div>
          <div><label>${T('Project')}</label><input type="text" id="cm-proj" value="${esc(cm.project)}"></div>
          <div><label>${T('Queue (remote agents)')}</label><input type="text" id="cm-q" value="${esc(cm.queue)}"></div></div>
        <div class="row" style="margin-top:8px"><button class="btn primary small" id="cm-save" style="flex:0">💾 ${T('Save & test')}</button></div>
        <h4 style="margin-top:14px">${T('Sync finished runs')}</h4>
        <table class="dtable">${runs.runs.filter(r => r.status !== 'running').slice(0, 10).map(r => `<tr><td class="mono">${esc(r.id)}</td><td>${esc(r.status)}</td><td><code>${esc((r.cmd || '').slice(0, 40))}</code></td>
          <td>${r.clearml && r.clearml.task_id ? `<a href="${esc(r.clearml.url)}" target="_blank" rel="noopener">${T('Open in ClearML')} ↗</a>` : `<button class="btn small" data-sync="${esc(r.id)}" ${clearOk ? '' : 'disabled'}>⇪ ${T('Sync')}</button>`}</td></tr>`).join('') || `<tr><td>${T('No runs yet')}</td></tr>`}</table>
        ${clearOk ? '' : `<div class="status">${T('Sync is enabled once ClearML is available.')}</div>`}</div>
      <div class="card dsec"><h4>🤖 Codex</h4>
        <div class="dform"><div><label class="chk"><input type="checkbox" id="cx-en" ${cx.enabled ? 'checked' : ''}> ${T('Enabled')}</label></div>
          <div><label>${T('CLI path (empty = PATH)')}</label><input type="text" id="cx-bin" value="${esc(cx.binary)}"></div>
          <div><label>${T('Model (optional)')}</label><input type="text" id="cx-model" value="${esc(cx.model)}"></div>
          <div><label>${T('Time limit (s)')}</label><input type="text" id="cx-to" value="${esc(cx.timeout_s)}"></div></div>
        <p class="status">${T('Authentication stays in the Codex CLI (codex login, or CODEX_API_KEY) — this app never stores it. ChatGPT-plan login and API-key billing are different accounts.')}</p>
        <div class="row"><button class="btn primary small" id="cx-save" style="flex:0">💾 ${T('Save & test')}</button></div></div></div>`;
    $('#cm-save').onclick = e => busy(e.target, async () => {
      await api('/api/config', {method: 'POST', body: {clearml: {enabled: $('#cm-en').checked, api_host: $('#cm-api').value.trim(), web_host: $('#cm-web').value.trim(),
        files_host: $('#cm-files').value.trim(), access_key: $('#cm-ak').value.trim(), secret_key: $('#cm-sk').value.trim(), project: $('#cm-proj').value.trim(), queue: $('#cm-q').value.trim()}}});
      show('integrations', true);
    });
    $('#cx-save').onclick = e => busy(e.target, async () => {
      await api('/api/config', {method: 'POST', body: {codex: {enabled: $('#cx-en').checked, binary: $('#cx-bin').value.trim(), model: $('#cx-model').value.trim(), timeout_s: $('#cx-to').value}}});
      show('integrations', true);
    });
    body.querySelectorAll('[data-sync]').forEach(b => b.onclick = () => busy(b, async () => {
      const r = await api('/api/experiments/clearml/sync', {method: 'POST', body: {run_id: b.dataset.sync}}); toast(`ClearML task ${r.task_id}`, 'ok'); show('integrations');
    }));
  }

  // ------------------------------------------------------------------ Codex
  async function renderCodex(body) {
    const [st, runs] = await Promise.all([api('/api/codex/status'), api('/api/codex/runs')]);
    body.innerHTML = `<div class="cxgrid" style="grid-template-columns:minmax(0,1fr) minmax(320px,1fr)">
      <div class="card"><h4>🤖 ${T('Run with Codex')} ${led(st.state)} <span class="status" style="margin:0">${esc(st.version || '')} · ${esc(T(st.state))} — ${esc(st.detail)}</span></h4>
        ${st.ok ? '' : `<ul class="ccsetup">${(st.setup || []).map(s => `<li>${esc(s)}</li>`).join('')}</ul>`}
        <p class="status" style="margin-top:0">${T('Codex works only inside this project’s code folder. Default: read-only sandbox (it can read and propose, not write). Codex never commits, pushes or deletes on its own; changed files are taken from git.')}</p>
        <textarea id="cc-cx-prompt" rows="6" placeholder="${esc(T('Coding task, e.g. Add a --seed argument to train.py and make the data loader deterministic. Run the unit tests.'))}"></textarea>
        <div class="row" style="gap:10px;margin-top:8px"><label class="chk" style="flex:0 0 auto;margin:0"><input type="checkbox" id="cc-cx-write"> ✏ ${T('Allow edits (workspace-write sandbox)')}</label><span></span>
          <button class="btn primary" id="cc-cx-run" ${st.ok ? '' : 'disabled'} style="flex:0">▶ ${T('Run with Codex')}</button></div>
        <div id="cc-cx-live"></div></div>
      <div class="card"><h4>🗂 ${T('Codex runs')}</h4>${runs.runs.length ? `<table class="dtable">${runs.runs.map(r => `<tr data-cxrun="${esc(r.id)}" style="cursor:pointer"><td class="mono">${esc(r.id)}</td><td>${esc(r.status)}</td><td>${esc(r.permission_mode)}</td><td>${esc((r.prompt || '').slice(0, 60))}</td></tr>`).join('')}</table>` : empty('No Codex run yet.')}</div></div>`;
    $('#cc-cx-run').onclick = e => busy(e.target, async () => {
      const w = $('#cc-cx-write').checked;
      if (w && !confirm(T('Codex will be allowed to EDIT files in the code workspace (no network, no commit). Continue?'))) return;
      const r = await api('/api/codex/runs', {method: 'POST', body: {prompt: $('#cc-cx-prompt').value, allow_write: w}});
      followCodex(r.id);
    });
    body.querySelectorAll('[data-cxrun]').forEach(tr => tr.onclick = () => followCodex(tr.dataset.cxrun));
  }

  function followCodex(id) {
    clearTimeout(S.codexTimer);
    const tick = async () => {
      const el = $('#cc-cx-live'); if (!el || S.sub !== 'codex') return;
      let r; try { r = await api('/api/codex/runs/' + id); } catch (e) { el.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
      const active = ['running', 'starting'].includes(r.status);
      el.innerHTML = `<div class="dsec"><div class="ccline">${chip(r.id, 'id')} ${chip(r.status, r.status)} ${chip(r.permission_mode)} ${r.thread_id ? chip('session ' + r.thread_id, 'link') : ''}
          ${active ? `<button class="btn small danger" id="cc-cx-cancel">■ ${T('Cancel')}</button>` : ''}</div>
        ${r.final_message ? `<div class="md">${md(r.final_message)}</div>` : ''}
        ${(r.errors || []).length ? `<div class="status" style="color:var(--err)">${r.errors.map(esc).join('<br>')}</div>` : ''}
        ${!active ? `<div class="status">${T('Changed files (git-derived)')}: ${(r.changed_files || []).map(f => `<code>${esc(f)}</code>`).join(' ') || T('none')}${r.usage && r.usage.output_tokens ? ` · tokens in/out ${r.usage.input_tokens}/${r.usage.output_tokens}` : ''}</div>
          <button class="btn small" id="cc-cx-review">🔎 ${T('Review changes in VS Code')}</button>` : ''}
        <pre class="joblog">${(r.events || []).slice(-40).map(ev => esc(ev.item ? `${ev.type} · ${ev.item.type}${ev.item.command ? ' · ' + ev.item.command : ''}${ev.item.text ? ' · ' + ev.item.text.slice(0, 200) : ''}` : `${ev.type}${ev.text ? ' · ' + ev.text : ''}`)).join('\n')}</pre></div>`;
      if ($('#cc-cx-cancel')) $('#cc-cx-cancel').onclick = () => api(`/api/codex/runs/${id}/cancel`, {method: 'POST'}).then(tick);
      if ($('#cc-cx-review')) $('#cc-cx-review').onclick = () => api('/api/workspace/open', {method: 'POST', body: {target: 'code'}}).then(r2 => toast(r2.note, 'ok')).catch(e => toast(e.message, 'err'));
      if (active) S.codexTimer = setTimeout(tick, 1500);
    };
    tick();
  }

  // ------------------------------------------------------------------ resources
  async function renderResources(body) {
    const [p, rt] = await Promise.all([api('/api/resources/policy'), api('/api/resources/routing')]);
    const row = (k, v, src) => `<tr><td>${esc(T(k))}</td><td><b>${esc(v)}</b></td><td class="status">${src ? esc(T(src)) : ''}</td></tr>`;
    body.innerHTML = `<div class="cxgrid" style="grid-template-columns:1fr 1fr">
      <div class="card"><h4>⚙ ${T('Hardware policy')} <span class="status" style="margin:0">${esc(p.gpu || 'CPU')}</span></h4>
        <table class="dtable">${row('VRAM safety cap', p.vram_safety_cap_gb + ' GB')}${row('Local AI VRAM (max)', p.local_ai_vram_gb + ' GB', p.source.local_ai_vram_gb)}
          ${row('RAM safety cap', p.ram_safety_cap_gb + ' GB')}${row('Sandbox RAM', p.sandbox_memory_gb + ' GB', p.source.sandbox_memory_gb)}
          ${row('Sandbox CPUs', p.sandbox_cpus, p.source.sandbox_cpus)}${row('Local AI threads', p.local_ai_threads, p.source.local_ai_threads)}
          ${row('GPU runs refused while local LLMs hold VRAM', p.settings.require_unload ? T('on') : T('off'))}${row('GPU temperature limit', p.settings.gpu_temp_limit_c + ' °C')}
          ${row('CPU fallback after a GPU fault', p.settings.cpu_fallback_on_gpu_fault ? T('on') : T('off'))}${row('Hard caps enforced', p.settings.enforce_caps ? T('on') : T('off'))}</table>
        <div class="row" style="margin-top:10px"><button class="btn" id="cc-unload" style="flex:0">🧹 ${T('Unload local LLMs from VRAM now')}</button></div><pre class="joblog" id="cc-unload-out" hidden></pre></div>
      <div class="card"><h4>🔀 ${T('Auto routing')} ${rt.gpu_busy ? chip(T('GPU busy'), 'testing') : ''}</h4>
        ${Object.keys(rt.routing).length ? `<table class="dtable"><tr><th>${T('Agent')}</th><th>${T('Task kind')}</th><th>${T('Engines (in order)')}</th><th>${T('Skipped')}</th></tr>${Object.entries(rt.routing).map(([a, r]) => `<tr><td>${esc(a)}</td><td>${esc(r.kind)}</td><td>${r.candidates.map(esc).join(' → ') || '<span style="color:var(--err)">' + T('none available') + '</span>'}</td><td class="status">${Object.entries(r.skipped).map(([k, v]) => esc(k + ': ' + v)).join('<br>')}</td></tr>`).join('')}</table>`
          : empty('No agent uses the "auto" engine. Set an agent to auto in Configuration → AI engines to route by task kind.')}</div></div>`;
    $('#cc-unload').onclick = e => busy(e.target, async () => { const r = await api('/api/resources/unload', {method: 'POST'}); const o = $('#cc-unload-out'); o.hidden = false;
      o.textContent = (r.log.join('\n') || T('No local model was loaded.')) + (r.errors.length ? '\n' + r.errors.join('\n') : ''); });
  }

  // ------------------------------------------------------------------ provenance
  async function renderProvenance(body) {
    body.innerHTML = `<div class="card"><h4>🛡 ${T('Artifact provenance inspector')}</h4>
      <p class="status" style="margin-top:0">${T('Drop a figure (PNG/JPG/SVG) or table (CSV) produced by a sandbox run: its embedded seal (run id, git commit, ClearML task) is read and the run record is shown. Files whose metadata was stripped are matched by their SHA-256.')}</p>
      <div class="resdrop" id="cc-prov-drop">⤓ ${T('Drop a file here or click to choose')}</div><input type="file" id="cc-prov-file" hidden>
      <div id="cc-prov-out"></div></div>`;
    const drop = $('#cc-prov-drop'), inp = $('#cc-prov-file');
    const go = async f => {
      const out = $('#cc-prov-out'); out.innerHTML = '<span class="spin"></span>';
      const fd = new FormData(); fd.append('file', f);
      try {
        const r = await api('/api/provenance/inspect', {method: 'POST', body: fd});
        const run = r.run, cm = r.clearml;
        out.innerHTML = `<div class="dsec">${r.found ? chip('✓ ' + T('provenance found'), 'supported') : chip(T('no provenance — not produced by a sealed run'), 'refuted')}
          <div class="kv ccv" style="margin-top:8px"><span>SHA-256</span><code>${esc(r.sha256)}</code>
            ${Object.entries(r.embedded || {}).map(([k, v]) => `<span>${esc(k)}</span><code>${esc(String(v))}</code>`).join('')}
            ${r.matched_by_hash ? `<span>${T('matched by hash')}</span><code>${esc(r.matched_by_hash.file)}</code>` : ''}</div>
          ${run ? `<h4 style="margin-top:12px">${T('Run')} ${esc(run.id)} · ${esc(run.status)}</h4><div class="kv ccv"><span>${T('Command')}</span><code>${esc(run.cmd)}</code>
            <span>Git</span><code>${esc((run.git || {}).sha || '—')}${(run.git || {}).dirty ? ' (+uncommitted)' : ''}</code><span>${T('Environment')}</span><code>${esc(JSON.stringify(run.environment || {}))}</code>
            <span>${T('Metrics')}</span><span>${Object.entries(run.metrics || {}).map(([k, v]) => `${esc(k)}=${fmt(v)}`).join(' · ') || '—'}</span></div>` : ''}
          ${r.run_error ? `<div class="status">⚠ ${esc(r.run_error)}</div>` : ''}
          ${cm ? (cm.error ? `<div class="status">ClearML ${esc(cm.task_id)}: ${esc(cm.error)}</div>` : `<h4 style="margin-top:12px">ClearML · ${esc(cm.name)}</h4><div class="kv ccv"><span>${T('Status')}</span><span>${esc(cm.status)}</span>
            <span>${T('Code')}</span><code>${esc((cm.script || {}).repository || '')} ${esc((cm.script || {}).commit || '')}</code><span>${T('Parameters')}</span><code>${esc(JSON.stringify(cm.parameters || {}).slice(0, 600))}</code></div>
            <a href="${esc(cm.url)}" target="_blank" rel="noopener">${T('Open in ClearML')} ↗</a>`) : ''}</div>`;
      } catch (e) { out.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; }
    };
    drop.onclick = () => inp.click();
    inp.onchange = () => inp.files[0] && go(inp.files[0]);
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); e.dataTransfer.files[0] && go(e.dataTransfer.files[0]); };
  }

  // ------------------------------------------------------------------ memory inspector
  async function renderMemory(body) {
    const plan = await api('/api/memory/v2/plan');
    body.innerHTML = `<div class="cxgrid" style="grid-template-columns:minmax(0,1.4fr) minmax(300px,1fr)">
      <div class="card"><h4>🧠 ${T('What the agents receive')}</h4>
        <p class="status" style="margin-top:0">${T('Tri-search (BM25 keyword ‖ vector ‖ graph) → reciprocal-rank fusion → reranker → deterministic compiler. Type the request an agent would get:')}</p>
        <div class="row"><input type="text" id="cc-mq" placeholder="${esc(T('e.g. why did the batch-size sweep fail?'))}"><button class="btn primary" id="cc-mgo" style="flex:0">⚡ ${T('Compile')}</button></div>
        <div id="cc-mout"></div></div>
      <div><div class="card"><h4>🗜 ${T('Compression')}</h4><div class="kv ccv"><span>${T('Short-term memory')}</span><span>${plan.pending_tokens.toLocaleString()} ${T('tokens')}</span>
          <span>${T('Watermarks')}</span><span>${plan.high.toLocaleString()} → ${plan.low.toLocaleString()}</span><span>${T('Would compress')}</span><span>${plan.trigger ? plan.spans.length + ' ' + T('chat(s)') + ' · ' + plan.tokens.toLocaleString() + ' ' + T('tokens') : T('nothing (below the high watermark)')}</span></div>
          <div class="row" style="margin-top:8px"><button class="btn" id="cc-mcomp" style="flex:0">🗜 ${T('Compress now')}</button></div><pre class="joblog" id="cc-mcomp-out" hidden></pre>
          <p class="status">${T('Raw turns are snapshotted in the page-store first; summaries point to them. Chat files are never deleted.')}</p></div>
        <div class="card dsec"><h4>📄 ${T('Page-store')}</h4><div id="cc-pages"><span class="spin"></span></div></div></div></div>`;
    const go = async () => {
      const out = $('#cc-mout'); out.innerHTML = '<span class="spin"></span>';
      try {
        const r = await api('/api/memory/v2/compile?q=' + encodeURIComponent($('#cc-mq').value));
        const dg = r.diagnostics;
        out.innerHTML = `<div class="status">${r.tokens} ${T('tokens')} · ${T('vector')}: ${esc(dg.vector_engine || '')} · ${T('reranker')}: ${esc(dg.reranker || '')} · ${dg.nodes} ${T('memory nodes')}${dg.vector_error ? ' · ⚠ ' + esc(dg.vector_error) : ''}</div>
          <pre class="joblog" style="max-height:420px">${esc(r.text)}</pre><h4>${T('Memory map (LOD 1)')}</h4><pre class="joblog">${esc(r.skeleton)}</pre>`;
      } catch (e) { out.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; }
    };
    $('#cc-mgo').onclick = go; $('#cc-mq').onkeydown = e => e.key === 'Enter' && go();
    $('#cc-mcomp').onclick = e => busy(e.target, async () => { const r = await api('/api/memory/v2/compress', {method: 'POST', body: {force: true}}); const o = $('#cc-mcomp-out'); o.hidden = false; o.textContent = JSON.stringify(r, null, 1); });
    api('/api/memory/pages?limit=30').then(r => { $('#cc-pages').innerHTML = r.pages.length ? `<table class="dtable">${r.pages.map(p => `<tr><td class="mono">${esc(p.id)}</td><td>${esc(p.header || p.source)}</td><td>${p.tokens}</td><td><button class="btn small" data-page="${esc(p.id)}">👁</button></td></tr>`).join('')}</table>` : empty('No page yet — pages are written when memory is compressed.');
      $$('#cc-pages [data-page]').forEach(b => b.onclick = async () => { const pg = await api('/api/memory/pages/' + b.dataset.page); const o = $('#cc-mcomp-out'); o.hidden = false; o.textContent = pg.content; });
    }).catch(() => {});
    go();
  }

  // ------------------------------------------------------------------ datasets
  async function renderDatasets(body) {
    const r = await api('/api/connectors');
    body.innerHTML = `<div class="card"><h4>🧬 ${T('Data connectors')}</h4>
      <p class="status" style="margin-top:0">${esc(T('Plugins found in backend/connectors/. In the Data chat you can also type /hf <query>, /kaggle <query> or /dataset <query>.'))}</p>
      <table class="dtable">${r.connectors.map(c => `<tr><td>${led(c.state)}</td><td><b>${esc(c.label)}</b></td><td>${esc(c.description || '')}</td><td class="status">${esc(c.detail || '')}</td></tr>`).join('')}</table>
      <div class="row" style="margin-top:10px"><select id="cc-dsc" style="flex:0 0 200px">${r.connectors.filter(c => c.state === 'available').map(c => `<option value="${esc(c.name)}">${esc(c.label)}</option>`).join('')}</select>
        <input type="text" id="cc-dsq" placeholder="${esc(T('e.g. hyperspectral image'))}"><button class="btn primary" id="cc-dsgo" style="flex:0">🔎 ${T('Search')}</button></div>
      <div id="cc-dsout"></div></div>`;
    const go = e => busy(e && e.target || $('#cc-dsgo'), async () => {
      const res = await api(`/api/connectors/${$('#cc-dsc').value}/search`, {method: 'POST', body: {query: $('#cc-dsq').value, limit: 15}});
      $('#cc-dsout').innerHTML = res.items.length ? `<table class="dtable">${res.items.map(it => `<tr><td><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title || it.id)}</a></td><td class="status">${esc(it.summary || '')}</td><td class="mono">${esc(it.load || '')}</td></tr>`).join('')}</table>` : empty('No results.');
    });
    $('#cc-dsgo').onclick = go; $('#cc-dsq').onkeydown = e => e.key === 'Enter' && go();
  }

  function init() {
    if (!S.inited) {
      S.inited = true; build();
      try { const s = localStorage.getItem('cc_sub'); if (s && SUBS.some(x => x[0] === s)) S.sub = s; } catch {}
    }
    show(S.sub);
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'control') init(); });
  window.CONTROL_API = {init, show};
})();
