/* PhD Research Lab v3.4 — 🔌 AI Gateway: one research memory for ChatGPT (Codex CLI), Claude (Claude Code), Google
   Antigravity / Gemini CLI. Providers (health, sign-in, MCP setup) · Ask / Compare with review-before-sending · streamed
   answers · "Save to memory" (a candidate you approve) · MCP connection guide. Plus the "MCP & privacy" Settings card. */
(() => {
  const T = s => I18N.tr(s);
  const G = {prov: null, policies: null, req: [], es: {}};
  const root = () => $('#tab-gateway');
  const ORDER = ['codex', 'claude_code', 'antigravity', 'gemini_cli'];
  const NAME = {codex: 'ChatGPT', claude_code: 'Claude', antigravity: 'Antigravity', gemini_cli: 'Gemini CLI'};
  const STATE_CLS = {CONNECTED: 'ok', UNKNOWN: '', DISCONNECTED: '', AUTH_EXPIRED: 'warn', RATE_LIMITED: 'warn', UNAVAILABLE: 'warn', ERROR: 'warn'};

  function build() {
    root().innerHTML = `<div class="v3sec">
      <h2>🔌 ${T('AI Gateway')}</h2>
      <p class="lead">${T('One research memory, several AI engines. ChatGPT, Claude and Gemini/Antigravity receive the same compiled research context (state, evidence, failures) through their official apps and sign-ins — never API keys you did not choose, never your passwords. They can also read the memory themselves through MCP.')}</p>
      <div class="gwgrid" id="gw-prov"><div class="status"><span class="spin"></span></div></div>
      <div class="card" style="margin-top:16px"><h4>💬 ${T('Ask with the project context')}</h4>
        <textarea id="gw-q" rows="3" placeholder="${esc(T('e.g. Should I test SwinIR next? What would you change in the next experiment?'))}"></textarea>
        <div class="row" style="flex-wrap:wrap;gap:10px;margin-top:8px">
          <div id="gw-pick" class="row" style="gap:10px;flex-wrap:wrap;flex:1 1 auto"></div>
          <select id="gw-role" style="flex:0 0 200px" title="${esc(T('Role of the context policy'))}"></select>
          <label class="chk" style="margin:0;flex:0 0 auto"><input type="checkbox" id="gw-review"> ${T('Review before sending')}</label>
          <button class="btn primary" id="gw-ask" style="flex:0">↑ ${T('Ask')}</button></div>
        <p class="status">${T('Pick two or more providers to compare their answers on the same context. Answers are kept here and never forwarded to another provider.')}</p>
        <div id="gw-out"></div></div>
      <div class="card" style="margin-top:16px"><h4>🔗 ${T('Connect an AI app to this memory (MCP)')}</h4><div id="gw-mcp"></div></div>
      <details class="card" style="margin-top:16px"><summary><b>🧾 ${T('Audit log')}</b> <span class="status">${T('metadata only — no prompts or answers')}</span></summary><div id="gw-audit"></div></details>
    </div>`;
    $('#gw-ask').onclick = ask;
    $('#gw-q').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ask(); } });
    $('#tab-gateway details').addEventListener('toggle', e => e.target.open && audit());
  }

  async function load() {
    try {
      const [p, pol, cfg] = await Promise.all([api('/api/gateway/providers'), G.policies ? {roles: G.policies} : api('/api/memory/policies'), api('/api/config')]);
      G.prov = p; G.policies = pol.roles; G.cfg = cfg;
    } catch (e) { $('#gw-prov').innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
    $('#gw-review').checked = !!G.cfg.gateway.review_before_external;
    $('#gw-role').innerHTML = Object.entries(G.policies).map(([k, v]) => `<option value="${esc(k)}" ${k === 'director' ? 'selected' : ''}>${esc(T(v.label))}</option>`).join('');
    renderProviders(); renderMcp();
  }

  function renderProviders() {
    $('#gw-prov').innerHTML = ORDER.filter(k => G.prov[k]).map(k => {
      const p = G.prov[k], caps = p.capabilities || {};
      const canSend = caps.send === true;
      return `<div class="card gwcard"><div class="row" style="gap:8px"><b style="flex:1">${esc(NAME[k])}</b><span class="badge ${STATE_CLS[p.state] || ''}">${esc(T(p.state))}</span></div>
        <div class="status" style="margin:4px 0">${esc(T(p.path || ''))}</div>
        <div class="status" style="margin:0">${p.version ? esc(p.version) + ' · ' : ''}${esc(T(p.detail || ''))}</div>
        <div class="status" style="margin:4px 0 0">💳 ${esc(T(p.billing || ''))}</div>
        ${(p.setup || []).length && ['UNAVAILABLE', 'ERROR', 'AUTH_EXPIRED'].includes(p.state) ? `<ol class="gwsetup">${p.setup.map(s => `<li>${esc(T(s))}</li>`).join('')}</ol>` : ''}
        <div class="row" style="gap:6px;margin-top:10px;flex-wrap:wrap">
          ${p.state !== 'UNAVAILABLE' || k === 'antigravity' ? `<button class="btn small" data-connect="${k}">🔑 ${p.state === 'DISCONNECTED' ? T('Enable') : T('Sign in')}</button>` : ''}
          ${p.state !== 'DISCONNECTED' ? `<button class="btn small" data-disc="${k}">${T('Disable')}</button>` : ''}
          <button class="btn small" data-mcp="${k}">🔗 MCP</button>
          ${canSend ? '' : `<span class="status" style="margin:0">${T('MCP only')}</span>`}</div></div>`;
    }).join('') + (G.prov.chatgpt_web ? `<div class="card gwcard muted"><b>ChatGPT web / desktop</b><div class="status">${esc(T(G.prov.chatgpt_web.detail))}</div></div>` : '');
    $('#gw-pick').innerHTML = ORDER.filter(k => G.prov[k] && (G.prov[k].capabilities || {}).send === true).map(k =>
      `<label class="chk" style="margin:0;flex:0 0 auto"><input type="checkbox" data-pick="${k}" ${['CONNECTED', 'UNKNOWN'].includes(G.prov[k].state) && k === 'codex' ? 'checked' : ''} ${['DISCONNECTED', 'UNAVAILABLE'].includes(G.prov[k].state) ? 'disabled' : ''}> ${esc(NAME[k])}</label>`).join('')
      || `<span class="status">${T('No provider can be called from here yet — install and sign in to one of them above, or use it through MCP.')}</span>`;
    $$('#gw-prov [data-connect]').forEach(b => b.onclick = () => busy(b, async () => {
      const r = await api(`/api/gateway/providers/${b.dataset.connect}/connect`, {method: 'POST', body: {launch: true}});
      toast(r.launched ? T('A terminal opened — finish the sign-in in your browser, then press ↻') : `${T('Run in a terminal')}: ${r.command}`, 'ok'); load();
    }));
    $$('#gw-prov [data-disc]').forEach(b => b.onclick = () => busy(b, async () => { await api(`/api/gateway/providers/${b.dataset.disc}/disconnect`, {method: 'POST', body: {}}); load(); }));
    $$('#gw-prov [data-mcp]').forEach(b => b.onclick = () => { $('#gw-mcpsel').value = b.dataset.mcp; renderMcpSnippet(); $('#gw-mcp').scrollIntoView({behavior: 'smooth', block: 'center'}); });
  }

  // ---------------------------------------------------------------- ask / compare
  async function ask() {
    const q = $('#gw-q').value.trim();
    const picks = $$('#gw-pick [data-pick]:checked').map(x => x.dataset.pick);
    if (!q) return toast(T('Ask a question'), 'err');
    if (!picks.length) return toast(T('Pick at least one provider'), 'err');
    const review = $('#gw-review').checked, role = $('#gw-role').value;
    await busy($('#gw-ask'), async () => {
      let reqs;
      if (picks.length > 1) reqs = (await api('/api/gateway/compare', {method: 'POST', body: {query: q, providers: picks, role, review}})).requests;
      else reqs = [await api('/api/gateway/requests', {method: 'POST', body: {query: q, provider: picks[0], role, review, send: !review}})];
      $('#gw-out').innerHTML = `<div class="gwanswers">${reqs.map(r => `<div class="card gwans" id="ans-${esc(r.id || r.provider)}"></div>`).join('')}</div>`;
      for (const r of reqs) {
        if (!r.id) { $(`#ans-${r.provider}`).innerHTML = `<b>${esc(NAME[r.provider])}</b><div class="status">⚠ ${esc((r.errors || []).join(' · '))}</div>`; continue; }
        const full = await api('/api/gateway/requests/' + r.id);
        full.status === 'review' ? showReview(full) : stream(full);
      }
    }, T('Preparing the context…'));
  }

  function header(r) {
    return `<div class="row" style="gap:8px;flex-wrap:wrap"><b style="flex:1">${esc(NAME[r.provider] || r.provider)}</b>
      <span class="status" style="margin:0">${r.context_tokens} token · ${T('role')} ${esc(T((G.policies[r.role] || {}).label || r.role))}${(r.blocked || []).length ? ` · 🔒 ${r.blocked.length} ${T('withheld')}` : ''}</span>
      <span class="badge" id="st-${esc(r.id)}">${esc(T(r.status))}</span></div>`;
  }

  function showReview(r) {
    const box = $(`#ans-${r.id}`);
    box.innerHTML = `${header(r)}
      <p class="status">${T('Nothing has left this computer yet. Check what will be sent:')} ${Object.entries(r.includes || {}).map(([k, v]) => `${esc(T(k))} ${v}`).join(' · ')}
        ${(r.sanitize || []).length ? ` · ✂ ${esc(r.sanitize.map(T).join(', '))}` : ''}${(r.blocked || []).length ? `<br>🔒 ${T('Withheld by the privacy policy')}: ${r.blocked.map(esc).join(', ')}` : ''}</p>
      <textarea class="gwprompt" rows="12">${esc(r.prompt)}</textarea>
      <div class="row" style="gap:8px;margin-top:8px"><span style="flex:1"></span><button class="btn" data-cancel>${T('Cancel')}</button><button class="btn primary" data-send>↑ ${T('Send')}</button></div>`;
    box.querySelector('[data-cancel]').onclick = () => api(`/api/gateway/requests/${r.id}/cancel`, {method: 'POST'}).then(() => box.remove());
    box.querySelector('[data-send]').onclick = e => busy(e.target, async () => {
      const edited = box.querySelector('.gwprompt').value;
      const out = await api(`/api/gateway/requests/${r.id}/send`, {method: 'POST', body: edited !== r.prompt ? {prompt: edited} : {}});
      stream({...r, ...out});
    });
  }

  function stream(r) {
    const box = $(`#ans-${r.id}`);
    box.innerHTML = `${header(r)}<div class="gwtools status" id="tl-${esc(r.id)}"></div><div class="md gwmd" id="md-${esc(r.id)}"><span class="cursor"></span></div><div id="ft-${esc(r.id)}"></div>`;
    if (r.status === 'failed') return done(r.id, r);
    let text = '';
    const es = new EventSource(`/api/gateway/requests/${r.id}/stream`); G.es[r.id] = es;
    const paint = () => { $(`#md-${r.id}`).innerHTML = md(text) + '<span class="cursor"></span>'; };
    es.onmessage = ev => {
      const e = JSON.parse(ev.data);
      if (e.type === 'text_delta') { text = e.final ? e.text : text + e.text; paint(); }
      else if (e.type === 'tool_call') $(`#tl-${r.id}`).insertAdjacentHTML('beforeend', `<span class="badge">🔧 ${esc(e.name || '')}</span> `);
      else if (e.type === 'status' && e.state === 'result' && e.final_text) { text = e.final_text; paint(); }
      else if (e.type === 'error') $(`#ft-${r.id}`).insertAdjacentHTML('beforeend', `<div class="status">⚠ ${esc(e.message)}</div>`);
    };
    es.addEventListener('end', () => { es.close(); delete G.es[r.id]; done(r.id); });
    es.onerror = () => { es.close(); done(r.id); };
  }

  async function done(id, known) {
    const r = known || await api('/api/gateway/requests/' + id).catch(() => null);
    if (!r) return;
    const st = $(`#st-${id}`); if (st) st.textContent = T(r.status);
    const mdBox = $(`#md-${id}`); if (mdBox) mdBox.innerHTML = r.answer ? md(r.answer) : (r.errors || []).map(e => `<div class="status">⚠ ${esc(e)}</div>`).join('') || '';
    const ft = $(`#ft-${id}`);
    if (!ft) return;
    if (r.status === 'failed' && (r.alternatives || []).length) ft.insertAdjacentHTML('beforeend', `<p class="status">${T('Not sent. Available instead')}: ${r.alternatives.map(a => esc(NAME[a] || a)).join(', ')}</p>`);
    if (r.status !== 'completed') return;
    ft.innerHTML = `<div class="row gwsave" style="gap:8px;margin-top:10px;flex-wrap:wrap"><span class="status" style="margin:0">${T('Save to memory as')}</span>
      <select style="flex:0 0 160px">${['decision', 'observation', 'claim', 'failure', 'note'].map(k => `<option value="${k}">${esc(T(k))}</option>`).join('')}</select>
      <button class="btn small">📥 ${T('Propose')}</button><span class="status" style="margin:0">${T('select text in the answer to save only that part')}</span></div>`;
    const sel = ft.querySelector('select');
    ft.querySelector('button').onclick = e => busy(e.target, async () => {
      const s = String(window.getSelection() || '').trim();
      const c = await api(`/api/gateway/requests/${id}/propose`, {method: 'POST', body: {kind: sel.value, text: (s || r.answer).slice(0, 4000)}});
      toast(`${c.id}: ${T('waiting for your approval in Context → Candidates')}`, 'ok');
      window.MEMORY33 && MEMORY33.countCandidates();
    });
  }

  // ---------------------------------------------------------------- MCP guide
  function renderMcp() {
    const base = location.origin;
    $('#gw-mcp').innerHTML = `<p class="status" style="margin-top:0">${T('Endpoint')}: <code>${esc(base)}/mcp</code> · ${T('local only')} · ${G.cfg.mcp.has_token ? '🔑 ' + T('token required') : T('no token')} ·
        ${T('research tools')} ${G.cfg.mcp.expose_research ? '✓' : '✕'} · ${T('sandbox tools')} ${G.cfg.mcp.expose_sandbox ? '✓' : '✕'}
        <a href="#settings/mcp">${T('change')}</a></p>
      <div class="row" style="gap:8px"><select id="gw-mcpsel" style="flex:0 0 220px">${ORDER.map(k => `<option value="${k}">${esc(NAME[k] + (k === 'codex' ? ' (Codex CLI)' : k === 'claude_code' ? ' (Claude Code)' : ''))}</option>`).join('')}</select>
        <span id="gw-mcpact"></span></div>
      <div id="gw-mcpsnip"></div>`;
    $('#gw-mcpsel').onchange = renderMcpSnippet;
    renderMcpSnippet();
  }

  async function renderMcpSnippet() {
    const k = $('#gw-mcpsel').value, out = $('#gw-mcpsnip');
    let r; try { r = await api(`/api/gateway/providers/${k}/mcp`); } catch (e) { out.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
    const text = r.command || (typeof r.snippet === 'string' ? r.snippet : JSON.stringify(r.snippet, null, 2));
    out.innerHTML = `<p class="status">${r.command ? T('Run once in a terminal:') : `${T('Add to')} <code>${esc(r.file || '')}</code>${r.workspace_file ? ` (${T('or per project')}: <code>${esc(r.workspace_file)}</code>)` : ''}:`}</p>
      <pre class="mxpre">${esc(text)}</pre>`;
    $('#gw-mcpact').innerHTML = `<button class="btn small" id="gw-copy">⧉ ${T('Copy')}</button>` + (k === 'antigravity' ? ` <button class="btn small primary" id="gw-reg">${T('Register automatically')}</button>` : '');
    $('#gw-copy').onclick = () => navigator.clipboard.writeText(text).then(() => toast(T('Copied'), 'ok'));
    const reg = $('#gw-reg');
    if (reg) reg.onclick = () => busy(reg, async () => { const x = await api('/api/gateway/providers/antigravity/register-mcp', {method: 'POST'}); toast(`${T('Registered in')} ${x.file}`, 'ok'); load(); });
  }

  async function audit() {
    try {
      const r = await api('/api/gateway/audit?limit=50');
      $('#gw-audit').innerHTML = `<table class="dtable"><tr><th>${T('Time')}</th><th>${T('Event')}</th><th>${T('Provider')}</th><th>${T('Tokens')}</th><th>${T('Status')}</th></tr>${r.events.reverse().map(e =>
        `<tr><td class="status">${new Date(e.ts * 1000).toLocaleString()}</td><td>${esc(T(e.event))}</td><td>${esc(NAME[e.provider] || e.provider || '')}</td><td>${e.context_tokens || ''}</td><td>${esc(T(e.status || ''))}${e.blocked_count ? ' · 🔒 ' + e.blocked_count : ''}</td></tr>`).join('')}</table>`;
    } catch (e) { $('#gw-audit').innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; }
  }

  // ---------------------------------------------------------------- Settings → MCP & privacy
  function settingsCard() {
    if ($('#set-mcp')) return;
    const main = $('#tab-settings .set-main'), more = $('#set-more');
    const card = document.createElement('section');
    card.className = 'set-card'; card.id = 'set-mcp'; card.dataset.set = 'mcp';
    card.innerHTML = `<header class="set-head"><svg class="ic"><use href="#i-share"/></svg><div><h3>${T('MCP & privacy')}</h3>
        <p class="set-desc">${T('What external AI apps may read or propose, and what never leaves this computer.')}</p></div></header>
      <div class="set-body">
        <h4 class="set-sub">${T('Privacy of the research context')}</h4>
        <label class="chk"><input type="checkbox" data-g="allow_internal"> ${T('Share INTERNAL records (default for research records) with external AI')}</label>
        <label class="chk"><input type="checkbox" data-g="allow_sensitive"> ${T('Also share records marked SENSITIVE (RESTRICTED never leaves)')}</label>
        <label class="chk"><input type="checkbox" data-g="block_source_code"> ${T('Never send source code (code blocks are removed)')}</label>
        <label class="chk"><input type="checkbox" data-g="review_before_external"> ${T('Always review the context before it is sent to an external AI')}</label>
        <label>${T('Context budget for external AI (tokens)')}</label><input type="number" data-g="context_budget_tokens" min="400" max="20000" step="100">
        <h4 class="set-sub">${T('Billing guard')}</h4>
        <p class="status">${T('Off = the official apps run with every vendor API key removed, so only your subscription sign-in is used and no API bill is created.')}</p>
        ${['codex', 'claude_code', 'antigravity', 'gemini_cli'].map(k => `<label class="chk"><input type="checkbox" data-g="${k}_api_fallback"> ${esc(NAME[k])}: ${T('allow API-key billing')}</label>`).join('')}
        <h4 class="set-sub">MCP</h4>
        <label class="chk"><input type="checkbox" data-m="enabled"> ${T('MCP endpoint enabled')} (<code>${esc(location.origin)}/mcp</code>)</label>
        <label class="chk"><input type="checkbox" data-m="expose_research"> ${T('Research tools (state, memory search, evidence, decisions, failures)')}</label>
        <label class="chk"><input type="checkbox" data-m="allow_writes"> ${T('Record tools (create candidates you approve)')}</label>
        <label class="chk"><input type="checkbox" data-m="expose_sandbox"> ${T('Sandbox tools (run code, read and write workspace files)')}</label>
        <label>${T('Access token (empty = local apps need no token)')}</label>
        <div class="row"><input type="password" data-m="token" autocomplete="off"><button class="btn small" id="mcp-gen" style="flex:0">${T('Generate')}</button></div>
        <label>${T('Rate limit (requests per minute, 0 = off)')}</label><input type="number" data-m="rate_limit_per_min" min="0" max="10000">
        <div class="row" style="margin-top:14px"><span style="flex:1"></span><button class="btn primary" id="mcp-save" style="flex:0">${T('Save')}</button></div>
      </div>`;
    main.insertBefore(card, more);
    const btn = document.createElement('button');
    btn.dataset.setGo = 'mcp'; btn.innerHTML = `<svg class="ic"><use href="#i-share"/></svg><span>${T('MCP & privacy')}</span>`;
    const menuMore = $('.set-menu [data-set-go="more"]'); menuMore.parentNode.insertBefore(btn, menuMore);
    btn.onclick = () => window.SHELL && SHELL.showSet('mcp');
    fillSettings();
    $('#mcp-gen').onclick = () => { const a = new Uint8Array(24); crypto.getRandomValues(a); $('[data-m=token]').value = [...a].map(x => x.toString(16).padStart(2, '0')).join(''); $('[data-m=token]').type = 'text'; };
    $('#mcp-save').onclick = e => busy(e.target, async () => {
      const g = {}, m = {};
      $$('#set-mcp [data-g]').forEach(i => g[i.dataset.g] = i.type === 'checkbox' ? i.checked : +i.value);
      $$('#set-mcp [data-m]').forEach(i => m[i.dataset.m] = i.type === 'checkbox' ? i.checked : i.type === 'number' ? +i.value : i.value);
      await api('/api/config', {method: 'POST', body: {gateway: g, mcp: m}});
      toast(T('MCP & privacy settings saved'), 'ok'); fillSettings();
    });
  }

  async function fillSettings() {
    try {
      const c = await api('/api/config');
      $$('#set-mcp [data-g]').forEach(i => i.type === 'checkbox' ? i.checked = !!c.gateway[i.dataset.g] : i.value = c.gateway[i.dataset.g]);
      $$('#set-mcp [data-m]').forEach(i => i.type === 'checkbox' ? i.checked = !!c.mcp[i.dataset.m] : i.value = c.mcp[i.dataset.m] ?? '');
    } catch {}
  }

  function init() {
    if (!root().dataset.built) { build(); root().dataset.built = '1'; }
    load();
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'gateway') init(); if (e.detail === 'settings') settingsCard(); });
  document.addEventListener('DOMContentLoaded', () => setTimeout(settingsCard, 0));
  setTimeout(settingsCard, 300);
  window.GATEWAY = {init};
})();
