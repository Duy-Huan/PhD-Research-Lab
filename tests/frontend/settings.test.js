'use strict';
// settings.js: models & agents, research providers, experiments & hardware, memory, skills, appearance.
const test = require('node:test');
const assert = require('node:assert');
const {boot, R, fixtures} = require('./harness');

const posted = (h) => JSON.parse(JSON.stringify(h.server.last('POST', '/api/config').body));
async function open(tab, opt = {}) {
  const h = await boot({...opt, routes: {'POST /api/config': () => fixtures.get('GET /api/config'), ...(opt.routes || {})}});
  await h.w.PL.settings.open(tab);
  await h.idle(30);
  return h;
}
const change = async (h, el, value) => {
  if (el.type === 'checkbox') el.checked = value; else el.value = value;
  el.dispatchEvent(new h.w.Event('change'));
  await h.idle(20);
};
const field = (h, label) => h.byText('.sb label.field, .sb .field', label).querySelector('input, select, textarea');

test('tabs switch; the configuration cannot be loaded', async () => {
  const h = await open();
  assert.deepStrictEqual(h.$$('.settings nav .nav').map((b) => b.textContent),
    ['Mô hình & agent', 'Research providers', 'Thí nghiệm & phần cứng', 'MCP & ChatGPT', 'Bộ nhớ & ngữ cảnh', 'Kỹ năng (/)', 'Plugin (GitHub)', 'Giao diện & ngôn ngữ']);
  assert.ok(h.$('.settings nav .nav.active').textContent.startsWith('Mô hình'));
  await h.clickText('.settings nav .nav', 'Giao diện', 20);
  assert.ok(h.$('.settings nav .nav.active').textContent.startsWith('Giao diện'));
  const h2 = await boot({routes: {'GET /api/config': () => R({detail: 'config unreadable'}, 500)}});
  await h2.w.PL.settings.open('models');
  assert.strictEqual(h2.$('.settings'), null);
  assert.match(h2.toast(), /config unreadable/);
});

test('settings search finds hardware and MCP, handles no matches, and clears the filter', async () => {
  const h = await open('models');
  const search = h.$('.settings-search');
  const query = async (value) => { search.value = value; search.dispatchEvent(new h.w.Event('input')); await h.idle(30); };
  await query('ClearML');
  assert.strictEqual(h.$('.settings nav .nav.active').dataset.k, 'hardware');
  assert.match(h.$('.sb').textContent, /ClearML Server/);
  await query('MCP');
  assert.strictEqual(h.$('.settings nav .nav.active').dataset.k, 'mcp');
  assert.match(h.$('.sb').textContent, /MCP research tools/);
  await query('no-such-setting-xyz');
  assert.match(h.$('.sb').textContent, /No matching settings/);
  await query('');
  assert.strictEqual(h.$$('.settings nav .nav').filter((el) => !el.hidden).length, 8);
  assert.strictEqual(h.$('.settings nav .nav.active').dataset.k, 'models');
});

