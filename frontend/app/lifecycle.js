/* PhD Research Lab v4.1 — model lifecycle: what is loaded right now (VRAM), manual unload, and the load/unload policy of
   every engine class (local models, CLI sessions, MCP sandbox container, cloud connection pool).
   Live status is polled only while the Settings page is visible and the browser tab is in the foreground. */
(() => {
  const T = s => I18N.tr(s);
  const C = window.WFCORE;
  const L = {timer: null, data: null, busy: false};
  const CLASSES = [
    ['local_background', 'Local AI — background tasks', 'Summaries, critic, PDF parsing, embeddings, workflow agents'],
    ['local_interactive', 'Local AI — chats', 'Chats and streamed answers you are reading'],
    ['cli', 'CLI agents (Codex, Claude Code, Antigravity)', 'Keep = resume the provider session on the next question; the process always exits'],
    ['mcp', 'MCP AI tools & sandbox container', 'Docker container used by MCP tools, agent and trial runs'],
    ['cloud', 'Cloud AI (Claude API, OpenAI, …)', 'Pooled HTTPS connections (faster follow-up calls)'],
  ];
  const IDLE = {local_background: 'local_idle_min', local_interactive: 'local_idle_min', cli: 'cli_idle_min', mcp: 'mcp_idle_min',
                cloud: 'cloud_idle_min'};

  function residentHTML(d) {
    const g = d.gpu || {}, pct = C.vramPct(g.vram_used_mb, g.vram_total_mb);
    const models = (d.local || {}).models || [], loading = (d.local || {}).loading || [];
    const rows = models.map(m => `<tr><td><b>${esc(m.model)}</b><div class="status" style="margin:0">${esc(m.engine_label)}${m.quantization ? ' · ' + esc(m.quantization) : ''}</div></td>
        <td>${C.fmtMB(m.vram_mb)}</td><td><span class="badge ${m.leases ? 'ok' : ''}">${esc(T(C.releaseLabel(m)))}</span></td>
        <td>${m.policy ? esc(T(C.policyLabel(m.policy))) : '—'}</td>
        <td><button class="btn small" data-lc-unload="${esc(m.engine)}" data-model="${esc(m.model)}" ${m.leases ? 'disabled title="' + esc(T('answering right now')) + '"' : ''}>⏏ ${T('Unload')}</button></td></tr>`).join('')
      + loading.map(r => `<tr><td><b>${esc(r.model)}</b></td><td>—</td><td><span class="badge warn">${T('loading…')}</span></td><td></td><td></td></tr>`).join('');
    return `<div class="lc-gpu">${g.name ? `<b>${esc(g.name)}</b> · ` : ''}VRAM ${C.fmtMB(g.vram_used_mb)} / ${C.fmtMB(g.vram_total_mb)}
        ${pct === null ? '' : `<div class="bar ${pct > 85 ? 'hot' : ''}"><i style="width:${pct}%"></i></div>`}</div>
      ${rows ? `<table class="dtable lc-table"><thead><tr><th>${T('Model in memory')}</th><th>VRAM</th><th>${T('State')}</th><th>${T('Policy')}</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
        : `<p class="status">${T('No local model is loaded — VRAM is free for training.')}</p>`}
      <div class="row" style="gap:8px;margin-top:8px"><span class="status" style="flex:1;margin:0">${onlineLine(d)}</span>
        ${models.length ? `<button class="btn small danger" data-lc-unload="all">⏏ ${T('Unload all')}</button>` : ''}
        <button class="btn small" data-lc-refresh>↻</button></div>`;
  }

  function onlineLine(d) {
    const o = ((d.local || {}).online) || {};
    return `Ollama ${o.ollama ? '●' : '○'} · LM Studio ${o.local ? '●' : '○'} · ${T('CLI processes')}: ${(d.cli || {}).running_processes || 0} · ${T('pool')}: ${(d.cloud || {}).pool_open ? T('open') : T('closed')}`;
  }

  function historyHTML(d) {
    const h = (d.history || []).slice(0, 12);
    if (!h.length) return `<p class="status">${T('Nothing released yet.')}</p>`;
    return `<ul class="lc-hist">${h.map(x => `<li class="${x.ok ? '' : 'err'}"><span>${new Date(x.ts * 1000).toLocaleTimeString()}</span> ${esc(x.action)} <code>${esc(x.key)}</code> ${esc(x.reason || '')} ${x.detail ? '— ' + esc(x.detail) : ''}</li>`).join('')}</ul>`;
  }

  function trackedHTML(d) {
    const items = (d.registry || []).filter(r => r.kind !== 'local');
    if (!items.length) return '';
    return `<table class="dtable lc-table"><thead><tr><th>${T('Resource')}</th><th>${T('State')}</th><th></th></tr></thead><tbody>${items.map(r => `<tr>
      <td><code>${esc(r.key)}</code></td><td>${esc(T(C.releaseLabel(r)))}</td>
      <td>${r.leases ? '' : `<button class="btn small" data-lc-release="${esc(r.key)}">${T('Release now')}</button>`}</td></tr>`).join('')}</tbody></table>`;
  }

  function paint() {
    const d = L.data;
    if (!d) return;
    $$('[data-lc-live]').forEach(el => el.innerHTML = residentHTML(d));
    if ($('#lc-tracked')) $('#lc-tracked').innerHTML = trackedHTML(d);
    if ($('#lc-hist')) $('#lc-hist').innerHTML = historyHTML(d);
  }

  async function refresh() {
    if (L.busy) return;
    L.busy = true;
    try { L.data = await api('/api/lifecycle/status'); paint(); } catch (e) {
      $$('[data-lc-live]').forEach(el => el.innerHTML = `<p class="status">⚠ ${esc(e.message)}</p>`);
    } finally { L.busy = false; }
  }

  document.addEventListener('click', e => {
    const u = e.target.closest('[data-lc-unload]');
    if (u) {
      const eng = u.dataset.lcUnload, model = u.dataset.model || '';
      busy(u, async () => {
        const r = await api('/api/lifecycle/unload', {method: 'POST', body: {engine: eng, model}});
        const n = (r.unloaded || []).length, sk = (r.skipped_in_use || []).length;
        toast(n ? T('Unloaded') + ': ' + r.unloaded.join(', ') : sk ? T('Skipped: the model is answering right now') : T('Nothing to unload'), n ? 'ok' : '');
        if ((r.errors || []).length) toast(r.errors.join(' · '), 'err');
        await refresh();
        if (typeof refreshLocal === 'function') refreshLocal();
      }, '…');
      return;
    }
    const rel = e.target.closest('[data-lc-release]');
    if (rel) return busy(rel, async () => { await api('/api/lifecycle/release', {method: 'POST', body: {key: rel.dataset.lcRelease}}); refresh(); }, '…');
    if (e.target.closest('[data-lc-refresh]')) refresh();
  });

  // ---------------------------------------------------------------- Settings card
  function card() {
    if ($('#set-lifecycle') || !$('#tab-settings .set-main')) return;
    const main = $('#tab-settings .set-main'), more = $('#set-more');
    const el = document.createElement('section');
    el.className = 'set-card'; el.id = 'set-lifecycle'; el.dataset.set = 'lifecycle';
    const opt = p => `<option value="${p}">${T(C.policyLabel(p))}</option>`;
    el.innerHTML = `<header class="set-head"><svg class="ic"><use href="#i-cpu"/></svg><div><h3>${T('Model lifecycle & resources')}</h3>
        <p class="set-desc">${T('When models, sessions and containers are loaded and released — keep this PC fast and VRAM free.')}</p></div></header>
      <div class="set-body">
        <h4 class="set-sub">${T('Loaded right now')}</h4>
        <div data-lc-live><div class="status"><span class="spin"></span></div></div>
        <div id="lc-tracked"></div>
        <h4 class="set-sub">${T('Load / unload policy')}</h4>
        <label class="chk"><input type="checkbox" data-lc="enabled"> ${T('Manage the lifecycle automatically (off = v4.0 behaviour)')}</label>
        <div class="lc-grid">${CLASSES.map(([k, t, d]) => `<div class="lc-row"><div><b>${T(t)}</b><div class="status" style="margin:0">${T(d)}</div></div>
          <select data-lc="${k}">${['unload_after_task', 'keep_loaded', 'idle_unload'].map(opt).join('')}</select>
          <label class="lc-idle">${T('idle')} <input type="number" min="1" max="1440" data-lc="${IDLE[k]}"> min</label></div>`).join('')}</div>
        <div class="row" style="gap:12px;margin-top:10px;flex-wrap:wrap">
          <label style="margin:0;flex:0 0 auto">${T('Unload delay after a task')} <input type="number" min="0" max="600" data-lc="unload_grace_s" style="width:80px"> s</label></div>
        <label class="chk"><input type="checkbox" data-lc="respect_manual_loads"> ${T('Never auto-unload a model I loaded myself')}</label>
        <label class="chk"><input type="checkbox" data-lc="single_model_vram"> ${T('Only one PhD-Lab model in VRAM at a time')}</label>
        <label class="chk"><input type="checkbox" data-res="auto_unload_for_gpu"> ${T('Free VRAM automatically before a GPU training run (idle models only)')}</label>
        <p class="status">${T('Load → task → unload frees VRAM right after background work; Keep loaded answers fastest; Unload when idle is the balance. A model that is answering is never unloaded.')}</p>
        <div class="row" style="margin-top:12px"><span style="flex:1"></span><button class="btn primary" id="lc-save" style="flex:0">${T('Save')}</button></div>
        <details style="margin-top:12px"><summary class="status">${T('Recent load / unload actions')}</summary><div id="lc-hist"></div></details>
      </div>`;
    main.insertBefore(el, more);
    const btn = document.createElement('button');
    btn.dataset.setGo = 'lifecycle'; btn.innerHTML = `<svg class="ic"><use href="#i-cpu"/></svg><span>${T('Model lifecycle')}</span>`;
    const local = $('.set-menu [data-set-go="local"]');
    local.parentNode.insertBefore(btn, local.nextSibling);
    btn.onclick = () => window.SHELL && SHELL.showSet && SHELL.showSet('lifecycle');
    // compact live list inside the Local AI card too
    const lb = $('#set-local .set-body');
    if (lb && !lb.querySelector('[data-lc-live]')) {
      const box = document.createElement('div');
      box.innerHTML = `<h4 class="set-sub">${T('In VRAM now')}</h4><div data-lc-live></div>`;
      lb.prepend(box);
    }
    fill();
    $('#lc-save').onclick = e => busy(e.target, async () => {
      const lc = {}, res = {};
      $$('#set-lifecycle [data-lc]').forEach(i => lc[i.dataset.lc] = i.type === 'checkbox' ? i.checked : i.type === 'number' ? +i.value : i.value);
      $$('#set-lifecycle [data-res]').forEach(i => res[i.dataset.res] = i.checked);
      await api('/api/config', {method: 'POST', body: {lifecycle: lc, resources: res}});
      toast(T('Lifecycle settings saved'), 'ok'); fill(); refresh();
    });
  }

  async function fill() {
    try {
      const c = await api('/api/config');
      $$('#set-lifecycle [data-lc]').forEach(i => { const v = c.lifecycle[i.dataset.lc]; i.type === 'checkbox' ? i.checked = !!v : i.value = v; });
      $$('#set-lifecycle [data-res]').forEach(i => i.checked = !!c.resources[i.dataset.res]);
    } catch {}
  }

  function tick() {
    const on = !!$('#tab-settings.on');
    if (C.shouldPoll(document.visibilityState === 'visible', on)) refresh();
    else stop();
  }
  function start() { card(); refresh(); if (!L.timer) L.timer = setInterval(tick, 4000); }
  function stop() { clearInterval(L.timer); L.timer = null; }

  window.addEventListener('tab-shown', e => { if (e.detail === 'settings') start(); else stop(); });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && $('#tab-settings.on')) start(); });
  setTimeout(card, 350);
  window.LIFECYCLE = {refresh, start, stop};
})();
