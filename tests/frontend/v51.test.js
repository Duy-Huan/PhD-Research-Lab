'use strict';
// v5.1: chat tools (charts, SVG / mermaid figures, export), notes on answers, English interface, GitHub plugins and
// automatic ranking in Settings, the Paper panel (AI-Scientist-v2), library ranking check, review revision guide.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const SID = fixtures.meta.session;
const CHART = '```chart\n{"type": "line", "title": "Acc", "xlabel": "Params", "ylabel": "Top-1", "x": [1, 2, 3], ' +
  '"series": [{"name": "A", "data": [70, 75, null], "error": [1, 0.5, 0]}, {"name": "B", "data": [68, 72, 78]}]}\n```';

async function chatWith(content, opt = {}) {
  let notes = opt.notes || [];
  const routes = {
    'GET /api/chat/sessions/:id': () => {
      const s = fixtures.get('GET /api/chat/sessions/:id');
      const m = s.messages.find((x) => x.role === 'assistant' && x.provider !== 'phdlab');
      m.content = content;
      s.notes = notes;
      return s;
    },
    'POST /api/chat/sessions/:id/notes': (req) => { const n = {id: 'nt-' + notes.length, created: 1, status: 'open', ...req.body}; notes = notes.concat(n); return n; },
    'PUT /api/chat/sessions/:id/notes/:nid': (req) => { notes = notes.map((n) => (n.id === req.params[1] ? {...n, ...req.body} : n)); return {}; },
    'DELETE /api/chat/sessions/:id/notes/:nid': (req) => { notes = notes.filter((n) => n.id !== req.params[1]); return {}; },
    ...(opt.routes || {}),
  };
  const h = await boot({...opt, routes, hash: '#/chat/' + SID});
  await h.idle(40);
  h.answer = () => h.$$('.msg.ai').find((m) => m.querySelector('.prose') && m.querySelector('.who').textContent.indexOf('PhD Lab') !== 0);
  h.msgId = () => h.answer().dataset.id;
  return h;
}

test('charts: parse, draw (line, bar, scatter, area, log), hover, table, PNG / SVG download, invalid specs', async () => {
  const h = await chatWith(CHART + '\n\n```chart\n{"type": "bar", "x": ["a", "b"], "series": [{"data": [1, -2]}, {"name": "s2", "data": [3, 4]}]}\n```' +
    '\n\n```chart\nnot json\n```\n\n```chart\n{"series": []}\n```\n\n```chart\n7\n```');
  const T = h.w.PL.tools;
  const figs = h.$$('figure.chart');
  assert.strictEqual(figs.length, 2);
  assert.strictEqual(h.$('figure.chart figcaption').textContent, 'Acc');
  assert.match(h.answer().textContent, /JSON biểu đồ không hợp lệ/);
  assert.match(h.answer().textContent, /Biểu đồ không có dữ liệu/);
  const svg = figs[0].querySelector('svg');
  assert.ok(svg.querySelectorAll('circle').length >= 5);
  assert.ok(figs[1].querySelectorAll('svg path').length >= 4);  // bars
  // hover tooltip near a point, nothing far away, leave
  svg.getBoundingClientRect = () => ({left: 0, top: 0, width: 640, height: 340});
  const p = svg._pts[0];
  svg.dispatchEvent(new h.w.MouseEvent('mousemove', {clientX: p.x, clientY: p.y}));
  assert.match(figs[0].querySelector('.chart-tip').textContent, /A · Params = 1 · Top-1 = 70 ± 1/);
  svg.dispatchEvent(new h.w.MouseEvent('mousemove', {clientX: 2000, clientY: 2000}));
  assert.ok(figs[0].querySelector('.chart-tip').hidden);
  svg.dispatchEvent(new h.w.MouseEvent('mouseleave'));
  // data table toggles
  await h.clickText('figure.chart .chart-tools button', 'Bảng dữ liệu');
  assert.match(figs[0].querySelector('.chart-table').textContent, /70 ± 1/);
  assert.match(figs[0].querySelector('.chart-table').textContent, /—/);
  await h.clickText('figure.chart .chart-tools button', 'Bảng dữ liệu');
  assert.strictEqual(figs[0].querySelector('.chart-table'), null);
  // downloads (anchors are clicked, not navigated); PNG needs an image that loads
  Object.defineProperty(h.w.HTMLImageElement.prototype, 'src', {set() { setTimeout(() => this.onload(), 1); }, configurable: true});
  h.w.HTMLCanvasElement.prototype.getContext = () => ({fillRect() {}, drawImage() {}});
  h.w.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,AA==';
  const got = [];
  h.w.HTMLAnchorElement.prototype.click = function () { got.push(this.getAttribute('download')); };
  await h.clickText('figure.chart .chart-tools button', 'SVG');
  await h.clickText('figure.chart .chart-tools button', 'PNG', 30);
  assert.deepStrictEqual(got, ['Acc.svg', 'Acc.png']);
  // the renderer itself: every type, log axis, a dark theme, numeric labels
  for (const s of [{type: 'scatter', x: [1, 10], series: [{data: [1, 1000]}], ylog: true}, {type: 'area', x: [0, 1, 2], series: [{data: [1e-4, 2e5, 3]}]},
    {type: 'zzz', series: [{data: [5, 5]}]}, {x: ['a'], series: [{name: 'x', data: [1], x: ['a']}]}]) {
    const r = T.parseChart(JSON.stringify(s));
    assert.ok(r.ok);
    assert.ok(T.svgChart(r.spec, {theme: 'dark'}).querySelector('rect'));
  }
  const many = T.parseChart(JSON.stringify({x: Array.from({length: 30}, (_, i) => 'c' + i), type: 'bar', series: [{data: Array.from({length: 30}, () => 1)}]}));
  assert.ok(T.svgChart(many.spec).querySelectorAll('text').length < 30);
  T.repaintAll();
  const detached = T.chart(T.parseChart(JSON.stringify({series: [{data: [1, 2]}]})).spec);
  assert.ok(T.charts.has(detached));
  T.repaintAll();
  assert.ok(!T.charts.has(detached));  // a figure that left the page is forgotten
  h.w.dispatchEvent(new h.w.Event('resize'));
  await h.idle(250);
  assert.strictEqual(typeof T.dark(), 'boolean');
});