test('models & agents: engines per agent, cloud keys (main list + others), local models in VRAM, lifecycle', async () => {
  const cfg = fixtures.get('GET /api/config');
  cfg.providers.groq = {has_key: true, model: 'llama'};
  cfg.agent_models = undefined;
  delete cfg.providers.custom;
  delete cfg.provider_specs.custom.models;
  const h = await open('models', {routes: {'GET /api/config': () => cfg,
    'POST /api/models/test': () => ({model: 'm', reply: 'pong'}),
    'GET /api/models/local': () => ({lmstudio: {online: true, loaded: ['qwen'], models: [{id: 'm1'}]}, ollama: {online: false, loaded: [{id: 'llama3'}, 'phi'], models: [{id: 'm2'}, {id: 'bad'}]}})}});
  const b = h.$('.sb');
  const agentRows = b.querySelectorAll('table.grid')[0].querySelectorAll('tr');
  assert.strictEqual(agentRows.length, 4);
  await change(h, agentRows[1].querySelector('select'), 'claude');
  assert.deepStrictEqual(posted(h), {agent_modes: {research: 'claude'}});
  const reviewerSelect = agentRows[2].querySelectorAll('select')[1];
  const reviewerModel = reviewerSelect.options[1].value;
  await change(h, reviewerSelect, reviewerModel);
  assert.deepStrictEqual(posted(h), {agent_models: {reviewer: reviewerModel}});
  await change(h, field(h, 'Cloud mặc định'), 'openai');
  assert.deepStrictEqual(posted(h), {default_cloud: 'openai'});
  // main providers + the ones with a key are shown; the rest fold into "other providers"
  const main = [...b.querySelectorAll('table.grid')[1].querySelectorAll('tr')].slice(1).map((r) => r.cells[0].textContent);
  assert.ok(main.includes('Groq') || main.some((x) => /groq/i.test(x)));
  assert.match(b.querySelector('details summary').textContent, /Nhà cung cấp khác \(\d+\)/);
  const row = b.querySelectorAll('table.grid')[1].querySelectorAll('tr')[1];
  const key = row.querySelector('input');
  const model = row.querySelector('select');
  const chosen = model.options[0].value;
  model.value = chosen;
  await h.clickText('.sb button', 'Lưu', 30);
  assert.deepStrictEqual(posted(h).providers.anthropic, {model: chosen});
  key.value = 'sk-123';
  row.querySelector('button').click();
  await h.idle(30);
  assert.strictEqual(posted(h).providers.anthropic.api_key, 'sk-123');
  assert.strictEqual(key.value, '');
  [...row.querySelectorAll('button')].find((x) => x.textContent === 'Thử').click();
  await h.idle(30);
  assert.strictEqual(h.toast(), 'OK · m: pong');
  // local servers
  assert.match(b.textContent, /Trong VRAM: LM Studio: qwen, Ollama: llama3, Ollama: phi/);
  await h.clickText('.sb button', 'Unload tất cả', 20);
  assert.strictEqual(h.server.last('POST', '/api/models/unload').body.engine, 'all');
  for (const [label, value, key2] of [['LM Studio URL', 'http://x', 'lmstudio_base_url'], ['Model LM Studio', 'm1', 'local_model'],
    ['Ollama URL', 'http://y', 'ollama_base_url'], ['Model Ollama', 'm2', 'ollama_model']]) {
    await change(h, field(h, label), value);
    assert.deepStrictEqual(posted(h), {[key2]: value});
  }
  await change(h, h.byText('.sb .field', 'Gỡ mô hình local').querySelector('input'), false);
  assert.deepStrictEqual(posted(h), {lifecycle: {unload_on_exit: false}});
  await change(h, field(h, 'Tự gỡ mô hình khi rảnh'), '15');
  assert.deepStrictEqual(posted(h), {lifecycle: {local_idle_min: 15}});
  // a failed save keeps the form
  h.server.on('POST /api/config', () => R({detail: 'invalid'}, 400));
  await change(h, field(h, 'Model Ollama'), 'bad');
  assert.strictEqual(h.toast(), 'invalid');
});

test('models tab when the local servers are offline or unreadable', async () => {
  const h = await open('models', {routes: {'GET /api/models/local': () => ({})}});
  assert.match(h.$('.sb').textContent, /VRAM trống/);
  assert.strictEqual(h.$$('.sb .row .dot.ok').length, 0);
  const h2 = await open('models', {routes: {'GET /api/models/local': () => R({}, 500)}});
  assert.match(h2.$('.sb').textContent, /Không đọc được trạng thái local/);
});

