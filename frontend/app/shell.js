/* PhD Research Lab — app shell (2026 refresh): navigation rail, page title, mobile drawer, Settings page, command palette.
   Works on top of the existing tab mechanism (nav button[data-tab] in index.html) — it never replaces it. */
(function () {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const T = s => (window.I18N ? I18N.tr(s) : s);
  const app = $('.app'), rail = $('#rail'), scrim = $('#rail-scrim');
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch { return null; } };
  const navBtn = tab => document.querySelector(`nav button[data-tab="${tab}"]`);
  const mobile = () => matchMedia('(max-width:900px)').matches;

  // ---------------------------------------------------------------- active tab: title, aria-current, drawer
  function syncActive() {
    const on = $('nav button[data-tab].on');
    $$('nav button[data-tab]').forEach(b => b.toggleAttribute('aria-current', b === on));
    if (on) {
      const lbl = on.querySelector('.lbl');
      $('#page-title').textContent = (lbl ? lbl.textContent : on.textContent).trim();
    }
  }
  window.addEventListener('tab-shown', () => { syncActive(); closeDrawer(); if ($('#tab-settings.on')) spy(); });
  $$('nav button[data-tab]').forEach(b => b.addEventListener('click', () => setTimeout(syncActive)));

  function go(tab, then) {
    const b = navBtn(tab);
    if (!b) return;
    if (!b.classList.contains('on')) b.click();
    if (then) setTimeout(then, 60);
  }
  window.SHELL = {go};

  // ---------------------------------------------------------------- collapse (desktop) / drawer (mobile)
  function setMin(min) {
    app.classList.toggle('rail-min', min);
    const b = $('#rail-collapse'), t = min ? 'Expand sidebar' : 'Collapse sidebar';
    b.setAttribute('aria-label', T(t)); b.title = T(t); b.setAttribute('data-i18n-title', t);
    store('rail_min', min ? '1' : '0');
  }
  $('#rail-collapse').onclick = () => setMin(!app.classList.contains('rail-min'));
  setMin(store('rail_min') === '1');
  function openDrawer() { rail.classList.add('open'); scrim.hidden = false; (rail.querySelector('nav button.on') || rail.querySelector('nav button')).focus(); }
  function closeDrawer() { if (!rail.classList.contains('open')) return; rail.classList.remove('open'); scrim.hidden = true; }
  $('#rail-open').onclick = openDrawer;
  scrim.onclick = closeDrawer;

  // arrow keys move through the rail like a menu
  rail.addEventListener('keydown', e => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
    const items = $$('.rail nav button').filter(b => b.offsetParent !== null);
    let i = items.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    i = e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : (i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
    items[i].focus();
  });

  // ---------------------------------------------------------------- "go to" buttons (project chip, More settings)
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-goto]');
    if (!b) return;
    const tab = b.dataset.goto, set = b.dataset.set, sub = b.dataset.sub;
    go(tab, () => {
      if (set) showSet(set);
      if (sub && tab === 'control') setTimeout(() => window.CONTROL_API && CONTROL_API.show(sub), 250);
    });
  });

  // ---------------------------------------------------------------- Settings page
  const scroller = $('#tab-settings');
  const cards = () => $$('#tab-settings .set-card');
  function mark(id) { $$('.set-menu [data-set-go]').forEach(b => b.classList.toggle('on', b.dataset.setGo === id)); }
  function showSet(id) {
    const c = document.getElementById('set-' + id);
    if (!c) return;
    $('#set-filter').value = ''; filter('');
    c.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth', block: 'start'});
    mark(id); pinned = Date.now() + 900;
    const f = c.querySelector('input:not([readonly]),select,button');
    if (f) setTimeout(() => f.focus({preventScroll: true}), 300);
  }
  $$('.set-menu [data-set-go]').forEach(b => b.onclick = () => showSet(b.dataset.setGo));
  window.SHELL.showSet = showSet;
  let pinned = 0;  // the section the researcher just picked wins over the scroll position for a moment
  function spy() {
    if (Date.now() < pinned) return;
    const vis = cards().filter(c => !c.hidden), top = scroller.getBoundingClientRect().top + 24;
    let cur = vis[0];
    for (const c of vis) if (c.getBoundingClientRect().top <= top) cur = c;
    if (scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 4) cur = vis[vis.length - 1];  // at the bottom
    if (cur) mark(cur.dataset.set);
  }
  scroller.addEventListener('scroll', () => requestAnimationFrame(spy), {passive: true});
  scroller.addEventListener('scrollend', spy);
  function filter(q) {
    q = q.trim().toLowerCase();
    let shown = 0;
    for (const c of cards()) {
      const hit = !q || c.textContent.toLowerCase().includes(q) ||
        [...c.querySelectorAll('[placeholder],[title]')].some(el => ((el.getAttribute('placeholder') || '') + ' ' + (el.title || '')).toLowerCase().includes(q));
      c.hidden = !hit; shown += hit;
      const m = document.querySelector(`.set-menu [data-set-go="${c.dataset.set}"]`);
      if (m) m.hidden = !hit;
    }
    $('#set-empty').hidden = shown > 0;
  }
  $('#set-filter').addEventListener('input', e => filter(e.target.value));

  // unsaved changes → highlight the save bar (provider keys, engines, search…; the theme/language apply at once)
  const bar = $('.set-savebar');
  const dirty = e => { if (!e.target.closest('.themesw, #set-mcp') && !e.target.matches('#set-filter')) bar.classList.add('dirty'); };
  $('#tab-settings .set-main').addEventListener('input', dirty);
  $('#tab-settings .set-main').addEventListener('change', dirty);
  $('#save-cfg').addEventListener('click', () => setTimeout(() => bar.classList.remove('dirty'), 400));

  // ---------------------------------------------------------------- quick theme toggle in the top bar
  function themeIcon() {
    const dark = document.documentElement.dataset.theme !== 'light';
    $('#theme-quick use').setAttribute('href', dark ? '#i-sun' : '#i-moon');
  }
  $('#theme-quick').onclick = () => {
    const dark = document.documentElement.dataset.theme !== 'light';
    const b = document.querySelector(`[data-theme-mode="${dark ? 'light' : 'dark'}"]`);
    if (b) b.click();
    themeIcon();
  };
  new MutationObserver(themeIcon).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  themeIcon();

  // ---------------------------------------------------------------- command palette (Ctrl/⌘ + K)
  const pal = $('#cmdk'), q = $('#cmdk-q'), list = $('#cmdk-list');
  let items = [], sel = 0, lastFocus = null;
  function entries() {
    const out = [];
    $$('.rail nav button[data-tab]').forEach(b => out.push({label: b.querySelector('.lbl').textContent.trim(), kind: T('Tool'),
      icon: b.querySelector('use').getAttribute('href'), run: () => go(b.dataset.tab)}));
    $$('.set-menu [data-set-go]').forEach(b => out.push({label: b.textContent.trim(), kind: T('Settings'),
      icon: b.querySelector('use').getAttribute('href'), run: () => go('settings', () => showSet(b.dataset.setGo))}));
    $$('#tab-settings .set-link').forEach(b => out.push({label: b.querySelector('b').textContent.trim(), kind: T('Settings'),
      icon: b.querySelector('use').getAttribute('href'), run: () => b.click()}));
    out.push({label: T('Toggle light / dark'), kind: T('Action'), icon: '#i-sun', run: () => $('#theme-quick').click()});
    out.push({label: T('Pinned notes'), kind: T('Action'), icon: '#i-pin', run: () => $('#notes-open').click()});
    return out;
  }
  const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  function render() {
    const s = norm(q.value.trim());
    items = entries().filter(it => !s || norm(it.label + ' ' + it.kind).includes(s))
      .map((it, i) => [it, s && !norm(it.label).includes(s) ? 1 : 0, i]).sort((a, b) => a[1] - b[1] || a[2] - b[2]).map(x => x[0]);  // name matches first
    sel = Math.min(sel, Math.max(0, items.length - 1));
    list.innerHTML = items.length ? items.map((it, i) =>
      `<button class="cmdk-item${i === sel ? ' sel' : ''}" role="option" aria-selected="${i === sel}" data-i="${i}">` +
      `<svg class="ic"><use href="${it.icon}"/></svg><span></span><small></small></button>`).join('')
      : `<div class="cmdk-empty">${T('No results')}</div>`;
    list.querySelectorAll('.cmdk-item').forEach((el, i) => { el.querySelector('span').textContent = items[i].label; el.querySelector('small').textContent = items[i].kind; });
    const cur = list.querySelector('.sel'); if (cur) cur.scrollIntoView({block: 'nearest'});
  }
  function openPal() { lastFocus = document.activeElement; pal.hidden = false; q.value = ''; sel = 0; render(); q.focus(); }
  function closePal() { pal.hidden = true; if (lastFocus && lastFocus.focus) lastFocus.focus(); }
  function runSel(i) { const it = items[i]; closePal(); if (it) it.run(); }
  $('#cmdk-open').onclick = openPal;
  q.addEventListener('input', () => { sel = 0; render(); });
  list.addEventListener('click', e => { const b = e.target.closest('.cmdk-item'); if (b) runSel(+b.dataset.i); });
  pal.addEventListener('click', e => { if (e.target === pal) closePal(); });
  pal.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % Math.max(1, items.length); render(); }
    else if (e.key === 'Enter') { e.preventDefault(); runSel(sel); }
    else if (e.key === 'Tab') e.preventDefault();  // focus stays in the dialog
  });
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); pal.hidden ? openPal() : closePal(); }
    else if (e.key === 'Escape') { if (!pal.hidden) closePal(); else closeDrawer(); }
  });

  $$('[data-ui-lang]').forEach(b => b.addEventListener('click', () => setTimeout(syncActive, 60)));
  // the built-in "Default project" name follows the interface language; names the researcher typed never change
  window.addEventListener('ui-lang', () => { const pt = $('#proj-tag'); if (pt && pt.dataset.name === 'Default project') pt.textContent = T('Default project'); });

  // deep links: #settings, #settings/cloud, #ide … (bookmarkable; the address follows the open tab)
  const initialHash = location.hash;  // read now: restoring the last tab rewrites the address before the timer below
  function fromHash(h) {
    const [tab, set] = decodeURIComponent((typeof h === 'string' ? h : location.hash).slice(1)).split('/');
    if (tab && navBtn(tab)) go(tab, set ? () => showSet(set) : null);
  }
  window.addEventListener('tab-shown', e => { if (location.hash.slice(1).split('/')[0] !== e.detail) history.replaceState(null, '', '#' + e.detail); });
  window.addEventListener('hashchange', fromHash);
  setTimeout(() => fromHash(initialHash), 150);  // after index.html restored the last tab (50 ms) — an explicit link wins

  // first paint (the saved tab is restored by index.html a moment later → tab-shown updates the title)
  syncActive();
  window.addEventListener('resize', () => { if (!mobile()) closeDrawer(); });
})();