test('svg figures are sanitised; mermaid diagrams load on demand and fall back to source', async () => {
  const h = await chatWith('```svg\n<svg width="40" height="20"><script>alert(1)</script><rect width="10" height="10"/></svg>\n```\n\n' +
    '```svg\n<p>not svg</p>\n```\n\n```mermaid\ngraph LR\nA-->B\n```');
  const fig = h.$('figure.svg-figure');
  assert.ok(fig.querySelector('rect'));
  assert.strictEqual(fig.querySelector('script'), null);
  assert.strictEqual(fig.querySelector('svg').getAttribute('viewBox'), '0 0 40 20');
  assert.strictEqual(h.$$('figure.svg-figure').length, 1);
  assert.ok(h.$('figure.mermaid-figure .spin'));  // loading on demand
  // the vendored script cannot load → the source is shown instead
  h.w.PL.load = async () => false;
  const box = h.w.document.createElement('div');
  h.w.PL.rich(box, '```mermaid\ngraph LR\nA-->B\n```');
  await h.until(() => box.querySelector('figure.mermaid-figure pre'));
  assert.match(box.textContent, /A-->B/);
  // a loaded mermaid renders (and a failing one falls back)
  h.w.mermaid = {initialize() {}, render: async (id, src) => (src === 'bad' ? Promise.reject(new Error('x')) : {svg: '<svg><text>ok</text></svg>'})};
  h.w.PL.load = async () => true;
  assert.match(await h.w.PL.tools.mermaid('graph'), /ok/);
  assert.strictEqual(await h.w.PL.tools.mermaid('bad'), '');
  const box2 = h.w.document.createElement('div');
  h.w.PL.rich(box2, '```mermaid\ngraph\n```');
  await h.until(() => box2.querySelector('figure.mermaid-figure svg'));
});