test('research providers: states, setup hints, sign-in, Feynman and coding defaults', async () => {
  const h = await open('providers', {routes: {'GET /api/providers': () => ({providers: [
    ...fixtures.get('GET /api/providers').providers, {id: 'odd', category: 'misc', label: 'Odd', state: 'STOPPED', ready: false, detail: 'd'}]})}});
  const b = h.$('.sb');
  assert.match(b.textContent, /feynman model login/);
  assert.ok(b.textContent.includes('misc'));
  const signIn = [...b.querySelectorAll('.li')].filter((li) => li.querySelector('button'));
  assert.deepStrictEqual(signIn.map((li) => li.querySelector('.t').firstChild.textContent), ['Feynman (AI research agent)', 'Claude Code', 'Google Antigravity']);
  signIn[1].querySelector('button').click();
  await h.idle(20);
  assert.strictEqual(h.server.calledWith('POST', '/api/providers/claude_code/connect').length, 1);
  assert.ok([...b.querySelectorAll('.li .dot')].some((d) => d.className === 'dot warn'));
  const toggles = [...b.querySelectorAll('.field input[type=checkbox]')].filter((el) => /Feynman/.test(el.closest('.field').textContent));
  await change(h, toggles[0], false);
  assert.deepStrictEqual(posted(h), {research_providers: {feynman_enabled: false}});
  await change(h, toggles[1], true);
  assert.deepStrictEqual(posted(h), {research_providers: {feynman_share_app_key: true}});
  await change(h, field(h, 'Giới hạn thời gian'), '900');
  assert.deepStrictEqual(posted(h), {research_providers: {feynman_timeout_s: 900}});
  await change(h, field(h, 'Coding provider'), 'codex');
  assert.deepStrictEqual(posted(h), {research_providers: {coding_default: 'codex'}});
  const h2 = await open('providers', {routes: {'GET /api/providers': () => R({}, 500)}});
  assert.strictEqual(h2.$$('.sb .list .li').length, 0);
});

test('paper and web search configuration saves scoped keys without returning secrets to password fields', async () => {
  const cfg = fixtures.get('GET /api/config');
  cfg.search = {web_engine: 'brave', n_results: 15, mailto: 'research@example.org', read_pages: true, ieee_key: '••••', serpapi_key: '••••'};
  const h = await open('providers', {routes: {'GET /api/config': () => cfg}});
  assert.strictEqual(field(h, 'Công cụ tìm web').value, 'brave');
  await change(h, field(h, 'Công cụ tìm web'), 'tavily');
  assert.deepStrictEqual(posted(h), {search: {web_engine: 'tavily'}});
  await change(h, field(h, 'Số kết quả tìm kiếm'), '20');
  assert.deepStrictEqual(posted(h), {search: {n_results: 20}});
  await change(h, field(h, 'Email cho API'), 'me@example.org');
  assert.deepStrictEqual(posted(h), {search: {mailto: 'me@example.org'}});
  await change(h, field(h, 'Đọc nội dung trang web'), false);
  assert.deepStrictEqual(posted(h), {search: {read_pages: false}});
  const labels = [['IEEE Xplore API key', 'ieee_key'], ['SerpAPI key', 'serpapi_key'], ['Tavily API key', 'tavily_key'],
    ['Brave Search API key', 'brave_key'], ['Semantic Scholar API key', 's2_key'], ['OpenAlex API key', 'openalex_key']];
  for (const [label, key] of labels) {
    const el = field(h, label);
    assert.strictEqual(el.value, '');
    el.value = 'new-key';
    el.parentNode.querySelector('button').click();
    await h.idle(20);
    assert.deepStrictEqual(posted(h), {search: {[key]: 'new-key'}});
    assert.strictEqual(el.value, '');
  }
});

