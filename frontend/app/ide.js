/* PhD Research Lab v3.0 — 💻 Code IDE: VS Code-style layout, Monaco editor, xterm terminal, Docker sandbox,
   Source Control / GitHub, run history with metrics & figures, AI co-coding agent with self-debugging loop. */
(() => {
  const T = s => I18N.tr(s);
  const IDE = {inited: false, mon: null, ed: null, diffEd: null, tabs: [], cur: null, tree: null, expanded: new Set(), sel: '',
    view: 'explorer', git: null, term: null, fit: null, es: null, liveJob: null, series: {}, chat: [], ctrl: null, sid: null,
    status: null, hist: []};
  try { IDE.expanded = new Set(JSON.parse(localStorage.getItem('ide_expanded') || '[]')); } catch {}
  try { IDE.hist = JSON.parse(localStorage.getItem('ide_cmd_hist') || '[]'); } catch {}
  const root = () => $('#tab-ide');
  const jsonErr = e => { try { return JSON.parse(e.message); } catch { return null; } };
  const LANG = {py: 'python', tex: 'latex', sty: 'latex', cls: 'latex', bib: 'bibtex', md: 'markdown', json: 'json', ipynb: 'json',
    yaml: 'yaml', yml: 'yaml', sh: 'shell', bash: 'shell', bat: 'bat', cmd: 'bat', ps1: 'powershell', c: 'cpp', h: 'cpp', cpp: 'cpp',
    hpp: 'cpp', cu: 'cpp', r: 'r', jl: 'julia', html: 'html', htm: 'html', css: 'css', ini: 'ini', cfg: 'ini', toml: 'ini', xml: 'xml',
    sql: 'sql', sv: 'systemverilog', v: 'systemverilog', dockerfile: 'dockerfile', txt: 'plaintext', csv: 'plaintext', log: 'plaintext'};
  const langOf = p => { const n = p.split('/').pop().toLowerCase(); if (n === 'dockerfile') return 'dockerfile'; return LANG[n.includes('.') ? n.split('.').pop() : ''] || 'plaintext'; };
  const IMG = /\.(png|jpe?g|gif|svg|webp)$/i;
  const icon = (n, dir, open) => dir ? (open ? '📂' : '📁') : /\.py$/.test(n) ? '🐍' : /\.(tex|bib|sty|cls)$/.test(n) ? '📜' : /\.(md|txt)$/.test(n) ? '📝'
    : /\.(json|ya?ml|toml|ini|cfg)$/.test(n) ? '⚙' : IMG.test(n) ? '🖼' : /\.(csv|tsv)$/.test(n) ? '📊' : /\.ipynb$/.test(n) ? '📓' : /\.pdf$/.test(n) ? '📕' : '📄';

  // ------------------------------------------------------------------ layout
  function build() {
    root().innerHTML = `<div class="ide" id="ide">
      <div class="actbar">
        <button data-v="explorer" title="Explorer">📁</button>
        <button data-v="search" title="Search in files">🔍</button>
        <button data-v="scm" title="Source Control · GitHub">⑂<span class="bdg" id="ide-scmbdg" hidden></span></button>
        <button data-v="runs" title="Runs · metrics · figures">📈</button>
        <span class="sp"></span>
        <button data-act="docker" title="Docker & System monitor">🐳</button>
        <button data-act="chat" title="Toggle AI co-coding panel">✳</button>
      </div>
      <div class="sidep" id="ide-side"></div>
      <div class="vsplit" data-split="side" style="grid-column:3"></div>
      <div class="edarea">
        <div class="edtabs" id="ide-tabs"></div>
        <div class="edbar">
          <button class="btn small primary" id="ide-run" title="Run in the sandbox (Ctrl+Enter)">▶ Run</button>
          <button class="btn small stop" id="ide-stop" disabled>■ Stop</button>
          <input id="ide-cmd" list="ide-cmdlist" placeholder="python train.py --epochs 2" spellcheck="false"><datalist id="ide-cmdlist"></datalist>
          <button class="btn small" id="ide-save" title="Save (Ctrl+S)">💾</button>
          <span class="status" id="ide-mode"></span>
        </div>
        <div class="edhost" id="ide-host"><div class="monaco" id="ide-monaco" style="display:none"></div><div class="edpane" id="ide-pane"></div></div>
      </div>
      <div class="vsplit" data-split="chat" style="grid-column:5"></div>
      <div class="hsplit" data-split="term"></div>
      <div class="botp">
        <div class="bottabs"><button class="t on" data-b="term">Terminal</button><button class="t" data-b="metrics">Live metrics</button>
          <span class="sp"></span><span class="status" id="ide-jobst"></span>
          <button class="iconbtn" id="ide-termclear" title="Clear terminal">🧹</button></div>
        <div class="botb">
          <div class="termwrap" id="ide-termwrap"><div class="termhost" id="ide-term"></div>
            <div class="termin"><span>$</span><input id="ide-termin" placeholder="pip install torch · ls -la · nvidia-smi   (runs in the sandbox)" spellcheck="false"></div></div>
          <div class="metricsp" id="ide-metrics" hidden></div>
        </div>
      </div>
      <div class="chatside" id="ide-chat"></div>
    </div>
    <div class="ctxmenu" id="ide-ctx"></div>`;
    const ide = $('#ide');
    try {
      const L = JSON.parse(localStorage.getItem('ide_layout') || '{}');
      ['side', 'chat', 'term'].forEach(k => L[k] && ide.style.setProperty('--' + k, L[k] + 'px'));
      if (L.nochat) ide.classList.add('nochat');
    } catch {}
    $$('#ide .actbar [data-v]').forEach(b => b.onclick = () => showView(b.dataset.v));
    $('#ide .actbar [data-act=docker]').onclick = () => document.querySelector('nav button[data-tab=docker]').click();
    $('#ide .actbar [data-act=chat]').onclick = () => { ide.classList.toggle('nochat'); saveLayout(); relayout(); };
    $$('#ide [data-split]').forEach(sp => sp.onmousedown = e => startDrag(e, sp.dataset.split));
    $$('#ide .bottabs [data-b]').forEach(b => b.onclick = () => {
      $$('#ide .bottabs [data-b]').forEach(x => x.classList.toggle('on', x === b));
      $('#ide-termwrap').hidden = b.dataset.b !== 'term'; $('#ide-metrics').hidden = b.dataset.b !== 'metrics';
      if (b.dataset.b === 'metrics') renderLiveMetrics(); else fitTerm();
    });
    $('#ide-run').onclick = runCmd;
    $('#ide-stop').onclick = stopJob;
    $('#ide-save').onclick = () => saveTab(IDE.cur);
    $('#ide-cmd').addEventListener('keydown', e => { if (e.key === 'Enter') runCmd(); });
    $('#ide-termin').addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.target.value.trim()) { const c = e.target.value.trim(); e.target.value = ''; startJob(c, 'shell'); }
    });
    $('#ide-termclear').onclick = () => IDE.term && IDE.term.clear();
    document.addEventListener('click', () => $('#ide-ctx').style.display = 'none');
    paintCmdHist();
    buildChat();
    showView('explorer');
    welcome();
  }
  function saveLayout() {
    const ide = $('#ide'), cs = getComputedStyle(ide);
    const L = {nochat: ide.classList.contains('nochat')};
    ['side', 'chat', 'term'].forEach(k => L[k] = parseInt(cs.getPropertyValue('--' + k)) || undefined);
    try { localStorage.setItem('ide_layout', JSON.stringify(L)); } catch {}
  }
  function startDrag(e, which) {
    e.preventDefault();
    const ide = $('#ide'), r = ide.getBoundingClientRect();
    const move = ev => {
      if (which === 'side') ide.style.setProperty('--side', Math.max(160, Math.min(520, ev.clientX - r.left - 46)) + 'px');
      if (which === 'chat') ide.style.setProperty('--chat', Math.max(280, Math.min(760, r.right - ev.clientX)) + 'px');
      if (which === 'term') ide.style.setProperty('--term', Math.max(90, Math.min(r.height - 150, r.bottom - ev.clientY)) + 'px');
      relayout();
    };
    const up = () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); saveLayout(); };
    document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
  }
  function relayout() { if (IDE.ed) IDE.ed.layout(); if (IDE.diffEd) IDE.diffEd.layout(); fitTerm(); }
  window.addEventListener('resize', () => { if (root().classList.contains('on')) relayout(); });

  // ------------------------------------------------------------------ Monaco
  function loadScript(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('Cannot load ' + src)); document.head.append(s); }); }
  async function loadMonaco() {
    if (IDE.mon) return IDE.mon;
    window.MonacoEnvironment = {getWorkerUrl: () => `data:text/javascript;charset=utf-8,${encodeURIComponent(
      `self.MonacoEnvironment={baseUrl:'${location.origin}/vendor/monaco/'};importScripts('${location.origin}/vendor/monaco/vs/base/worker/workerMain.js');`)}`};
    await loadScript('/vendor/monaco/vs/loader.js');
    await new Promise((res, rej) => { window.require.config({paths: {vs: '/vendor/monaco/vs'}}); window.require(['vs/editor/editor.main'], res, rej); });
    const m = window.monaco;
    m.languages.register({id: 'latex', extensions: ['.tex', '.sty', '.cls']});
    m.languages.setMonarchTokensProvider('latex', {tokenizer: {root: [
      [/%.*$/, 'comment'], [/\\(begin|end)\{[^}]*\}/, 'keyword'], [/\\(sub)*section\*?|\\paragraph|\\caption|\\title/, 'type'],
      [/\\(cite[a-zA-Z]*|ref|eqref|label|autoref|cref)\*?(\[[^\]]*\])?\{[^}]*\}/, 'string'], [/\$\$[^$]*\$\$|\$[^$\n]+\$/, 'number'],
      [/\\textcolor\{red\}\{\[[^\]]*\]\}|\[(TBD|CITATION NEEDED)[^\]]*\]/, 'invalid'], [/\\[a-zA-Z@]+\*?|\\./, 'tag'], [/[{}[\]]/, 'delimiter'], [/&/, 'operator']]}});
    m.languages.register({id: 'bibtex', extensions: ['.bib']});
    m.languages.setMonarchTokensProvider('bibtex', {tokenizer: {root: [[/%.*$/, 'comment'], [/@\w+/, 'keyword'], [/\b\w+(?=\s*=)/, 'type'],
      [/\{[^{}]*\}|"[^"]*"/, 'string'], [/\d+/, 'number']]}});
    IDE.mon = m;
    const theme = () => m.editor.setTheme(document.documentElement.dataset.theme === 'light' ? 'vs' : 'vs-dark');
    theme(); new MutationObserver(theme).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
    IDE.ed = m.editor.create($('#ide-monaco'), {automaticLayout: true, fontSize: 13, minimap: {enabled: true}, scrollBeyondLastLine: false,
      fontFamily: "'IBM Plex Mono', Consolas, monospace", tabSize: 4, renderWhitespace: 'selection', wordWrap: 'off'});
    IDE.ed.addCommand(m.KeyMod.CtrlCmd | m.KeyCode.KeyS, () => saveTab(IDE.cur));
    IDE.ed.addCommand(m.KeyMod.CtrlCmd | m.KeyCode.Enter, () => runCmd());
    return m;
  }

  // ------------------------------------------------------------------ side views
  function showView(v) {
    IDE.view = v;
    $$('#ide .actbar [data-v]').forEach(b => b.classList.toggle('on', b.dataset.v === v));
    if (v === 'explorer') explorerView(); else if (v === 'search') searchView(); else if (v === 'scm') scmView(); else if (v === 'runs') runsView();
  }
  async function explorerView() {
    const side = $('#ide-side');
    side.innerHTML = `<div class="sideh"><span>${T('Explorer')}</span>
      <button class="iconbtn" data-a="newf" title="New file">＋📄</button><button class="iconbtn" data-a="newd" title="New folder">＋📁</button>
      <button class="iconbtn" data-a="up" title="Upload files">⤒</button><button class="iconbtn" data-a="seed" title="Create starter project from the Tool 2 blueprint">🧪</button>
      <button class="iconbtn" data-a="ref" title="Refresh">↻</button></div>
      <div class="sideb ftree" id="ide-tree"></div><input type="file" id="ide-upl" multiple hidden>`;
    side.querySelector('[data-a=newf]').onclick = () => newItem(false);
    side.querySelector('[data-a=newd]').onclick = () => newItem(true);
    side.querySelector('[data-a=up]').onclick = () => $('#ide-upl').click();
    side.querySelector('[data-a=seed]').onclick = seedBlueprint;
    side.querySelector('[data-a=ref]').onclick = loadTree;
    $('#ide-upl').onchange = async e => {
      const fd = new FormData(); fd.append('folder', folderOf(IDE.sel)); [...e.target.files].forEach(f => fd.append('files', f)); e.target.value = '';
      try { await api('/api/ide/upload', {method: 'POST', body: fd}); toast(T('Uploaded'), 'ok'); loadTree(); } catch (err) { toast(err.message, 'err'); }
    };
    loadTree();
  }
  function folderOf(p) { if (!p) return ''; const n = findNode(p); return n && n.dir ? p : p.split('/').slice(0, -1).join('/'); }
  function findNode(p, nodes = (IDE.tree || {}).children || []) {
    for (const n of nodes) { if (n.path === p) return n; if (n.dir) { const r = findNode(p, n.children); if (r) return r; } } return null;
  }
  async function loadTree() {
    try { IDE.tree = await api('/api/ide/tree'); } catch (e) { $('#ide-tree') && ($('#ide-tree').innerHTML = `<div class="empty">⚠ ${esc(e.message)}</div>`); return; }
    if (!IDE.git) refreshGit(true);
    renderTree();
  }
  function renderTree() {
    const box = $('#ide-tree'); if (!box) return;
    const gmap = {};
    ((IDE.git || {}).files || []).forEach(f => gmap[f.path] = f.status === 'untracked' ? 'U' : f.status === 'added' ? 'A' : f.status === 'deleted' ? 'D' : 'M');
    const rows = [];
    const walk = (nodes, depth) => nodes.forEach(n => {
      const open = IDE.expanded.has(n.path);
      rows.push(`<div class="fi ${IDE.sel === n.path ? 'sel' : ''}" data-p="${esc(n.path)}" data-dir="${n.dir ? 1 : 0}" style="padding-left:${8 + depth * 13}px">
        <span class="tw">${n.dir ? (open ? '▾' : '▸') : ''}</span><span>${icon(n.name, n.dir, open)}</span><span class="nm">${esc(n.name)}</span>
        ${gmap[n.path] ? `<span class="gs ${gmap[n.path]}">${gmap[n.path]}</span>` : ''}</div>`);
      if (n.dir && open) walk(n.children, depth + 1);
    });
    walk(IDE.tree.children, 0);
    box.innerHTML = rows.join('') || `<div class="empty" style="padding:24px 12px">${T('Empty workspace.')}<br><br><button class="btn small" id="ide-seed2">🧪 ${T('Create from blueprint')}</button></div>`;
    $('#ide-seed2') && ($('#ide-seed2').onclick = seedBlueprint);
    box.querySelectorAll('.fi').forEach(el => {
      el.onclick = () => {
        const p = el.dataset.p; IDE.sel = p;
        if (el.dataset.dir === '1') { IDE.expanded.has(p) ? IDE.expanded.delete(p) : IDE.expanded.add(p); try { localStorage.setItem('ide_expanded', JSON.stringify([...IDE.expanded])); } catch {} renderTree(); }
        else { renderTree(); openFile(p); }
      };
      el.oncontextmenu = e => { e.preventDefault(); IDE.sel = el.dataset.p; renderTree(); ctxMenu(e, el.dataset.p, el.dataset.dir === '1'); };
    });
  }
  function ctxMenu(e, p, dir) {
    const m = $('#ide-ctx');
    const items = [[T('New file here'), () => newItem(false)], [T('New folder here'), () => newItem(true)], ['hr'],
      ...(!dir && /\.py$/.test(p) ? [[`▶ ${T('Run')} ${p.split('/').pop()}`, () => { $('#ide-cmd').value = `python ${p}`; runCmd(); }]] : []),
      [T('Rename…'), () => renameItem(p)], [T('Copy path'), () => navigator.clipboard.writeText(p)], ['hr'], [`🗑 ${T('Delete')}`, () => deleteItem(p)]];
    m.innerHTML = items.map((it, i) => it[0] === 'hr' ? '<hr>' : `<div data-i="${i}">${esc(it[0])}</div>`).join('');
    m.querySelectorAll('[data-i]').forEach(d => d.onclick = () => { m.style.display = 'none'; items[d.dataset.i][1](); });
    m.style.display = 'block'; m.style.left = Math.min(e.clientX, innerWidth - 190) + 'px'; m.style.top = Math.min(e.clientY, innerHeight - 260) + 'px';
  }
  async function newItem(folder) {
    const base = folderOf(IDE.sel);
    const name = prompt(folder ? 'New folder name:' : 'New file name (e.g. src/model.py):', ''); if (!name) return;
    const path = (base ? base + '/' : '') + name.replace(/^\/+/, '');
    try { await api('/api/ide/create', {method: 'POST', body: {path, folder}}); if (base) IDE.expanded.add(base); await loadTree(); if (!folder) openFile(path); }
    catch (e) { toast(e.message, 'err'); }
  }
  async function renameItem(p) {
    const to = prompt('Rename / move to:', p); if (!to || to === p) return;
    try { await api('/api/ide/rename', {method: 'POST', body: {from: p, to}}); IDE.tabs.filter(t => t.path === p).forEach(t => closeTab(t, true)); loadTree(); } catch (e) { toast(e.message, 'err'); }
  }
  async function deleteItem(p) {
    if (!confirm(`Delete "${p}"? It is moved to code/.trash/ (recoverable).`)) return;
    try { await api('/api/ide/file?path=' + encodeURIComponent(p), {method: 'DELETE'}); IDE.tabs.filter(t => t.path === p || t.path.startsWith(p + '/')).forEach(t => closeTab(t, true)); loadTree(); }
    catch (e) { toast(e.message, 'err'); }
  }
  async function seedBlueprint() {
    try {
      const r = await api('/api/ide/seed', {method: 'POST'});
      toast(r.created.length ? `${T('Created')}: ${r.created.join(', ')}` : T('Nothing to create — the files already exist'), 'ok');
      IDE.tree = r.tree; renderTree(); if (r.created.includes('experiment_skeleton.py')) openFile('experiment_skeleton.py');
    } catch (e) { toast(e.message, 'err'); }
  }
  function searchView() {
    $('#ide-side').innerHTML = `<div class="sideh"><span>${T('Search')}</span></div>
      <div style="padding:8px"><input type="text" id="ide-q" placeholder="${esc(T('Search in workspace files…'))}"></div><div class="sideb" id="ide-hits"></div>`;
    let tm = null;
    $('#ide-q').oninput = e => { clearTimeout(tm); tm = setTimeout(async () => {
      const q = e.target.value.trim(); if (!q) { $('#ide-hits').innerHTML = ''; return; }
      const {hits} = await api('/api/ide/search?q=' + encodeURIComponent(q));
      $('#ide-hits').innerHTML = hits.map((h, i) => `<div class="fi" data-i="${i}" style="padding:4px 10px;display:block;cursor:pointer"><div style="font-size:12px;color:var(--accent2)">${esc(h.path)}:${h.line}</div><div style="font-family:var(--mono);font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(h.text)}</div></div>`).join('') || `<div class="empty">${T('No matches')}</div>`;
      $$('#ide-hits [data-i]').forEach(el => el.onclick = () => { const h = hits[el.dataset.i]; openFile(h.path, h.line); });
    }, 250); };
    $('#ide-q').focus();
  }

  // ------------------------------------------------------------------ editor tabs
  function welcome() {
    IDE.cur = null; renderTabs();
    $('#ide-monaco').style.display = 'none'; const pane = $('#ide-pane'); pane.style.display = '';
    pane.innerHTML = `<div class="welcome"><h2>💻 ${T('Research Code IDE')}</h2>
      <p class="status">${T('Code runs in an isolated Docker container (GPU passthrough when available) or a private Python venv. The AI co-coding agent on the right can write the code from your blueprint, run it and fix errors automatically.')}</p>
      <div class="grid">
        <div class="wcard" data-w="seed"><b>🧪 ${T('Start from the blueprint')}</b><span>${T('Create the project from Tool 2 (experiment_skeleton.py + design)')}</span></div>
        <div class="wcard" data-w="agent"><b>✳ ${T('Ask the agent to implement it')}</b><span>${T('Implements the experiment, runs a smoke test, self-debugs')}</span></div>
        <div class="wcard" data-w="new"><b>📄 ${T('New file')}</b><span>${T('Python, LaTeX, BibTeX, Markdown, configs…')}</span></div>
        <div class="wcard" data-w="docker"><b>🐳 ${T('Sandbox status')}</b><span>${T('Docker, GPU/VRAM, container, jobs')}</span></div>
        <div class="wcard" data-w="scm"><b>⑂ ${T('Source control')}</b><span>${T('Commit and publish to GitHub')}</span></div>
        <div class="wcard" data-w="runs"><b>📈 ${T('Runs & metrics')}</b><span>${T('metrics.json, live curves, figures')}</span></div>
      </div></div>`;
    pane.querySelectorAll('[data-w]').forEach(c => c.onclick = () => ({seed: seedBlueprint, new: () => newItem(false),
      docker: () => document.querySelector('nav button[data-tab=docker]').click(), scm: () => showView('scm'), runs: () => showView('runs'),
      agent: () => { $('#ide').classList.remove('nochat'); relayout(); const ta = $('#ide-cin'); ta.value = T('Implement the experiment described in the blueprint as a clean, runnable Python project, then run a quick smoke test.'); ta.focus(); }})[c.dataset.w]());
  }
  function renderTabs() {
    $('#ide-tabs').innerHTML = IDE.tabs.map((t, i) => `<div class="edtab ${t === IDE.cur ? 'on' : ''} ${t.dirty ? 'dirty' : ''}" data-i="${i}" title="${esc(t.path || t.title)}">
      <span>${t.kind === 'diff' ? '⇄ ' : t.kind === 'run' ? '📈 ' : ''}${esc(t.title)}</span><button class="x" data-x="${i}"><span>✕</span></button></div>`).join('');
    $$('#ide-tabs .edtab').forEach(el => el.onclick = e => { if (e.target.closest('[data-x]')) return; activate(IDE.tabs[el.dataset.i]); });
    $$('#ide-tabs [data-x]').forEach(b => b.onclick = e => { e.stopPropagation(); closeTab(IDE.tabs[b.dataset.x]); });
    const t = IDE.cur;
    $('#ide-save').disabled = !(t && t.kind === 'file');
    if (t && t.kind === 'file' && /\.py$/.test(t.path) && !$('#ide-cmd').dataset.touched) $('#ide-cmd').value = `python ${t.path}`;
  }
  async function openFile(path, line) {
    let t = IDE.tabs.find(x => x.kind === 'file' && x.path === path);
    if (!t) {
      if (IMG.test(path)) {
        t = {kind: 'image', path, title: path.split('/').pop()}; IDE.tabs.push(t); activate(t); return;
      }
      let d;
      try { d = await api('/api/ide/file?path=' + encodeURIComponent(path)); } catch (e) { return toast(e.message, 'err'); }
      if (d.binary) { window.open('/api/ide/raw?path=' + encodeURIComponent(path), '_blank'); return; }
      const m = await loadMonaco();
      const model = m.editor.createModel(d.content, langOf(path), m.Uri.parse('file:///' + encodeURI(path)));
      t = {kind: 'file', path, title: path.split('/').pop(), model, mtime: d.mtime, saved: d.content, dirty: false};
      model.onDidChangeContent(() => { const dirty = model.getValue() !== t.saved; if (dirty !== t.dirty) { t.dirty = dirty; renderTabs(); } });
      IDE.tabs.push(t);
    }
    activate(t);
    if (line && IDE.ed) { IDE.ed.revealLineInCenter(line); IDE.ed.setPosition({lineNumber: line, column: 1}); IDE.ed.focus(); }
  }
  function activate(t) {
    IDE.cur = t; renderTabs();
    const mon = $('#ide-monaco'), pane = $('#ide-pane');
    if (IDE.diffEd && t.kind !== 'diff') { IDE.diffEd.dispose(); IDE.diffEd = null; $('#ide-diffhost') && $('#ide-diffhost').remove(); }
    if (t.kind === 'file') {
      pane.style.display = 'none'; mon.style.display = ''; IDE.ed.setModel(t.model); IDE.ed.layout(); IDE.ed.focus();
    } else if (t.kind === 'diff') {
      mon.style.display = 'none'; pane.style.display = ''; renderDiff(t);
    } else if (t.kind === 'image') {
      mon.style.display = 'none'; pane.style.display = '';
      pane.innerHTML = `<div style="text-align:center"><img src="/api/ide/raw?path=${encodeURIComponent(t.path)}&t=${Date.now()}" style="max-width:100%;border-radius:8px;background:#fff"></div>`;
    } else if (t.kind === 'run') {
      mon.style.display = 'none'; pane.style.display = ''; renderRun(t);
    }
  }
  function closeTab(t, force) {
    if (!t) return;
    if (t.dirty && !force && !confirm(`"${t.title}" has unsaved changes. Close anyway?`)) return;
    const i = IDE.tabs.indexOf(t); IDE.tabs.splice(i, 1);
    if (t.model) t.model.dispose();
    if (IDE.cur === t) { const n = IDE.tabs[Math.max(0, i - 1)]; n ? activate(n) : welcome(); } else renderTabs();
  }
  async function saveTab(t, overwrite) {
    if (!t || t.kind !== 'file') return;
    try {
      const v = t.model.getValue();
      const r = await api('/api/ide/file', {method: 'PUT', body: {path: t.path, content: v, mtime: overwrite ? null : t.mtime}});
      t.mtime = r.mtime; t.saved = v; t.dirty = false; renderTabs(); refreshGit(); return true;
    } catch (e) {
      if (/CONFLICT/.test(e.message)) {
        if (confirm(`${t.path} changed on disk (the AI agent or a run wrote it).\n\nOK = overwrite with your version · Cancel = reload from disk`)) return saveTab(t, true);
        await reloadTab(t); return false;
      }
      toast(e.message, 'err'); return false;
    }
  }
  async function reloadTab(t) {
    const d = await api('/api/ide/file?path=' + encodeURIComponent(t.path));
    t.saved = d.content; t.mtime = d.mtime; t.model.setValue(d.content); t.dirty = false; renderTabs();
  }
  async function refreshOpenTabs(paths) {
    for (const t of IDE.tabs.filter(x => x.kind === 'file' && (!paths || paths.includes(x.path)))) {
      if (!t.dirty) await reloadTab(t).catch(() => {});
    }
  }
  async function saveAll() { for (const t of IDE.tabs.filter(x => x.dirty)) await saveTab(t); }

  // diff tabs (git changes, agent proposals)
  async function openDiff(title, original, modified, lang, onAccept) {
    await loadMonaco();
    const t = {kind: 'diff', title, original, modified, lang, onAccept, path: ''};
    IDE.tabs.push(t); activate(t);
  }
  function renderDiff(t) {
    const pane = $('#ide-pane');
    pane.innerHTML = `<div style="display:flex;flex-direction:column;height:100%;margin:-18px -22px"><div class="edbar" style="border-top:0">
        <b style="flex:1;font-size:12.5px">${esc(t.title)}</b>${t.onAccept ? `<button class="btn small primary" id="ide-acc">✓ ${T('Accept change')}</button>` : ''}
        <button class="btn small" id="ide-dclose">${T('Close')}</button></div><div id="ide-diffhost" style="flex:1;min-height:0"></div></div>`;
    const m = IDE.mon;
    IDE.diffEd = m.editor.createDiffEditor($('#ide-diffhost'), {automaticLayout: true, readOnly: true, renderSideBySide: true, fontSize: 12.5});
    IDE.diffEd.setModel({original: m.editor.createModel(t.original || '', t.lang), modified: m.editor.createModel(t.modified || '', t.lang)});
    $('#ide-dclose').onclick = () => closeTab(t, true);
    if (t.onAccept) $('#ide-acc').onclick = async () => { await t.onAccept(); closeTab(t, true); };
  }

  // ------------------------------------------------------------------ sandbox: run, stream, stop
  function paintCmdHist() { $('#ide-cmdlist').innerHTML = IDE.hist.map(c => `<option value="${esc(c)}">`).join(''); }
  async function runCmd() {
    const cmd = $('#ide-cmd').value.trim();
    if (!cmd) return toast(T('Type a command, e.g. python train.py'), 'err');
    $('#ide-cmd').dataset.touched = 1;
    IDE.hist = [cmd, ...IDE.hist.filter(c => c !== cmd)].slice(0, 20); try { localStorage.setItem('ide_cmd_hist', JSON.stringify(IDE.hist)); } catch {} paintCmdHist();
    await saveAll();
    startJob(cmd, 'run');
  }
  async function startJob(cmd, kind) {
    await ensureTerm();
    try {
      const j = await api('/api/sandbox/run', {method: 'POST', body: {cmd, kind}});
      followJob(j);
    } catch (e) {
      const d = jsonErr(e);
      if (d && d.need_image) {
        if (confirm(`The sandbox image ${d.need_image} is not downloaded yet (PyTorch+CUDA images are several GB).\n\nDownload it now?`)) {
          const p = await api('/api/sandbox/pull', {method: 'POST', body: {image: d.need_image}});
          followJob(p, () => startJob(cmd, kind));
        }
        return;
      }
      IDE.term.writeln(`\x1b[31m✗ ${e.message}\x1b[0m`); toast(e.message, 'err');
    }
  }
  function followJob(j, onDone) {
    if (IDE.es) IDE.es.close();
    IDE.liveJob = j; IDE.series = {};
    $('#ide-stop').disabled = false; jobStatus(j);
    const es = new EventSource(`/api/sandbox/jobs/${j.id}/stream`);
    IDE.es = es;
    es.onmessage = ev => {
      const d = JSON.parse(ev.data);
      if (d.type === 'lines') d.lines.forEach(([s, t]) => termLine(s, t));
      else if (d.type === 'info') jobStatus(d.job);
      else if (d.type === 'end') { es.close(); IDE.es = null; jobStatus(d.job); $('#ide-stop').disabled = true; jobEnded(d.job); onDone && d.job.status === 'done' && onDone(); }
    };
    es.onerror = () => { es.close(); IDE.es = null; $('#ide-stop').disabled = true; };
  }
  function jobStatus(j) {
    const st = {running: '⏳', done: '✅', failed: '❌', stopped: '■'}[j.status] || '';
    $('#ide-jobst').textContent = `${st} ${j.title || j.cmd} · ${j.status}${j.duration != null ? ' · ' + j.duration + ' s' : ''}${j.mode ? ' · ' + j.mode : ''}`;
  }
  async function jobEnded(j) {
    loadTree(); refreshGit(); refreshOpenTabs();
    if (IDE.view === 'runs') runsView();
    if (j.kind === 'run' && j.status === 'done' && j.meta && Object.keys(j.meta.metrics || {}).length)
      toast(`${T('Run finished')} · ` + Object.entries(j.meta.metrics).slice(0, 4).map(([k, v]) => `${k}=${(+v).toPrecision(4)}`).join(' · '), 'ok');
    if (j.status === 'failed' && !IDE.agentBusy) offerFix(j);
  }
  function offerFix(j) {
    const box = $('#ide-cmsgs'); if (!box) return;
    const d = document.createElement('div'); d.className = 'evline err';
    d.innerHTML = `❌ ${esc(j.cmd)} — exit ${j.exit_code} <button class="btn small" style="margin-left:6px">✳ ${T('Ask the agent to fix it')}</button>`;
    d.querySelector('button').onclick = () => { $('#ide').classList.remove('nochat'); relayout(); sendAgent(`The command \`${j.cmd}\` failed (exit ${j.exit_code}). Read the error in the last run, fix the code and run it again.`, true); };
    box.append(d); box.scrollTop = box.scrollHeight;
  }
  async function stopJob() {
    if (!IDE.liveJob) return;
    try { await api(`/api/sandbox/jobs/${IDE.liveJob.id}/stop`, {method: 'POST'}); } catch (e) { toast(e.message, 'err'); }
  }
  async function ensureTerm() {
    if (IDE.term) return;
    const term = new Terminal({convertEol: true, fontSize: 12.5, fontFamily: "'IBM Plex Mono', Consolas, monospace", scrollback: 20000,
      theme: {background: '#0d1117', foreground: '#d6deeb'}, cursorBlink: false, disableStdin: true});
    const fit = new FitAddon.FitAddon(); term.loadAddon(fit);
    term.open($('#ide-term')); IDE.term = term; IDE.fit = fit; fitTerm();
    term.writeln('\x1b[90mPhD Research Lab sandbox terminal — output of runs, shell commands and the AI agent appears here.\x1b[0m');
  }
  function fitTerm() { try { IDE.fit && $('#ide-termwrap').offsetParent && IDE.fit.fit(); } catch {} }
  const KV = /([A-Za-z_][\w./-]{0,40})\s*[=:]\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\b/g;
  function termLine(stream, text) {
    if (!IDE.term) return;
    if (stream === 'err') IDE.term.writeln(`\x1b[31m${text}\x1b[0m`);
    else if (stream === 'sys') IDE.term.writeln(`\x1b[36m${text}\x1b[0m`);
    else IDE.term.writeln(text);
    if (stream === 'out' && text.length < 400) {   // live metrics: "epoch 3 loss=0.12 psnr=28.4"
      const pairs = [...text.matchAll(KV)].map(m => [m[1], +m[2]]);
      let step = (pairs.find(([k]) => /^(epoch|step|iter|iteration|ep)$/i.test(k)) || [])[1];
      const m0 = text.match(/^\s*(?:epoch|ep)\s+(\d+)/i); if (step == null && m0) step = +m0[1];
      if (step != null) pairs.forEach(([k, v]) => { if (!/^(epoch|step|iter|iteration|ep)$/i.test(k)) (IDE.series[k] = IDE.series[k] || []).push([step, v]); });
      if (step != null && !$('#ide-metrics').hidden) renderLiveMetrics();
    }
  }
  function lineChart(points, color = 'var(--accent2)', w = 320, h = 120) {
    if (!points.length) return '';
    const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const X = x => 30 + (x1 === x0 ? 0.5 : (x - x0) / (x1 - x0)) * (w - 40), Y = y => 8 + (y1 === y0 ? 0.5 : 1 - (y - y0) / (y1 - y0)) * (h - 26);
    const d = points.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
    return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:${w}px;height:auto"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.8"/>
      <text x="2" y="12" font-size="9" fill="currentColor" opacity=".6">${(+y1).toPrecision(4)}</text><text x="2" y="${h - 14}" font-size="9" fill="currentColor" opacity=".6">${(+y0).toPrecision(4)}</text>
      <text x="30" y="${h - 2}" font-size="9" fill="currentColor" opacity=".6">${x0}</text><text x="${w - 10}" y="${h - 2}" font-size="9" fill="currentColor" opacity=".6" text-anchor="end">${x1}</text></svg>`;
  }
  function renderLiveMetrics() {
    const keys = Object.keys(IDE.series);
    $('#ide-metrics').innerHTML = keys.length ? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px">${keys.map(k => {
      const s = IDE.series[k]; return `<div class="dcard"><h5>${esc(k)} <span style="margin-left:auto;color:var(--text)">${(+s[s.length - 1][1]).toPrecision(5)}</span></h5>${lineChart(s)}</div>`; }).join('')}</div>`
      : `<div class="empty">${T('Log lines like "epoch 3 loss=0.12 psnr=28.4" are plotted here live.')}</div>`;
  }

  // ------------------------------------------------------------------ runs view & run detail
  async function runsView() {
    const side = $('#ide-side');
    side.innerHTML = `<div class="sideh"><span>${T('Runs')}</span><button class="iconbtn" id="ide-rref" title="Refresh">↻</button></div><div class="sideb" id="ide-runs"></div>`;
    $('#ide-rref').onclick = runsView;
    try {
      const {runs, best} = await api('/api/sandbox/runs');
      $('#ide-runs').innerHTML = (Object.keys(best).length ? `<div style="padding:6px 10px;font-size:11.5px;color:var(--muted)">🏆 ${Object.entries(best).slice(0, 5).map(([k, v]) => `${esc(k)}=${(+v.value).toPrecision(4)}`).join(' · ')}</div>` : '')
        + (runs.map(r => `<div class="fi" data-r="${esc(r.id)}" style="display:block;padding:5px 10px;cursor:pointer;border-bottom:1px solid var(--line)">
          <div style="display:flex;gap:6px;align-items:center"><span class="st ${r.status}">${esc(T(r.status || ''))}</span><span style="font-family:var(--mono);font-size:11px;color:var(--muted)">${esc(r.id)}</span></div>
          <div style="font-family:var(--mono);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(r.cmd || '')}</div>
          <div style="font-size:11px;color:var(--muted)">${r.duration != null ? r.duration + ' s · ' : ''}${Object.entries(r.metrics || {}).slice(0, 3).map(([k, v]) => `${esc(k)}=${(+v).toPrecision(4)}`).join(' · ')}${(r.figures || []).length ? ` · 🖼 ${r.figures.length}` : ''}</div></div>`).join('')
        || `<div class="empty">${T('No runs yet. ▶ Run a script.')}</div>`);
      $$('#ide-runs [data-r]').forEach(el => el.onclick = () => openRun(el.dataset.r));
    } catch (e) { $('#ide-runs').innerHTML = `<div class="empty">⚠ ${esc(e.message)}</div>`; }
  }
  async function openRun(id) {
    let t = IDE.tabs.find(x => x.kind === 'run' && x.id === id);
    if (!t) { t = {kind: 'run', id, title: id.slice(-9)}; IDE.tabs.push(t); }
    activate(t);
  }
  async function renderRun(t) {
    const pane = $('#ide-pane'); pane.innerHTML = '<div class="empty">…</div>';
    let r; try { r = await api('/api/sandbox/runs/' + t.id); } catch (e) { pane.innerHTML = `<div class="empty">⚠ ${esc(e.message)}</div>`; return; }
    const series = (r.parsed || {}).series || {};
    pane.innerHTML = `<h3 style="margin:0 0 4px;font-family:var(--serif)">📈 ${esc(r.id)} <span class="st ${r.status}">${esc(T(r.status || ''))}</span></h3>
      <div class="status" style="font-family:var(--mono)">$ ${esc(r.cmd || '')} · ${esc(r.mode || '')} · exit ${r.exit_code} · ${r.duration ?? '?'} s</div>
      <div class="row" style="gap:6px;margin:10px 0"><button class="btn small" id="rr-rerun">↻ ${T('Run again')}</button><button class="btn small" id="rr-paper">→ ${T('Use results in the paper')}</button>
        <button class="btn small" id="rr-agent">✳ ${T('Discuss with the agent')}</button></div>
      ${Object.keys(r.metrics || {}).length ? `<h4>${T('Metrics')} <span class="status">${esc(r.metrics_source || '')}</span></h4><table class="dtable" style="max-width:560px">${Object.entries(r.metrics).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono">${esc(String(v))}</td></tr>`).join('')}</table>` : ''}
      ${Object.keys(series).length ? `<h4>${T('Curves')}</h4><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">${Object.entries(series).map(([k, s]) => `<div class="dcard"><h5>${esc(k)}</h5>${lineChart(s)}</div>`).join('')}</div>` : ''}
      ${(r.figures || []).length ? `<h4>${T('Figures')}</h4><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px">${r.figures.map(f => /\.pdf$/i.test(f)
        ? `<a class="btn small" target="_blank" href="/api/sandbox/runs/${encodeURIComponent(r.id)}/file?path=${encodeURIComponent(f)}">📕 ${esc(f)}</a>`
        : `<a target="_blank" href="/api/sandbox/runs/${encodeURIComponent(r.id)}/file?path=${encodeURIComponent(f)}"><img src="/api/sandbox/runs/${encodeURIComponent(r.id)}/file?path=${encodeURIComponent(f)}" style="width:100%;border-radius:8px;background:#fff;border:1px solid var(--line)"></a>`).join('')}</div>` : ''}
      ${r.stderr ? `<h4>stderr</h4><pre class="joblog e">${esc(r.stderr.slice(-8000))}</pre>` : ''}
      <h4>stdout</h4><pre class="joblog">${esc((r.stdout || '').slice(-20000)) || '(empty)'}</pre>`;
    $('#rr-rerun').onclick = () => { $('#ide-cmd').value = r.cmd; runCmd(); };
    $('#rr-paper').onclick = async () => {
      try { await api('/api/paper/import-results', {method: 'POST', body: {run_ids: [r.id]}}); toast(T('Results and a LaTeX table were added to the Paper Writer'), 'ok'); } catch (e) { toast(e.message, 'err'); }
    };
    $('#rr-agent').onclick = () => { $('#ide').classList.remove('nochat'); relayout(); $('#ide-cin').value = `Analyse run ${r.id} (${r.status}, metrics ${JSON.stringify(r.metrics || {})}). What should I try next?`; $('#ide-cin').focus(); };
  }

  // ------------------------------------------------------------------ source control / GitHub
  async function refreshGit(quiet) {
    try { IDE.git = await api('/api/git/status'); } catch (e) { if (!quiet) toast(e.message, 'err'); return; }
    const n = (IDE.git.files || []).length, b = $('#ide-scmbdg');
    if (b) { b.hidden = !n; b.textContent = n > 99 ? '99+' : n; }
    if (IDE.view === 'explorer') renderTree();
    if (IDE.view === 'scm') paintScm();
  }
  async function scmView() {
    $('#ide-side').innerHTML = `<div class="sideh"><span>${T('Source Control')}</span><button class="iconbtn" id="scm-ref" title="Refresh">↻</button></div><div class="sideb" id="scm-body" style="padding:8px 10px"></div>`;
    $('#scm-ref').onclick = () => refreshGit();
    await refreshGit(true); paintScm();
  }
  function paintScm() {
    const g = IDE.git || {}, box = $('#scm-body'); if (!box) return;
    const gh = (typeof CFG !== "undefined" && CFG && CFG.github) || {};
    if (!g.git) { box.innerHTML = `<div class="empty" style="padding:12px 4px">${T('Git is not installed.')}<br><a href="https://git-scm.com/download/win" target="_blank" rel="noopener">Git for Windows ↗</a></div>`; return; }
    if (!g.repo) { box.innerHTML = `<p class="status">${T('The workspace is not a Git repository yet.')}</p><button class="btn primary" id="scm-init" style="width:100%">⑂ ${T('Initialize repository')}</button>`; $('#scm-init').onclick = async () => { try { IDE.git = await api('/api/git/init', {method: 'POST'}); paintScm(); renderTree(); } catch (e) { toast(e.message, 'err'); } }; return; }
    box.innerHTML = `<div class="status" style="margin:0 0 6px">⑂ ${esc(g.branch || 'main')}${g.remote ? ` · <a href="${esc(g.remote.replace(/\.git$/, ''))}" target="_blank" rel="noopener">${esc(g.remote.replace(/^https:\/\/github.com\//, '').replace(/\.git$/, ''))}</a>` : ''}${g.ahead ? ` · ↑${g.ahead}` : ''}${g.behind ? ` · ↓${g.behind}` : ''}</div>
      <textarea id="scm-msg" rows="3" placeholder="${esc(T('Commit message (Ctrl+Enter to commit)'))}"></textarea>
      <div class="row" style="margin:6px 0;gap:6px"><button class="btn small primary" id="scm-commit" style="flex:1">✓ ${T('Commit')}${g.files.length ? ` (${g.files.length})` : ''}</button>
        ${g.remote ? `<button class="btn small" id="scm-push" title="Push">↑ ${T('Push')}</button><button class="btn small" id="scm-pull" title="Pull">↓</button>` : ''}</div>
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin:10px 0 4px">${T('Changes')}</div>
      <div id="scm-files">${g.files.map((f, i) => `<div class="fi" data-i="${i}" style="padding:3px 4px;display:flex;gap:6px;cursor:pointer"><input type="checkbox" data-c="${i}" checked><span class="nm" style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(f.path)}</span><span class="gs ${f.status === 'untracked' ? 'U' : f.status === 'deleted' ? 'D' : f.status === 'added' ? 'A' : 'M'}">${f.status === 'untracked' ? 'U' : f.status[0].toUpperCase()}</span></div>`).join('') || `<div class="status">${T('No changes')}</div>`}</div>
      <details style="margin-top:12px" ${g.remote ? '' : 'open'}><summary style="cursor:pointer;font-weight:600;font-size:13px">🚀 ${T('Publish to GitHub')}</summary>
        <label>${T('Repository name')}</label><input type="text" id="scm-repo" value="${esc((($('#proj-tag') || {}).textContent || 'research-code').replace(/^📂\s*/, '').trim().toLowerCase().replace(/[^a-z0-9._-]+/g, '-'))}">
        <label>${T('Description')}</label><input type="text" id="scm-desc" placeholder="${esc(T('Code for my PhD research project'))}">
        <label class="chk"><input type="checkbox" id="scm-private" checked> 🔒 ${T('Private repository')}</label>
        <button class="btn primary" id="scm-publish" style="width:100%;margin-top:8px">🚀 ${T('Publish to GitHub')}</button><div class="status" id="scm-pubst"></div></details>
      <details style="margin-top:10px" ${gh.has_token ? '' : 'open'}><summary style="cursor:pointer;font-weight:600;font-size:13px">⚙ ${T('GitHub settings')} ${gh.has_token ? '✓' : ''}</summary>
        <label>${T('Personal Access Token')} <a href="https://github.com/settings/tokens?type=beta" target="_blank" rel="noopener" style="font-size:11px">${T('create ↗')}</a></label>
        <input type="password" id="gh-token" value="${esc(gh.token || '')}" placeholder="github_pat_…" autocomplete="off">
        <div class="row" style="gap:6px"><div><label>${T('Commit name')}</label><input type="text" id="gh-name" value="${esc(gh.name || '')}"></div><div><label>E-mail</label><input type="text" id="gh-email" value="${esc(gh.email || '')}"></div></div>
        <div class="row" style="margin-top:6px;gap:6px"><button class="btn small" id="gh-save">💾 ${T('Save')}</button><button class="btn small" id="gh-test">${T('Test token')}</button></div>
        <div class="status">${T('The token is stored only in data/config.json and sent only to GitHub. It is never written into .git/config.')}</div></details>
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin:14px 0 4px">${T('History')}</div>
      ${(g.commits || []).map(c => `<div style="font-size:12px;padding:3px 0;border-bottom:1px dashed var(--line)"><span style="font-family:var(--mono);color:var(--accent2)">${esc(c.hash)}</span> ${esc(c.message)}<div class="status" style="margin:0">${esc(c.author)} · ${esc(c.when)}</div></div>`).join('') || `<div class="status">${T('No commits yet')}</div>`}`;
    const files = g.files;
    $$('#scm-files .fi').forEach(el => el.onclick = async e => {
      if (e.target.matches('input')) return;
      const f = files[el.dataset.i];
      try { const d = await api('/api/git/diff?path=' + encodeURIComponent(f.path)); openDiff(`${f.path} (HEAD ↔ ${T('working tree')})`, d.original, d.modified, langOf(f.path)); } catch (err) { toast(err.message, 'err'); }
    });
    const commit = async () => {
      const paths = files.filter((_, i) => $(`#scm-files [data-c="${i}"]`)?.checked).map(f => f.path);
      try { await saveAll(); IDE.git = await api('/api/git/commit', {method: 'POST', body: {message: $('#scm-msg').value, paths: paths.length === files.length ? null : paths}}); toast(T('Committed'), 'ok'); paintScm(); renderTree(); }
      catch (err) { toast(err.message, 'err'); }
    };
    $('#scm-commit').onclick = commit;
    $('#scm-msg').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) commit(); });
    $('#scm-push') && ($('#scm-push').onclick = e => busy(e.target, async () => { IDE.git = await api('/api/git/push', {method: 'POST'}); toast(T('Pushed to GitHub'), 'ok'); paintScm(); }, '…'));
    $('#scm-pull') && ($('#scm-pull').onclick = e => busy(e.target, async () => { IDE.git = await api('/api/git/pull', {method: 'POST'}); toast(T('Pulled'), 'ok'); paintScm(); loadTree(); refreshOpenTabs(); }, '…'));
    $('#scm-publish').onclick = e => busy(e.target, async () => {
      await saveAll();
      const r = await api('/api/git/publish', {method: 'POST', body: {repo: $('#scm-repo').value, private: $('#scm-private').checked, description: $('#scm-desc').value}});
      IDE.git = r.status; paintScm();
      $('#scm-pubst').innerHTML = `✓ <a href="${esc(r.html_url)}" target="_blank" rel="noopener">${esc(r.html_url)}</a> (${r.private ? T('private') : T('public')})`;
      toast(T('Published to GitHub'), 'ok');
    }, T('Publishing…'));
    const saveGh = async () => { await api('/api/config', {method: 'POST', body: {github: {token: $('#gh-token').value, name: $('#gh-name').value, email: $('#gh-email').value}}}); CFG = await api('/api/config'); };
    $('#gh-save').onclick = e => busy(e.target, async () => { await saveGh(); toast(T('GitHub settings saved'), 'ok'); paintScm(); }, '…');
    $('#gh-test').onclick = e => busy(e.target, async () => { await saveGh(); const u = await api('/api/git/user'); await api('/api/config', {method: 'POST', body: {github: {user: u.login}}}); toast(`✓ ${u.login}${u.name ? ' (' + u.name + ')' : ''}`, 'ok'); }, '…');
  }

  // ------------------------------------------------------------------ AI co-coding agent
  function buildChat() {
    try { IDE.chat = JSON.parse(localStorage.getItem('ide_chat_' + projKey()) || '[]'); IDE.sid = localStorage.getItem('ide_sid_' + projKey()) || null; } catch {}
    $('#ide-chat').innerHTML = `<div class="chath"><div class="row1"><b>✳ ${T('Co-coding agent')}</b><span class="rtbadge" data-agent="coder" title="Engine / model of this agent — click to change"></span></div>
      <div class="row1"><select id="ide-amode" title="Suggest: review changes before applying. Auto: apply, run and self-debug.">
        <option value="suggest">${T('💡 Suggest (review changes)')}</option><option value="auto">${T('⚡ Auto: apply → run → self-debug')}</option></select>
        <label title="Maximum self-debugging attempts">${T('tries')} <select id="ide-aiter"><option>2</option><option>3</option><option selected>4</option><option>6</option><option>8</option></select></label>
        <span style="flex:1"></span><button class="iconbtn" id="ide-cclear" title="New conversation">🧹</button></div></div>
      <div class="cmsgs" id="ide-cmsgs"></div>
      <div class="ccomp"><textarea id="ide-cin" rows="3" placeholder="${esc(T('Ask the agent: implement, refactor, explain, fix… (Enter to send)'))}"></textarea>
        <div class="row" style="gap:6px;flex-wrap:wrap"><button class="chip" style="white-space:nowrap" data-q="smoke">${T('Smoke test')}</button><button class="chip" style="white-space:nowrap" data-q="explain">${T('Explain file')}</button><button class="chip" style="white-space:nowrap" data-q="metrics">${T('Add metrics output')}</button>
          <span style="flex:1"></span><button class="sendbtn" id="ide-csend" title="Send">↑</button></div></div>`;
    try { $('#ide-amode').value = localStorage.getItem('ide_amode') || 'suggest'; } catch {}
    $('#ide-amode').onchange = e => { try { localStorage.setItem('ide_amode', e.target.value); } catch {} };
    $('#ide-csend').onclick = () => IDE.agentBusy ? stopAgent() : sendAgent();
    $('#ide-cin').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!IDE.agentBusy) sendAgent(); } });
    $('#ide-cclear').onclick = () => { if (IDE.agentBusy) return; IDE.chat = []; IDE.sid = null; persistChat(); renderChat(); };
    $$('#ide-chat [data-q]').forEach(b => b.onclick = () => {
      const f = IDE.cur && IDE.cur.kind === 'file' ? IDE.cur.path : '';
      const q = {smoke: `Run a quick smoke test of ${f || 'the project'} (tiny data, 1-2 epochs) and fix any error.`,
        explain: `Explain ${f || 'the open file'} step by step: what it does, inputs/outputs, and any bug or weakness you see.`,
        metrics: `Make ${f || 'the training script'} write its final metrics to $RUN_DIR/metrics.json and log "epoch N key=value" lines.`}[b.dataset.q];
      $('#ide-cin').value = q; $('#ide-cin').focus();
    });
    renderChat();
    window.refreshRuntimeBadges && refreshRuntimeBadges();
  }
  function projKey() { return ((typeof CFG !== "undefined" && CFG && CFG.project && CFG.project.data_dir) || 'default').replace(/[^\w]/g, '').slice(-40); }
  function persistChat() { try { localStorage.setItem('ide_chat_' + projKey(), JSON.stringify(IDE.chat.slice(-60))); IDE.sid ? localStorage.setItem('ide_sid_' + projKey(), IDE.sid) : localStorage.removeItem('ide_sid_' + projKey()); } catch {} }
  function renderChat() {
    const box = $('#ide-cmsgs');
    box.innerHTML = IDE.chat.length ? IDE.chat.map((m, i) => m.role === 'user'
      ? `<div class="cmsg user"><div class="ububble">${esc(m.content)}</div></div>`
      : `<div class="cmsg ai" data-i="${i}"><div class="md"></div>${(m.events || []).map(ev => `<div class="evline ${ev.c || ''}">${esc(ev.t)}</div>`).join('')}<div class="props"></div></div>`).join('')
      : `<div class="emptystate"><div class="avatar big">✳</div>${T('Pair-program with the AI. In ⚡ Auto mode it applies its changes, runs them in the sandbox and fixes errors from stderr until the run succeeds.')}</div>`;
    box.querySelectorAll('.cmsg.ai').forEach(el => {
      const m = IDE.chat[el.dataset.i]; setRich(el.querySelector('.md'), m.content || '');
      (m.proposals || []).forEach(p => el.querySelector('.props').append(proposalCard(p, m)));
    });
    box.scrollTop = box.scrollHeight;
  }
  function proposalCard(p, msg) {
    const d = document.createElement('div');
    const applied = p.applied;
    d.innerHTML = (p.files || []).map((f, i) => `<div class="prop"><div class="ph"><span>${f.exists ? '✎' : '＋'}</span><b title="${esc(f.path)}">${esc(f.path)}</b><span class="add">+${f.added}</span><span class="rem">−${f.removed}</span></div>
        <div class="pa"><button class="iconbtn" data-diff="${i}">⇄ ${T('Diff')}</button>${applied ? `<span class="status" style="margin:0 6px">✓ ${T('applied')}</span>` : `<button class="iconbtn" data-apply="${i}">✓ ${T('Apply')}</button>`}<button class="iconbtn" data-open="${i}">↗ ${T('Open file')}</button></div></div>`).join('')
      + ((p.files || []).length || p.run ? `<div class="row" style="gap:6px;margin:4px 0">${!applied && (p.files || []).length ? `<button class="btn small primary" data-all>✓ ${T('Apply all')}</button>` : ''}
        ${p.run ? `<button class="btn small" data-run>▶ ${applied || !(p.files || []).length ? '' : T('Apply & ')}${T('Run')} <code style="font-size:11px">${esc(p.run.slice(0, 50))}</code></button>` : ''}</div>` : '');
    const applyFiles = async files => { await api('/api/ide/apply', {method: 'POST', body: {files}}); await loadTree(); await refreshOpenTabs(files.map(f => f.path)); refreshGit(); };
    d.querySelectorAll('[data-diff]').forEach(b => b.onclick = () => { const f = p.files[b.dataset.diff];
      openDiff(`${f.path} (${T('current')} ↔ ${T('proposed')})`, f.old, f.content, langOf(f.path), applied ? null : async () => { await applyFiles([f]); toast(`✓ ${f.path}`, 'ok'); }); });
    d.querySelectorAll('[data-apply]').forEach(b => b.onclick = async () => { const f = p.files[b.dataset.apply]; try { await applyFiles([f]); b.outerHTML = `<span class="status" style="margin:0 6px">✓ ${T('applied')}</span>`; } catch (e) { toast(e.message, 'err'); } });
    d.querySelectorAll('[data-open]').forEach(b => b.onclick = () => openFile(p.files[b.dataset.open].path));
    const all = d.querySelector('[data-all]');
    if (all) all.onclick = async () => { try { await applyFiles(p.files); p.applied = true; persistChat(); renderChat(); toast(T('Changes applied'), 'ok'); } catch (e) { toast(e.message, 'err'); } };
    const run = d.querySelector('[data-run]');
    if (run) run.onclick = async () => { try { if (!p.applied && (p.files || []).length) { await applyFiles(p.files); p.applied = true; persistChat(); } $('#ide-cmd').value = p.run; runCmd(); renderChat(); } catch (e) { toast(e.message, 'err'); } };
    return d;
  }
  function stopAgent() { if (IDE.ctrl) IDE.ctrl.abort(); }
  function setAgentBusy(on) {
    IDE.agentBusy = on; const b = $('#ide-csend'); b.classList.toggle('stop', on); b.textContent = on ? '■' : '↑'; b.title = on ? T('Stop the agent (and its run)') : T('Send');
  }
  async function sendAgent(text, forceAuto) {
    const q = (text || $('#ide-cin').value).trim(); if (!q) return;
    $('#ide-cin').value = '';
    await saveAll();
    IDE.chat.push({role: 'user', content: q});
    const ai = {role: 'assistant', content: '', events: [], proposals: []};
    IDE.chat.push(ai); renderChat();
    const el = $('#ide-cmsgs').lastElementChild, mdEl = el.querySelector('.md');
    mdEl.innerHTML = '<span class="thinking">Thinking<span>.</span><span>.</span><span>.</span></span>';
    const auto = forceAuto || $('#ide-amode').value === 'auto';
    setAgentBusy(true); IDE.ctrl = new AbortController();
    let cur = '', paintT = null;
    const paint = () => { paintT = null; mdEl.innerHTML = md(ai.content + cur) + '<span class="cursor"></span>'; $('#ide-cmsgs').scrollTop = $('#ide-cmsgs').scrollHeight; };
    const ev = (t, c) => { ai.events.push({t, c}); const d = document.createElement('div'); d.className = 'evline ' + (c || ''); d.textContent = t; el.insertBefore(d, el.querySelector('.props')); $('#ide-cmsgs').scrollTop = $('#ide-cmsgs').scrollHeight; };
    try {
      await ensureTerm();
      const hist = IDE.chat.slice(0, -1).filter(m => m.content).map(m => ({role: m.role, content: m.content}));
      const resp = await fetch('/api/ide/agent', {method: 'POST', signal: IDE.ctrl.signal, headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({messages: hist.slice(-24), auto, max_iters: +$('#ide-aiter').value, open_file: IDE.cur && IDE.cur.kind === 'file' ? IDE.cur.path : '', session_id: IDE.sid})});
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || 'HTTP ' + resp.status);
      const reader = resp.body.getReader(), dec = new TextDecoder(); let buf = '';
      for (;;) {
        const {value, done} = await reader.read(); if (done) break;
        buf += dec.decode(value, {stream: true}); let k;
        while ((k = buf.indexOf('\n\n')) >= 0) {
          const line = buf.slice(0, k).trim(); buf = buf.slice(k + 2);
          if (!line.startsWith('data:')) continue;
          const d = JSON.parse(line.slice(5));
          if (d.type === 'start') { IDE.sid = d.session_id; }
          else if (d.type === 'iter' && d.n > 1) { ai.content += cur + `\n\n---\n**${T('Attempt')} ${d.n}**\n\n`; cur = ''; }
          else if (d.type === 'delta') { cur += d.text; if (!paintT) paintT = setTimeout(paint, 60); }
          else if (d.type === 'proposal') {
            ai.content += cur; cur = '';
            const prop = {files: d.files, run: d.run, applied: auto};
            ai.proposals.push(prop); clearTimeout(paintT); paintT = null; setRich(mdEl, ai.content);
            el.querySelector('.props').append(proposalCard(prop, ai));
            if (d.note) ev('⚠ ' + d.note, 'err');
            if (!d.files.length && !d.run && auto) ev(T('(no file changes or command proposed)'));
          }
          else if (d.type === 'applied') { ev(`✓ ${T('applied')}: ${d.paths.join(', ')}`, 'ok'); loadTree(); refreshOpenTabs(d.paths); refreshGit(); }
          else if (d.type === 'run_start') { ev(`▶ ${d.job.cmd}`, 'run'); IDE.liveJob = d.job; IDE.series = {}; $('#ide-stop').disabled = false; jobStatus(d.job); termLine('sys', `── agent run ${d.job.id} ──`); }
          else if (d.type === 'run_lines') d.lines.forEach(([s, t]) => termLine(s, t));
          else if (d.type === 'run_end') { const j = d.job; jobStatus(j); $('#ide-stop').disabled = true;
            ev(`${j.status === 'done' ? '✅' : j.status === 'stopped' ? '■' : '❌'} ${j.cmd} → ${T(j.status)} (exit ${j.exit_code}, ${j.duration} s)${j.meta && j.meta.metrics && Object.keys(j.meta.metrics).length ? ' · ' + Object.entries(j.meta.metrics).slice(0, 3).map(([k, v]) => `${k}=${(+v).toPrecision(4)}`).join(' ') : ''}`, j.status === 'done' ? 'ok' : 'err');
            loadTree(); }
          else if (d.type === 'gave_up') ev(`⚠ ${T('Stopped after')} ${d.n} ${T('attempts — read the error and guide the agent.')}`, 'err');
          else if (d.type === 'done') { ai.content = (ai.content + cur).trim() || d.reply; cur = ''; }
          else if (d.type === 'error') { ev('⚠ ' + d.detail, 'err'); }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') { ev('■ ' + T('Stopped by user'), 'err'); if (IDE.liveJob && IDE.liveJob.status === 'running') stopJob(); }
      else ev('⚠ ' + e.message, 'err');
    }
    ai.content = (ai.content + cur).trim();
    clearTimeout(paintT); IDE.ctrl = null; setAgentBusy(false); persistChat(); renderChat();
  }

  // ------------------------------------------------------------------ sandbox status in the editor bar
  async function refreshMode() {
    try {
      const s = await api('/api/sandbox/status?full=0'); IDE.status = s;
      const c = s.container || {};
      $('#ide-mode').innerHTML = s.mode === 'docker'
        ? `🐳 docker · ${esc(s.image)}${c.running ? ` · <span class="led ok"></span> ${T('container up')}` : ` · <span class="led warn"></span> ${T('starts on first run')}`}${c.gpu || (!c.exists && s.settings.gpu) ? ' · GPU' : ''}`
        : `🐍 ${T('local venv')}${s.docker_installed && !s.docker_running ? ` · <span class="led warn"></span> ${T('Docker not running')}` : ''}`;
    } catch {}
  }

  // ------------------------------------------------------------------ init
  async function init() {
    if (IDE.inited) { relayout(); refreshMode(); return; }
    IDE.inited = true;
    build();
    refreshMode();
    setInterval(() => { if (root().classList.contains('on')) refreshMode(); }, 15000);
    try { await loadMonaco(); } catch (e) { toast('Monaco: ' + e.message, 'err'); }
    ensureTerm();
  }
  window.addEventListener('tab-shown', e => { if (e.detail === 'ide') init(); });
  window.IDE_API = {openFile, init, sendAgent, state: IDE};
})();
