/* PhD Research Lab v3.0 — 🧠 Context Manager: knowledge graph (vis-network) of the global research state,
   node inspector (pin / purge / edit), Context Decision Agent chat, and the 3-tier hierarchical memory. */
(() => {
  const T = s => I18N.tr(s);
  const C = {inited: false, net: null, g: null, sel: null, filter: new Set(), showPurged: true, q: '', mem: null, chat: []};
  const root = () => $('#tab-context');
  const COLORS = {project: '#d9a441', hub: '#6b7686', objective: '#5cb87a', hypothesis: '#9b7fe0', decision: '#e06c6c', constraint: '#e0a85a',
    literature: '#5fa8d3', assumption: '#c2703d', code: '#56b6c2', metric: '#98c379', run: '#7d8590', episode: '#a3a8b4', note: '#d19a66', idea: '#c678dd', result: '#e5c07b'};
  const TYPE_LABEL = {objective: 'Objective', hypothesis: 'Hypothesis', decision: 'Decision', constraint: 'Constraint', literature: 'Literature',
    assumption: 'Code assumption', code: 'Code', metric: 'Metric', episode: 'Episode', note: 'Pinned note', idea: 'Idea', result: 'Result'};

  function build() {
    root().innerHTML = `<div class="v3sec">
      <h2>🧠 ${T('Context Manager & Decision Hub')}</h2>
      <p class="lead">${T('Everything the AI agents know about your project, as a graph. 📌 Pin = every agent must follow it. 🗑 Purge = hidden from all agents (data is kept). Talk to the Context Decision Agent on the right to reshape the context in plain language.')}</p>
      <div class="cxgrid">
        <div>
          <div class="cxtools">
            <input type="text" id="cx-q" placeholder="${esc(T('Search nodes…'))}">
            <div class="chips" id="cx-types" style="padding:0"></div>
            <label class="chk" style="margin:0"><input type="checkbox" id="cx-purged" checked> ${T('show purged')}</label>
            <span style="flex:1"></span>
            <button class="btn small" id="cx-add">＋ ${T('Add node')}</button><button class="btn small" id="cx-fit">⤢ ${T('Fit')}</button><button class="btn small" id="cx-ref">↻</button>
          </div>
          <div class="cxgraph"><div class="net" id="cx-net"></div><div class="cxlegend" id="cx-legend"></div></div>
          <div class="card inspector" id="cx-insp"><div class="status">${T('Click a node to inspect, edit, pin or purge it.')}</div></div>
        </div>
        <div class="card cxchat">
          <div class="row" style="margin-bottom:6px"><b style="flex:1">💬 ${T('Context Decision Agent')}</b><span class="rtbadge" data-agent="context_agent"></span><button class="iconbtn" id="cx-cclear" title="Clear">🧹</button></div>
          <div class="cmsgs" id="cx-msgs"></div>
          <div class="chips" id="cx-chips"></div>
          <div class="composer2" style="margin-top:6px"><textarea id="cx-in" rows="2" placeholder="${esc(T('e.g. Prune the old CNN assumptions and focus strictly on tensor-decomposition FLOPs reduction'))}"></textarea>
            <div class="ctools"><span style="flex:1"></span><button class="sendbtn" id="cx-send">↑</button></div></div>
        </div>
      </div>
      <div class="memgrid">
        <div class="card"><h4>⚡ ${T('Tier 1 · Working memory')}</h4><div id="mem-t1"></div></div>
        <div class="card"><h4>🗂 ${T('Tier 2 · Episodic summaries')}</h4><div id="mem-t2"></div></div>
        <div class="card"><h4>🏛 ${T('Tier 3 · Long-term knowledge')}</h4><div id="mem-t3"></div></div>
      </div></div>`;
    $('#cx-q').oninput = e => { C.q = e.target.value.trim().toLowerCase(); draw(); };
    $('#cx-purged').onchange = e => { C.showPurged = e.target.checked; draw(); };
    $('#cx-fit').onclick = () => C.net && C.net.fit({animation: true});
    $('#cx-ref').onclick = load;
    $('#cx-add').onclick = addNode;
    $('#cx-send').onclick = send;
    $('#cx-in').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    $('#cx-cclear').onclick = async () => { if (!confirm('Clear the Context Decision Agent conversation?')) return; await api('/api/context/chat', {method: 'DELETE'}); C.chat = []; renderChat(); };
    const chips = ['Summarize what every agent currently must follow', 'Which context items look outdated or contradictory?', 'Pin our chosen direction and target venue as constraints', 'Purge literature unrelated to the locked direction'];
    $('#cx-chips').innerHTML = chips.map((c, i) => `<button class="chip" data-c="${i}">${esc(T(c))}</button>`).join('');
    $$('#cx-chips [data-c]').forEach(b => b.onclick = () => { $('#cx-in').value = T(chips[b.dataset.c]); $('#cx-in').focus(); });
    window.refreshRuntimeBadges && refreshRuntimeBadges();
  }

  // ------------------------------------------------------------------ graph
  async function load() {
    try { C.g = await api('/api/context/graph'); } catch (e) { toast(e.message, 'err'); return; }
    const types = [...new Set(C.g.nodes.filter(n => !['hub', 'project'].includes(n.type)).map(n => n.type))];
    $('#cx-types').innerHTML = types.map(t => `<button class="chip ${C.filter.has(t) ? '' : 'on'}" data-t="${t}" style="border-color:${COLORS[t] || 'var(--line)'}">${esc(T(TYPE_LABEL[t] || t))} · ${C.g.nodes.filter(n => n.type === t).length}</button>`).join('');
    $$('#cx-types [data-t]').forEach(b => b.onclick = () => { C.filter.has(b.dataset.t) ? C.filter.delete(b.dataset.t) : C.filter.add(b.dataset.t); b.classList.toggle('on'); draw(); });
    $('#cx-legend').innerHTML = `<span>📌 ${C.g.stats.pinned} ${T('pinned')}</span><span>🗑 ${C.g.stats.purged} ${T('purged')}</span><span>${C.g.stats.nodes} ${T('nodes')}</span>`
      + types.map(t => `<span><i style="background:${COLORS[t]}"></i>${esc(T(TYPE_LABEL[t] || t))}</span>`).join('');
    draw();
    if (C.sel) inspect(C.g.nodes.find(n => n.id === C.sel.id));
  }
  function visible(n) {
    if (n.type === 'hub') return !C.filter.has(n.hub_for);
    if (n.type === 'project') return true;
    if (C.filter.has(n.type) || (!C.showPurged && n.purged)) return false;
    return !C.q || (n.label + ' ' + (n.text || '') + ' ' + n.id).toLowerCase().includes(C.q);
  }
  function draw() {
    if (!C.g || !window.vis) return;
    const dark = document.documentElement.dataset.theme !== 'light';
    const nodes = C.g.nodes.filter(visible).map(n => {
      const col = COLORS[n.type] || '#888';
      const size = n.type === 'project' ? 26 : n.type === 'hub' ? 14 : n.pinned ? 13 : 9;
      return {id: n.id, label: (n.pinned ? '📌 ' : '') + (n.purged ? '🗑 ' : '') + (n.type === 'hub' || n.type === 'project' ? T(n.label) : n.label.length > 42 ? n.label.slice(0, 40) + '…' : n.label),
        title: undefined, shape: n.type === 'hub' ? 'box' : n.type === 'project' ? 'star' : 'dot', size,
        color: {background: n.purged ? (dark ? '#3a3f47' : '#d8d8d8') : col, border: n.pinned ? '#ffd166' : (dark ? '#0f1216' : '#ffffff'),
          highlight: {background: col, border: '#ffffff'}},
        borderWidth: n.pinned ? 3 : 1, font: {color: n.purged ? '#888' : (dark ? '#e6e9ee' : '#1f2328'), size: n.type === 'hub' ? 13 : 11, face: 'IBM Plex Sans, Segoe UI, sans-serif',
          ...(n.type === 'hub' ? {color: '#fff'} : {})}, opacity: n.purged ? 0.55 : 1};
    });
    const ids = new Set(nodes.map(n => n.id));
    const edges = C.g.edges.filter(e => ids.has(e.from) && ids.has(e.to)).map(e => ({from: e.from, to: e.to, label: e.label || undefined,
      color: {color: e.custom ? '#d9a441' : (dark ? '#3b4452' : '#c9cfd8')}, width: e.custom ? 2 : 1, dashes: !!e.custom,
      font: {size: 9, color: dark ? '#aab' : '#555', strokeWidth: 0}}));
    const data = {nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges)};
    if (!C.net) {
      C.net = new vis.Network($('#cx-net'), data, {physics: {solver: 'forceAtlas2Based', forceAtlas2Based: {gravitationalConstant: -38, springLength: 90}, stabilization: {iterations: 180}},
        interaction: {hover: true, navigationButtons: false, keyboard: false}, edges: {smooth: {type: 'continuous'}}});
      C.net.on('click', p => { if (p.nodes.length) inspect(C.g.nodes.find(n => n.id === p.nodes[0])); });
    } else C.net.setData(data);
  }
  function inspect(n) {
    C.sel = n; const box = $('#cx-insp');
    if (!n || n.type === 'hub' || n.type === 'project') { box.innerHTML = `<div class="status">${T('Click a node to inspect, edit, pin or purge it.')}</div>`; return; }
    box.innerHTML = `<div class="row" style="gap:8px;align-items:center"><span class="badge" style="border-color:${COLORS[n.type]};color:${COLORS[n.type]}">${esc(T(TYPE_LABEL[n.type] || n.type))}</span>
        <span class="status" style="margin:0;font-family:var(--mono)">${esc(n.id)}</span><span class="status" style="margin:0;flex:1">${esc(n.source || '')}</span>
        ${n.pinned ? '<span class="badge warn">📌 ' + T('pinned') + '</span>' : ''}${n.purged ? '<span class="badge">🗑 ' + T('purged') + '</span>' : ''}</div>
      <label>${T('Label')}</label><input type="text" id="cx-lab" value="${esc(n.label.replace(/^🔒 /, ''))}">
      <label>${T('Content')}</label><textarea id="cx-txt" rows="6">${esc(n.text || '')}</textarea>
      <div class="row" style="margin-top:8px;gap:6px;flex-wrap:wrap">
        <button class="btn small ${n.pinned ? '' : 'primary'}" data-o="${n.pinned ? 'unpin' : 'pin'}">${n.pinned ? T('Unpin') : '📌 ' + T('Pin (must-follow)')}</button>
        <button class="btn small" data-o="${n.purged ? 'restore' : 'purge'}">${n.purged ? '↺ ' + T('Restore') : '🗑 ' + T('Purge from AI context')}</button>
        <button class="btn small" data-o="edit">💾 ${T('Save edits')}</button>
        ${n.deletable ? `<button class="btn small danger" data-o="delete">✕ ${T('Delete')}</button>` : ''}
        ${n.type === 'literature' ? `<button class="btn small" data-read="1">📕 ${T('Read PDF')}</button>` : ''}
        ${n.type === 'code' ? `<button class="btn small" data-code="1">↗ ${T('Open in IDE')}</button>` : ''}
        ${n.type === 'result' ? `<button class="btn small" data-res="1">👁 ${T('Open result')}</button>` : ''}</div>`;
    box.querySelectorAll('[data-o]').forEach(b => b.onclick = () => {
      const op = b.dataset.o;
      if (op === 'delete' && !confirm('Delete this node permanently?')) return;
      apply([op === 'edit' ? {op, id: n.id, label: $('#cx-lab').value, text: $('#cx-txt').value} : {op, id: n.id}]);
    });
    const rd = box.querySelector('[data-read]'); if (rd) rd.onclick = () => { const p = (typeof CATALOG !== 'undefined' && CATALOG[n.id.slice(4)]) || {}; p.file ? openPdf(p.file) : toast('PDF not found', 'err'); };
    const rs = box.querySelector('[data-res]'); if (rs) rs.onclick = () => window.RESULTS_API && RESULTS_API.view(n.rid);
    const cd = box.querySelector('[data-code]'); if (cd) cd.onclick = () => { document.querySelector('nav button[data-tab=ide]').click(); setTimeout(() => window.IDE_API && IDE_API.openFile(n.id.slice(5)), 400); };
  }
  async function apply(ops) {
    try {
      const r = await api('/api/context/ops', {method: 'POST', body: {ops}});
      r.errors.forEach(e => toast(e, 'err'));
      if (r.applied.length) toast(`${r.applied.length} ${T('change(s) applied — all agents use the new context from their next message')}`, 'ok');
      C.g = r.graph; await load(); loadMem(); window.refreshDecisions && refreshDecisions();
    } catch (e) { toast(e.message, 'err'); }
  }
  function addNode() {
    const type = prompt('Node type: assumption, constraint, decision, objective, hypothesis or idea', 'assumption'); if (!type) return;
    const text = prompt('Content:', ''); if (!text) return;
    apply([{op: 'add', type: type.trim().toLowerCase(), label: text.slice(0, 60), text, pinned: confirm('Pin it (every agent must follow it)?')}]);
  }

  // ------------------------------------------------------------------ Context Decision Agent chat
  async function loadChat() { try { C.chat = (await api('/api/context/chat')).messages; } catch {} renderChat(); }
  function renderChat() {
    const box = $('#cx-msgs');
    box.innerHTML = C.chat.length ? C.chat.map((m, i) => m.role === 'user' ? `<div class="cmsg user"><div class="ububble">${esc(m.content)}</div></div>`
      : `<div class="cmsg ai"><div class="md">${md(m.content || '')}</div>${(m.ops || []).length ? `<div class="opslist" data-i="${i}">${m.ops.map((o, j) => `<label><input type="checkbox" data-j="${j}" ${m.applied ? 'disabled' : 'checked'}><span>${opText(o)}</span></label>`).join('')}
          ${m.applied ? `<div class="status">✓ ${T('applied')}</div>` : `<div class="row" style="gap:6px;margin-top:4px"><button class="btn small primary" data-apply="${i}">✓ ${T('Apply selected')}</button></div>`}</div>` : ''}</div>`).join('')
      : `<div class="emptystate">${T('Tell the agent how to reshape the context: what to focus on, what is obsolete, what must always be respected. It proposes changes; you approve them.')}</div>`;
    box.querySelectorAll('[data-apply]').forEach(b => b.onclick = async () => {
      const m = C.chat[b.dataset.apply];
      const ops = m.ops.filter((_, j) => box.querySelector(`.opslist[data-i="${b.dataset.apply}"] [data-j="${j}"]`).checked);
      await apply(ops); m.applied = true; renderChat();
    });
    box.scrollTop = box.scrollHeight;
  }
  function opText(o) {
    const n = C.g && C.g.nodes.find(x => x.id === o.id);
    const name = n ? `“${esc(n.label.slice(0, 60))}”` : `<code>${esc(o.id || '')}</code>`;
    const map = {pin: '📌 ' + T('Pin') + ' ' + name, unpin: T('Unpin') + ' ' + name, purge: '🗑 ' + T('Purge') + ' ' + name, restore: '↺ ' + T('Restore') + ' ' + name,
      edit: '✎ ' + T('Edit') + ' ' + name + (o.text ? ` → “${esc(o.text.slice(0, 80))}”` : ''), delete: '✕ ' + T('Delete') + ' ' + name,
      add: `＋ ${T('Add')} ${esc(T(TYPE_LABEL[o.type] || o.type))}${o.pinned ? ' 📌' : ''}: “${esc((o.text || o.label || '').slice(0, 100))}”`,
      link: `⇢ ${T('Link')} <code>${esc(o.from)}</code> → <code>${esc(o.to)}</code> ${esc(o.label || '')}`};
    return map[o.op] || esc(JSON.stringify(o));
  }
  async function send() {
    const msg = $('#cx-in').value.trim(); if (!msg) return;
    $('#cx-in').value = ''; C.chat.push({role: 'user', content: msg}); C.chat.push({role: 'assistant', content: '…'}); renderChat();
    const b = $('#cx-send'); b.disabled = true;
    try { await api('/api/context/agent', {method: 'POST', body: {message: msg}}); await loadChat(); }
    catch (e) { C.chat.pop(); C.chat.push({role: 'assistant', content: '⚠ ' + e.message}); renderChat(); }
    finally { b.disabled = false; }
  }

  // ------------------------------------------------------------------ hierarchical memory
  async function loadMem() {
    try { C.mem = await api('/api/memory/status'); } catch (e) { return; }
    const m = C.mem, s = m.settings, t1 = m.tier1;
    const pctv = Math.min(100, 100 * t1.tokens / s.tier1_threshold_tokens);
    $('#mem-t1').innerHTML = `<div class="status" style="margin:0">${T('Recent chat turns of every tool + latest sandbox logs')}</div>
      <div class="gauge"><i style="width:${pctv}%"></i></div>
      <div style="font-size:13px"><b>${t1.tokens.toLocaleString()}</b> / ${s.tier1_threshold_tokens.toLocaleString()} ${T('tokens')} · ${T('chats')} ${t1.chat_tokens.toLocaleString()} · ${T('logs')} ${t1.log_tokens.toLocaleString()}</div>
      <div style="margin-top:8px;max-height:180px;overflow:auto">${t1.sessions.slice(0, 15).map(x => `<div class="sessrow"><span title="${esc(x.title)}">${esc(TOOL_NAMES[x.tool] || x.tool)} · ${esc(x.title)}</span><span>${x.messages} ${T('msg')}</span><span>${x.summarized ? '🗂 ' + x.summarized : ''}</span><span>${x.pending_tokens.toLocaleString()} tok</span></div>`).join('') || `<div class="status">${T('No conversations yet')}</div>`}</div>
      <div class="row" style="gap:6px;margin-top:10px;flex-wrap:wrap"><button class="btn small primary" id="mem-sum">🗜 ${T('Summarize now')}</button>
        <label class="chk" style="margin:0"><input type="checkbox" id="mem-auto" ${s.auto_summarize ? 'checked' : ''}> ${T('auto (background)')}</label></div>
      <div class="row" style="gap:6px;margin-top:6px"><div><label>${T('Threshold (tokens)')}</label><input type="text" id="mem-th" value="${s.tier1_threshold_tokens}"></div><div><label>${T('Keep recent turns')}</label><input type="text" id="mem-keep" value="${s.keep_recent_turns}"></div></div>
      <div class="status">${m.busy ? '⏳ ' + T('summarizing…') : ''}${m.stats.last_summary ? ` ${T('Last summary')}: ${esc(m.stats.last_summary.replace('T', ' ').slice(0, 16))}` : ''}${m.stats.last_error ? ` · ⚠ ${esc(m.stats.last_error)}` : ''}</div>`;
    $('#mem-sum').onclick = e => busy(e.target, async () => {
      const r = await api('/api/memory/summarize', {method: 'POST', body: {force: true}});
      toast(r.skipped ? T('Nothing to summarize yet') : `${r.episodes} ${T('episode(s) written')}${r.errors.length ? ' · ⚠ ' + r.errors.join('; ') : ''}`, r.errors.length ? 'err' : 'ok'); loadMem(); load();
    }, T('Summarizing…'));
    const saveMemCfg = () => api('/api/config', {method: 'POST', body: {memory: {auto_summarize: $('#mem-auto').checked, tier1_threshold_tokens: $('#mem-th').value, keep_recent_turns: $('#mem-keep').value}}}).then(() => toast(T('Memory settings saved'), 'ok'));
    ['#mem-auto', '#mem-th', '#mem-keep'].forEach(id => $(id).onchange = saveMemCfg);
    $('#mem-t2').innerHTML = `<div class="status" style="margin:0">${m.tier2.count} ${T('episodes')} · ${m.tier2.tokens.toLocaleString()} ${T('tokens')}</div>
      <div style="max-height:420px;overflow:auto;margin-top:6px">${m.tier2.episodes.map(e => `<details class="ep"><summary>${e.pinned ? '📌' : ''}<b title="${esc(e.title)}">${esc(e.title)}</b><span class="status" style="margin:0">${esc(e.created.slice(0, 10))}</span></summary>
        <div class="status" style="padding:0 12px">${esc(e.source || '')}${e.turns ? ` · ${T('turns')} ${e.turns[0]}–${e.turns[1]}` : ''}${e.compressed_tokens ? ` · ${e.compressed_tokens} → ${Math.round(e.summary.length / 4)} tok` : ''}</div>
        <div class="md">${md(e.summary)}</div><div class="row" style="gap:4px;padding:0 10px 8px"><button class="iconbtn" data-epin="${esc(e.id)}">${e.pinned ? T('Unpin') : '📌 ' + T('Keep (never merge)')}</button><button class="iconbtn" data-edel="${esc(e.id)}">✕ ${T('Delete')}</button></div></details>`).join('') || `<div class="status">${T('No episodes yet. They are written automatically when Tier 1 grows past the threshold.')}</div>`}</div>`;
    $$('#mem-t2 [data-epin]').forEach(b => b.onclick = async () => { const e = m.tier2.episodes.find(x => x.id === b.dataset.epin); await api('/api/memory/episode/' + e.id, {method: 'PUT', body: {pinned: !e.pinned}}); loadMem(); });
    $$('#mem-t2 [data-edel]').forEach(b => b.onclick = async () => { if (!confirm('Delete this episode from memory?')) return; await api('/api/memory/episode/' + b.dataset.edel, {method: 'DELETE'}); loadMem(); load(); });
    const t3 = m.tier3;
    const list = k => (t3[k] || []).join('\n');
    $('#mem-t3').innerHTML = `<label>${T('Research goals (one per line)')}</label><textarea id="t3-goals" rows="3">${esc(list('goals'))}</textarea>
      <label>${T('Hypotheses')}</label><textarea id="t3-hyp" rows="3">${esc(list('hypotheses'))}</textarea>
      <label>${T('Constraints')}</label><textarea id="t3-con" rows="2">${esc(list('constraints'))}</textarea>
      <button class="btn small primary" id="t3-save" style="margin-top:6px">💾 ${T('Save Tier 3')}</button>
      <div style="margin-top:10px;font-size:12.5px"><b>🏆 ${T('Best metrics')}</b> ${Object.entries(t3.best_metrics || {}).map(([k, v]) => `<span class="badge ok" title="run ${esc(v.run)}">${esc(k)} = ${(+v.value).toPrecision(4)} ${v.direction === 'min' ? '↓' : '↑'}</span>`).join(' ') || '<span class="status">–</span>'}</div>
      <div style="margin-top:6px;font-size:12.5px"><b>📚 ${T('Validated references')}</b> <span class="status">${(t3.references || []).length} ${T('BibTeX keys')}</span></div>
      <div style="margin-top:6px;font-size:12.5px"><b>🔒 ${T('Locked decisions')}</b> <span class="status">${m.decisions.filter(d => d.locked).length}</span></div>`;
    $('#t3-save').onclick = async () => {
      const lines = id => $(id).value.split('\n').map(x => x.trim()).filter(Boolean);
      await api('/api/memory/tier3', {method: 'PUT', body: {goals: lines('#t3-goals'), hypotheses: lines('#t3-hyp'), constraints: lines('#t3-con')}});
      toast(T('Tier 3 saved'), 'ok'); load();
    };
  }

  async function init() {
    if (!C.inited) { C.inited = true; build(); loadChat(); }
    load(); loadMem();
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'context') init(); });
  new MutationObserver(() => C.inited && draw()).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  window.CONTEXT_API = {init, reload: () => C.inited && (load(), loadMem())};
})();