test('journal ranking CSV import validates year and file, reports faults and permits retry', async () => {
  const cfg = fixtures.get('GET /api/config');
  delete cfg.search;
  const h = await open('providers', {routes: {'GET /api/config': () => cfg,
    'POST /api/journals/import': () => R({detail: 'Invalid SCImago CSV'}, 400)}});
  const importButton = h.byText('.sb button', 'Nhập bảng xếp hạng');
  importButton.click();
  await h.idle();
  assert.match(h.$('.sb').textContent, /Chọn file CSV trước/);
  const input = h.$('.sb input[type=file]');
  await h.setFiles(input, ['ranking.csv']);
  const year = h.$('.sb input[aria-label="Năm dữ liệu xếp hạng"]');
  await change(h, year, '1');
  importButton.click();
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', '/api/journals/import').length, 0);
  await change(h, year, '2024');
  importButton.click();
  await h.idle(20);
  assert.match(h.$('.sb').textContent, /Invalid SCImago CSV/);
  assert.ok(!importButton.disabled);
  const req = h.server.last('POST', '/api/journals/import');
  assert.strictEqual(req.body.get('year'), '2024');
  assert.strictEqual(req.body.get('file').name, 'ranking.csv');
  h.server.on('POST /api/journals/import', () => ({records: 42, year: 2024, source: 'SCImago (imported CSV)'}));
  importButton.click();
  await h.idle(20);
  assert.match(h.$('.sb').textContent, /Đã nhập 42 tạp chí · 2024 · SCImago/);
  const key = field(h, 'IEEE Xplore API key');
  const saveButton = key.parentNode.querySelector('button');
  saveButton.click();
  await h.idle();
  assert.strictEqual(h.server.calledWith('POST', '/api/config').length, 0);
  h.server.on('POST /api/config', () => R({detail: 'save failed'}, 400));
  key.value = 'new-key'; saveButton.click();
  await h.idle(20);
  assert.strictEqual(key.value, 'new-key');
  assert.strictEqual(h.toast(), 'save failed');
});

test('experiments & hardware: approvals, budgets, recovery, web search, slots, GPU, VS Code path', async () => {
  const h = await open('hardware');
  const cases = [
    [field(h, 'Tự chạy không cần hỏi'), '0', {runs: {auto_approve_risk: 0}}],
    [field(h, 'Ngân sách mỗi run'), '60', {runs: {max_minutes: 60}}],
    [field(h, 'Số lần tự phục hồi'), '2', {runs: {max_retries: 2}}],
    [field(h, 'Job CPU đồng thời'), '1', {runs: {slot_cpu: 1}}],
    [field(h, 'Mô hình local đồng thời'), '1', {runs: {slot_local_llm: 1}}],
    [field(h, 'CLI provider đồng thời'), '1', {runs: {slot_cli: 1}}],
    [field(h, 'Gọi cloud đồng thời'), '2', {runs: {slot_cloud: 2}}],
    [field(h, 'Nhiệt độ GPU'), '80', {resources: {gpu_temp_limit_c: 80}}],
    [field(h, 'Đường dẫn VS Code'), 'C:/code.cmd', {workspace: {vscode_path: 'C:/code.cmd'}}],
  ];
  for (const [el, v, want] of cases) { await change(h, el, v); assert.deepStrictEqual(posted(h), want); }
  const toggles = h.$$('.sb .field input[type=checkbox]').filter((el) => !el.closest('.field').textContent.includes('ClearML Server'));
  await change(h, toggles[0], false);
  assert.deepStrictEqual(posted(h), {runs: {auto_recover: false}});
  await change(h, toggles[1], true);
  assert.deepStrictEqual(posted(h), {runs: {web_search: true}});
  await change(h, toggles[2], true);
  assert.deepStrictEqual(posted(h), {resources: {auto_unload_for_gpu: true}});
  const cfg = fixtures.get('GET /api/config');
  cfg.workspace = {};
  const h2 = await open('hardware', {routes: {'GET /api/config': () => cfg}});
  assert.strictEqual(field(h2, 'Đường dẫn VS Code').value, '');
});

