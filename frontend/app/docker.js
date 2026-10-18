/* PhD Research Lab v3.0 — 🐳 Docker & System: machine scan + recommended setup, live GPU/VRAM/RAM/container monitor,
   container lifecycle, image pulls, sandbox settings, job monitor with logs, local AI servers, MCP endpoint. */
(() => {
  const T = s => I18N.tr(s);
  const D = {inited: false, timer: null, scan: null, status: null, local: null, cstats: [], logJob: null, es: null};
  const root = () => $('#tab-docker');
  const led = (ok, warn) => `<span class="led ${ok ? 'ok' : warn ? 'warn' : 'err'}"></span>`;
  const gb = mb => mb == null ? '?' : (mb / 1024).toFixed(1) + ' GB';
  const pct = v => v == null ? '–' : Math.round(v) + '%';
  const parsePct = s => parseFloat(String(s || '').replace('%', '')) || 0;

  function spark(values, color, max) {
    const v = values.filter(x => x != null);
    if (v.length < 2) return `<svg class="spark"></svg>`;
    const w = 300, h = 46, mx = max || Math.max(...v, 1), n = values.length;
    const pts = values.map((y, i) => [i / (n - 1) * w, h - 3 - ((y ?? 0) / mx) * (h - 6)]);
    const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path class="a" d="${d}L${w},${h}L0,${h}Z" fill="${color}"/><path class="l" d="${d}" stroke="${color}"/></svg>`;
  }

  function build() {
    root().innerHTML = `<div class="v3sec">
      <div class="row" style="align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:12px">
        <div style="flex:1;min-width:300px"><h2 style="margin:0 0 4px">🐳 ${T('Docker & System')}</h2>
          <p class="lead" style="margin:0">${T('Live status of the code sandbox (Docker + GPU), your machine and the local AI servers. Everything refreshes every 2 seconds while this tab is open.')}</p></div>
        <div class="row" style="flex:0 0 auto;gap:6px"><button class="btn" id="dk-rescan">🔎 ${T('Rescan machine')}</button><button class="btn primary" id="dk-apply">⚡ ${T('Apply recommended setup')}</button></div>
      </div>
      <div class="dgrid" id="dk-cards"></div>
      <div class="dgrid" id="dk-charts"></div>
      <div class="cxgrid" style="grid-template-columns:minmax(0,1.3fr) minmax(320px,1fr)">
        <div>
          <div class="card dsec"><h4>📦 ${T('Sandbox container')} <span class="status" id="dk-cname" style="margin:0;font-family:var(--mono)"></span></h4>
            <div class="row" style="flex-wrap:wrap;gap:6px" id="dk-cact">
              <button class="btn small primary" data-c="start">▶ ${T('Start')}</button><button class="btn small" data-c="stop">■ ${T('Stop')}</button>
              <button class="btn small" data-c="restart">↻ ${T('Restart')}</button><button class="btn small" data-c="recreate" title="Apply new settings (image, limits, GPU)">♻ ${T('Recreate')}</button>
              <button class="btn small danger" data-c="remove">🗑 ${T('Remove')}</button><span style="flex:1"></span>
              <button class="btn small" id="dk-pull">⤓ ${T('Pull image')}</button><button class="btn small" id="dk-gpu">🎮 ${T('Test GPU')}</button></div>
            <div id="dk-cinfo" style="margin-top:10px"></div></div>
          <div class="card dsec"><h4>⚙ ${T('Sandbox settings')} <span class="status" style="margin:0">(${T('saved per project')})</span></h4>
            <div class="dform">
              <div><label>${T('Engine')}</label><select id="dk-mode"><option value="auto">${T('Auto (Docker if running, else local)')}</option><option value="docker">${T('Docker only')}</option><option value="local">${T('Local Python venv')}</option></select></div>
              <div style="grid-column:span 2"><label>${T('Docker image')}</label><input type="text" id="dk-image" list="dk-images" placeholder="pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime"><datalist id="dk-images"></datalist></div>
              <div><label>${T('RAM limit (GB)')}</label><input type="text" id="dk-mem"></div>
              <div><label>${T('CPU limit')}</label><input type="text" id="dk-cpus"></div>
              <div><label>${T('Shared memory (GB)')}</label><input type="text" id="dk-shm"></div>
              <div><label>${T('Time limit per run (s)')}</label><input type="text" id="dk-timeout"></div>
              <div><label>${T('Self-debug attempts')}</label><input type="text" id="dk-sd"></div>
              <div><label class="chk"><input type="checkbox" id="dk-gpuon"> 🎮 ${T('GPU passthrough (--gpus all)')}</label>
                <label class="chk"><input type="checkbox" id="dk-net"> 🌐 ${T('Network (pip install, downloads)')}</label></div>
            </div>
            <div class="row" style="margin-top:10px;gap:6px"><button class="btn primary" id="dk-save">💾 ${T('Save settings')}</button><span class="status" id="dk-savest" style="margin:0"></span></div></div>
          <div class="card dsec"><h4>🧾 ${T('Jobs')} <span class="status" style="margin:0" id="dk-jobsum"></span></h4>
            <div style="overflow-x:auto"><table class="dtable" id="dk-jobs"></table></div>
            <div id="dk-logbox" hidden><div class="row" style="margin-top:10px;gap:6px"><b id="dk-logtitle" style="flex:1;font-size:13px"></b><button class="btn small" id="dk-logstop">■ ${T('Stop')}</button><button class="btn small" id="dk-logclose">✕</button></div><pre class="joblog" id="dk-log"></pre></div></div>
        </div>
        <div>
          <div class="card dsec"><h4>🧭 ${T('Recommended setup for this machine')}</h4><div id="dk-recs"></div></div>
          <div class="card dsec"><h4>🖥 ${T('Machine')}</h4><div id="dk-machine"></div></div>
          <div class="card dsec"><h4>🤖 ${T('Local AI servers')}</h4><div id="dk-local"></div></div>
          <div class="card dsec"><h4>🖼 ${T('Images')} & ${T('containers')}</h4><div id="dk-images-l"></div></div>
          <div class="card dsec"><h4>🔌 MCP ${T('server')}</h4><p class="status" style="margin-top:0">${T('The sandbox is also exposed as MCP tools (sandbox_run_code, sandbox_manage_files, sandbox_get_metrics) for external AI clients on this computer.')}</p>
            <div class="mcpbox" id="dk-mcp"></div></div>
        </div>
      </div></div>`;
    $('#dk-rescan').onclick = e => busy(e.target, () => loadScan(true), T('Scanning…'));
    $('#dk-apply').onclick = e => busy(e.target, async () => {
      if (!confirm('Apply the recommended sandbox settings and agent engines for this machine?')) return;
      const r = await api('/api/system/apply-recommendation', {method: 'POST'});
      toast(T('Recommended setup applied'), 'ok'); fillSettings(r.settings); if (window.loadConfig) loadConfig(); tick(true);
    }, '…');
    $$('#dk-cact [data-c]').forEach(b => b.onclick = () => container(b.dataset.c, b));
    $('#dk-pull').onclick = () => pull();
    $('#dk-gpu').onclick = async () => { try { const j = await api('/api/sandbox/test-gpu', {method: 'POST'}); showLog(j); } catch (e) { needImage(e) || toast(e.message, 'err'); } };
    $('#dk-save').onclick = e => busy(e.target, saveSettings, '…');
    $('#dk-logclose').onclick = () => { $('#dk-logbox').hidden = true; D.es && D.es.close(); };
    $('#dk-logstop').onclick = () => D.logJob && api(`/api/sandbox/jobs/${D.logJob.id}/stop`, {method: 'POST'}).catch(e => toast(e.message, 'err'));
    $('#dk-mcp').textContent = `Endpoint (Streamable HTTP):  ${location.origin}/mcp\n\nClaude Desktop (stdio) — claude_desktop_config.json:\n{"mcpServers": {"phd-research-lab": {"command": "python", "args": ["<app folder>/mcp_stdio_bridge.py"]}}}`;
  }

  function needImage(e) {
    let d = null; try { d = JSON.parse(e.message); } catch {}
    if (d && d.need_image) { if (confirm(`Image ${d.need_image} is not downloaded yet. Pull it now?`)) pull(d.need_image); return true; }
    return false;
  }
  async function container(action, btn) {
    if (action === 'remove' && !confirm('Remove the sandbox container? Packages installed inside it (pip install) are lost; your code and runs stay in data/.')) return;
    try {
      const r = await busy(btn, () => api('/api/sandbox/container', {method: 'POST', body: {action}}), '…');
      if (r && r.warning) toast(r.warning, 'err');
      tick(true);
    } catch (e) { needImage(e); }
  }
  async function pull(image) {
    image = image || $('#dk-image').value.trim() || (D.status && D.status.image);
    try { const j = await api('/api/sandbox/pull', {method: 'POST', body: {image}}); showLog(j); toast(`${T('Pulling')} ${image}…`); } catch (e) { toast(e.message, 'err'); }
  }
  function fillSettings(s) {
    $('#dk-mode').value = s.mode; $('#dk-image').value = s.image || ''; $('#dk-mem').value = s.memory_gb; $('#dk-cpus').value = s.cpus;
    $('#dk-shm').value = s.shm_gb; $('#dk-timeout').value = s.timeout_s; $('#dk-sd').value = s.self_debug_max; $('#dk-gpuon').checked = s.gpu; $('#dk-net').checked = s.network;
  }
  async function saveSettings() {
    const body = {mode: $('#dk-mode').value, image: $('#dk-image').value.trim(), memory_gb: $('#dk-mem').value, cpus: $('#dk-cpus').value, shm_gb: $('#dk-shm').value,
      timeout_s: $('#dk-timeout').value, self_debug_max: $('#dk-sd').value, gpu: $('#dk-gpuon').checked, network: $('#dk-net').checked};
    const r = await api('/api/sandbox/settings', {method: 'PUT', body});
    fillSettings(r.settings);
    const c = (D.status || {}).container;
    $('#dk-savest').textContent = c && c.exists ? T('Saved — press ♻ Recreate to apply image/limits to the running container.') : T('Saved.');
    toast(T('Sandbox settings saved'), 'ok'); tick(true);
  }

  function showLog(job) {
    D.logJob = job; $('#dk-logbox').hidden = false; $('#dk-logtitle').textContent = `${job.title || job.cmd} · ${job.status}`;
    const box = $('#dk-log'); box.innerHTML = '';
    if (D.es) D.es.close();
    const es = new EventSource(`/api/sandbox/jobs/${job.id}/stream`); D.es = es;
    es.onmessage = ev => {
      const d = JSON.parse(ev.data);
      if (d.type === 'lines') { box.insertAdjacentHTML('beforeend', d.lines.map(([s, t]) => `<div class="${s === 'err' ? 'e' : s === 'sys' ? 's' : ''}">${esc(t)}</div>`).join('')); box.scrollTop = box.scrollHeight; }
      if (d.type === 'end') { es.close(); $('#dk-logtitle').textContent = `${job.title || job.cmd} · ${d.job.status} (exit ${d.job.exit_code})`; tick(true); }
    };
    es.onerror = () => es.close();
  }

  // ------------------------------------------------------------------ rendering
  function cards() {
    const s = D.status || {}, sc = D.scan || {}, lv = D.live || {};
    const dk = sc.docker || {}, c = s.container || {}, st = s.stats || {};
    const g = (lv.gpus || sc.gpus || [])[0];
    const mem = lv.memory || sc.memory || {};
    const vramPct = g && g.vram_total_mb ? 100 * g.vram_used_mb / g.vram_total_mb : 0;
    $('#dk-cards').innerHTML = `
      <div class="dcard"><h5>${led(s.docker_running, s.docker_installed)} Docker</h5>
        <div class="big">${s.docker_running ? T('Running') : s.docker_installed ? T('Not running') : T('Not installed')}</div>
        <div class="kv"><span>${T('Version')}</span><span>${esc(dk.server_version || dk.client_version || '–')}</span><span>${T('Backend')}</span><span>${esc(dk.os || '–')}${dk.wsl2 ? ' · WSL2' : ''}</span>
          <span>GPU</span><span>${dk.gpu_runtime ? '✓ ' + T('available') : '–'}</span><span>${T('Containers')}</span><span>${dk.containers_running ?? '–'} ${T('running')}</span></div></div>
      <div class="dcard"><h5>${led(s.mode === 'docker' ? c.running : true, s.mode === 'docker')} ${T('Sandbox')}</h5>
        <div class="big">${s.mode === 'docker' ? '🐳 Docker' : '🐍 ' + T('Local venv')}</div>
        <div class="kv"><span>${T('Image')}</span><span title="${esc(s.image || '')}">${esc(s.mode === 'docker' ? s.image || '' : '–')}</span>
          <span>${T('Container')}</span><span>${c.exists ? (c.running ? '✓ ' + T('up') : T(c.status || 'stopped')) : T('not created')}</span>
          <span>GPU</span><span>${c.exists ? (c.gpu ? '✓ --gpus all' : '–') : (s.settings && s.settings.gpu ? T('requested') : '–')}</span>
          <span>${T('Limits')}</span><span>${c.exists ? `${c.memory_gb || '∞'} GB · ${c.cpus || '∞'} CPU · shm ${c.shm_gb} GB` : '–'}</span></div></div>
      <div class="dcard"><h5>${led(!!g, false)} GPU ${g ? '· ' + esc(g.name) : ''}</h5>
        ${g ? `<div class="big">${pct(g.util_pct)} <span class="status" style="font-size:12px">${T('utilization')}</span></div>
        <div class="bar ${vramPct > 85 ? 'hot' : ''}"><i style="width:${vramPct}%"></i></div>
        <div class="kv"><span>VRAM</span><span>${gb(g.vram_used_mb)} / ${gb(g.vram_total_mb)}</span><span>${T('Temp / power')}</span><span>${g.temp_c ?? '–'} °C · ${g.power_w ?? '–'} W</span>
          <span>${T('Driver / CUDA')}</span><span>${esc(g.driver || '')} · ${esc(g.cuda || (sc.gpus && sc.gpus[0] && sc.gpus[0].cuda) || '')}</span></div>`
        : `<div class="big">–</div><div class="status">${T('No NVIDIA GPU detected (nvidia-smi not found).')}</div>`}</div>
      <div class="dcard"><h5>${led(true)} ${T('Host')}</h5><div class="big">${pct(mem.used_pct)} <span class="status" style="font-size:12px">RAM</span></div>
        <div class="bar ${mem.used_pct > 85 ? 'hot' : ''}"><i style="width:${mem.used_pct || 0}%"></i></div>
        <div class="kv"><span>RAM</span><span>${mem.available_gb ?? '?'} / ${mem.total_gb ?? '?'} GB ${T('free')}</span><span>CPU</span><span title="${esc((sc.cpu || {}).name || '')}">${(sc.cpu || {}).cores || '?'} ${T('cores')}${lv.cpu && lv.cpu.load_1m != null ? ' · load ' + lv.cpu.load_1m : ''}</span>
          <span>${T('Disk (data/)')}</span><span>${(sc.disk || {}).free_gb ?? '?'} GB ${T('free')}</span></div></div>
      <div class="dcard"><h5>${led(c.running, c.exists)} ${T('Container usage')}</h5>
        ${st.cpu_pct ? `<div class="big">${esc(st.cpu_pct)} <span class="status" style="font-size:12px">CPU</span></div><div class="bar"><i style="width:${Math.min(100, parsePct(st.mem_pct))}%"></i></div>
        <div class="kv"><span>${T('Memory')}</span><span>${esc(st.mem || '')} (${esc(st.mem_pct || '')})</span><span>${T('Processes')}</span><span>${esc(st.pids || '')}</span><span>${T('Net / disk I/O')}</span><span>${esc(st.net || '')} · ${esc(st.block || '')}</span></div>`
        : `<div class="big">–</div><div class="status">${T('Container not running.')}</div>`}</div>`;
    const h = (lv.history || []);
    $('#dk-charts').innerHTML = `
      <div class="dcard"><h5>GPU % <span style="margin-left:auto;color:var(--text)">${g ? pct(g.util_pct) : '–'}</span></h5>${spark(h.map(x => x.gpu_util), 'var(--accent2)', 100)}</div>
      <div class="dcard"><h5>VRAM <span style="margin-left:auto;color:var(--text)">${g ? gb(g.vram_used_mb) : '–'}</span></h5>${spark(h.map(x => x.vram_used), 'var(--local)', (g || {}).vram_total_mb)}</div>
      <div class="dcard"><h5>${T('Host RAM')} % <span style="margin-left:auto;color:var(--text)">${pct(mem.used_pct)}</span></h5>${spark(h.map(x => x.ram_pct), 'var(--accent)', 100)}</div>
      <div class="dcard"><h5>${T('Container CPU')} % <span style="margin-left:auto;color:var(--text)">${esc(st.cpu_pct || '–')}</span></h5>${spark(D.cstats.map(x => x.cpu), 'var(--ok)')}</div>`;
    $('#dk-cname').textContent = c.name || '';
    $('#dk-cinfo').innerHTML = c.exists ? `<div class="kv" style="display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:12.5px">
        <span class="status" style="margin:0">ID</span><span style="font-family:var(--mono)">${esc(c.id)}</span><span class="status" style="margin:0">${T('Started')}</span><span>${esc((c.started || '').replace('T', ' ').slice(0, 19))}</span>
        <span class="status" style="margin:0">${T('Network')}</span><span>${esc(c.network || '')}</span>
        ${(c.mounts || []).map(m => `<span class="status" style="margin:0">${esc(m.dst)}</span><span style="font-family:var(--mono);font-size:11.5px;overflow:hidden;text-overflow:ellipsis">${esc(m.src)}</span>`).join('')}</div>`
      : `<div class="status">${s.mode === 'docker' ? T('The container is created automatically on the first run (or press ▶ Start).') + (s.image_present === false ? ` <b>${T('Image not downloaded yet')}</b> — ⤓ ${T('Pull image')}.` : '') : T('Local mode: code runs in data/…/sandbox/venv.')}</div>`;
  }
  function jobs() {
    const js = (D.status || {}).jobs || [];
    const run = js.filter(j => j.status === 'running').length;
    $('#dk-jobsum').textContent = `${run} ${T('running')} · ${js.length} ${T('recent')}`;
    $('#dk-jobs').innerHTML = `<tr><th>${T('Status')}</th><th>${T('Job')}</th><th>${T('Kind')}</th><th>${T('Engine')}</th><th>${T('Duration')}</th><th>${T('Exit')}</th><th></th></tr>`
      + (js.map((j, i) => `<tr><td><span class="st ${j.status}">${esc(T(j.status))}</span></td><td class="mono" title="${esc(j.cmd)}">${esc((j.title || j.cmd).slice(0, 70))}</td><td>${esc(j.kind)}</td><td>${esc(j.mode)}</td>
        <td>${j.duration != null ? j.duration + ' s' : ''}</td><td>${j.exit_code ?? ''}</td><td style="white-space:nowrap"><button class="iconbtn" data-log="${i}">📜</button>${j.status === 'running' ? `<button class="iconbtn" data-stop="${i}">■</button>` : ''}</td></tr>`).join('')
      || `<tr><td colspan="7" class="status">${T('No jobs yet in this session. Runs from the Code IDE appear here.')}</td></tr>`);
    $$('#dk-jobs [data-log]').forEach(b => b.onclick = () => showLog(js[b.dataset.log]));
    $$('#dk-jobs [data-stop]').forEach(b => b.onclick = () => api(`/api/sandbox/jobs/${js[b.dataset.stop].id}/stop`, {method: 'POST'}).then(() => tick(true)).catch(e => toast(e.message, 'err')));
  }
  function lists() {
    const s = D.status || {};
    $('#dk-images').innerHTML = ['pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime', 'python:3.11-slim', ...(s.images || []).map(i => `${i.repo}:${i.tag}`)].map(x => `<option value="${esc(x)}">`).join('');
    $('#dk-images-l').innerHTML = s.docker_running ? `<table class="dtable"><tr><th>${T('Image')}</th><th>${T('Size')}</th><th>${T('Created')}</th></tr>${(s.images || []).slice(0, 20).map(i => `<tr><td class="mono">${esc(i.repo)}:${esc(i.tag)}</td><td>${esc(i.size)}</td><td>${esc(i.created)}</td></tr>`).join('') || `<tr><td colspan="3" class="status">${T('No images')}</td></tr>`}</table>
      <table class="dtable" style="margin-top:8px"><tr><th>${T('Container')}</th><th>${T('Image')}</th><th>${T('Status')}</th></tr>${(s.containers || []).map(c => `<tr><td class="mono">${c.mine ? '★ ' : ''}${esc(c.name)}</td><td class="mono">${esc(c.image)}</td><td>${esc(c.status)}</td></tr>`).join('') || `<tr><td colspan="3" class="status">–</td></tr>`}</table>`
      : `<div class="status">${T('Docker is not running.')}</div>`;
  }
  function scanView() {
    const sc = D.scan; if (!sc) return;
    const rec = sc.recommendation || {};
    $('#dk-recs').innerHTML = (rec.items || []).map(r => `<div class="rec ${r.level}"><span class="lv">${esc(r.level.toUpperCase())}</span><span class="ar">${esc(T(r.area))}</span><span>${esc(r.text)}</span></div>`).join('')
      + (rec.sandbox ? `<div class="status" style="margin-top:8px">${T('Recommended sandbox')}: <b>${esc(rec.sandbox.mode)}</b>${rec.sandbox.image ? ' · ' + esc(rec.sandbox.image) : ''}${rec.sandbox.memory_gb ? ` · ${rec.sandbox.memory_gb} GB RAM · ${rec.sandbox.cpus} CPU` : ''}${rec.sandbox.gpu ? ' · GPU' : ''}</div>` : '');
    const t = sc.tools || {}, w = sc.wsl || {};
    const row = (k, v, ok) => `<tr><td>${esc(k)}</td><td>${ok === undefined ? '' : led(ok, false)} ${v}</td></tr>`;
    $('#dk-machine').innerHTML = `<table class="dtable">
      ${row('OS', esc(`${sc.os.system} ${sc.os.release} (${sc.os.machine}) · Python ${sc.os.python}`))}
      ${row('CPU', esc(`${sc.cpu.name || '?'} · ${sc.cpu.cores} ${T('cores')}`))}
      ${row('RAM', esc(`${sc.memory.total_gb} GB`))}
      ${(sc.gpus || []).map(g => row('GPU', esc(`${g.name} · ${gb(g.vram_total_mb)} · driver ${g.driver} · CUDA ${g.cuda || '?'}`), true)).join('') || row('GPU', T('none detected'), false)}
      ${w.applicable ? row('WSL', esc(w.installed ? (w.distros || []).map(d => `${d.name} (v${d.version}, ${d.state})`).join(', ') || 'installed' : T('not installed')), !!w.wsl2) : ''}
      ${row('Docker', esc(sc.docker.installed ? `${sc.docker.server_version || sc.docker.client_version || ''} ${sc.docker.running ? '' : '(' + T('daemon not running') + ')'}` : T('not installed')), sc.docker.running)}
      ${row('Git', esc(t.git || T('not installed')), !!t.git)}
      ${row('LaTeX', esc((t.latex || []).join(', ') || T('none')), (t.latex || []).length > 0)}
      ${row('CUDA toolkit (nvcc)', esc(t.nvcc || '–'))}
      ${row('LM Studio CLI (lms)', t.lms_cli ? '✓' : '–')}
    </table><div class="status">${T('Scanned')} ${esc((sc.time || '').replace('T', ' ').slice(0, 19))} UTC</div>`;
  }
  function localView() {
    const L = D.local; if (!L) return;
    const lm = L.lmstudio || {}, ol = L.ollama || {};
    $('#dk-local').innerHTML = `<table class="dtable">
      <tr><td>${led(lm.online)} LM Studio</td><td>${lm.online ? `${(lm.loaded || []).length} ${T('loaded')}: <span style="font-family:var(--mono);font-size:11.5px">${esc((lm.loaded || []).join(', ') || '–')}</span> · ${(lm.models || []).length} ${T('available')}` : esc(lm.error || T('offline'))}</td></tr>
      <tr><td>${led(ol.online)} Ollama</td><td>${ol.online ? `${(ol.loaded || []).length} ${T('loaded')}: ${(ol.loaded || []).map(m => `<span style="font-family:var(--mono);font-size:11.5px">${esc(m.id)}</span> (${m.size_vram ? (m.size_vram / 2 ** 30).toFixed(1) + ' GB VRAM' : 'CPU'})`).join(', ') || '–'} · ${(ol.models || []).length} ${T('available')}` : esc(ol.error || T('offline'))}</td></tr>
    </table><div class="status">${T('Load / unload models in the sidebar (🖥 LM Studio · 🦙 Ollama). Unload the local model before long GPU training runs on a 12 GB card.')}</div>`;
  }

  // ------------------------------------------------------------------ polling
  async function loadScan(force) {
    try { D.scan = await api('/api/system/scan' + (force ? '?force=1' : '')); scanView(); cards(); } catch (e) { toast(e.message, 'err'); }
  }
  let lastFull = 0;
  async function tick(full) {
    if (!root().classList.contains('on')) return;
    const doFull = full || Date.now() - lastFull > 10000;
    try {
      const [st, lv] = await Promise.all([api('/api/sandbox/status?full=' + (doFull ? 1 : 0)), api('/api/system/live')]);
      if (!doFull && D.status) { st.images = D.status.images; st.containers = D.status.containers; st.image_present = D.status.image_present; } else lastFull = Date.now();
      D.status = st; D.live = lv;
      if (st.stats) { D.cstats.push({t: Date.now(), cpu: parsePct(st.stats.cpu_pct)}); D.cstats = D.cstats.slice(-150); }
      if (!D.filled) { fillSettings(st.settings); D.filled = true; }
      cards(); jobs(); if (doFull) lists();
    } catch (e) { /* server busy */ }
    if (doFull) { try { D.local = await api('/api/local/status'); localView(); } catch {} }
  }
  async function init() {
    if (!D.inited) { D.inited = true; build(); loadScan(false); }
    tick(true);
    clearInterval(D.timer); D.timer = setInterval(() => tick(false), 2000);
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'docker') init(); else clearInterval(D.timer); });
  window.DOCKER_API = {init, showLog};
})();