test('export: menu formats, PDF / Word / LaTeX of an answer and of the conversation, print fallback, errors', async () => {
  let reply = () => R('%PDF', 200);
  const h = await chatWith(CHART + '\n\n```svg\n<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>\n```', {routes: {'POST /api/export': (req) => reply(req)}});
  const got = [];
  h.w.HTMLAnchorElement.prototype.click = function () { got.push(this.getAttribute('download')); };
  h.w.URL.createObjectURL = () => 'blob:x';
  h.w.URL.revokeObjectURL = () => {};
  // rasterising needs a canvas: a stand-in that "draws"
  h.w.HTMLCanvasElement.prototype.getContext = () => ({fillRect() {}, drawImage() {}, set fillStyle(v) {}});
  h.w.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,AA==';
  Object.defineProperty(h.w.HTMLImageElement.prototype, 'src', {set(v) { setTimeout(() => (v.includes('svg') ? this.onload() : this.onerror()), 1); }, configurable: true});
  const exportBtn = [...h.answer().querySelectorAll('.msg-actions button')].find((b) => b.title.startsWith('Xuất'));
  exportBtn.click();
  await h.idle();
  assert.deepStrictEqual(h.$$('.menu.pop .mi').map((b) => b.textContent), ['PDF (.pdf)', 'Word (.docx)', 'LaTeX (.tex)', 'Markdown (.md)', 'HTML (.html)']);
  h.$$('.menu.pop .mi')[0].click();
  await h.until(() => got.length === 1);
  let body = h.server.last('POST', '/api/export').body;
  assert.strictEqual(body.format, 'pdf');
  assert.match(body.html, /<svg/);
  assert.ok(!body.html.includes('chart-tools'));
  assert.match(h.toast(), /Đã xuất/);
  exportBtn.click();
  await h.idle();
  h.$$('.menu.pop .mi')[1].click();
  await h.until(() => got.length === 2, 3000);
  body = h.server.last('POST', '/api/export').body;
  assert.deepStrictEqual(Object.keys(body.images).sort(), ['chart-0', 'svg-0']);
  // no browser for the PDF → the print dialog; a server error → toast; offline → toast
  let printed = '';
  h.w.open = () => ({document: {write: (x) => { printed = x; }, close() {}}, setTimeout: (f) => f(), print() { printed += '+print'; }});
  reply = () => R({detail: 'No Edge'}, 501);
  await h.w.PL.tools.exportAs('pdf', {title: 'T', markdown: 'x', els: []});
  assert.match(printed, /\+print$/);
  h.w.open = () => null;
  await h.w.PL.tools.exportAs('pdf', {title: 'T', markdown: 'x'});
  assert.match(h.toast(), /chặn cửa sổ in/);
  reply = () => R({detail: 'bad format'}, 400);
  await h.w.PL.tools.exportAs('md', {title: 'T', markdown: 'x'});
  assert.strictEqual(h.toast(), 'bad format');
  reply = () => R('', 500);
  await h.w.PL.tools.exportAs('md', {markdown: 'x'});
  reply = () => new Error('offline');
  await h.w.PL.tools.exportAs('md', {markdown: 'x'});
  assert.match(h.toast(), /Không kết nối/);
  // the whole conversation, from the header and from the thread menu
  reply = () => R('ok', 200);
  await h.clickText('#top-tools button', 'Xuất');
  h.$$('.menu.pop .mi')[3].click();
  await h.idle(30);
  body = h.server.last('POST', '/api/export').body;
  assert.strictEqual(body.format, 'md');
  assert.match(body.markdown, /### Bạn/);
  // a canvas that cannot draw: no image, no crash
  h.w.HTMLCanvasElement.prototype.getContext = () => null;
  assert.strictEqual(await h.w.PL.tools.svgToPng('<svg viewBox="0 0 1 1"></svg>'), '');
  h.w.HTMLCanvasElement.prototype.getContext = () => ({fillRect() {}, drawImage() {}});
  h.w.HTMLCanvasElement.prototype.toDataURL = () => { throw new Error('tainted'); };
  assert.strictEqual(await h.w.PL.tools.svgToPng('<svg></svg>'), '');
  assert.strictEqual(await h.w.PL.tools.svgToPng('<nope>'), '');
});

test('notes: select a passage, note a chart point, highlights, the notes panel, ask the AI, resolve / edit / delete', async () => {
  const h = await chatWith('Kết quả **độ trễ đo thật** trên phần cứng biên.\n\n' + CHART);
  const prose = h.answer().querySelector('.prose');
  // selecting text inside an answer shows the note button
  const strong = prose.querySelector('strong');
  const range = h.w.document.createRange();
  range.selectNodeContents(strong);
  range.getBoundingClientRect = () => ({left: 10, top: 100, width: 50, height: 10});
  h.w.getSelection = () => ({isCollapsed: false, rangeCount: 1, getRangeAt: () => range, toString: () => 'độ trễ đo thật', removeAllRanges() {}});
  h.$('#thread').dispatchEvent(new h.w.MouseEvent('mouseup', {bubbles: true}));
  await h.idle(10);
  assert.ok(h.$('.note-pop'));
  await h.clickText('.note-pop button', 'Hỏi về đoạn này');
  assert.match(h.$('#input').value, /^> độ trễ đo thật/);
  h.$('#thread').dispatchEvent(new h.w.KeyboardEvent('keyup', {shiftKey: true, bubbles: true}));
  h.$('#thread').dispatchEvent(new h.w.KeyboardEvent('keyup', {bubbles: true}));
  await h.clickText('.note-pop button', 'Ghi chú');
  await h.idle();
  h.$('#modal textarea').value = 'Cần đo trên Jetson';
  await h.clickText('.dialog-f button', 'Lưu ghi chú', 60);
  const saved = h.server.last('POST', `/api/chat/sessions/${SID}/notes`).body;
  assert.strictEqual(saved.quote, 'độ trễ đo thật');
  assert.strictEqual(saved.prefix, 'Kết quả ');
  await h.until(() => h.$('mark.note-hl'));
  assert.strictEqual(h.$('mark.note-hl').textContent, 'độ trễ đo thật');
  assert.strictEqual(h.$('sup.note-ref').textContent, '1');
  assert.match(h.$('#notes-btn').textContent, /1/);
  // scrolling hides the selection button; a collapsed selection shows nothing
  h.$('#thread').dispatchEvent(new h.w.MouseEvent('mouseup', {bubbles: true}));
  await h.idle(10);
  h.$('#thread').dispatchEvent(new h.w.Event('scroll'));
  assert.strictEqual(h.$('.note-pop'), null);
  h.w.getSelection = () => ({isCollapsed: true});
  h.$('#thread').dispatchEvent(new h.w.MouseEvent('mouseup', {bubbles: true}));
  await h.idle(10);
  assert.strictEqual(h.$('.note-pop'), null);
  // a chart point
  const svg = h.$('figure.chart svg');
  svg.getBoundingClientRect = () => ({left: 0, top: 0, width: 640, height: 340});
  const p = svg._pts.find((q) => q.s.name === 'B');
  svg.dispatchEvent(new h.w.MouseEvent('click', {clientX: p.x, clientY: p.y}));
  await h.idle();
  assert.match(h.$('#modal .note-quote').textContent, /Điểm B: 1 = 68/);
  await h.clickText('.dialog-f button', 'Lưu ghi chú', 60);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', `/api/chat/sessions/${SID}/notes`).body.point)), {chart: 'Acc', series: 'B', x: '1', y: '68', label: 'B @ 1'});
  await h.until(() => [...h.$$('figure.chart svg text')].some((t) => t.textContent === '2'));  // the numbered badge on the point
  svg.dispatchEvent(new h.w.MouseEvent('click', {clientX: 5000, clientY: 5000}));  // far from any point: nothing
  // notes panel: count, jump, ask the AI about all open notes
  await h.click('#notes-btn', 20);
  assert.strictEqual(h.$('#panel-title').textContent, 'Ghi chú (2)');
  assert.match(h.$('#panel-body').textContent, /2 chưa xử lý/);
  h.w.Element.prototype.scrollIntoView = function () { this.dataset.seen = '1'; };
  h.$$('#panel-body .note-item button')[0].click();
  assert.ok(h.$('mark.note-hl').classList.contains('flash'));
  await h.clickText('#panel-body button', 'Gửi ghi chú cho AI');
  assert.match(h.$('#input').value, /1\. > độ trễ đo thật\n {3}Ghi chú: Cần đo trên Jetson/);
  assert.match(h.$('#input').value, /Điểm B: 1 = 68/);
  // the menu of a highlight: edit, resolve, ask, delete
  h.$('mark.note-hl').click();
  await h.idle();
  assert.strictEqual(h.$('.menu.pop .mh').textContent, 'Cần đo trên Jetson');
  await h.clickText('.menu.pop .mi', 'Sửa ghi chú');
  h.$('#modal textarea').value = 'Sửa';
  await h.clickText('.dialog-f button', 'Lưu ghi chú', 60);
  assert.strictEqual(h.server.last('PUT', `/api/chat/sessions/${SID}/notes/nt-0`).body.text, 'Sửa');
  h.$('mark.note-hl').click();
  await h.clickText('.menu.pop .mi', 'Đánh dấu đã xử lý', 60);
  await h.until(() => h.$('mark.note-hl.resolved'));
  h.$('mark.note-hl').click();
  await h.clickText('.menu.pop .mi', 'Mở lại', 60);
  h.$('sup.note-ref').click();
  await h.clickText('.menu.pop .mi', 'Hỏi AI về ghi chú này');
  assert.match(h.$('#input').value, /^Xem lại các điểm/);
  h.$('mark.note-hl').click();
  await h.clickText('.menu.pop .mi', 'Xoá ghi chú', 60);
  await h.until(() => !h.$('mark.note-hl'));
  // the per-message note button notes the start of the answer; a failed save keeps the dialog
  h.server.on('POST /api/chat/sessions/:id/notes', () => R({detail: 'nope'}, 400));
  [...h.answer().querySelectorAll('.msg-actions button')].find((b) => b.title.startsWith('Ghi chú')).click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Lưu ghi chú', 40);
  assert.ok(!h.$('#modal').hidden);
  assert.strictEqual(h.toast(), 'nope');
});

test('notes panel when there are none; a note whose passage is gone; highlight helper edge cases', async () => {
  const h = await chatWith('Plain answer.', {notes: [{id: 'nt-x', message_id: 'm-none', quote: 'zzz', status: 'resolved', created: 1}]});
  await h.click('#notes-btn', 20);
  assert.match(h.$('#panel-body').textContent, /0 chưa xử lý/);
  assert.match(h.$('#panel-body').textContent, /\(chưa có nội dung\)/);
  h.$$('#panel-body .note-item button')[0].click();  // nothing to jump to
  const T = h.w.PL.tools;
  const div = h.w.document.createElement('div');
  div.innerHTML = 'abc <b>def</b> ghi';
  assert.strictEqual(T.highlight(div, {id: 'a', quote: ''}), false);
  assert.strictEqual(T.highlight(div, {id: 'a', quote: 'nope'}), false);
  assert.strictEqual(T.highlight(div, {id: 'b', quote: 'c de', prefix: 'ab', status: 'resolved'}, 3), true);
  assert.strictEqual(div.querySelectorAll('mark').length, 2);
  assert.strictEqual(div.querySelector('sup').textContent, '3');
  assert.strictEqual(T.highlight(div, {id: 'c', quote: 'ghi', prefix: 'zz'}), true);
  h.w.getSelection = undefined;
  assert.strictEqual(T.selectionInAnswer(), null);
  h.w.getSelection = () => ({isCollapsed: false, rangeCount: 1, getRangeAt: () => ({startContainer: h.$('#input'), endContainer: h.$('#input')}), toString: () => 'x'});
  assert.strictEqual(T.selectionInAnswer(), null);
  const prose = h.answer().querySelector('.prose');
  h.w.getSelection = () => ({isCollapsed: false, rangeCount: 1, getRangeAt: () => ({startContainer: prose.firstChild, endContainer: prose.firstChild}), toString: () => ' a '});
  assert.strictEqual(T.selectionInAnswer(), null);  // too short
  // empty notes panel
  const h2 = await chatWith('x');
  await h2.click('#notes-btn', 20);
  assert.match(h2.$('#panel-body').textContent, /Chưa có ghi chú/);
});

test('composer tools menu; streaming closes an open code fence; md cache', async () => {
  const h = await chatWith('x');
  h.$('.composer .bar button[aria-label="Công cụ"]').click();
  await h.idle();
  assert.match(h.$('.menu.pop').textContent, /Vẽ đồ thị/);
  await h.clickText('.menu.pop .mi', 'Vẽ đồ thị từ dữ liệu');
  assert.match(h.$('#input').value, /```chart/);
  for (const label of ['Vẽ sơ đồ kiến trúc', 'Vẽ hình minh hoạ', 'Viết bảng LaTeX']) {
    h.$('.composer .bar button[aria-label="Công cụ"]').click();
    await h.clickText('.menu.pop .mi', label);
  }
  h.$('.composer .bar button[aria-label="Công cụ"]').click();
  await h.clickText('.menu.pop .mi', 'PDF · Word');
  assert.match(h.$('.menu.pop').textContent, /Xuất ra/);
  const el = h.w.document.createElement('div');
  h.w.PL.rich(el, 'start\n```python\nx = 1', {stream: true});
  assert.ok(el.querySelector('pre code'));
  const long = 'y'.repeat(300);
  assert.strictEqual(h.w.PL.md(long), h.w.PL.md(long));
  for (let i = 0; i < 125; i++) h.w.PL.md(long + i);  // the cache stays bounded
  // keyboard navigation of a popup menu
  const anchor = h.$('#send');
  h.w.PL.menu(anchor, [{label: 'one', run() {}}, {label: 'two', run() {}}]);
  await h.idle();
  const key = (k) => h.w.document.dispatchEvent(new h.w.KeyboardEvent('keydown', {key: k}));
  key('ArrowDown'); key('ArrowDown'); key('ArrowUp'); key('Tab');
  key('Escape');
  assert.strictEqual(h.$('.menu.pop'), null);
});

test('English interface: static markup, constants, dates, skills in English, language switch reloads', async () => {
  const h = await boot({storage: {'pl.lang': 'en', 'pl.font': 'serif'}, hash: '#/',
    routes: {'GET /api/config': () => ({...fixtures.get('GET /api/config'), ui: {language: 'en', prose_font: 'serif'}}),
      'GET /api/skills': () => ({skills: [{name: 'lit', title: 'Tổng quan', title_en: 'Literature review', description: 'vi', description_en: 'Find papers',
        aliases: [], category: 'research', mode: 'run', risk: 0, origin: 'builtin'}, {name: 'ext', title: 'Ext', description: 'd', aliases: [], category: 'writing',
        mode: 'chat', risk: 0, origin: 'plugin', plugin: 'acme-x'}]})}});
  await h.idle(40);
  assert.strictEqual(h.w.document.documentElement.lang, 'en');
  assert.strictEqual(h.w.document.documentElement.dataset.font, 'serif');
  assert.strictEqual(h.$('#new-chat').textContent, 'New conversation');
  assert.strictEqual(h.$('#search').placeholder, 'Search conversations…');
  assert.strictEqual(h.w.PL.STATUS.RUNNING, 'Running');
  assert.strictEqual(h.w.PL.t('Không có ở từ điển {0}', 1), 'Không có ở từ điển 1');
  assert.strictEqual(h.w.PL.t('Run {0} không còn'), 'Run {0} no longer exists');
  assert.match(h.w.PL.ago(1), /\d/);
  await h.input('#input', '/');
  assert.match(h.$('.menu.slash').textContent, /Literature review/);
  assert.match(h.$('.menu.slash').textContent, /plugin/);
  // settings changed elsewhere → reload once in that language; never in a loop
  let reloads = 0;
  const h2 = await boot({hash: '#/', storage: {}, routes: {'GET /api/config': () => ({...fixtures.get('GET /api/config'), ui: {language: 'en'}})}});
  await h2.idle(40);
  assert.strictEqual(h2.w.localStorage.getItem('pl.lang'), 'en');
  h2.w.PL.setLang = () => { reloads++; };
  assert.strictEqual(reloads, 0);
});

test('settings: language, font, plugins (install, toggle, skills, update, remove, errors), automatic ranking', async () => {
  let plugins = [];
  let rank = {journals: {records: 0}, conferences: {records: 0}, refreshed: {core: {error: 'offline'}}};
  const h = await boot({hash: '#/', routes: {
    'GET /api/plugins': () => ({plugins, root: 'D:/data/plugins'}),
    'POST /api/plugins': (req) => {
      if (req.body.url.includes('fail')) return R({detail: 'Could not download'}, 502);
      plugins = [{id: 'acme-x', owner: 'acme', repo: 'x', subdir: '', ref: 'main', commit: 'abcdef123456', enabled: true, adapter: '', errors: [{}],
        skills: [{name: 'one', description: 'first', enabled: true}, {name: 'two', title: 'Two', enabled: false}]},
      {id: 'acme-y', owner: 'acme', repo: 'y', subdir: 'skills', ref: 'dev', commit: '', enabled: false, adapter: 'ai_scientist', skills: []}];
      return plugins[0];
    },
    'GET /api/ranking': (req) => (req.query.refresh ? {journals: {records: 30000, year: 2024, origin: 'scimagojr 2024.csv'},
      conferences: {records: 987, source: 'ICORE2026', fetched_at: '2026-10-21T00:00'}, refreshed: {scimago: {imported: true, file: 'scimagojr 2024.csv'}}} : rank),
  }});
  h.w.PL.settings.open('look');
  await h.idle(30);
  let reload = '';
  h.w.PL.setLang = (v) => { reload = v; };
  await h.change('.settings .sb select:nth-of-type(1)', 'dark');
  const selects = h.$$('.settings .sb select');
  selects[1].value = 'serif';
  selects[1].dispatchEvent(new h.w.Event('change'));
  await h.idle(20);
  assert.strictEqual(h.w.document.documentElement.dataset.font, 'serif');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(h.server.last('POST', '/api/config').body)), {ui: {prose_font: 'serif'}});
  selects[2].value = 'en';
  selects[2].dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.strictEqual(reload, 'en');
  // plugins
  await h.clickText('.settings nav .nav', 'Plugin');
  await h.idle(20);
  assert.match(h.$('.settings .sb').textContent, /Chưa có plugin nào/);
  await h.clickText('.settings .sb button', 'Cài plugin');  // empty URL: focus only
  assert.strictEqual(h.server.calledWith('POST', '/api/plugins').length, 0);
  await h.clickText('.settings .sb .chip', 'SakanaAI');
  assert.match(h.$('.settings .sb input').value, /SakanaAI\/AI-Scientist-v2/);
  await h.input('.settings .sb input', 'https://github.com/acme/fail');
  await h.key('.settings .sb input', 'Enter');
  await h.idle(30);
  assert.match(h.toast(), /Could not download/);
  await h.input('.settings .sb input', 'https://github.com/acme/x');
  await h.clickText('.settings .sb button', 'Cài plugin', 40);
  assert.match(h.toast(), /Đã cài acme-x · 2 kỹ năng/);
  const card = h.$$('.plugin-card');
  assert.strictEqual(card.length, 2);
  assert.match(card[0].textContent, /main · commit abcdef12 · 2 kỹ năng/);
  assert.match(card[0].textContent, /1 file không đọc được/);
  assert.match(card[1].textContent, /adapter ai_scientist/);
  assert.match(card[1].textContent, /Không tìm thấy SKILL.md/);
  card[0].querySelector('label.switch input').checked = false;
  card[0].querySelector('label.switch input').dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.strictEqual(h.server.last('PUT', '/api/plugins/acme-x').body.enabled, false);
  const skillBox = h.$$('.plugin-card')[0].querySelector('.li input');
  skillBox.checked = false;
  skillBox.dispatchEvent(new h.w.Event('change'));
  await h.idle(20);
  assert.strictEqual(h.server.last('PUT', '/api/plugins/skills/one').body.enabled, false);
  h.$$('.plugin-card')[0].querySelector('button[aria-label="Cập nhật từ GitHub"]').click();
  await h.idle(30);
  assert.strictEqual(h.server.calledWith('POST', '/api/plugins/acme-x/update').length, 1);
  h.$$('.plugin-card')[0].querySelector('button[aria-label="Gỡ plugin"]').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Huỷ', 20);
  // reopen settings (the dialog closed) and remove for real
  h.w.PL.settings.open('plugins');
  await h.idle(40);
  h.$$('.plugin-card')[0].querySelector('button[aria-label="Gỡ plugin"]').click();
  await h.idle();
  await h.clickText('.dialog-f button', 'Gỡ', 30);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/plugins/acme-x').length, 1);
  // ranking status inside research providers
  h.w.PL.settings.open('providers');
  await h.idle(60);
  assert.match(h.$('.rank-status').textContent, /chưa tải/);
  assert.match(h.$('.rank-status').textContent, /CORE: offline/);
  await h.clickText('.settings .sb button', 'Cập nhật ngay', 40);
  assert.match(h.$('.rank-status').textContent, /987 hội nghị · ICORE2026 · cập nhật 2026-10-21/);
  assert.match(h.$('.rank-status').textContent, /30000 tạp chí · năm 2024 · scimagojr 2024.csv/);
  assert.match(h.$('.rank-status').textContent, /Đã tự nhập scimagojr 2024.csv/);
  rank = R({detail: 'down'}, 500);
  h.w.PL.settings.open('providers');
  await h.idle(60);
  assert.match(h.$('.rank-status').textContent, /down/);
  const coreSel = [...h.$$('.settings .sb select')].find((s) => [...s.options].some((o) => o.value === 'CORE2023'));
  coreSel.value = 'CORE2023';
  coreSel.dispatchEvent(new h.w.Event('change'));
  await h.idle(40);
  assert.strictEqual(h.server.last('POST', '/api/config').body.ranking.core_source, 'CORE2023');
  // plugins unavailable
  h.server.on('GET /api/plugins', () => R({detail: 'broken'}, 500));
  h.w.PL.settings.open('plugins');
  await h.idle(40);
  assert.match(h.$('.settings .sb').textContent, /broken/);
});

