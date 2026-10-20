/* PhD Research Lab v3.1 — research results provided by the researcher (Experiment Design tab)
 * Upload figures / PDF / LaTeX / Markdown / CSV / Excel / notebooks … produced outside the app. They are stored in
 * data/results/, read by every agent as context, shown as nodes in the Context graph, and can be presented in any
 * section of the paper (Writer → 🎯 Brief). Also provides the results picker used by the Writer brief.
 */
(function () {
  const T = s => (window.I18N ? I18N.tr(s) : s);
  const R = {items: [], runs: 0, kind: 'all', q: '', loaded: false};
  const ICON = {figure: '🖼', table: '▦', document: '📄', data: '📊', code: '⌨', note: '📝'};
  const KIND_LABEL = {figure: 'Figure', table: 'Table', document: 'Document', data: 'Data', code: 'Code', note: 'Note'};
  const IMG = /\.(png|jpe?g|gif|webp|svg|bmp)$/i;
  const ACCEPT = 'image/*,.pdf,.eps,.tex,.md,.txt,.csv,.tsv,.json,.yaml,.yml,.log,.py,.ipynb,.m,.r,.jl,.docx,.pptx,.xlsx,.xlsm,.html,.htm,.bib,.out,.dat,.xml';
  const SECTION_NAMES = [['abstract', 'Abstract'], ['introduction', 'Introduction'], ['related_work', 'Related Work'], ['methodology', 'Methodology'],
    ['experiments', 'Experiments and Results'], ['discussion', 'Discussion'], ['conclusion', 'Conclusion']];
  const PRESENT = [['auto', 'Auto (AI chooses)'], ['table', 'As a table'], ['figure', 'As a figure'], ['text', 'Numbers in the text'],
    ['comparison', 'Comparative analysis'], ['highlight', 'Headline result']];
  const fmtSize = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : n > 1024 ? Math.round(n / 1024) + ' KB' : n ? n + ' B' : '';

  // ------------------------------------------------------------------ panel
  function shell() {
    const host = document.getElementById('res-card');
    if (!host || host.dataset.ready) return;
    host.dataset.ready = '1';
    host.innerHTML = `
      <h3>📥 ${T('Your research results')} <span class="status" id="res-count"></span></h3>
      <p class="status" style="margin:0">${T('Did the work outside the app? Drop the results here — figures, PDF reports, LaTeX, Markdown, CSV/Excel, notebooks, logs… They are saved in data/results/, every agent reads them as context (Lit2Plan, Experiment, Writer, chats, Context graph), and you choose which ones each paper section presents (Writer → 🎯 Brief).')}</p>
      <div class="resopts" style="margin-top:10px">
        <input type="text" id="res-notes" placeholder="${esc(T('Describe these files (optional): experiment, dataset, setting, what the result shows…'))}">
        <input type="text" id="res-tags" placeholder="${esc(T('tags, comma separated'))}">
      </div>
      <div class="resdrop" id="res-drop">📥 <b>${T('Drop result files here')}</b> ${T('or click to choose')}<br><span class="status">${T('Images (PNG/JPG/SVG/EPS), PDF, .tex, .md, .csv, .xlsx, .docx, .ipynb, .json, .txt, .log … up to 40 MB each')}</span></div>
      <input type="file" id="res-input" multiple hidden accept="${ACCEPT}">
      <div class="resbar">
        <button class="btn small" id="res-addnote">＋ ${T('Type a result')}</button>
        <input type="text" id="res-q" placeholder="${esc(T('Search results…'))}">
        <div class="chips" id="res-kinds" style="padding:0"></div>
        <span style="flex:1"></span>
        <button class="btn small" id="res-refresh" title="${esc(T('Refresh'))}">↻</button>
      </div>
      <div class="resgrid" id="res-grid"></div>`;
    const drop = host.querySelector('#res-drop'), inp = host.querySelector('#res-input');
    drop.onclick = () => inp.click();
    inp.onchange = () => { upload([...inp.files]); inp.value = ''; };
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
    drop.addEventListener('drop', e => upload([...e.dataTransfer.files]));
    host.querySelector('#res-addnote').onclick = () => noteModal();
    host.querySelector('#res-refresh').onclick = refresh;
    host.querySelector('#res-q').oninput = e => { R.q = e.target.value.toLowerCase(); renderGrid(); };
  }

  async function refresh() {
    shell();
    try {
      const d = await api('/api/results');
      R.items = d.items; R.runs = d.runs; R.loaded = true;
      renderGrid();
    } catch (e) { toast(e.message, 'err'); }
  }

  async function upload(files) {
    if (!files.length) return;
    const fd = new FormData();
    files.forEach(f => fd.append('files', f));
    fd.append('notes', (document.getElementById('res-notes') || {}).value || '');
    fd.append('tags', (document.getElementById('res-tags') || {}).value || '');
    toast(`${T('Uploading')} ${files.length} ${T('file(s)')}…`);
    try {
      const r = await api('/api/results/upload', {method: 'POST', body: fd});
      r.errors.forEach(e => toast(e, 'err'));
      if (r.items.length) toast(`✓ ${r.items.length} ${T('result(s) saved — every agent can use them now')}`, 'ok');
      const n = document.getElementById('res-notes'); if (n && r.items.length) n.value = '';
      await refresh();
      return r.items;
    } catch (e) { toast(e.message, 'err'); return []; }
  }

  function thumb(it) {
    if (it.ext && IMG.test(it.ext)) return `<img loading="lazy" src="/api/results/${it.id}/file" alt="">`;
    return `<span class="ico">${ICON[it.kind] || '📄'}</span>`;
  }

  function renderGrid() {
    const grid = document.getElementById('res-grid');
    if (!grid) return;
    const kinds = ['all', ...Object.keys(ICON).filter(k => R.items.some(i => i.kind === k))];
    if (!kinds.includes(R.kind)) R.kind = 'all';
    document.getElementById('res-kinds').innerHTML = kinds.length > 2 ? kinds.map(k => `<button class="chip ${R.kind === k ? 'on' : ''}" data-k="${k}">${k === 'all' ? T('All') : ICON[k] + ' ' + T(KIND_LABEL[k])} · ${k === 'all' ? R.items.length : R.items.filter(i => i.kind === k).length}</button>`).join('') : '';
    document.querySelectorAll('#res-kinds [data-k]').forEach(b => b.onclick = () => { R.kind = b.dataset.k; renderGrid(); });
    const list = R.items.filter(i => (R.kind === 'all' || i.kind === R.kind) &&
      (!R.q || [i.title, i.notes, i.findings, (i.tags || []).join(' '), i.file].join(' ').toLowerCase().includes(R.q)));
    document.getElementById('res-count').textContent = `— ${R.items.length} ${T('uploaded')}` + (R.runs ? ` · ${R.runs} ${T('runs from Workspace & Runs are also available to the Writer')}` : '');
    if (!R.items.length) { grid.innerHTML = `<div class="resempty">${T('No results yet. Drop files above or type a result.')}</div>`; return; }
    grid.innerHTML = list.map(it => `
      <div class="resitem ${it.pinned ? 'pinned' : ''} ${it.purged ? 'purged' : ''}" data-id="${it.id}">
        <div class="resthumb" data-a="view">${thumb(it)}${it.ext ? `<span class="ext">${esc(it.ext.slice(1))}</span>` : ''}</div>
        <div class="resbody">
          <input type="text" class="rtitle" data-f="title" value="${esc(it.title)}" title="${esc(T('Title (click to edit)'))}">
          <div class="resmeta">
            <select data-f="kind" title="${esc(T('Type'))}">${Object.keys(ICON).map(k => `<option value="${k}" ${k === it.kind ? 'selected' : ''}>${ICON[k]} ${T(KIND_LABEL[k])}</option>`).join('')}</select>
            ${it.file ? `<span>${esc(fmtSize(it.size))}</span>` : `<span>${T('typed')}</span>`}
            ${it.chars ? `<span>· ${it.chars.toLocaleString()} ${T('chars read')}</span>` : ''}
            ${it.pinned ? `<span class="kbadge" style="color:var(--accent);border-color:var(--accent)">📌 ${T('pinned')}</span>` : ''}
            ${it.purged ? `<span class="kbadge">🗑 ${T('hidden from AI')}</span>` : ''}
            ${(it.tags || []).map(t => `<span class="kbadge">#${esc(t)}</span>`).join('')}
          </div>
          <textarea data-f="notes" rows="2" placeholder="${esc(T('What is this result? Experiment, dataset, setting, baseline, what it shows… (the AI relies on this)'))}">${esc(it.notes || '')}</textarea>
          ${it.warning ? `<div class="reswarn">⚠ ${esc(T(it.warning))}</div>` : ''}
          ${it.findings ? `<div class="resfind collapsed md" data-a="fold" title="${esc(T('Click to expand'))}"></div>` : ''}
        </div>
        <div class="resact">
          <button class="iconbtn" data-a="view">👁 ${T('View')}</button>
          <button class="iconbtn" data-a="analyze" title="${esc(T('The AI reads the file / image and writes key numbers and findings (grounded in the file only)'))}">✨ ${T(it.findings ? 'Re-analyze' : 'Analyze')}</button>
          ${['table', 'data', 'document', 'note'].includes(it.kind) ? `<button class="iconbtn" data-a="table" title="${esc(T('Convert to a LaTeX table and add it to the Paper Writer'))}">▦ ${T('LaTeX table')}</button>` : ''}
          <button class="iconbtn" data-a="paper" title="${esc(T('Present this result in a paper section (adds it to that section’s brief)'))}">✍ ${T('Use in paper')}</button>
          <button class="iconbtn" data-a="${it.pinned ? 'unpin' : 'pin'}" title="${esc(T('Pinned results are must-follow context for every agent'))}">${it.pinned ? '📌 ' + T('Unpin') : '📌 ' + T('Pin')}</button>
          <button class="iconbtn" data-a="${it.purged ? 'restore' : 'purge'}" title="${esc(T('Hide from every AI agent (the file is kept)'))}">${it.purged ? '↺ ' + T('Show to AI') : '🙈 ' + T('Hide from AI')}</button>
          <span style="flex:1"></span>
          <button class="iconbtn" data-a="del" title="${esc(T('Delete (moved to data/results/_trash/)'))}">🗑</button>
        </div>
      </div>`).join('') || `<div class="resempty">${T('No matches')}</div>`;
    grid.querySelectorAll('.resitem').forEach(card => {
      const it = R.items.find(x => x.id === card.dataset.id);
      const f = card.querySelector('.resfind');
      if (f) { setRich(f, it.findings); f.onclick = () => f.classList.remove('collapsed'); }
      card.querySelectorAll('[data-f]').forEach(el => el.addEventListener('change', () => save(it, {[el.dataset.f]: el.value})));
      card.querySelectorAll('[data-a]').forEach(b => b.addEventListener('click', e => act(it, b.dataset.a, b, e)));
    });
  }

  async function save(it, fields) {
    try {
      const r = await api('/api/results/' + it.id, {method: 'PUT', body: fields});
      Object.assign(it, r.item);
      toast(T('Saved'), 'ok');
      if ('kind' in fields) renderGrid();
    } catch (e) { toast(e.message, 'err'); }
  }

  async function act(it, a, btn, e) {
    if (a === 'fold') return;
    if (a === 'view') return view(it.id);
    if (a === 'analyze') {
      return busy(btn, async () => {
        const r = await api(`/api/results/${it.id}/analyze`, {method: 'POST'});
        Object.assign(it, r.item); renderGrid();
        toast(`✓ ${T('Analysis saved')} · ${r.engine}`, 'ok');
        if (r.note) toast(r.note);
      }, '…').catch(() => {});
    }
    if (a === 'table') {
      return busy(btn, async () => {
        const r = await api(`/api/results/${it.id}/latex-table`, {method: 'POST', body: {add: true}});
        toast(T('LaTeX table added to the Paper Writer (Paper project → LaTeX tables)'), 'ok');
        if (typeof loadProject === 'function') loadProject().catch(() => {});
        return r;
      }, '…').catch(() => {});
    }
    if (a === 'paper') return paperModal([`up:${it.id}`], it.kind === 'figure' ? 'figure' : it.kind === 'table' ? 'table' : 'auto');
    if (['pin', 'unpin', 'purge', 'restore'].includes(a)) {
      try {
        await api('/api/context/ops', {method: 'POST', body: {ops: [{op: a, id: `result:${it.id}`}]}});
        toast(T(a === 'pin' ? 'Pinned — every agent must take this result into account' : a === 'purge' ? 'Hidden from every AI agent' : 'Updated'), 'ok');
        refresh();
      } catch (err) { toast(err.message, 'err'); }
      return;
    }
    if (a === 'del') {
      if (!confirm(T('Delete this result? It is moved to data/results/_trash/ and removed from the section briefs.'))) return;
      try { await api('/api/results/' + it.id, {method: 'DELETE'}); refresh(); } catch (err) { toast(err.message, 'err'); }
    }
  }

  // ------------------------------------------------------------------ modals
  function modal(html, cls = '') {
    const m = document.createElement('div');
    m.className = 'rmodal ' + cls;
    m.innerHTML = `<div class="card">${html}</div>`;
    m.addEventListener('mousedown', e => { if (e.target === m) m.remove(); });
    const onKey = e => { if (e.key === 'Escape') { m.remove(); document.removeEventListener('keydown', onKey); } };
    document.addEventListener('keydown', onKey);
    document.body.appendChild(m);
    m.querySelectorAll('[data-close]').forEach(b => b.onclick = () => m.remove());
    return m;
  }

  async function view(rid) {
    let it = R.items.find(x => x.id === rid);
    if (!it) { try { await refresh(); it = R.items.find(x => x.id === rid); } catch {} }
    if (!it) return toast(T('Result not found'), 'err');
    const url = `/api/results/${rid}/file`;
    const m = modal(`<div class="row" style="align-items:center"><h4 style="margin:0;flex:1">${ICON[it.kind] || ''} ${esc(it.title)}</h4>
        ${it.file ? `<a class="btn small" href="${url}?download=1">⬇ ${esc(it.file)}</a>` : ''}<button class="btn small" data-close>✕</button></div>
      ${it.notes ? `<div class="status">${esc(it.notes)}</div>` : ''}
      <div class="rvbody" id="rsv-body"><span class="status">…</span></div>
      ${it.findings ? `<details open><summary class="status">✨ ${T('AI analysis')}</summary><div class="md" id="rsv-find"></div></details>` : ''}`);
    const body = m.querySelector('#rsv-body');
    if (it.ext && IMG.test(it.ext)) body.innerHTML = `<img src="${url}" alt="">`;
    else if (it.ext === '.pdf') body.innerHTML = `<iframe src="${url}#view=FitH"></iframe>`;
    else {
      const txt = await api(`/api/results/${rid}/text`).catch(e => e.message);
      if (it.ext === '.md') setRich(body, txt || ''); else body.innerHTML = `<pre class="log">${esc(txt || T('(no text)'))}</pre>`;
    }
    if (it.findings) setRich(m.querySelector('#rsv-find'), it.findings);
  }

  function noteModal() {
    const m = modal(`<h4 style="margin:0">＋ ${T('Type a result')}</h4>
      <p class="status" style="margin:0">${T('Paste numbers from your lab notebook, a Markdown table, a short report… The AI uses exactly what you write.')}</p>
      <div class="row"><input type="text" id="rn-title" placeholder="${esc(T('Title, e.g. Ablation on Indian Pines'))}">
      <select id="rn-kind" style="flex:0 0 170px">${Object.keys(ICON).map(k => `<option value="${k}" ${k === 'note' ? 'selected' : ''}>${ICON[k]} ${T(KIND_LABEL[k])}</option>`).join('')}</select></div>
      <textarea id="rn-text" rows="12" class="code" placeholder="| Method | PSNR | SSIM |\n|---|---|---|\n| Ours | 34.21 | 0.951 |"></textarea>
      <input type="text" id="rn-tags" placeholder="${esc(T('tags, comma separated'))}">
      <div class="row" style="justify-content:flex-end"><button class="btn" data-close>${T('Cancel')}</button><button class="btn primary" id="rn-ok">${T('Save result')}</button></div>`);
    m.querySelector('#rn-ok').onclick = async () => {
      try {
        await api('/api/results/note', {method: 'POST', body: {title: m.querySelector('#rn-title').value, kind: m.querySelector('#rn-kind').value,
          text: m.querySelector('#rn-text').value, tags: m.querySelector('#rn-tags').value.split(',').map(s => s.trim()).filter(Boolean)}});
        m.remove(); toast(T('Result saved'), 'ok'); refresh();
      } catch (e) { toast(e.message, 'err'); }
    };
    setTimeout(() => m.querySelector('#rn-text').focus(), 50);
  }

  function paperModal(refs, as = 'auto') {
    const m = modal(`<h4 style="margin:0">✍ ${T('Present in a paper section')}</h4>
      <label>${T('Section')}</label><select id="rpm-sec">${SECTION_NAMES.map(([id, t]) => `<option value="${id}" ${id === 'experiments' ? 'selected' : ''}>${T(t)}</option>`).join('')}</select>
      <label>${T('Present as')}</label><select id="rpm-as">${PRESENT.map(([v, t]) => `<option value="${v}" ${v === as ? 'selected' : ''}>${T(t)}</option>`).join('')}</select>
      <p class="status">${T('The result is added to that section’s 🎯 Brief in the Paper Writer, where you can reorder it and add a note on how to present it.')}</p>
      <div class="row" style="justify-content:flex-end"><button class="btn" data-close>${T('Cancel')}</button><button class="btn primary" id="rpm-ok">${T('Add to brief')}</button></div>`);
    m.style.alignItems = 'center';
    m.querySelector('.card').style.width = 'min(480px,94vw)';
    m.querySelector('#rpm-ok').onclick = async () => {
      const sec = m.querySelector('#rpm-sec').value;
      try {
        await api('/api/results/to-section', {method: 'POST', body: {section: sec, refs, as: m.querySelector('#rpm-as').value}});
        m.remove();
        toast(`✓ ${T('Added to the brief of')} ${T(SECTION_NAMES.find(s => s[0] === sec)[1])}`, 'ok');
        if (window.BRIEF_API) BRIEF_API.invalidate(sec);
      } catch (e) { toast(e.message, 'err'); }
    };
  }

  /** Results picker for the Writer brief. opts: {selected: [refs], onDone(refs: [{ref,title,kind,figure_ok,thumb}])} */
  async function pick(opts = {}) {
    let pool = [];
    const chosen = new Set();
    const already = new Set(opts.selected || []);
    let src = 'all', q = '';
    const m = modal(`<div class="row" style="align-items:center"><h4 style="margin:0;flex:1">📊 ${T('Choose the results to present')}</h4><button class="btn small" data-close>✕</button></div>
      <div class="row" style="gap:6px;flex-wrap:wrap;align-items:center">
        <div class="chips" id="pk-src" style="padding:0"></div>
        <input type="text" id="pk-q" placeholder="${esc(T('Search…'))}" style="flex:1;min-width:160px">
        <button class="btn small" id="pk-up">📥 ${T('Upload new…')}</button>
        <input type="file" id="pk-file" multiple hidden accept="${ACCEPT}">
      </div>
      <div class="picklist" id="pk-list"></div>
      <div class="row" style="justify-content:flex-end;align-items:center"><span class="status" id="pk-n" style="flex:1"></span><button class="btn" data-close>${T('Cancel')}</button><button class="btn primary" id="pk-ok">${T('Add selected')}</button></div>`);
    const load = async () => { pool = (await api('/api/results/pool')).pool; draw(); };
    const draw = () => {
      const srcs = [['all', T('All')], ['upload', '📥 ' + T('Uploaded')], ['run', '💻 ' + T('sandbox runs')], ['writer', '✍ ' + T('Writer tables & notes')]];
      m.querySelector('#pk-src').innerHTML = srcs.map(([v, t]) => `<button class="chip ${src === v ? 'on' : ''}" data-s="${v}">${t} · ${v === 'all' ? pool.length : pool.filter(p => p.source === v).length}</button>`).join('');
      m.querySelectorAll('#pk-src [data-s]').forEach(b => b.onclick = () => { src = b.dataset.s; draw(); });
      const list = pool.filter(p => (src === 'all' || p.source === src) && (!q || (p.title + ' ' + p.sub + ' ' + (p.tags || []).join(' ')).toLowerCase().includes(q)));
      m.querySelector('#pk-list').innerHTML = list.map(p => `
        <div class="pickrow ${chosen.has(p.ref) ? 'on' : ''}" data-ref="${esc(p.ref)}" ${already.has(p.ref) ? 'style="opacity:.5"' : ''}>
          <input type="checkbox" ${chosen.has(p.ref) || already.has(p.ref) ? 'checked' : ''} ${already.has(p.ref) ? 'disabled' : ''}>
          <div class="pthumb">${p.thumb ? `<img loading="lazy" src="${esc(p.thumb)}" alt="">` : (ICON[p.kind] || '📄')}</div>
          <div><div class="pt">${esc(p.title)}</div><div class="ps">${esc(p.sub || '')}</div></div>
          <span class="kbadge ${p.kind}">${T(KIND_LABEL[p.kind] || p.kind)}${already.has(p.ref) ? ' · ' + T('already in brief') : ''}</span>
        </div>`).join('') || `<div class="resempty">${T('No results yet — upload files in Experiment Design, run code in Workspace & Runs, or add LaTeX tables.')}</div>`;
      m.querySelectorAll('.pickrow').forEach(row => row.onclick = () => {
        const ref = row.dataset.ref;
        if (already.has(ref)) return;
        chosen.has(ref) ? chosen.delete(ref) : chosen.add(ref);
        draw();
      });
      m.querySelector('#pk-n').textContent = chosen.size ? `${chosen.size} ${T('selected')}` : '';
    };
    m.querySelector('#pk-q').oninput = e => { q = e.target.value.toLowerCase(); draw(); };
    m.querySelector('#pk-up').onclick = () => m.querySelector('#pk-file').click();
    m.querySelector('#pk-file').onchange = async e => {
      const items = await upload([...e.target.files]);
      (items || []).forEach(it => chosen.add(`up:${it.id}`));
      await load();
    };
    m.querySelector('#pk-ok').onclick = () => {
      const out = pool.filter(p => chosen.has(p.ref));
      m.remove();
      if (opts.onDone) opts.onDone(out);
    };
    try { await load(); } catch (e) { toast(e.message, 'err'); }
  }

  window.RESULTS_API = {refresh, view: rid => { view(rid); }, pick, upload, paperModal, ICON, KIND_LABEL, PRESENT};
  window.addEventListener('tab-shown', e => { if (e.detail === 'experiment') refresh(); });
  document.addEventListener('DOMContentLoaded', () => { shell(); if (document.querySelector('#tab-experiment.on, #tab-experiment.active')) refresh(); });
  if (document.readyState !== 'loading') { shell(); }
})();
