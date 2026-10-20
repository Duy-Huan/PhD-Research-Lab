/* PhD Research Lab v3.2 — 💻 Workspace & Runs (replaces the Monaco Code IDE).
   Code is written in VS Code (+ the Codex extension, or the Codex CLI from the Control Center). This tab keeps what the
   research workflow needs around the code: open the workspace in VS Code / a Dev Container, run commands in the sandbox
   with a live log and curves, runs with metrics and figures, the self-debugging co-coding agent, and Git / GitHub.
   GPU runs are refused while local LLMs hold VRAM — the researcher unloads them (🧹) or runs on CPU. */
(() => {
  const T = s => I18N.tr(s);
  const W = {inited: false, es: null, job: null, series: {}, git: null, chat: [], sid: null, busy: false, ctrl: null, hist: [], vs: null};
  const root = () => $('#tab-ide');
  const CODEX_EXT = 'openai.chatgpt';
  const fmt = v => typeof v === 'number' ? (+v).toPrecision(4) : esc(v);
  const detailOf = e => { try { return JSON.parse(e.message); } catch { return null; } };

  function build() {
    root().innerHTML = `<div class="v3sec">
      <div class="row" style="align-items:flex-start;flex-wrap:wrap;gap:10px;margin-bottom:10px">
        <div style="flex:1;min-width:280px"><h2 style="margin:0 0 4px">💻 ${T('Workspace & Runs')}</h2>
          <p class="lead" style="margin:0">${T('Write code in VS Code (with the Codex extension). Run it here in the sandbox, follow logs and curves, keep every run with its metrics, figures and git commit.')}</p></div>
        <div class="row" style="flex:0 0 auto;gap:6px;flex-wrap:wrap" id="ws-actions"></div></div>
      <div id="ws-vsnote"></div>
      <div class="cxgrid" style="grid-template-columns:minmax(0,1.35fr) minmax(330px,1fr)">
        <div>
          <div class="card" id="ws-env"></div>
          <div class="card"><h4>▶ ${T('Run in the sandbox')} <span class="status" style="margin:0" id="ws-mode"></span></h4>
            <div class="row"><input type="text" id="ws-cmd" list="ws-cmdlist" placeholder="python train.py --epochs 2"><datalist id="ws-cmdlist"></datalist>
              <button class="btn primary" id="ws-run" style="flex:0">▶ ${T('Run')}</button><button class="btn" id="ws-stop" style="flex:0" disabled>■ ${T('Stop')}</button></div>
            <div class="row" style="margin-top:6px;gap:14px;flex-wrap:wrap"><label class="chk" style="flex:0 0 auto;margin:0"><input type="checkbox" id="ws-cpu"> ${T('Run on CPU (no GPU)')}</label>
              <span class="status" style="margin:0;flex:1" id="ws-vram"></span><button class="btn small" id="ws-unload" style="flex:0">🧹 ${T('Unload local LLMs')}</button></div>
            <div id="ws-gate"></div>
            <div class="status" id="ws-jobst"></div>
            <pre class="joblog" id="ws-log" style="max-height:340px;min-height:80px"></pre>
            <div id="ws-curves"></div></div>
          <div class="card dsec"><h4>📈 ${T('Runs')} <span class="status" style="margin:0" id="ws-best"></span><button class="btn small" id="ws-rref" style="margin-left:auto">↻</button></h4>
            <div id="ws-runs"></div><div id="ws-rundetail"></div></div>
        </div>
        <div>
          <div class="card" id="ws-agent"></div>
          <div class="card dsec"><h4>⑂ ${T('Source Control')} <button class="btn small" id="ws-gref" style="margin-left:auto">↻</button></h4><div id="ws-scm"></div></div>
        </div></div></div>`;
    try { W.hist = JSON.parse(localStorage.getItem('ide_cmd_hist') || '[]'); } catch {}
    paintHist();
    $('#ws-run').onclick = () => runCmd();
    $('#ws-cmd').addEventListener('keydown', e => { if (e.key === 'Enter') runCmd(); });
    $('#ws-stop').onclick = stopJob;
    $('#ws-unload').onclick = e => busy(e.target, async () => { await unload(); });
    $('#ws-rref').onclick = loadRuns;
    $('#ws-gref').onclick = () => refreshGit();
    buildAgent();
  }

  // ------------------------------------------------------------------ VS Code / Codex hand-off
  async function loadWorkspace() {
    let w;
    try { w = await api('/api/workspace'); } catch (e) { $('#ws-actions').innerHTML = `<span class="status">⚠ ${esc(e.message)}</span>`; return; }
    W.vs = w.vscode;
    const vs = w.vscode, ok = vs.ok, ex = vs.extra || {};
    $('#ws-actions').innerHTML = `
      <button class="btn primary" data-open="folder" ${ok ? '' : 'disabled'}>🚀 ${T('Open in VS Code')}</button>
      <button class="btn" data-open="devcontainer" ${ok ? '' : 'disabled'} title="${esc(T(ex.dev_containers_ext && w.devcontainer ? 'Reopen the workspace inside the dev container' : 'Installs the Dev Containers extension and generates .devcontainer/ from the sandbox image when missing'))}">🐳 ${T('Dev Container')}</button>
      <button class="btn" id="ws-seed" title="${esc(T('Create the code workspace from the Tool 2 blueprint'))}">🧬 ${T('Start from blueprint')}</button>
      <button class="btn" id="ws-jup" ${w.jupyter.ok ? '' : 'disabled'} title="${esc(w.jupyter.ok ? (w.jupyter.version || 'JupyterLab') : w.jupyter.detail)}">📓 Jupyter</button>
      <button class="btn" id="ws-nb" ${w.jupyter.ok ? '' : 'disabled'} title="${esc(T('New research notebook (project context, git commit, ClearML task)'))}">＋ ${T('Notebook')}</button>
      <button class="btn" id="ws-codex">🤖 ${T('Codex runs')}</button>`;
    const notes = [];
    if (!ok) notes.push(`⚠ VS Code: ${esc(vs.detail)} ${(vs.setup || []).map(esc).join(' · ')}`);
    else if (!ex.codex_ext) notes.push(`${T('The Codex extension for VS Code is not installed.')} <button class="btn small" id="ws-instcodex">⤓ ${T('Install Codex extension')}</button> <span class="status" style="margin:0">(${CODEX_EXT}, ${T('sign in with your ChatGPT account inside VS Code')})</span>`);
    else notes.push(`✓ ${T('Codex extension installed — open the workspace in VS Code and use the Codex panel.')}`);
    $('#ws-vsnote').innerHTML = `<div class="status" style="margin:0 0 10px">${notes.join('<br>')} · <code>${esc(w.targets.code)}</code>${w.git && w.git.short ? ` · ⑂ ${esc(w.git.branch)} <code>${esc(w.git.short)}</code>${w.git.dirty ? ' ✎' : ''}` : ''}</div>`;
    $$('#ws-actions [data-open]').forEach(b => b.onclick = () => {
      if (b.dataset.open === 'devcontainer' && !(ex.dev_containers_ext && w.devcontainer)) {
        const todo = [!ex.dev_containers_ext && T('install the VS Code “Dev Containers” extension'), !w.devcontainer && T('generate .devcontainer/ (Dockerfile + devcontainer.json) from the sandbox image')].filter(Boolean);
        if (!confirm(`${T('To open the Dev Container PhD-Lab will')}:\n• ${todo.join('\n• ')}\n\n${T('Continue?')}`)) return;
      }
      busy(b, async () => {
        const r = await api('/api/workspace/open', {method: 'POST', body: {target: 'code', mode: b.dataset.open}});
        toast([...(r.steps || []), T(r.note || '')].filter(Boolean).join(' · '), 'ok'); if (r.steps && r.steps.length) loadWorkspace();
      });
    });
    $('#ws-seed').onclick = e => busy(e.target, async () => { const r = await api('/api/ide/seed', {method: 'POST'}); toast(r.created.length ? `${T('Created')}: ${r.created.join(', ')}` : T('The workspace already has these files'), 'ok'); refreshGit(true); });
    $('#ws-codex').onclick = () => { document.querySelector('nav button[data-tab=control]').click(); setTimeout(() => window.CONTROL_API && CONTROL_API.show('codex'), 300); };
    // the tab is opened synchronously on click (popup blockers), then pointed at Jupyter once it answers
    const openJupyter = async (nbName) => {
      const win = window.open('about:blank', '_blank');
      try {
        const r = await api('/api/jupyter/launch', {method: 'POST', body: {target: 'code'}});
        if (r.kernel) toast(r.kernel.registered ? `${T('Notebook kernel')}: PhD-Lab · ${T('project environment')} (${r.kernel.python})` : `${T('Notebook kernel')}: ${r.kernel.detail || ''}`, r.kernel.registered ? 'ok' : '');
        let url = r.url;
        if (nbName != null) { const nb = await api('/api/jupyter/notebook', {method: 'POST', body: {name: nbName}}); url = nb.url || url; toast(`${T('Created')} ${nb.path}`, 'ok'); }
        if (win) win.location = url; else window.open(url, '_blank');
      } catch (e) { if (win) win.close(); throw e; }
    };
    if ($('#ws-jup')) $('#ws-jup').onclick = e => busy(e.target, () => openJupyter(null), T('Starting…'));
    if ($('#ws-nb')) $('#ws-nb').onclick = e => { const n = prompt(T('Notebook name'), 'experiment'); if (n) busy(e.target, () => openJupyter(n), T('Starting…')); };
    const inst = $('#ws-instcodex');
    if (inst) inst.onclick = () => busy(inst, async () => { await api('/api/workspace/extension', {method: 'POST', body: {id: CODEX_EXT}}); toast(T('Codex extension installed in VS Code'), 'ok'); loadWorkspace(); });
  }

  async function openFile(path, line) {
    try { const r = await api('/api/workspace/open-file', {method: 'POST', body: {path, line: line || 1}}); toast(r.note, 'ok'); }
    catch (e) { toast(e.message, 'err'); }
  }

  // ------------------------------------------------------------------ VRAM gate (GPU runs need free VRAM)
  async function refreshVram() {
    try {
      const v = await api('/api/resources/vram');
      $('#ws-vram').innerHTML = v.loaded.length ? `⛔ ${T('VRAM held by')}: ${v.loaded.map(m => `<code>${esc(m)}</code>`).join(' ')} — ${T('GPU runs are refused until you unload')}`
        : `✓ ${T('no local LLM in VRAM')}${v.vram_used_mb != null ? ` · ${Math.round(v.vram_used_mb)}/${Math.round(v.vram_total_mb)} MB` : ''}`;
      $('#ws-unload').disabled = !v.loaded.length;
    } catch {}
  }
  async function unload() {
    const r = await api('/api/resources/unload', {method: 'POST'});
    toast(r.unloaded.length ? `${T('Unloaded')}: ${r.unloaded.join(', ')}${r.vram_after_mb != null ? ` · VRAM ${Math.round(r.vram_after_mb)} MB` : ''}` : T('No local model was loaded.'), r.errors.length ? 'err' : 'ok');
    if (r.errors.length) toast(r.errors.join('; '), 'err');
    refreshVram(); window.refreshRuntimeBadges && refreshRuntimeBadges();
    return r;
  }
  function showGate(d, retry) {
    const box = $('#ws-gate');
    box.innerHTML = `<div class="card" style="border-color:var(--err);margin:8px 0;padding:10px 12px"><b>⛔ ${T('GPU run refused')}</b>
      <div class="status" style="margin:4px 0">${esc(d.message || '')}</div>
      <div class="row" style="gap:6px;flex-wrap:wrap"><button class="btn small primary" data-g="unload">🧹 ${T('Unload & run')}</button>
        <button class="btn small" data-g="cpu">${T('Run on CPU instead')}</button><button class="btn small" data-g="cancel">${T('Cancel')}</button></div></div>`;
    box.querySelector('[data-g=unload]').onclick = e => busy(e.target, async () => { const r = await unload(); if (!r.errors.length) { box.innerHTML = ''; retry(false); } });
    box.querySelector('[data-g=cpu]').onclick = () => { box.innerHTML = ''; retry(true); };
    box.querySelector('[data-g=cancel]').onclick = () => { box.innerHTML = ''; };
  }

  // ------------------------------------------------------------------ run / stream / stop
  function paintHist() { const l = $('#ws-cmdlist'); if (l) l.innerHTML = W.hist.map(c => `<option value="${esc(c)}">`).join(''); }
  async function runCmd(cmd) {
    cmd = (cmd || $('#ws-cmd').value).trim();
    if (!cmd) return toast(T('Type a command, e.g. python train.py'), 'err');
    $('#ws-cmd').value = cmd;
    W.hist = [cmd, ...W.hist.filter(c => c !== cmd)].slice(0, 20); try { localStorage.setItem('ide_cmd_hist', JSON.stringify(W.hist)); } catch {} paintHist();
    startJob(cmd, $('#ws-cpu').checked);
  }
  async function startJob(cmd, cpu) {
    try {
      followJob(await api('/api/sandbox/run', {method: 'POST', body: {cmd, kind: 'run', cpu}}));
    } catch (e) {
      const d = detailOf(e);
      if (d && d.vram_busy) return showGate(d, onCpu => startJob(cmd, onCpu || cpu));
      if (d && d.need_image) {
        if (confirm(`${T('The sandbox image')} ${d.need_image} ${T('is not downloaded yet (PyTorch+CUDA images are several GB). Download it now?')}`))
          followJob(await api('/api/sandbox/pull', {method: 'POST', body: {image: d.need_image}}), () => startJob(cmd, cpu));
        return;
      }
      logLine('err', '✗ ' + e.message); toast(e.message, 'err');
    }
  }
  function followJob(j, onDone) {
    if (W.es) W.es.close();
    W.job = j; W.series = {}; $('#ws-log').innerHTML = ''; $('#ws-curves').innerHTML = '';
    $('#ws-stop').disabled = false; jobStatus(j);
    const es = new EventSource(`/api/sandbox/jobs/${j.id}/stream`); W.es = es;
    es.onmessage = ev => {
      const d = JSON.parse(ev.data);
      if (d.type === 'lines') d.lines.forEach(([s, t]) => logLine(s, t));
      else if (d.type === 'info') jobStatus(d.job);
      else if (d.type === 'end') { es.close(); W.es = null; jobStatus(d.job); $('#ws-stop').disabled = true; jobEnded(d.job); if (onDone && d.job.status === 'done') onDone(); }
    };
    es.onerror = () => { es.close(); W.es = null; $('#ws-stop').disabled = true; };
  }
  function jobStatus(j) {
    W.job = j;
    const st = {running: '⏳', done: '✅', failed: '❌', stopped: '■'}[j.status] || '';
    $('#ws-jobst').textContent = `${st} ${j.title || j.cmd} · ${T(j.status)}${j.duration != null ? ' · ' + j.duration + ' s' : ''}${j.mode ? ' · ' + j.mode : ''}`;
  }
  function jobEnded(j) {
    loadRuns(); refreshGit(true); refreshVram();
    if (j.status === 'done' && j.meta && Object.keys(j.meta.metrics || {}).length)
      toast(`${T('Run finished')} · ` + Object.entries(j.meta.metrics).slice(0, 4).map(([k, v]) => `${k}=${fmt(v)}`).join(' · '), 'ok');
    if (j.status === 'failed' && !W.busy) {
      const d = document.createElement('div'); d.className = 'evline err';
      d.innerHTML = `❌ ${esc(j.cmd)} — exit ${j.exit_code} <button class="btn small">✳ ${T('Ask the agent to fix it')}</button>`;
      d.querySelector('button').onclick = () => sendAgent(`The command \`${j.cmd}\` failed (exit ${j.exit_code}). Read the error in the last run, fix the code and run it again.`, true);
      $('#ws-log').after(d);
    }
  }
  async function stopJob() { if (W.job) try { await api(`/api/sandbox/jobs/${W.job.id}/stop`, {method: 'POST'}); } catch (e) { toast(e.message, 'err'); } }
  const KV = /([A-Za-z_][\w./-]{0,40})\s*[=:]\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\b/g;
  const STEP = /^(epoch|step|iter|iteration|ep)$/i;
  let curvesT = null;
  function logLine(stream, text) {
    const log = $('#ws-log'); if (!log) return;
    const s = document.createElement('span');
    if (stream === 'err') s.className = 'e'; else if (stream === 'sys') s.className = 's';
    s.textContent = text + '\n'; log.append(s);
    while (log.childNodes.length > 3000) log.firstChild.remove();
    log.scrollTop = log.scrollHeight;
    if (stream === 'out' && text.length < 400) {   // live metrics: "epoch 3 loss=0.12 psnr=28.4"
      const pairs = [...text.matchAll(KV)].map(m => [m[1], +m[2]]);
      let step = (pairs.find(([k]) => STEP.test(k)) || [])[1];
      const m0 = text.match(/^\s*(?:epoch|ep)\s+(\d+)/i); if (step == null && m0) step = +m0[1];
      if (step != null) { pairs.forEach(([k, v]) => { if (!STEP.test(k)) (W.series[k] = W.series[k] || []).push([step, v]); }); if (!curvesT) curvesT = setTimeout(paintCurves, 300); }
    }
  }
  function lineChart(points, color = 'var(--accent2)', w = 320, h = 110) {
    if (!points.length) return '';
    const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const X = x => 30 + (x1 === x0 ? 0.5 : (x - x0) / (x1 - x0)) * (w - 40), Y = y => 8 + (y1 === y0 ? 0.5 : 1 - (y - y0) / (y1 - y0)) * (h - 26);
    const d = points.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
    return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:${w}px;height:auto"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.8"/>
      <text x="2" y="12" font-size="9" fill="currentColor" opacity=".6">${(+y1).toPrecision(4)}</text><text x="2" y="${h - 14}" font-size="9" fill="currentColor" opacity=".6">${(+y0).toPrecision(4)}</text>
      <text x="30" y="${h - 2}" font-size="9" fill="currentColor" opacity=".6">${x0}</text><text x="${w - 10}" y="${h - 2}" font-size="9" fill="currentColor" opacity=".6" text-anchor="end">${x1}</text></svg>`;
  }
  function curvesHtml(series) {
    const keys = Object.keys(series);
    return keys.length ? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:10px">${keys.map(k => {
      const s = series[k]; return `<div class="dcard"><h5>${esc(k)} <span style="margin-left:auto;color:var(--text)">${(+s[s.length - 1][1]).toPrecision(5)}</span></h5>${lineChart(s)}</div>`; }).join('')}</div>` : '';
  }
  function paintCurves() { curvesT = null; $('#ws-curves').innerHTML = curvesHtml(W.series); }

  // ------------------------------------------------------------------ runs
  async function loadRuns() {
    const box = $('#ws-runs'); if (!box) return;
    try {
      const {runs, best} = await api('/api/sandbox/runs');
      $('#ws-best').innerHTML = Object.keys(best).length ? '🏆 ' + Object.entries(best).slice(0, 4).map(([k, v]) => `${esc(k)}=${fmt(v.value)}`).join(' · ') : '';
      box.innerHTML = runs.length ? `<table class="dtable">${runs.slice(0, 40).map(r => `<tr data-r="${esc(r.id)}" style="cursor:pointer">
        <td><span class="st ${esc(r.status)}">${esc(T(r.status || ''))}</span></td><td class="mono">${esc(r.id)}</td><td class="mono">${esc((r.cmd || '').slice(0, 46))}</td>
        <td>${Object.entries(r.metrics || {}).slice(0, 3).map(([k, v]) => `${esc(k)}=${fmt(v)}`).join(' · ')}${(r.figures || []).length ? ` · 🖼 ${r.figures.length}` : ''}</td>
        <td class="mono">${r.git && r.git.short ? esc(r.git.short) + (r.git.dirty ? '✎' : '') : ''}</td></tr>`).join('')}</table>`
        : `<div class="status">${T('No runs yet. ▶ Run a script.')}</div>`;
      $$('#ws-runs [data-r]').forEach(tr => tr.onclick = () => openRun(tr.dataset.r));
    } catch (e) { box.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; }
  }
  async function openRun(id) {
    const pane = $('#ws-rundetail'); pane.innerHTML = '<div class="status"><span class="spin"></span></div>';
    let r; try { r = await api('/api/sandbox/runs/' + encodeURIComponent(id)); } catch (e) { pane.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
    const file = f => `/api/sandbox/runs/${encodeURIComponent(r.id)}/file?path=${encodeURIComponent(f)}`;
    const g = r.git || {}, cm = r.clearml || {};
    pane.innerHTML = `<div class="dsec"><h4>📈 ${esc(r.id)} <span class="st ${esc(r.status)}">${esc(T(r.status || ''))}</span><button class="btn small" id="rr-close" style="margin-left:auto">✕</button></h4>
      <div class="status" style="font-family:var(--mono)">$ ${esc(r.cmd || '')} · ${esc(r.mode || '')} · exit ${r.exit_code} · ${r.duration ?? '?'} s
        ${g.sha ? ` · ⑂ ${esc(g.sha.slice(0, 10))}${g.dirty ? ' (+' + T('uncommitted') + ')' : ''}` : ''}${r.environment && r.environment.gpu === false ? ' · CPU' : ''}${cm.task_id ? (cm.url ? ` · <a href="${esc(cm.url)}" target="_blank" rel="noopener">ClearML ↗</a>` : ` · ClearML offline <span title="${esc(cm.session_zip || '')}">${esc(cm.task_id.slice(0, 20))}…</span>`) : cm.error ? ` · ClearML ⚠ ${esc(cm.error.slice(0, 80))}` : ''}</div>
      <div class="row" style="gap:6px;margin:8px 0;flex-wrap:wrap"><button class="btn small" id="rr-rerun" style="flex:0">↻ ${T('Run again')}</button><button class="btn small" id="rr-paper" style="flex:0">→ ${T('Use results in the paper')}</button>
        <button class="btn small" id="rr-agent" style="flex:0">✳ ${T('Discuss with the agent')}</button><button class="btn small" id="rr-record" style="flex:0">🔬 ${T('Record as experiment')}</button></div>
      ${Object.keys(r.metrics || {}).length ? `<table class="dtable" style="max-width:520px">${Object.entries(r.metrics).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono">${esc(String(v))}</td></tr>`).join('')}</table>` : ''}
      ${curvesHtml((r.parsed || {}).series || {})}
      ${(r.figures || []).length ? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-top:10px">${r.figures.map(f => /\.pdf$/i.test(f)
        ? `<a class="btn small" target="_blank" href="${file(f)}">📕 ${esc(f)}</a>` : `<a target="_blank" href="${file(f)}"><img src="${file(f)}" style="width:100%;border-radius:8px;background:#fff;border:1px solid var(--line)"></a>`).join('')}</div>` : ''}
      ${r.stderr ? `<details><summary class="status">stderr</summary><pre class="joblog">${esc(r.stderr.slice(-8000))}</pre></details>` : ''}
      <details><summary class="status">stdout</summary><pre class="joblog">${esc((r.stdout || '').slice(-20000)) || '(empty)'}</pre></details></div>`;
    $('#rr-close').onclick = () => { pane.innerHTML = ''; };
    $('#rr-rerun').onclick = () => runCmd(r.cmd);
    $('#rr-paper').onclick = () => api('/api/paper/import-results', {method: 'POST', body: {run_ids: [r.id]}}).then(() => toast(T('Results and a LaTeX table were added to the Paper Writer'), 'ok')).catch(e => toast(e.message, 'err'));
    $('#rr-agent').onclick = () => { $('#ws-cin').value = `Analyse run ${r.id} (${r.status}, metrics ${JSON.stringify(r.metrics || {})}). What should I try next?`; $('#ws-cin').focus(); };
    $('#rr-record').onclick = () => { document.querySelector('nav button[data-tab=control]').click(); setTimeout(() => { window.CONTROL_API && CONTROL_API.show('timeline'); setTimeout(() => { const s = $('#cc-e-run'); if (s) s.value = r.id; }, 1200); }, 300); };
  }

  // ------------------------------------------------------------------ text diff (no editor needed)
  function diffLines(a, b) {
    const A = (a || '').split('\n'), B = (b || '').split('\n');
    if (A.length * B.length > 4e6) return B.map(l => ['+', l]);
    const n = A.length, m = B.length, L = Array.from({length: n + 1}, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = []; let i = 0, j = 0;
    while (i < n && j < m) { if (A[i] === B[j]) { out.push([' ', A[i]]); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) out.push(['-', A[i++]]); else out.push(['+', B[j++]]); }
    while (i < n) out.push(['-', A[i++]]); while (j < m) out.push(['+', B[j++]]);
    return out;
  }
  function diffHtml(a, b) {
    const d = diffLines(a, b), keep = new Set();
    d.forEach(([t], k) => { if (t !== ' ') for (let x = Math.max(0, k - 3); x <= Math.min(d.length - 1, k + 3); x++) keep.add(x); });
    let last = -1, html = '';
    d.forEach(([t, l], k) => { if (!keep.has(k)) return; if (last >= 0 && k > last + 1) html += '<span class="s">…\n</span>'; last = k;
      html += `<span${t === '-' ? ' class="e"' : t === '+' ? ' class="ok"' : ''}>${t} ${esc(l)}\n</span>`; });
    return `<pre class="joblog wsdiff">${html || T('(no changes)')}</pre>`;
  }

  // ------------------------------------------------------------------ source control / GitHub
  async function refreshGit(quiet) {
    try { W.git = await api('/api/git/status'); } catch (e) { if (!quiet) toast(e.message, 'err'); return; }
    paintScm();
  }
  function paintScm() {
    const g = W.git || {}, box = $('#ws-scm'); if (!box) return;
    const gh = (typeof CFG !== 'undefined' && CFG && CFG.github) || {};
    if (!g.git) { box.innerHTML = `<div class="status">${T('Git is not installed.')} <a href="https://git-scm.com/download/win" target="_blank" rel="noopener">Git for Windows ↗</a></div>`; return; }
    if (!g.repo) { box.innerHTML = `<p class="status">${T('The workspace is not a Git repository yet.')}</p><button class="btn primary" id="scm-init">⑂ ${T('Initialize repository')}</button>`;
      $('#scm-init').onclick = e => busy(e.target, async () => { W.git = await api('/api/git/init', {method: 'POST'}); paintScm(); }); return; }
    box.innerHTML = `<div class="status" style="margin:0 0 6px">⑂ ${esc(g.branch || 'main')}${g.remote ? ` · <a href="${esc(g.remote.replace(/\.git$/, ''))}" target="_blank" rel="noopener">${esc(g.remote.replace(/^https:\/\/github.com\//, '').replace(/\.git$/, ''))}</a>` : ''}${g.ahead ? ` · ↑${g.ahead}` : ''}${g.behind ? ` · ↓${g.behind}` : ''}</div>
      <textarea id="scm-msg" rows="2" placeholder="${esc(T('Commit message (Ctrl+Enter to commit)'))}"></textarea>
      <div class="row" style="margin:6px 0;gap:6px"><button class="btn small primary" id="scm-commit">✓ ${T('Commit')}${g.files.length ? ` (${g.files.length})` : ''}</button>
        ${g.remote ? `<button class="btn small" id="scm-push" style="flex:0">↑ ${T('Push')}</button><button class="btn small" id="scm-pull" style="flex:0">↓</button>` : ''}</div>
      <div id="scm-files">${g.files.map((f, i) => `<div class="ccline"><input type="checkbox" data-c="${i}" checked style="flex:0 0 auto"><a href="#" data-d="${i}" style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(f.path)}</a><span class="ccchip">${esc(T(f.status))}</span><a href="#" data-o="${i}" title="${esc(T('Open in VS Code'))}">↗</a></div>`).join('') || `<div class="status">${T('No changes')}</div>`}</div>
      <div id="scm-diff"></div>
      <details style="margin-top:10px" ${g.remote ? '' : 'open'}><summary style="cursor:pointer;font-weight:600;font-size:13px">🚀 ${T('Publish to GitHub')}</summary>
        <label>${T('Repository name')}</label><input type="text" id="scm-repo" value="${esc((($('#proj-tag') || {}).textContent || 'research-code').replace(/^📂\s*/, '').trim().toLowerCase().replace(/[^a-z0-9._-]+/g, '-'))}">
        <label>${T('Description')}</label><input type="text" id="scm-desc" placeholder="${esc(T('Code for my PhD research project'))}">
        <label class="chk"><input type="checkbox" id="scm-private" checked> 🔒 ${T('Private repository')}</label>
        <button class="btn primary" id="scm-publish" style="width:100%;margin-top:8px">🚀 ${T('Publish to GitHub')}</button><div class="status" id="scm-pubst"></div></details>
      <details style="margin-top:8px" ${gh.has_token ? '' : 'open'}><summary style="cursor:pointer;font-weight:600;font-size:13px">⚙ ${T('GitHub settings')} ${gh.has_token ? '✓' : ''}</summary>
        <label>${T('Personal Access Token')} <a href="https://github.com/settings/tokens?type=beta" target="_blank" rel="noopener" style="font-size:11px">${T('create ↗')}</a></label>
        <input type="password" id="gh-token" value="${esc(gh.token || '')}" placeholder="github_pat_…" autocomplete="off">
        <div class="row" style="gap:6px"><div><label>${T('Commit name')}</label><input type="text" id="gh-name" value="${esc(gh.name || '')}"></div><div><label>E-mail</label><input type="text" id="gh-email" value="${esc(gh.email || '')}"></div></div>
        <div class="row" style="margin-top:6px;gap:6px"><button class="btn small" id="gh-save">💾 ${T('Save')}</button><button class="btn small" id="gh-test">${T('Test token')}</button></div>
        <div class="status">${T('The token is stored only in data/config.json and sent only to GitHub. It is never written into .git/config.')}</div></details>
      <div class="status" style="margin-top:10px">${(g.commits || []).slice(0, 8).map(c => `<div><span style="font-family:var(--mono);color:var(--accent2)">${esc(c.hash)}</span> ${esc(c.message)} · ${esc(c.when)}</div>`).join('') || T('No commits yet')}</div>`;
    const files = g.files;
    $$('#scm-files [data-d]').forEach(a => a.onclick = async e => { e.preventDefault(); const f = files[a.dataset.d];
      try { const d = await api('/api/git/diff?path=' + encodeURIComponent(f.path)); $('#scm-diff').innerHTML = `<div class="status">${esc(f.path)} (HEAD ↔ ${T('working tree')})</div>` + diffHtml(d.original, d.modified); } catch (err) { toast(err.message, 'err'); } });
    $$('#scm-files [data-o]').forEach(a => a.onclick = e => { e.preventDefault(); openFile(files[a.dataset.o].path); });
    const commit = () => busy($('#scm-commit'), async () => {
      const paths = files.filter((_, i) => $(`#scm-files [data-c="${i}"]`)?.checked).map(f => f.path);
      W.git = await api('/api/git/commit', {method: 'POST', body: {message: $('#scm-msg').value, paths: paths.length === files.length ? null : paths}}); toast(T('Committed'), 'ok'); paintScm();
    });
    $('#scm-commit').onclick = commit;
    $('#scm-msg').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) commit(); });
    $('#scm-push') && ($('#scm-push').onclick = e => busy(e.target, async () => { W.git = await api('/api/git/push', {method: 'POST'}); toast(T('Pushed to GitHub'), 'ok'); paintScm(); }, '…'));
    $('#scm-pull') && ($('#scm-pull').onclick = e => busy(e.target, async () => { W.git = await api('/api/git/pull', {method: 'POST'}); toast(T('Pulled'), 'ok'); paintScm(); }, '…'));
    $('#scm-publish').onclick = e => busy(e.target, async () => {
      const r = await api('/api/git/publish', {method: 'POST', body: {repo: $('#scm-repo').value, private: $('#scm-private').checked, description: $('#scm-desc').value}});
      W.git = r.status; paintScm();
      $('#scm-pubst').innerHTML = `✓ <a href="${esc(r.html_url)}" target="_blank" rel="noopener">${esc(r.html_url)}</a> (${r.private ? T('private') : T('public')})`;
      toast(T('Published to GitHub'), 'ok');
    }, T('Publishing…'));
    const saveGh = async () => { await api('/api/config', {method: 'POST', body: {github: {token: $('#gh-token').value, name: $('#gh-name').value, email: $('#gh-email').value}}}); CFG = await api('/api/config'); };
    $('#gh-save').onclick = e => busy(e.target, async () => { await saveGh(); toast(T('GitHub settings saved'), 'ok'); paintScm(); }, '…');
    $('#gh-test').onclick = e => busy(e.target, async () => { await saveGh(); const u = await api('/api/git/user'); await api('/api/config', {method: 'POST', body: {github: {user: u.login}}}); toast(`✓ ${u.login}${u.name ? ' (' + u.name + ')' : ''}`, 'ok'); }, '…');
  }

  // ------------------------------------------------------------------ self-debugging co-coding agent (customer scenario 2)
  function projKey() { return ((typeof CFG !== 'undefined' && CFG && CFG.project && CFG.project.data_dir) || 'default').replace(/[^\w]/g, '').slice(-40); }
  function persistChat() { try { localStorage.setItem('ide_chat_' + projKey(), JSON.stringify(W.chat.slice(-60))); W.sid ? localStorage.setItem('ide_sid_' + projKey(), W.sid) : localStorage.removeItem('ide_sid_' + projKey()); } catch {} }
  function buildAgent() {
    try { W.chat = JSON.parse(localStorage.getItem('ide_chat_' + projKey()) || '[]'); W.sid = localStorage.getItem('ide_sid_' + projKey()) || null; } catch {}
    $('#ws-agent').innerHTML = `<div class="row" style="margin-bottom:6px"><b style="flex:1">✳ ${T('Self-debugging agent')}</b><span class="rtbadge" data-agent="coder" title="Engine / model of this agent — click to change"></span><button class="iconbtn" id="ws-cclear" title="New conversation">🧹</button></div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:6px"><select id="ws-amode" style="flex:1 1 180px"><option value="suggest">${T('💡 Suggest (review changes)')}</option><option value="auto">${T('⚡ Auto: apply → run → self-debug')}</option></select>
        <label style="flex:0 0 auto;margin:0">${T('tries')} <select id="ws-aiter" style="width:auto"><option>2</option><option>3</option><option selected>4</option><option>6</option><option>8</option></select></label>
        <label class="chk" style="flex:0 0 auto;margin:0" title="${esc(T('The agent’s commands run without GPU — useful for smoke tests while a local LLM runs the agent'))}"><input type="checkbox" id="ws-acpu"> ${T('agent runs on CPU')}</label></div>
      <div class="cmsgs" id="ws-cmsgs" style="max-height:440px;overflow:auto"></div>
      <div class="ccomp"><textarea id="ws-cin" rows="3" placeholder="${esc(T('Ask the agent: implement, refactor, explain, fix… (Enter to send)'))}"></textarea>
        <div class="row" style="gap:6px;justify-content:flex-end"><button class="sendbtn" id="ws-csend" title="Send" style="flex:0 0 auto">↑</button></div></div>
      <div class="status">${T('For larger edits use Codex in VS Code. A local engine for this agent holds VRAM: unload it before GPU training, or tick “agent runs on CPU”.')}</div>`;
    try { $('#ws-amode').value = localStorage.getItem('ide_amode') || 'suggest'; } catch {}
    $('#ws-amode').onchange = e => { try { localStorage.setItem('ide_amode', e.target.value); } catch {} };
    $('#ws-csend').onclick = () => W.busy ? (W.ctrl && W.ctrl.abort()) : sendAgent();
    $('#ws-cin').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!W.busy) sendAgent(); } });
    $('#ws-cclear').onclick = () => { if (W.busy) return; W.chat = []; W.sid = null; persistChat(); renderChat(); };
    renderChat();
    window.refreshRuntimeBadges && refreshRuntimeBadges();
  }
  function renderChat() {
    const box = $('#ws-cmsgs');
    box.innerHTML = W.chat.length ? W.chat.map((m, i) => m.role === 'user' ? `<div class="cmsg user"><div class="ububble">${esc(m.content)}</div></div>`
      : `<div class="cmsg ai" data-i="${i}"><div class="md"></div>${(m.events || []).map(ev => `<div class="evline ${ev.c || ''}">${esc(ev.t)}</div>`).join('')}<div class="props"></div></div>`).join('')
      : `<div class="status">${T('In ⚡ Auto mode the agent applies its changes, runs them in the sandbox and fixes errors from stderr until the run succeeds.')}</div>`;
    box.querySelectorAll('.cmsg.ai').forEach(el => { const m = W.chat[el.dataset.i]; setRich(el.querySelector('.md'), m.content || ''); (m.proposals || []).forEach(p => el.querySelector('.props').append(proposalCard(p))); });
    box.scrollTop = box.scrollHeight;
  }
  function proposalCard(p) {
    const d = document.createElement('div');
    d.innerHTML = (p.files || []).map((f, i) => `<div class="prop"><div class="ph"><span>${f.exists ? '✎' : '＋'}</span><b title="${esc(f.path)}">${esc(f.path)}</b><span class="add">+${f.added}</span><span class="rem">−${f.removed}</span></div>
        <div class="pa"><button class="iconbtn" data-diff="${i}">⇄ ${T('Diff')}</button>${p.applied ? `<span class="status" style="margin:0 6px">✓ ${T('applied')}</span>` : `<button class="iconbtn" data-apply="${i}">✓ ${T('Apply')}</button>`}<button class="iconbtn" data-open="${i}">↗ VS Code</button></div><div data-dbox="${i}"></div></div>`).join('')
      + ((p.files || []).length || p.run ? `<div class="row" style="gap:6px;margin:4px 0">${!p.applied && (p.files || []).length ? `<button class="btn small primary" data-all>✓ ${T('Apply all')}</button>` : ''}
        ${p.run ? `<button class="btn small" data-run>▶ ${p.applied || !(p.files || []).length ? '' : T('Apply & ')}${T('Run')} <code style="font-size:11px">${esc(p.run.slice(0, 50))}</code></button>` : ''}</div>` : '');
    const applyFiles = async files => { await api('/api/ide/apply', {method: 'POST', body: {files}}); refreshGit(true); };
    d.querySelectorAll('[data-diff]').forEach(b => b.onclick = () => { const box = d.querySelector(`[data-dbox="${b.dataset.diff}"]`); const f = p.files[b.dataset.diff];
      box.innerHTML = box.innerHTML ? '' : diffHtml(f.old, f.content); });
    d.querySelectorAll('[data-apply]').forEach(b => b.onclick = async () => { try { await applyFiles([p.files[b.dataset.apply]]); b.outerHTML = `<span class="status" style="margin:0 6px">✓ ${T('applied')}</span>`; } catch (e) { toast(e.message, 'err'); } });
    d.querySelectorAll('[data-open]').forEach(b => b.onclick = () => openFile(p.files[b.dataset.open].path));
    const all = d.querySelector('[data-all]');
    if (all) all.onclick = async () => { try { await applyFiles(p.files); p.applied = true; persistChat(); renderChat(); toast(T('Changes applied'), 'ok'); } catch (e) { toast(e.message, 'err'); } };
    const run = d.querySelector('[data-run]');
    if (run) run.onclick = async () => { try { if (!p.applied && (p.files || []).length) { await applyFiles(p.files); p.applied = true; persistChat(); } runCmd(p.run); renderChat(); } catch (e) { toast(e.message, 'err'); } };
    return d;
  }
  function setBusy(on) { W.busy = on; const b = $('#ws-csend'); b.classList.toggle('stop', on); b.textContent = on ? '■' : '↑'; }
  async function sendAgent(text, forceAuto) {
    const q = (text || $('#ws-cin').value).trim(); if (!q) return;
    $('#ws-cin').value = '';
    W.chat.push({role: 'user', content: q});
    const ai = {role: 'assistant', content: '', events: [], proposals: []};
    W.chat.push(ai); renderChat();
    const el = $('#ws-cmsgs').lastElementChild, mdEl = el.querySelector('.md');
    mdEl.innerHTML = '<span class="thinking">Thinking<span>.</span><span>.</span><span>.</span></span>';
    const auto = forceAuto || $('#ws-amode').value === 'auto';
    setBusy(true); W.ctrl = new AbortController();
    let cur = '', paintT = null;
    const paint = () => { paintT = null; mdEl.innerHTML = md(ai.content + cur) + '<span class="cursor"></span>'; $('#ws-cmsgs').scrollTop = $('#ws-cmsgs').scrollHeight; };
    const ev = (t, c) => { ai.events.push({t, c}); const x = document.createElement('div'); x.className = 'evline ' + (c || ''); x.textContent = t; el.insertBefore(x, el.querySelector('.props')); $('#ws-cmsgs').scrollTop = $('#ws-cmsgs').scrollHeight; };
    try {
      const hist = W.chat.slice(0, -1).filter(m => m.content).map(m => ({role: m.role, content: m.content}));
      const resp = await fetch('/api/ide/agent', {method: 'POST', signal: W.ctrl.signal, headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({messages: hist.slice(-24), auto, max_iters: +$('#ws-aiter').value, cpu: $('#ws-acpu').checked, session_id: W.sid})});
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || 'HTTP ' + resp.status);
      const reader = resp.body.getReader(), dec = new TextDecoder(); let buf = '';
      for (;;) {
        const {value, done} = await reader.read(); if (done) break;
        buf += dec.decode(value, {stream: true}); let k;
        while ((k = buf.indexOf('\n\n')) >= 0) {
          const line = buf.slice(0, k).trim(); buf = buf.slice(k + 2);
          if (!line.startsWith('data:')) continue;
          const d = JSON.parse(line.slice(5));
          if (d.type === 'start') W.sid = d.session_id;
          else if (d.type === 'iter' && d.n > 1) { ai.content += cur + `\n\n---\n**${T('Attempt')} ${d.n}**\n\n`; cur = ''; }
          else if (d.type === 'delta') { cur += d.text; if (!paintT) paintT = setTimeout(paint, 60); }
          else if (d.type === 'proposal') {
            ai.content += cur; cur = ''; clearTimeout(paintT); paintT = null; setRich(mdEl, ai.content);
            const prop = {files: d.files, run: d.run, applied: auto}; ai.proposals.push(prop); el.querySelector('.props').append(proposalCard(prop));
            if (d.note) ev('⚠ ' + d.note, 'err');
            if (!d.files.length && !d.run && auto) ev(T('(no file changes or command proposed)'));
          }
          else if (d.type === 'applied') { ev(`✓ ${T('applied')}: ${d.paths.join(', ')}`, 'ok'); refreshGit(true); }
          else if (d.type === 'run_start') { ev(`▶ ${d.job.cmd}`, 'run'); W.series = {}; $('#ws-log').innerHTML = ''; jobStatus(d.job); $('#ws-stop').disabled = false; logLine('sys', `── agent run ${d.job.id} ──`); }
          else if (d.type === 'run_lines') d.lines.forEach(([s, t]) => logLine(s, t));
          else if (d.type === 'run_end') { const j = d.job; jobStatus(j); $('#ws-stop').disabled = true; loadRuns();
            ev(`${j.status === 'done' ? '✅' : j.status === 'stopped' ? '■' : '❌'} ${j.cmd} → ${T(j.status)} (exit ${j.exit_code}, ${j.duration} s)`, j.status === 'done' ? 'ok' : 'err'); }
          else if (d.type === 'gave_up') ev(`⚠ ${T('Stopped after')} ${d.n} ${T('attempts — read the error and guide the agent.')}`, 'err');
          else if (d.type === 'done') { ai.content = (ai.content + cur).trim() || d.reply; cur = ''; }
          else if (d.type === 'error') { ev('⚠ ' + d.detail, 'err'); if (d.vram_busy) showGate({message: d.detail}, onCpu => { if (onCpu) $('#ws-acpu').checked = true; sendAgent(q, auto); }); }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') { ev('■ ' + T('Stopped by user'), 'err'); if (W.job && W.job.status === 'running') stopJob(); }
      else ev('⚠ ' + e.message, 'err');
    }
    ai.content = (ai.content + cur).trim();
    clearTimeout(paintT); W.ctrl = null; setBusy(false); persistChat(); renderChat();
  }

  // ------------------------------------------------------------------ sandbox mode line
  async function refreshMode() {
    try {
      const s = await api('/api/sandbox/status?full=0'), c = s.container || {};
      $('#ws-mode').innerHTML = s.mode === 'docker'
        ? `🐳 docker · ${esc(s.image)}${c.running ? ` · <span class="led ok"></span> ${T('container up')}` : ` · <span class="led warn"></span> ${T('starts on first run')}`}${s.settings.gpu ? ' · GPU' : ''}`
        : `🐍 ${T('local venv')}${s.docker_installed && !s.docker_running ? ` · <span class="led warn"></span> ${T('Docker not running')}` : ''}`;
    } catch {}
  }

  function init() {
    if (!W.inited) { W.inited = true; build(); setInterval(() => { if (root().classList.contains('on')) { refreshMode(); refreshVram(); } }, 15000); }
    loadWorkspace(); refreshMode(); refreshVram(); loadRuns(); refreshGit(true);
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'ide') { init(); window.ENV_PANEL && ENV_PANEL.render(); } });
  // kept for callers of the former Code IDE: opening a file now opens it in VS Code
  window.IDE_API = {openFile, init, sendAgent, state: W, followJob, startJob};
})();