test('paper panel: sections, AI-Scientist install, write the manuscript (stream), compile, downloads', async () => {
  let ais = {installed: false};
  let compile = {ok: true};
  const h = await boot({hash: '#/', routes: {
    'GET /api/paper': () => ({sections: [{id: 'abstract', text: 'An abstract'}, {id: 'introduction', text: ''}]}),
    'GET /api/paper/ais': () => ais,
    'POST /api/paper/ais/install': () => { ais = {installed: true, commit: '96bd51617c', templates: ['icml', 'icbinb'], has_tex: false}; return {}; },
    'POST /api/paper/ais/writeup': () => R('', 200, {sse: [{type: 'start'}, {type: 'delta', text: '\\begin'}, 'data: nope\n\n',
      {type: 'done', dropped_citations: ['x']}]}),
    'POST /api/paper/ais/compile': () => compile,
  }});
  await h.clickText('.nav', 'Viết bài báo', 40);
  assert.strictEqual(h.$('#panel-title').textContent, 'Viết bài báo');
  assert.match(h.$('#panel-body').textContent, /12 ký tự|11 ký tự/);
  assert.match(h.$('#panel-body').textContent, /chưa được cài/);
  await h.clickText('#panel-body button', 'Cài AI-Scientist-v2', 60);
  assert.match(h.$('#panel-body').textContent, /Commit 96bd51617c/);
  assert.strictEqual(h.$$('#panel-body select option').length, 2);
  ais = {...ais, has_tex: true, has_pdf: true};
  await h.clickText('#panel-body button', 'Viết toàn bài', 80);
  assert.match(h.toast(), /bỏ 1 trích dẫn/);
  assert.ok(h.$$('#panel-body a').some((a) => a.getAttribute('href') === '/api/paper/ais/download/pdf'));
  const compileBtn = () => h.$$('#panel-body button').find((b) => b.textContent === 'Biên dịch PDF');
  compileBtn().click();
  await h.idle(40);
  assert.strictEqual(h.toast(), 'Đã biên dịch PDF');
  compile = {ok: false};
  compileBtn().click();
  await h.idle(40);
  assert.match(h.toast(), /Chưa biên dịch được/);
  // the write buttons go to the chat with the command typed
  await h.clickText('#panel-body .li button', 'Sửa', 120);
  assert.match(h.$('#input').value, /^\/write abstract /);
  h.w.PL.panels.paper();
  await h.idle(40);
  await h.clickText('#panel-body button', 'Phản biện NeurIPS', 120);
  assert.match(h.$('#input').value, /^\/ais-review /);
  h.w.PL.panels.paper();
  await h.idle(40);
  h.server.on('POST /api/paper/ais/writeup', () => R({detail: 'no model'}, 400));
  await h.clickText('#panel-body button', 'Viết lại toàn bài', 60);
  assert.strictEqual(h.toast(), 'no model');
  // install failure keeps the button usable; the paper API down
  ais = {installed: false};
  h.server.on('POST /api/paper/ais/install', () => R({detail: 'offline'}, 502));
  h.server.on('GET /api/paper', () => R({}, 500));
  h.w.PL.panels.paper();
  await h.idle(40);
  await h.clickText('#panel-body button', 'Cài AI-Scientist-v2', 40);
  assert.ok(!h.byText('#panel-body button', 'Cài AI-Scientist-v2').disabled);
});

