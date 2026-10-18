/* PhD Research Lab v3.1 — writing brief per paper section (Paper Writer → 🎯 Brief)
 * Directions (the existing #sec-notes box) + results to present (from uploads, Code IDE runs, Writer tables) with how to
 * present each one + required structure + must include / must avoid + tone & length + references to emphasise.
 * Plus a paper-wide brief (story, style, terminology, never-do) applied to every section.
 * The brief is sent to the Author (3.2), the Editor (3.4) and the section Reviewer (3.3) on every run.
 */
(function () {
  const T = s => (window.I18N ? I18N.tr(s) : s);
  const B = {sec: null, brief: null, summary: {}, paper: null, catalog: null, timer: null, stale: new Set(), paperReady: false};
  const TONES = [['', 'Default'], ['concise', 'Concise'], ['detailed', 'Detailed'], ['persuasive', 'Persuasive'], ['cautious', 'Cautious / hedged'],
    ['tutorial', 'Didactic'], ['formal', 'Strictly formal']];
  const LENGTHS = [['', 'Default'], ['short', 'Short'], ['standard', 'Standard'], ['long', 'Long / in depth']];
  const SUGGEST = {
    _: ['Emphasise the novelty of our method', 'Compare explicitly with the strongest baselines', 'Keep it concise — no filler', 'Define every symbol on first use'],
    abstract: ['Include the headline quantitative result', 'One sentence each: problem, gap, method, result, impact'],
    introduction: ['Open with the real-world motivation', 'End with a bullet list of 3 contributions', 'State the research gap explicitly'],
    related_work: ['Group prior work by approach; end each group with how we differ', 'Be fair to competing methods'],
    methodology: ['Start with a formal problem statement', 'Explain the intuition before the equations', 'Add a complexity analysis'],
    experiments: ['Report mean ± std over repeated runs', 'Add an ablation study paragraph', 'Discuss failure cases honestly', 'Describe the implementation details for reproducibility'],
    discussion: ['Explain why the method works', 'Discuss limitations and threats to validity honestly'],
    conclusion: ['Summarise the findings with the key numbers', 'End with 2 concrete future directions'],
  };
  const empty = () => ({must: [], avoid: [], outline: [], tone: '', length: '', words: 0, cite: [], results: [], results_only: true});

  // ------------------------------------------------------------------ data
  async function load(sec) {
    if (!sec) return;
    const changed = B.sec !== sec;
    B.sec = sec;
    if (!changed && B.brief && !B.stale.has(sec)) { renderLine(); return; }
    try {
      const d = await api('/api/paper/brief?section=' + encodeURIComponent(sec));
      if (B.sec !== sec) return;
      B.brief = {...empty(), ...d.brief}; B.summary = d.summary; B.paper = d.paper_brief; B.stale.delete(sec);
      render(); renderPaper(); renderLine(); decorateBoard();
    } catch (e) { toast(e.message, 'err'); }
  }
  function invalidate(sec) { B.stale.add(sec); B.sumFetched = false; if (sec === B.sec) load(sec); else decorateBoard(); }

  function save(now) {
    clearTimeout(B.timer);
    const run = async () => {
      if (!B.sec || !B.brief) return;
      const {directions, ...structured} = B.brief;      // directions are saved by the #sec-notes box itself
      try {
        const r = await api('/api/paper/brief', {method: 'PUT', body: {section: B.sec, brief: structured}});
        B.brief = {...empty(), ...r.brief};
        const s = (await api('/api/paper/brief')).summary; B.summary = s;
        renderLine(); decorateBoard();
      } catch (e) { toast(e.message, 'err'); }
    };
    if (now) return run();
    B.timer = setTimeout(run, 450);
  }

  // ------------------------------------------------------------------ UI pieces
  function listEditor(key, placeholder, ordered) {
    const items = B.brief[key];
    return `<div class="blist" data-list="${key}">${items.map((x, i) => `<div class="bi">${ordered ? `<span class="n">${i + 1}.</span>` : '<span class="n">•</span>'}
        <input type="text" value="${esc(x)}" data-i="${i}">
        ${ordered ? `<button class="iconbtn" data-up="${i}" title="${esc(T('Move up'))}" ${i ? '' : 'disabled'}>↑</button><button class="iconbtn" data-down="${i}" title="${esc(T('Move down'))}" ${i < items.length - 1 ? '' : 'disabled'}>↓</button>` : ''}
        <button class="iconbtn" data-del="${i}" title="${esc(T('Remove'))}">✕</button></div>`).join('')}</div>
      <div class="badd" data-add="${key}"><input type="text" placeholder="${esc(T(placeholder))}"><button class="btn small">＋</button></div>`;
  }

  function resultsEditor() {
    const ICON = (window.RESULTS_API && RESULTS_API.ICON) || {};
    const PRESENT = (window.RESULTS_API && RESULTS_API.PRESENT) || [['auto', 'Auto']];
    const rs = B.brief.results;
    return `<div class="bres">${rs.map((r, i) => {
      const up = r.ref.startsWith('up:') ? r.ref.slice(3) : null;
      const runfig = r.ref.startsWith('runfig:') ? r.ref.slice(7) : null;
      const thumb = r.thumb || (up && /figure/.test(r.kind || '') ? `/api/results/${up}/file` : '') ||
        (runfig && /\.(png|jpe?g|gif|webp|svg)$/i.test(runfig) ? `/api/sandbox/runs/${runfig.split('/')[0]}/file?path=figures/${runfig.split('/').slice(1).join('/')}` : '');
      return `<div class="bresrow" data-i="${i}">
        <span class="rn">R${i + 1}</span>
        <div class="pthumb">${thumb ? `<img src="${esc(thumb)}" alt="" onerror="this.replaceWith(document.createTextNode('${ICON[r.kind] || '📊'}'))">` : (ICON[r.kind] || (r.ref.startsWith('run:') ? '💻' : r.ref.startsWith('table:') ? '▦' : '📊'))}</div>
        <div><div class="t">${esc(r.title || r.ref)}${r.missing ? ` <span class="reswarn">⚠ ${T('no longer available — remove it')}</span>` : ''}</div>
          <input type="text" data-note="${i}" value="${esc(r.note || '')}" placeholder="${esc(T('How to present / what to emphasise, e.g. highlight the +1.2 dB over QRNN3D'))}"></div>
        <select data-as="${i}" title="${esc(T('Present as'))}">${PRESENT.map(([v, t]) => `<option value="${v}" ${v === r.as ? 'selected' : ''}>${T(t)}</option>`).join('')}</select>
        <div class="acts">${up ? `<button class="iconbtn" data-view="${up}" title="${esc(T('View'))}">👁</button>` : ''}
          <button class="iconbtn" data-rup="${i}" ${i ? '' : 'disabled'} title="${esc(T('Move up'))}">↑</button><button class="iconbtn" data-rdown="${i}" ${i < rs.length - 1 ? '' : 'disabled'} title="${esc(T('Move down'))}">↓</button>
          <button class="iconbtn" data-rdel="${i}" title="${esc(T('Remove'))}">✕</button></div>
      </div>`;
    }).join('') || `<div class="status">${T('No results selected — the AI uses the Results notes and LaTeX tables of the Paper project, and writes [TBD] placeholders for missing numbers.')}</div>`}</div>
      <div class="bfoot"><button class="btn small primary" id="br-pick">＋ ${T('Choose results…')}</button>
        <label class="chk" style="margin:0"><input type="checkbox" id="br-only" ${B.brief.results_only ? 'checked' : ''}> ${T('Present only the selected results in this section')}</label></div>`;
  }

  function citeEditor() {
    const cat = B.catalog || [];
    if (!cat.length) return `<div class="status">${T('No references in the library yet (① Reference Library).')}</div>`;
    return `<div class="bkeys">${cat.map(p => `<span class="kk ${B.brief.cite.includes(p.key) ? 'on' : ''}" data-key="${esc(p.key)}" title="${esc((p.title || '') + (p.year ? ' (' + p.year + ')' : ''))}">${esc(p.key)}</span>`).join('')}</div>`;
  }

  function render() {
    const host = document.getElementById('brief-host');
    if (!host || !B.brief) return;
    const b = B.brief, sec = B.sec;
    const chips = [...(SUGGEST[sec] || []), ...SUGGEST._];
    host.innerHTML = `
      <div class="bchips">${chips.map(c => `<button class="chip" data-sugg="${esc(c)}" title="${esc(T('Add to the directions'))}">＋ ${esc(T(c))}</button>`).join('')}</div>
      <div class="bsec"><h5>📊 ${T('Results to present')} <span class="status">— ${T('pick what this section shows and how; uploads (Experiment Design), Code IDE runs and figures, Writer tables')}</span></h5>${resultsEditor()}</div>
      <div class="bsec"><h5>🧱 ${T('Structure (optional)')} <span class="status">— ${T('one paragraph or subsection per line, in order')}</span></h5>${listEditor('outline', 'e.g. Datasets and metrics', true)}</div>
      <div class="bgrid">
        <div class="bsec"><h5>✅ ${T('Must include')}</h5>${listEditor('must', 'e.g. the 2 W power budget')}</div>
        <div class="bsec"><h5>⛔ ${T('Must avoid')}</h5>${listEditor('avoid', 'e.g. claiming real-time performance')}</div>
      </div>
      <div class="bsec"><h5>🎚 ${T('Tone & length')}</h5>
        <div class="row" style="gap:8px;flex-wrap:wrap">
          <div style="flex:1;min-width:150px"><label style="margin-top:0">${T('Tone')}</label><select id="br-tone">${TONES.map(([v, t]) => `<option value="${v}" ${v === b.tone ? 'selected' : ''}>${T(t)}</option>`).join('')}</select></div>
          <div style="flex:1;min-width:150px"><label style="margin-top:0">${T('Length')}</label><select id="br-len">${LENGTHS.map(([v, t]) => `<option value="${v}" ${v === b.length ? 'selected' : ''}>${T(t)}</option>`).join('')}</select></div>
          <div style="flex:0 0 150px"><label style="margin-top:0">${T('or ≈ words')}</label><input type="text" id="br-words" value="${b.words || ''}" placeholder="—"></div>
        </div></div>
      <div class="bsec"><h5>📚 ${T('References to emphasise')} <span class="status">— ${T('click to toggle')}</span></h5><div id="br-cite">${citeEditor()}</div></div>
      <div class="bfoot">
        <button class="btn small" id="br-preview">👁 ${T('Preview what the AI receives')}</button>
        <button class="btn small" id="br-copy">⧉ ${T('Copy this brief to other sections…')}</button>
        <button class="btn small" id="br-clear">↺ ${T('Clear brief')}</button>
        <button class="btn small" id="br-paper" title="${esc(T('Story, style and terminology for the whole paper'))}">🧭 ${T('Paper-wide brief…')}</button>
        <span style="flex:1"></span>
        <button class="btn small primary" id="br-write" title="${esc(T('Agent 3.2 writes this section following the brief'))}">✍ ${T('Write with this brief')}</button>
      </div>`;
    bind(host);
    if (!B.catalog) api('/api/library/catalog').then(d => { B.catalog = d.papers || []; const c = document.getElementById('br-cite'); if (c) { c.innerHTML = citeEditor(); bindCite(); } }).catch(() => {});
  }

  function bindCite() {
    document.querySelectorAll('#br-cite [data-key]').forEach(k => k.onclick = () => {
      const key = k.dataset.key, c = B.brief.cite;
      c.includes(key) ? c.splice(c.indexOf(key), 1) : c.push(key);
      k.classList.toggle('on'); save();
    });
  }

  function bind(host) {
    host.querySelectorAll('[data-sugg]').forEach(c => c.onclick = () => {
      const ta = document.getElementById('sec-notes');
      const line = T(c.dataset.sugg);
      if (ta.value.includes(line)) return;
      ta.value = (ta.value.trim() ? ta.value.trim() + '\n' : '') + '- ' + line;
      ta.dispatchEvent(new Event('change'));
    });
    // lists
    host.querySelectorAll('[data-list]').forEach(box => {
      const key = box.dataset.list, arr = B.brief[key];
      box.querySelectorAll('input[data-i]').forEach(inp => inp.addEventListener('change', () => {
        const v = inp.value.trim(); v ? arr[+inp.dataset.i] = v : arr.splice(+inp.dataset.i, 1); save(); if (!v) render();
      }));
      box.querySelectorAll('[data-del]').forEach(b => b.onclick = () => { arr.splice(+b.dataset.del, 1); save(); render(); });
      box.querySelectorAll('[data-up]').forEach(b => b.onclick = () => { const i = +b.dataset.up; [arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]; save(); render(); });
      box.querySelectorAll('[data-down]').forEach(b => b.onclick = () => { const i = +b.dataset.down; [arr[i + 1], arr[i]] = [arr[i], arr[i + 1]]; save(); render(); });
    });
    host.querySelectorAll('[data-add]').forEach(row => {
      const inp = row.querySelector('input'), key = row.dataset.add;
      const add = () => {
        const parts = inp.value.split(/\n|;\s*/).map(s => s.trim()).filter(Boolean);
        if (!parts.length) return;
        B.brief[key].push(...parts); save(); render();
        setTimeout(() => { const n = document.querySelector(`#brief-host [data-add="${key}"] input`); if (n) n.focus(); }, 0);
      };
      row.querySelector('button').onclick = add;
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); add(); } });
    });
    // results
    const rs = B.brief.results;
    host.querySelectorAll('[data-note]').forEach(i => i.addEventListener('change', () => { rs[+i.dataset.note].note = i.value; save(); }));
    host.querySelectorAll('[data-as]').forEach(s => s.addEventListener('change', () => { rs[+s.dataset.as].as = s.value; save(); }));
    host.querySelectorAll('[data-rdel]').forEach(b => b.onclick = () => { rs.splice(+b.dataset.rdel, 1); save(); render(); });
    host.querySelectorAll('[data-rup]').forEach(b => b.onclick = () => { const i = +b.dataset.rup; [rs[i - 1], rs[i]] = [rs[i], rs[i - 1]]; save(); render(); });
    host.querySelectorAll('[data-rdown]').forEach(b => b.onclick = () => { const i = +b.dataset.rdown; [rs[i + 1], rs[i]] = [rs[i], rs[i + 1]]; save(); render(); });
    host.querySelectorAll('[data-view]').forEach(b => b.onclick = () => window.RESULTS_API && RESULTS_API.view(b.dataset.view));
    host.querySelector('#br-pick').onclick = () => {
      if (!window.RESULTS_API) return;
      RESULTS_API.pick({selected: rs.map(r => r.ref), onDone: items => {
        items.forEach(p => rs.push({ref: p.ref, title: p.title, kind: p.kind, thumb: p.thumb || '',
          as: p.kind === 'figure' && p.figure_ok ? 'figure' : p.kind === 'table' ? 'table' : 'auto', note: ''}));
        save(true); render();
      }});
    };
    host.querySelector('#br-only').onchange = e => { B.brief.results_only = e.target.checked; save(); };
    host.querySelector('#br-tone').onchange = e => { B.brief.tone = e.target.value; save(); };
    host.querySelector('#br-len').onchange = e => { B.brief.length = e.target.value; save(); };
    host.querySelector('#br-words').onchange = e => { const n = parseInt(e.target.value, 10); B.brief.words = n > 0 ? n : 0; e.target.value = B.brief.words || ''; save(); };
    bindCite();
    host.querySelector('#br-preview').onclick = async () => {
      await save(true);
      if (typeof flushSectionEdits === 'function') await flushSectionEdits().catch(() => {});
      const txt = await api('/api/paper/brief/preview?section=' + B.sec).catch(e => e.message);
      const m = document.createElement('div'); m.className = 'rmodal';
      m.innerHTML = `<div class="card"><div class="row" style="align-items:center"><h4 style="margin:0;flex:1">👁 ${T('What the Author agent receives from the brief')}</h4><button class="btn small" data-x>✕</button></div><div class="rvbody"><pre class="log">${esc(txt)}</pre></div></div>`;
      closable(m);
    };
    host.querySelector('#br-copy').onclick = () => copyModal();
    host.querySelector('#br-paper').onclick = () => {
      const card = document.getElementById('p-card'), d = document.querySelector('#pbrief-host details');
      if (card) card.open = true;
      if (d) d.open = true;
      const t = document.querySelector('#pbrief-host [data-pb=story]');
      if (t) { t.scrollIntoView({behavior: 'smooth', block: 'center'}); setTimeout(() => t.focus(), 300); }
    };
    host.querySelector('#br-clear').onclick = async () => {
      if (!confirm(T('Clear the structured brief of this section? (The directions text is kept.)'))) return;
      B.brief = {...empty(), directions: B.brief.directions}; await save(true); render();
    };
    host.querySelector('#br-write').onclick = async () => {
      await save(true);
      const btn = document.getElementById('ws-draft');
      if (btn && !btn.disabled) btn.click();
    };
  }

  function copyModal() {
    const names = (typeof SECTIONS !== 'undefined' ? SECTIONS : []).filter(([id]) => id !== B.sec);
    const m = document.createElement('div'); m.className = 'rmodal';
    m.innerHTML = `<div class="card" style="width:min(460px,94vw)"><h4 style="margin:0">⧉ ${T('Copy this brief to…')}</h4>
      ${names.map(([id, t]) => `<label class="chk"><input type="checkbox" value="${id}"> ${esc(T(t))}</label>`).join('')}
      <p class="status">${T('Replaces the brief (directions included) of the ticked sections.')}</p>
      <div class="row" style="justify-content:flex-end"><button class="btn" data-x>${T('Cancel')}</button><button class="btn primary" data-ok>${T('Copy')}</button></div></div>`;
    closable(m);
    m.querySelector('[data-ok]').onclick = async () => {
      const to = [...m.querySelectorAll('input:checked')].map(i => i.value);
      if (!to.length) return m.remove();
      await save(true);
      if (typeof flushSectionEdits === 'function') await flushSectionEdits().catch(() => {});
      try {
        await api('/api/paper/brief/copy', {method: 'POST', body: {from: B.sec, to}});
        if (typeof PROJ !== 'undefined' && PROJ) to.forEach(s => { PROJ.section_notes[s] = (PROJ.section_notes || {})[B.sec] || ''; });
        to.forEach(s => B.stale.add(s));
        B.summary = (await api('/api/paper/brief')).summary; decorateBoard();
        toast(`✓ ${T('Brief copied to')} ${to.length} ${T('section(s)')}`, 'ok');
      } catch (e) { toast(e.message, 'err'); }
      m.remove();
    };
  }

  function closable(m) {
    const onKey = e => { if (e.key === 'Escape') close(); };
    const close = () => { m.remove(); document.removeEventListener('keydown', onKey); };
    m.onmousedown = e => { if (e.target === m) close(); };
    m.querySelectorAll('[data-x]').forEach(b => b.onclick = close);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(m);
  }

  function renderPaper() {
    const host = document.getElementById('pbrief-host');
    if (!host || !B.paper) return;
    const filled = Object.values(B.paper).filter(v => (v || '').trim()).length;
    if (B.paperReady) { const s = host.querySelector('.pbcount'); if (s) s.textContent = filled ? `· ${filled}/4` : ''; return; }
    B.paperReady = true;
    host.innerHTML = `<details class="pbrief" ${filled ? 'open' : ''}><summary>🧭 ${T('Paper-wide brief')} <span class="status pbcount">${filled ? `· ${filled}/4` : ''}</span> <span class="status">— ${T('applies to every section')}</span></summary>
      <label>${T('Overall story & key claims the whole paper must support')}</label><textarea rows="3" data-pb="story" placeholder="${esc(T('e.g. A 2 W onboard denoiser that matches heavy transformers at 1/20 of the FLOPs.'))}">${esc(B.paper.story)}</textarea>
      <label>${T('Writing style preferences')}</label><textarea rows="2" data-pb="style" placeholder="${esc(T('e.g. British spelling, active voice, short paragraphs, no rhetorical questions.'))}">${esc(B.paper.style)}</textarea>
      <label>${T('Terminology & notation')}</label><textarea rows="2" data-pb="terms" placeholder="${esc(T('e.g. call the module “gated spectral block (GSB)”; X ∈ R^{H×W×B} for the input cube.'))}">${esc(B.paper.terms)}</textarea>
      <label>${T('Never do / never claim')}</label><textarea rows="2" data-pb="avoid" placeholder="${esc(T('e.g. do not claim real-time; do not mention the unpublished dataset.'))}">${esc(B.paper.avoid)}</textarea></details>`;
    host.querySelectorAll('[data-pb]').forEach(t => t.addEventListener('change', async () => {
      B.paper[t.dataset.pb] = t.value;
      try {
        await api('/api/paper/brief', {method: 'PUT', body: {paper_brief: B.paper}});
        toast(T('Paper-wide brief saved'), 'ok'); renderPaper();
      } catch (e) { toast(e.message, 'err'); }
    }));
  }

  function renderLine() {
    const el = document.getElementById('ws-brief');
    if (!el || !B.brief) return;
    const b = B.brief, bits = [];
    if ((document.getElementById('sec-notes') || {}).value) bits.push(T('directions'));
    if (b.results.length) bits.push(`${b.results.length} ${T('result(s)')}`);
    if (b.outline.length) bits.push(`${b.outline.length} ${T('part(s)')}`);
    if (b.must.length + b.avoid.length) bits.push(`${b.must.length + b.avoid.length} ${T('rule(s)')}`);
    if (b.tone) bits.push(T((TONES.find(t => t[0] === b.tone) || [, b.tone])[1]));
    el.textContent = bits.length ? `🎯 ${bits.join(' · ')}` : '';
    el.title = T('Open the brief');
    el.onclick = () => typeof setWTab === 'function' && setWTab('notes');
  }

  function decorateBoard() {
    if (!B.sumFetched) {
      B.sumFetched = true;
      api('/api/paper/brief').then(d => { B.summary = d.summary; B.paper = d.paper_brief; renderPaper(); decorateBoard(); }).catch(() => { B.sumFetched = false; });
    }
    document.querySelectorAll('#secboard .secrow').forEach(row => {
      const s = B.summary[row.dataset.sec];
      const nm = row.querySelector('.nm b');
      if (!nm) return;
      let tag = nm.querySelector('.secbrief');
      if (!s || s.empty) { if (tag) tag.remove(); return; }
      if (!tag) { tag = document.createElement('span'); tag.className = 'secbrief'; nm.appendChild(tag); }
      tag.textContent = ' 🎯' + (s.results ? s.results : '');
      tag.title = T('This section has a brief') + (s.results ? ` · ${s.results} ${T('result(s)')}` : '');
    });
  }

  document.addEventListener('change', e => { if (e.target && e.target.id === 'sec-notes') setTimeout(renderLine, 50); });
  window.BRIEF_API = {load, invalidate, decorateBoard, render};
})();
