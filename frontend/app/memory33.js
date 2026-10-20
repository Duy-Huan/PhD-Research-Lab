/* PhD Research Lab v3.4 — Context Memory (v3.3 architecture) in the Context tab:
   Research State · Retrieval & trace (why each record was chosen, CONTEXT TRACE) · Evidence & claims · Memory candidates
   (AI/provider proposals waiting for the researcher) · Storage tiers (the v3.0 Tier 1/2/3 view, kept as the raw layer). */
(() => {
  const T = s => I18N.tr(s);
  const M = {sub: 'state', policies: null, research: null};
  const SUBS = [['state', '🧭', 'Research state'], ['retrieve', '🔎', 'Retrieval & trace'], ['evidence', '🧪', 'Evidence & claims'],
    ['candidates', '📥', 'Candidates'], ['tiers', '🗄', 'Storage tiers']];
  const LEVELS = ['', 'PUBLIC', 'INTERNAL', 'SENSITIVE', 'RESTRICTED'];

  function mount() {
    const sec = $('#tab-context .v3sec');
    if (!sec || $('#mx')) return;
    const grid = sec.querySelector('.memgrid');
    const wrap = document.createElement('div');
    wrap.id = 'mx'; wrap.className = 'card mx';
    wrap.innerHTML = `<div class="row" style="flex-wrap:wrap;gap:10px;margin-bottom:4px"><h4 style="margin:0;flex:1">🧠 ${T('Context Memory')}
        <span class="status" style="margin:0 0 0 8px">${T('research state → state-aware retrieval → evidence → role-aware compiler')}</span></h4>
        <span class="status" id="mx-ver" style="margin:0"></span></div>
      <div class="ccnav" id="mx-nav">${SUBS.map(([k, i, l]) => `<button data-mx="${k}" class="${k === M.sub ? 'on' : ''}">${i} ${T(l)}${k === 'candidates' ? ' <span class="count" id="mx-ccount"></span>' : ''}</button>`).join('')}</div>
      <div id="mx-body"></div><div id="mx-tiers" hidden></div>`;
    sec.insertBefore(wrap, sec.querySelector('.cxgrid') || grid);  // the memory architecture first, the graph below
    $('#mx-tiers').appendChild(grid);
    $$('#mx-nav [data-mx]').forEach(b => b.onclick = () => show(b.dataset.mx));
    try { const s = localStorage.getItem('mx_sub'); if (s && SUBS.some(x => x[0] === s)) M.sub = s; } catch {}
    show(M.sub);
  }

  function show(sub) {
    M.sub = sub; try { localStorage.setItem('mx_sub', sub); } catch {}
    $$('#mx-nav [data-mx]').forEach(b => b.classList.toggle('on', b.dataset.mx === sub));
    $('#mx-tiers').hidden = sub !== 'tiers';
    $('#mx-body').hidden = sub === 'tiers';
    if (sub !== 'tiers') ({state: renderState, retrieve: renderRetrieve, evidence: renderEvidence, candidates: renderCandidates}[sub])($('#mx-body'));
    countCandidates();
  }

  async function countCandidates() {
    try { const r = await api('/api/memory/candidates?status=pending'); const c = $('#mx-ccount'); if (c) { c.textContent = r.candidates.length || ''; c.hidden = !r.candidates.length; } } catch {}
  }

  const li = (id, txt, extra = '') => `<li><code>${esc(id)}</code> ${esc(txt)}${extra}</li>`;

  // ------------------------------------------------------------------ research state
  async function renderState(b) {
    b.innerHTML = `<div class="status"><span class="spin"></span></div>`;
    let st, rs;
    try { [st, rs] = await Promise.all([api('/api/memory/state'), api('/api/research')]); } catch (e) { b.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
    M.research = rs;
    $('#mx-ver').textContent = 'context_version ' + st.context_version;
    const cur = st.current_experiment, bl = st.baseline;
    const best = Object.entries(st.best_results || {});
    b.innerHTML = `<p class="status" style="margin:0 0 10px">${T('What every agent and every connected AI (ChatGPT, Claude, Gemini) receives first. It is recomputed from your records — it survives restarts, context resets and provider changes.')}</p>
      <div class="mxgrid">
        <div class="mxcard"><h5>🎯 ${T('Objective')}</h5>${st.objective.length ? `<ul>${st.objective.map(g => `<li>${esc(g)}</li>`).join('')}</ul>` : `<p class="status">${T('No research goal yet — generate a plan in Lit2Plan.')}</p>`}</div>
        <div class="mxcard"><h5>🧪 ${T('Active hypothesis')}</h5>${st.active_hypotheses.length ? `<ul>${st.active_hypotheses.map(h => li(h.id, h.text, ` <span class="badge">${esc(T(h.status))}</span>`)).join('')}</ul>` : `<p class="status">${T('No open hypothesis.')}</p>`}
          <label>${T('Focus (overrides the automatic choice)')}</label>
          <div class="row"><select id="mx-fh"><option value="">${T('automatic')}</option>${rs.hypotheses.map(h => `<option value="${esc(h.id)}" ${st.focus.hypothesis_id === h.id ? 'selected' : ''}>${esc(h.id)} · ${esc(h.text.slice(0, 70))}</option>`).join('')}</select>
            <select id="mx-fe"><option value="">${T('automatic')}</option>${rs.experiments.map(e => `<option value="${esc(e.id)}" ${st.focus.experiment_id === e.id ? 'selected' : ''}>${esc(e.id)} · ${esc(e.title.slice(0, 60))}</option>`).join('')}</select></div></div>
        <div class="mxcard"><h5>🔬 ${T('Current experiment')}</h5>${cur ? `<p><code>${esc(cur.id)}</code> ${esc(cur.title)}</p><p class="status">${[cur.dataset_version && 'dataset ' + esc(cur.dataset_version), cur.git_sha && 'git ' + esc(cur.git_sha.slice(0, 10)), cur.clearml_task_id && 'ClearML ' + esc(cur.clearml_task_id.slice(0, 8))].filter(Boolean).join(' · ')}</p>${cur.conclusion ? `<p>${esc(cur.conclusion)}</p>` : ''}` : `<p class="status">${T('Nothing recorded yet')}</p>`}
          ${bl && (!cur || bl.id !== cur.id) ? `<h5>📏 ${T('Baseline')}</h5><p><code>${esc(bl.id)}</code> ${esc(bl.title)}</p>` : ''}</div>
        <div class="mxcard"><h5>📏 ${T('Constraints')}</h5>${st.constraints.length ? `<ul>${st.constraints.map(c => `<li>${esc(c)}</li>`).join('')}</ul>` : `<p class="status">${T('None')}</p>`}
          ${best.length ? `<h5>🏆 ${T('Best results')}</h5><ul>${best.map(([k, v]) => `<li><b>${esc(k)}</b> = ${esc(String(v.value))} <span class="status">(${esc(v.source)})</span></li>`).join('')}</ul>` : ''}</div>
        <div class="mxcard"><h5>🔒 ${T('Decisions')}</h5>${st.recent_decisions.length ? `<ul>${st.recent_decisions.map(d => li(d.id, d.text, ` <span class="badge">${esc(T(d.kind))}</span>`)).join('')}</ul>` : `<p class="status">${T('No decisions yet.')}</p>`}</div>
        <div class="mxcard"><h5>💥 ${T('Known failures')}</h5>${st.known_failures.length ? `<ul>${st.known_failures.map(f => li(f.id, f.text, f.lesson ? `<br><span class="status">↳ ${esc(f.lesson)}</span>` : '')).join('')}</ul>` : `<p class="status">${T('No recorded failure.')}</p>`}</div>
      </div>`;
    const focus = () => api('/api/memory/focus', {method: 'PUT', body: {hypothesis_id: $('#mx-fh').value, experiment_id: $('#mx-fe').value}})
      .then(() => { toast(T('Focus updated'), 'ok'); renderState(b); }).catch(e => toast(e.message, 'err'));
    $('#mx-fh').onchange = focus; $('#mx-fe').onchange = focus;
  }

  // ------------------------------------------------------------------ retrieval & trace
  async function renderRetrieve(b) {
    if (!M.policies) try { M.policies = await api('/api/memory/policies'); } catch { M.policies = {roles: {}}; }
    const roles = Object.entries(M.policies.roles);
    b.innerHTML = `<p class="status" style="margin:0 0 8px">${T('Ask what an agent would ask: see which records come back, why, and the exact context it receives within its token budget.')}</p>
      <div class="row" style="flex-wrap:wrap;gap:8px"><input type="text" id="mx-q" placeholder="${esc(T('e.g. Should we use Swin Transformer?'))}" style="flex:1 1 320px">
        <select id="mx-role" style="flex:0 0 200px">${roles.map(([k, v]) => `<option value="${esc(k)}" ${k === 'default' ? 'selected' : ''}>${esc(T(v.label))}</option>`).join('')}</select>
        <input type="number" id="mx-budget" value="3500" min="400" max="20000" step="100" style="flex:0 0 110px" title="${esc(T('Token budget'))}">
        <button class="btn primary" id="mx-go" style="flex:0">🔎 ${T('Retrieve')}</button><button class="btn" id="mx-comp" style="flex:0">⚡ ${T('Compile context')}</button></div>
      <div id="mx-out"></div>`;
    const q = () => $('#mx-q').value.trim();
    const enter = e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); $('#mx-go').click(); } };
    $('#mx-q').addEventListener('keydown', enter);
    $('#mx-go').onclick = e => busy(e.target, async () => {
      const r = await api('/api/memory/v3/retrieve', {method: 'POST', body: {query: q(), role: $('#mx-role').value, k: 20}});
      const d = r.diagnostics;
      $('#mx-out').innerHTML = `<p class="status">${d.nodes} ${T('records')} · ${T('sources')}: ${esc(Object.entries(d.sources || {}).map(([k, v]) => k + ' ' + v).join(', '))} · ${esc(d.vector_engine)} · ${d.cache_hit ? T('from cache') : (d.latency_ms || 0) + ' ms'}${d.intent ? ' · ' + T('asks for') + ': ' + esc(d.intent.join(', ')) : ''}</p>
        <table class="dtable mxhits"><tr><th>#</th><th>${T('Record')}</th><th>${T('Score')}</th><th>${T('Why')}</th><th>${T('Sharing')}</th></tr>
        ${r.hits.map((h, i) => `<tr><td>${i + 1}</td><td><code>${esc(h.id)}</code> <span class="badge">${esc(T(h.type))}</span></td><td>${h.score.toFixed(2)}</td>
          <td class="status">${h.reasons.map(x => esc(T(x))).join('<br>')}</td>
          <td><select data-sens="${esc(h.id)}" title="${esc(T('Who may receive this record'))}">${LEVELS.map(l => `<option value="${l}">${l ? l : T('default')}</option>`).join('')}</select></td></tr>`).join('')}</table>`;
      $$('#mx-out [data-sens]').forEach(s => s.onchange = () => api('/api/memory/sensitivity', {method: 'PUT', body: {id: s.dataset.sens, level: s.value}})
        .then(() => toast(`${s.dataset.sens} → ${s.value || T('default')}`, 'ok')).catch(e => toast(e.message, 'err')));
    });
    $('#mx-comp').onclick = e => busy(e.target, async () => {
      const c = await api('/api/memory/v3/compile', {method: 'POST', body: {query: q(), role: $('#mx-role').value, budget_tokens: +$('#mx-budget').value || 3500, trace: true}});
      $('#mx-out').innerHTML = `<div class="mxsplit"><div><h5>${T('Compiled context')} · ${c.tokens} token</h5><pre class="mxpre">${esc(c.text)}</pre></div>
        <div><h5>CONTEXT TRACE</h5><pre class="mxpre">${esc(c.trace_text)}</pre></div></div>`;
    });
  }

  // ------------------------------------------------------------------ evidence & claims
  async function renderEvidence(b) {
    let ev, rs;
    try { [ev, rs] = await Promise.all([api('/api/evidence'), api('/api/research')]); } catch (e) { b.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
    const byClaim = {}; ev.evidence.forEach(x => (byClaim[x.claim_id || ''] = byClaim[x.claim_id || ''] || []).push(x));
    const evRow = x => `<li><code>${esc(x.id)}</code> <span class="badge ${x.stance === 'supports' ? 'ok' : x.stance === 'refutes' ? 'warn' : ''}">${esc(T(x.stance))}</span>
      ${x.metric && x.metric.name ? `<b>${esc(x.metric.name)} = ${esc(String(x.metric.value))}</b>` : ''} ${esc(x.text || '')}
      <span class="status">${[x.experiment_id, x.git_sha && 'git ' + x.git_sha.slice(0, 10), x.dataset_version, x.origin !== 'human' && x.origin].filter(Boolean).map(esc).join(' · ')}</span>
      <span class="badge">${esc(T(x.status))}</span>${x.status !== 'validated' ? `<button class="btn small" data-evs="${esc(x.id)}" data-to="validated">✓ ${T('Validate')}</button>` : ''}${x.status !== 'rejected' ? `<button class="btn small danger" data-evs="${esc(x.id)}" data-to="rejected">✕</button>` : ''}</li>`;
    b.innerHTML = `<p class="status" style="margin:0 0 8px">${T('A claim is supported or refuted only by VALIDATED evidence. Evidence proposed by an AI stays a candidate until you validate it; provenance (run, git commit, dataset, ClearML) is copied from the experiment.')}</p>
      ${ev.claims.map(c => `<div class="mxclaim"><div><code>${esc(c.id)}</code> <b>${esc(c.text)}</b> <span class="badge ${c.status === 'supported' ? 'ok' : c.status === 'refuted' || c.status === 'contested' ? 'warn' : ''}">${esc(T(c.status))}</span>
        <span class="status">${[c.hypothesis_id, ...(c.source_refs || [])].filter(Boolean).map(esc).join(' · ')}</span></div>
        <ul>${(byClaim[c.id] || []).map(evRow).join('') || `<li class="status">${T('No evidence yet')}</li>`}</ul></div>`).join('') || `<p class="status">${T('No claims yet')}</p>`}
      ${(byClaim[''] || []).length ? `<h5>${T('Evidence without a claim')}</h5><ul>${byClaim[''].map(evRow).join('')}</ul>` : ''}
      <details class="mxform"><summary>＋ ${T('New claim')}</summary>
        <div class="row" style="flex-wrap:wrap;gap:8px"><input type="text" id="mx-ct" placeholder="${esc(T('Claim, e.g. Window attention improves PSNR over spectral attention on CAVE'))}" style="flex:1 1 320px">
          <select id="mx-ch" style="flex:0 0 200px"><option value="">${T('hypothesis (optional)')}</option>${rs.hypotheses.map(h => `<option value="${esc(h.id)}">${esc(h.id)} · ${esc(h.text.slice(0, 50))}</option>`).join('')}</select>
          <input type="text" id="mx-cs" placeholder="${esc(T('sources, e.g. lit:liang2021swinir, EXP-004'))}" style="flex:0 0 240px"><button class="btn primary" id="mx-cadd" style="flex:0">${T('Add')}</button></div></details>
      <details class="mxform"><summary>＋ ${T('New evidence')}</summary>
        <div class="row" style="flex-wrap:wrap;gap:8px">
          <select id="mx-ec" style="flex:0 0 200px"><option value="">${T('claim (optional)')}</option>${ev.claims.map(c => `<option value="${esc(c.id)}">${esc(c.id)} · ${esc(c.text.slice(0, 50))}</option>`).join('')}</select>
          <select id="mx-ee" style="flex:0 0 200px"><option value="">${T('experiment (optional)')}</option>${rs.experiments.map(e => `<option value="${esc(e.id)}">${esc(e.id)} · ${esc(e.title.slice(0, 50))}</option>`).join('')}</select>
          <select id="mx-es" style="flex:0 0 130px"><option value="supports">${T('supports')}</option><option value="refutes">${T('refutes')}</option><option value="neutral">${T('neutral')}</option></select>
          <input type="text" id="mx-em" placeholder="${esc(T('metric, e.g. PSNR=31.42'))}" style="flex:0 0 160px">
          <input type="text" id="mx-et" placeholder="${esc(T('observation'))}" style="flex:1 1 220px"><button class="btn primary" id="mx-eadd" style="flex:0">${T('Add')}</button></div></details>`;
    $$('#mx-body [data-evs]').forEach(x => x.onclick = () => api(`/api/evidence/${x.dataset.evs}/status`, {method: 'PUT', body: {status: x.dataset.to}})
      .then(() => renderEvidence(b)).catch(e => toast(e.message, 'err')));
    $('#mx-cadd').onclick = e => busy(e.target, async () => {
      await api('/api/evidence/claims', {method: 'POST', body: {text: $('#mx-ct').value, hypothesis_id: $('#mx-ch').value,
        source_refs: $('#mx-cs').value.split(/[,\s]+/).filter(Boolean)}});
      toast(T('Claim added'), 'ok'); renderEvidence(b);
    });
    $('#mx-eadd').onclick = e => busy(e.target, async () => {
      const m = $('#mx-em').value.match(/^\s*([^=:]+)\s*[=:]\s*(-?[\d.]+)/);
      const body = {claim_id: $('#mx-ec').value, experiment_id: $('#mx-ee').value, stance: $('#mx-es').value, text: $('#mx-et').value, status: 'validated'};
      if (m) body.metric = {name: m[1].trim(), value: +m[2]};
      if (!body.experiment_id) body.source_type = 'observation';
      await api('/api/evidence', {method: 'POST', body});
      toast(T('Evidence added'), 'ok'); renderEvidence(b);
    });
  }

  // ------------------------------------------------------------------ candidates
  async function renderCandidates(b) {
    let r;
    try { r = await api('/api/memory/candidates'); } catch (e) { b.innerHTML = `<div class="status">⚠ ${esc(e.message)}</div>`; return; }
    const open = r.candidates.filter(c => c.status === 'pending' || c.status === 'duplicate').reverse();
    const done = r.candidates.filter(c => !open.includes(c)).reverse().slice(0, 30);
    const row = c => `<div class="mxcand ${esc(c.status)}"><div class="row" style="gap:8px;flex-wrap:wrap"><code>${esc(c.id)}</code>
        <span class="badge">${esc(T(c.kind))}</span><span class="badge">${esc(T(c.classification))}</span>
        <span class="status" style="margin:0">${esc(c.origin.provider || T(c.origin.type))}${c.origin.session ? ' · ' + esc(c.origin.session.slice(0, 18)) : ''} · ${T('confidence')} ${c.confidence}</span>
        ${c.duplicate_of ? `<span class="badge warn">${T('duplicate of')} ${esc(c.duplicate_of)}</span>` : ''}<span style="flex:1"></span>
        ${c.status === 'pending' || c.status === 'duplicate' ? `<button class="btn small primary" data-ok="${esc(c.id)}">✓ ${T('Approve')}</button><button class="btn small danger" data-no="${esc(c.id)}">✕ ${T('Reject')}</button>`
          : `<span class="badge ${c.status === 'approved' ? 'ok' : ''}">${esc(T(c.status))}${c.committed ? ' → ' + esc(c.committed.id) : ''}</span>`}</div>
      <p>${esc(c.payload.text)}</p>${c.payload.metric ? `<p class="status">${esc(c.payload.metric.name)} = ${esc(String(c.payload.metric.value))}</p>` : ''}</div>`;
    b.innerHTML = `<p class="status" style="margin:0 0 8px">${T('Nothing an AI says becomes memory on its own. Proposals from ChatGPT, Claude, Gemini/Antigravity (MCP record tools or “Save to memory”) wait here; approving writes them with their origin.')}</p>
      ${open.map(row).join('') || `<p class="status">${T('No pending candidates.')}</p>`}
      ${done.length ? `<details><summary>${T('Reviewed')} (${done.length})</summary>${done.map(row).join('')}</details>` : ''}`;
    $$('#mx-body [data-ok]').forEach(x => x.onclick = () => busy(x, async () => { await api(`/api/memory/candidates/${x.dataset.ok}/approve`, {method: 'POST', body: {}}); toast(T('Approved and written to memory'), 'ok'); renderCandidates(b); countCandidates(); }));
    $$('#mx-body [data-no]').forEach(x => x.onclick = () => { const why = prompt(T('Reason (optional)'), '') ?? null; if (why === null) return;
      api(`/api/memory/candidates/${x.dataset.no}/reject`, {method: 'POST', body: {reason: why}}).then(() => { renderCandidates(b); countCandidates(); }).catch(e => toast(e.message, 'err')); });
  }

  window.addEventListener('tab-shown', e => { if (e.detail === 'context') setTimeout(() => { mount(); if ($('#mx') && M.sub !== 'tiers') show(M.sub); }, 50); });
  window.MEMORY33 = {show, countCandidates};
})();