test('library: ranking badges, the ranking check; search results show CORE ranks', async () => {
  const refs = [{file: 'a.pdf', title: 'A', journal_ranking: {quartile: 'Q1', sjr: 2.1, source: 'SCImago', year: 2024}},
    {file: 'b.pdf', title: 'B', journal_ranking: {core_rank: 'A*', acronym: 'CVPR', source: 'CORE ICORE2026'}},
    {file: 'c.pdf', title: 'C', journal_ranking: {quartile: 'Q3'}}, {file: 'd.pdf', title: 'D', pdf_available: false}];
  const h = await boot({hash: '#/', routes: {'GET /api/library': () => ({references: refs}),
    'POST /api/library/rank': () => ({checked: 4, ranked: 2, conference: 1})}});
  await h.clickText('.nav', 'Tài liệu', 40);
  const chips = h.$$('#panel-body .chip.rank').map((c) => c.textContent);
  assert.deepStrictEqual(chips, ['Q1 · SJR 2.1', 'CORE A* · CVPR', 'Q3']);
  await h.clickText('#panel-body button', 'Kiểm tra ranking', 40);
  assert.match(h.toast(), /Đã kiểm tra 4 tài liệu · 2 tạp chí có hạng · 1 hội nghị CORE/);
  // a conference reference opens with its CORE details
  h.w.PL.panels.reference({file: 'x.pdf', pdf_available: false, title: 'Conf paper',
    journal_ranking: {status: 'conference', core_rank: 'A', conference: 'Conf', acronym: 'CNF', source: 'CORE ICORE2026', source_url: 'https://portal.core.edu.au/conf-ranks/1/'}});
  assert.match(h.$('#panel-body').textContent, /Conf \(CNF\) — CORE A/);
  assert.ok(h.$$('#panel-body a').some((a) => a.textContent === 'Xem trên CORE'));
  h.w.PL.panels.reference({file: 'y.pdf', pdf_available: false, title: 'Conf 2', journal_ranking: {status: 'conference', core_rank: 'B'}});
  assert.match(h.$('#panel-body').textContent, /CORE B/);
  assert.strictEqual(h.w.PL.panels.rankBadge(null), null);
});