test('memory & context settings', async () => {
  const h = await open('memory');
  for (const [label, v, want] of [['Ghi nhớ', 'manual', {aiws: {memory_mode: 'manual'}}], ['Chế độ', 'manual', {aiws: {operating_mode: 'manual'}}],
    ['Ngân sách ngữ cảnh', '4000', {aiws: {context_budget_tokens: 4000}}], ['Thời gian tối đa', '600', {aiws: {max_turn_s: 600}}]]) {
    await change(h, field(h, label), v);
    assert.deepStrictEqual(posted(h), want);
  }
});

test('skills: list, delete a user skill, create one (ok / invalid), load errors', async () => {
  const skills = [...fixtures.get('GET /api/skills').skills, {name: 'tomtat', title: 'Tóm tắt', description: 'd', mode: 'chat', origin: 'project'}];
  let saveReply = {name: 'tomtat'};
  const h = await open('skills', {routes: {'GET /api/skills': () => ({skills, errors: [{file: 'bad.md', error: 'no front matter'}]}),
    'POST /api/skills': () => saveReply}});
  const b = h.$('.sb');
  assert.strictEqual(b.querySelectorAll('table.grid tr').length, skills.length + 1);
  assert.match(b.querySelector('.err-line').textContent, /bad\.md: no front matter/);
  assert.strictEqual(b.querySelectorAll('table.grid button.icon').length, 1);
  b.querySelector('table.grid button.icon').click();
  await h.idle(40);
  assert.strictEqual(h.server.calledWith('DELETE', '/api/skills/tomtat').length, 1);
  assert.ok(h.$('.sb table.grid'));
  h.$('.sb select').value = 'user';
  h.$('.sb select').dispatchEvent(new h.w.Event('change'));
  await h.clickText('.sb button', 'Lưu kỹ năng', 40);
  const body = h.server.last('POST', '/api/skills').body;
  assert.strictEqual(body.scope, 'user');
  assert.match(body.text, /^---\nname: tomtat/);
  saveReply = R({detail: 'missing name'}, 400);
  await h.clickText('.sb button', 'Lưu kỹ năng', 40);
  assert.strictEqual(h.toast(), 'missing name');
  h.server.on('DELETE /api/skills/:n', () => R({detail: 'builtin'}, 400));
  h.$('.sb table.grid button.icon').click();
  await h.idle(30);
  assert.strictEqual(h.toast(), 'builtin');
  const h2 = await open('skills', {routes: {'GET /api/skills': () => R({}, 500)}});
  assert.strictEqual(h2.$$('.sb table.grid tr').length, 1);
  const h3 = await open('skills', {routes: {'GET /api/skills': () => ({skills: []})}});
  assert.strictEqual(h3.$('.sb .err-line'), null);
});

test('appearance: theme follows the system, light, dark; storage blocked', async () => {
  const h = await open('look', {storage: {'pl.theme': 'dark'}});
  const sel = field(h, 'Chủ đề');
  assert.strictEqual(sel.value, 'dark');
  assert.match(h.$('.sb').textContent, /PhD Research Lab 5\.0\.0/);
  await change(h, sel, 'light');
  assert.strictEqual(h.document.documentElement.dataset.theme, 'light');
  assert.strictEqual(h.w.localStorage.getItem('pl.theme'), 'light');
  await change(h, sel, 'system');
  assert.strictEqual(h.document.documentElement.dataset.theme, undefined);
  assert.strictEqual(h.w.localStorage.getItem('pl.theme'), null);
  const cfg = fixtures.get('GET /api/config');
  cfg.project = {name: 'x'};
  const h2 = await open('look', {routes: {'GET /api/config': () => cfg}});
  assert.match(h2.$('.sb').textContent, /dữ liệu dự án: $/);
  assert.strictEqual(field(h2, 'Chủ đề').value, 'system');
  Object.defineProperty(h2.w, 'localStorage', {get() { throw new Error('private'); }});
  await h2.w.PL.settings.open('look');
  await h2.idle(20);
  await change(h2, field(h2, 'Chủ đề'), 'dark');
  assert.strictEqual(h2.document.documentElement.dataset.theme, 'dark');
});
