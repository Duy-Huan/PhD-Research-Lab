/* PhD Research Lab v3.4 — Environment panel of Workspace & Runs: Auto / Python environment / Docker, interpreter and image
   pickers (vetted catalog, images on this machine, Docker Hub search with tags), automatic dependencies, one-click prepare. */
(() => {
  const T = s => I18N.tr(s);
  const E = {sum: null, pythons: null, cat: null, hub: null, tags: null, busy: false};
  const box = () => $('#ws-env');

  async function load(force) {
    const [sum, py, cat] = await Promise.all([api('/api/env'), E.pythons && !force ? {pythons: E.pythons} : api('/api/env/pythons' + (force ? '?refresh=1' : '')),
      api('/api/env/docker/catalog').catch(() => ({docker: false, catalog: [], local: []}))]);
    E.sum = sum; E.pythons = py.pythons; E.cat = cat;
  }

  async function render(force) {
    const b = box(); if (!b) return;
    if (!E.sum || force) {
      if (!E.sum) b.innerHTML = `<h4>🧰 ${T('Environment')}</h4><div class="status"><span class="spin"></span>${T('Detecting Python interpreters and Docker images…')}</div>`;
      try { await load(force); } catch (e) { b.innerHTML = `<h4>🧰 ${T('Environment')}</h4><div class="status">⚠ ${esc(e.message)}</div>`; return; }
    }
    const s = E.sum.settings, eff = E.sum.effective, kind = {local: 'python', docker: 'docker'}[s.mode] || 'auto';
    const effTxt = eff.mode === 'docker' ? `🐳 Docker · <code>${esc(eff.image)}</code>` : `🐍 Python · <code>${esc((eff.python || {}).python || '')}</code>`;
    const base = s.python_base || (E.pythons.find(p => p.source === 'PhD-Lab app') || {}).path || '';
    const pyOpts = E.pythons.map(p => `<option value="${esc(p.path)}" ${p.path === base ? 'selected' : ''}>${esc(`Python ${p.version} · ${p.conda ? 'conda' : p.venv ? 'venv' : T('system')}${p.jupyterlab ? ' · Jupyter' : ''}${p.torch ? ' · torch' : ''} — ${p.path}`)}</option>`).join('');
    const cur = s.image || E.cat.recommended || '';
    const groups = {};
    E.cat.catalog.forEach(c => (groups[c.group] = groups[c.group] || []).push(c));
    const imgOpt = c => `<option value="${esc(c.image)}" ${c.image === cur ? 'selected' : ''}>${c.present ? '✓ ' : '⤓ '}${esc(c.image)}${c.recommended ? ' ★' : ''}${c.size_gb ? ` (~${c.size_gb} GB)` : ''}</option>`;
    const known = new Set([...E.cat.catalog.map(c => c.image), ...E.cat.local.map(c => c.image)]);
    const imgSel = Object.entries(groups).map(([g, items]) => `<optgroup label="${esc(T(g))}">${items.map(imgOpt).join('')}</optgroup>`).join('')
      + (E.cat.local.length ? `<optgroup label="${esc(T('On this machine'))}">${E.cat.local.map(c => imgOpt({...c})).join('')}</optgroup>` : '')
      + (cur && !known.has(cur) ? `<optgroup label="${esc(T('Custom'))}">${imgOpt({image: cur})}</optgroup>` : '');
    const curInfo = [...E.cat.catalog, ...E.cat.local].find(c => c.image === cur) || {};
    const deps = E.sum.deps, pk = [...(deps.requirements_files || []).map(f => '📄 ' + f), ...(deps.declared || []), ...deps.imports.map(i => i.pip)];
    b.innerHTML = `<h4>🧰 ${T('Environment')} <span class="status" style="margin:0 0 0 auto">${T('Active')}: ${effTxt}</span></h4>
      <div class="seg2 themesw" role="radiogroup" aria-label="${esc(T('Environment'))}">
        ${[['auto', '✨ ' + T('Auto')], ['python', '🐍 ' + T('Python environment')], ['docker', '🐳 Docker']].map(([k, l]) =>
          `<button data-kind="${k}" class="${k === kind ? 'on' : ''}" role="radio" aria-checked="${k === kind}">${l}</button>`).join('')}</div>
      <p class="status" style="margin:6px 0 0">${kind === 'auto' ? `${T('Auto chooses per run')}: ${esc(T(eff.reason))}.`
        : kind === 'python' ? T('Runs in a Python on this computer — starts instantly, uses your local packages and GPU drivers.')
        : T('Runs in a container — reproducible, the same CUDA stack on every machine; the first pull downloads the image.')}</p>
      <div class="envgrid">
        <div class="envcol ${kind === 'docker' ? 'dim' : ''}">
          <label>🐍 ${T('Python interpreter')} <button class="iconbtn" id="env-pyref" title="${esc(T('Scan this computer again'))}">↻</button></label>
          <select id="env-py">${pyOpts}</select>
          <div class="row" style="gap:14px;flex-wrap:wrap;margin-top:6px">
            <label class="chk" style="margin:0;flex:0 0 auto"><input type="radio" name="env-pm" value="venv" ${s.python_mode !== 'existing' ? 'checked' : ''}> ${T('Private project venv built from it')}</label>
            <label class="chk" style="margin:0;flex:0 0 auto"><input type="radio" name="env-pm" value="existing" ${s.python_mode === 'existing' ? 'checked' : ''}> ${T('Use this interpreter directly')}</label></div>
          <p class="status">${s.python_mode === 'existing' ? T('Packages are installed into this interpreter — use it for a conda/venv you manage yourself.')
            : T('Isolated per project; it also sees the packages of the chosen interpreter.')}</p>
        </div>
        <div class="envcol ${kind === 'python' ? 'dim' : ''}">
          <label>🐳 ${T('Docker image')} ${E.cat.docker ? '' : `<span class="badge warn">${T('Docker not running')}</span>`}</label>
          <div class="row"><select id="env-img">${imgSel}</select><button class="btn small" id="env-hub" style="flex:0">🔎 Docker Hub</button></div>
          <div class="row" style="gap:12px;margin-top:6px;flex-wrap:wrap">
            <label class="chk" style="margin:0;flex:0 0 auto"><input type="checkbox" id="env-gpu" ${s.gpu ? 'checked' : ''}> ${T('Use the GPU')}</label>
            <span class="status" style="margin:0">${curInfo.present ? '✓ ' + T('downloaded') : '⤓ ' + T('not downloaded yet')}${curInfo.note ? ' · ' + esc(curInfo.note) : ''}</span>
            ${curInfo.present || !E.cat.docker ? '' : `<button class="btn small" id="env-pull" style="flex:0">⤓ ${T('Pull now')}</button>`}</div>
          <div id="env-hubbox"></div>
        </div>
      </div>
      <div class="envdeps">
        <label class="chk" style="margin:0"><input type="checkbox" id="env-auto" ${s.auto_deps !== false ? 'checked' : ''}> ${T('Install the libraries the project needs automatically before every run')}</label>
        <div class="status" style="margin:4px 0 0">${pk.length ? `${T('Detected')} (${pk.length}): ` + pk.slice(0, 18).map(x => `<code>${esc(x)}</code>`).join(' ') + (pk.length > 18 ? ' …' : '')
          : T('No third-party import found yet — add code or a requirements.txt.')}${deps.gpu_frameworks.length ? ` · GPU: ${esc(deps.gpu_frameworks.join(', '))}` : ''}</div>
        <div class="row" style="margin-top:8px;gap:8px"><button class="btn primary" id="env-prepare" style="flex:0">⚙ ${T('Prepare environment')}</button>
          <span class="status" style="margin:0">${T('Optional: Run does the same automatically. Use it to download / install ahead of time.')}</span></div>
      </div>`;
    wire(kind);
  }

  async function save(patch, msg) {
    try { E.sum = await api('/api/env/select', {method: 'POST', body: patch}); if (msg) toast(T(msg), 'ok'); }
    catch (e) { toast(e.message, 'err'); }
    render();
  }

  function wire() {
    $$('#ws-env [data-kind]').forEach(b => b.onclick = () => save({kind: b.dataset.kind}, 'Environment updated'));
    $('#env-py').onchange = e => save({python_base: e.target.value === (E.pythons.find(p => p.source === 'PhD-Lab app') || {}).path ? '' : e.target.value}, 'Interpreter updated');
    $$('#ws-env input[name=env-pm]').forEach(r => r.onchange = () => save({python_mode: r.value}, 'Environment updated'));
    $('#env-pyref').onclick = e => busy(e.target, async () => { E.pythons = null; await render(true); });
    $('#env-img').onchange = e => save({image: e.target.value}, 'Image selected — the container is recreated on the next run');
    $('#env-gpu').onchange = e => save({gpu: e.target.checked});
    $('#env-auto').onchange = e => save({auto_deps: e.target.checked});
    $('#env-hub').onclick = hubBox;
    const pull = $('#env-pull'); if (pull) pull.onclick = () => follow(api('/api/sandbox/pull', {method: 'POST', body: {image: $('#env-img').value}}), () => render(true));
    $('#env-prepare').onclick = e => busy(e.target, prepare);
  }

  function follow(promise, after) {
    return promise.then(j => { window.IDE_API && IDE_API.followJob(j, after); $('#ws-log') && $('#ws-log').scrollIntoView({block: 'nearest'}); return j; })
      .catch(e => toast(e.message, 'err'));
  }

  async function prepare() {
    try {
      const r = await api('/api/env/prepare', {method: 'POST'});
      IDE_API.followJob(r.job, r.step === 'pull' ? () => prepare() : () => { toast(T('Environment ready — press Run'), 'ok'); render(true); });
    } catch (e) { toast(e.message, 'err'); }
  }

  // ---- Docker Hub search → repository → tag
  function hubBox() {
    const hb = $('#env-hubbox');
    if (hb.innerHTML) { hb.innerHTML = ''; return; }
    hb.innerHTML = `<div class="hub"><div class="row"><input type="text" id="env-hq" placeholder="${esc(T('e.g. pytorch, tensorflow, nvidia/cuda, mambaorg/micromamba'))}">
        <button class="btn small" id="env-hgo" style="flex:0">${T('Search')}</button></div>
      <div class="row" style="margin-top:6px"><input type="text" id="env-hcustom" placeholder="${esc(T('or type a full image, e.g. ghcr.io/org/image:tag'))}"><button class="btn small" id="env-huse" style="flex:0">${T('Use')}</button></div>
      <div id="env-hres"></div></div>`;
    const go = () => busy($('#env-hgo'), async () => {
      try {
        const r = await api('/api/env/docker/search?q=' + encodeURIComponent($('#env-hq').value.trim()));
        $('#env-hres').innerHTML = r.results.length ? `<div class="hublist">${r.results.map(x => `<button class="hubitem" data-repo="${esc(x.name)}"><b>${esc(x.name)}</b>${x.official ? ` <span class="badge ok">${T('official')}</span>` : ''} <span class="status">★ ${x.stars}</span><small>${esc(x.description)}</small></button>`).join('')}</div>` : `<div class="status">${T('No results')}</div>`;
        $$('#env-hres [data-repo]').forEach(el => el.onclick = () => tags(el.dataset.repo));
      } catch (e) { toast(e.message, 'err'); }
    });
    $('#env-hgo').onclick = go;
    $('#env-hq').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); go(); } });
    $('#env-huse').onclick = () => { const v = $('#env-hcustom').value.trim(); if (v) save({image: v, kind: 'docker'}, 'Image selected — the container is recreated on the next run'); };
    $('#env-hq').focus();
  }

  async function tags(repo, q = '') {
    const out = $('#env-hres');
    out.innerHTML = `<div class="status"><span class="spin"></span>${esc(repo)}…</div>`;
    try {
      const r = await api(`/api/env/docker/tags?repo=${encodeURIComponent(repo)}&q=${encodeURIComponent(q)}`);
      out.innerHTML = `<div class="row" style="margin:6px 0"><b style="flex:1">${esc(repo)}</b><input type="text" id="env-tq" value="${esc(q)}" placeholder="${esc(T('filter tags, e.g. cuda12'))}" style="flex:0 0 200px"></div>
        <div class="hublist">${r.tags.map(t => `<button class="hubitem" data-img="${esc(t.image)}"><b>${esc(t.tag)}</b> <span class="status">${t.size_gb ? '~' + t.size_gb + ' GB · ' : ''}${esc(t.updated)}</span></button>`).join('') || `<div class="status">${T('No results')}</div>`}</div>`;
      $('#env-tq').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); tags(repo, e.target.value.trim()); } });
      $$('#env-hres [data-img]').forEach(el => el.onclick = () => save({image: el.dataset.img, kind: 'docker'}, 'Image selected — the container is recreated on the next run'));
    } catch (e) { out.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; }
  }

  window.ENV_PANEL = {render};
})();