test('review: venue ranking lookup, the revision guide tab (write with AI, show, rewrite)', async () => {
  const RVID = fixtures.meta.review;
  let rv = fixtures.get('GET /api/review/:id');
  rv.state = {...rv.state, reviewers: {R1: {text: 'r1'}}, issues: [{id: 'I1', severity: 'major', title: 'T', location: '', problem: 'p', status: 'open'}], fixes: {}};
  let lookup = {venue: 'x', conference: {acronym: 'CVPR', title: 'CVPR', rank: 'A*', source: 'CORE ICORE2026'}};
  const h = await boot({hash: '#/review/' + RVID, routes: {
    'GET /api/review/:id': () => rv,
    'GET /api/ranking/lookup': () => lookup,
    'POST /api/review/:id/stage': (req) => {
      if (req.body.stage === 'guide') { rv = {...rv, state: {...rv.state, guide: {text: '# Revision guide\n\nStep 1'}}}; }
      return R('', 200, {sse: [{type: 'delta', text: '# Rev'}, {type: 'done'}]});
    },
  }});
  await h.idle(60);
  const venue = h.$$('#rv-main input.input').find((i) => i.placeholder.includes('hội nghị'));
  venue.value = 'CVPR 2026';
  venue.dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.match(h.$('#rv-main small[role=status]').textContent, /CVPR · CORE A\*/);
  lookup = {venue: 'x', journal: {title: 'TGRS', quartile: 'Q2', sjr: 2.4, year: 2024}};
  venue.dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.match(h.$('#rv-main small[role=status]').textContent, /TGRS · Q2 · SJR 2.4/);
  lookup = {venue: 'x'};
  venue.dispatchEvent(new h.w.Event('change'));
  await h.idle(30);
  assert.match(h.$('#rv-main small[role=status]').textContent, /Không tìm thấy hạng/);
  venue.value = '';
  venue.dispatchEvent(new h.w.Event('change'));
  await h.idle(10);
  assert.strictEqual(h.$('#rv-main small[role=status]').textContent, '');
  await h.clickText('.rv-tabs button', 'Hướng dẫn sửa bài', 20);
  assert.match(h.$('#rv-body').textContent, /Chưa có bản do AI soạn/);
  await h.clickText('#rv-body button', 'Soạn hướng dẫn bằng AI', 80);
  assert.strictEqual(h.server.last('POST', `/api/review/${RVID}/stage`).body.stage, 'guide');
  assert.match(h.$('#rv-body').textContent, /Step 1/);
  assert.ok(h.byText('#rv-body button', 'Soạn lại bằng AI'));
  // without issues the guide waits for the review
  rv = {...rv, state: {...rv.state, issues: []}};
  h.w.PL.dispatch();
  await h.idle(60);
  await h.clickText('.rv-tabs button', 'Hướng dẫn sửa bài', 20);
  assert.match(h.$('#rv-body').textContent, /Chạy phản biện trước/);
});
