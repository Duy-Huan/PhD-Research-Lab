import AxeBuilder from '@axe-core/playwright';
import { MODEL, test, expect, boot, json, topic } from './live';

test('real selected local-model chat, SSE, pin, memory save and reload', async ({ page, request }, info) => {
  test.setTimeout(180_000);
  await boot(page);
  const create = page.waitForResponse(res => res.url().endsWith('/api/chat/sessions') && res.request().method() === 'POST');
  await page.getByRole('textbox', { name: 'Ask anything, or type / for research skills…' }).fill('Return just the result of 13 plus 29. Do not use any tools.');
  await page.keyboard.press('Enter');
  const session = await (await create).json();
  await expect(page.locator('.msg-card.assistant').last()).toContainText('42', { timeout: 120_000 });
  await expect(page.getByRole('button', { name: 'Stop generating', exact: true })).toHaveCount(0);
  const saved = await json(request, 'get', `/api/chat/sessions/${session.id}`);
  expect(saved.turns.at(-1).status).toBe('completed');
  expect(saved.messages.at(-1).status).toBe('complete');
  expect(saved.messages.at(-1).content).toContain('42');
  await info.attach('real-session.json', { body: JSON.stringify(saved, null, 2), contentType: 'application/json' });
  await page.locator('.msg-card.assistant').last().getByRole('button', { name: 'Pin', exact: true }).click();
  await expect(page.locator('.msg-card.assistant').last().getByRole('button', { name: 'Unpin', exact: true })).toBeVisible();
  const memory = page.waitForResponse(res => res.url().endsWith(`/sessions/${session.id}/memory`) && res.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save to Project Memory', exact: true }).last().click();
  const memoryRes = await memory;
  expect(memoryRes.ok(), await memoryRes.text()).toBeTruthy();
  const memories = await json(request, 'get', '/api/memory/candidates?status=approved');
  expect(JSON.stringify(memories)).toContain('42');
  await page.reload();
  await expect(page.locator('#live')).toHaveClass(/active/);
  await page.getByText(session.title, { exact: true }).first().click();
  await expect(page.locator('.msg-card.assistant').last()).toContainText('42');
});

test('chat cancellation is persisted and the composer recovers', async ({ page, request }) => {
  await boot(page);
  const create = page.waitForResponse(res => res.url().endsWith('/api/chat/sessions') && res.request().method() === 'POST');
  await page.locator('#view textarea').fill('Write 100 numbered paragraphs about a synthetic experiment. Do not use tools.');
  await page.keyboard.press('Enter');
  const session = await (await create).json();
  await page.getByRole('button', { name: 'Stop generating', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Stop generating', exact: true })).toHaveCount(0);
  await expect.poll(async () => (await json(request, 'get', `/api/chat/sessions/${session.id}`)).turns.at(-1)?.status).toBe('cancelled');
  await page.locator('#view textarea').fill('/help');
  await page.getByRole('button', { name: 'Send (Enter)', exact: true }).click();
  await expect(page.locator('.msg-card.assistant').last()).toContainText('/help');
});

test('provider settings persist, memory navigation and responsive settings', async ({ page, request }, info) => {
  await boot(page);
  await page.getByRole('button', { name: 'System Settings', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'assistant provider', exact: true })).toHaveValue('local');
  for (const agent of ['assistant', 'research', 'reviewer', 'utility']) {
    await page.getByRole('combobox', { name: `${agent} provider`, exact: true }).selectOption('local');
    await page.getByRole('combobox', { name: `${agent} model`, exact: true }).selectOption(MODEL);
  }
  const model = page.getByRole('textbox', { name: 'Model LM Studio', exact: true });
  await model.fill(MODEL);
  await model.press('Tab');
  await expect.poll(async () => (await json(request, 'get', '/api/config')).agent_modes).toEqual({ assistant: 'local', research: 'local', reviewer: 'local', utility: 'local' });
  const nav = page.getByRole('navigation', { name: 'Settings sections', exact: true });
  for (const tab of ['Research Engines', 'Search & Ranking', 'Experiments & Hardware', 'Memory & Context', 'MCP & Security Firewall', 'Skills & Plugins', 'Appearance & Language', 'Models & AI Agents']) {
    await nav.getByRole('button', { name: new RegExp(`^${tab.replace(/[&]/g, '\\&')}`) }).click();
    await expect(page.locator('.settings-studio-content')).not.toBeEmpty();
    await info.attach(`settings-${tab.replace(/\W/g, '-')}.png`, { body: await page.screenshot(), contentType: 'image/png' });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await info.attach('settings-mobile.png', { body: await page.screenshot(), contentType: 'image/png' });
  expect(await page.locator('.settings-studio').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
  await page.getByRole('button', { name: 'Back to Workspace', exact: true }).click();
  await expect(page.locator('#view textarea')).toBeVisible();
  await page.reload();
  const config = await json(request, 'get', '/api/config');
  expect(config.agent_models.assistant).toBe(MODEL);
});

test('project create, rename, delete cancellation and switch isolate topics', async ({ page, request }) => {
  await boot(page);
  const original = (await json(request, 'get', '/api/config')).project;
  const name = `PW Project ${Date.now()}`;
  await page.getByRole('button', { name: /^Workspace:/ }).click();
  await page.getByRole('button', { name: 'New Project', exact: true }).click();
  await page.getByPlaceholder('vd: Vision-Language Reasoning').fill(name);
  await page.getByRole('button', { name: 'Create Project', exact: true }).click();
  await expect(page.getByRole('button', { name: `Workspace: ${name}`, exact: true })).toBeVisible();
  const freshTopic = await topic(page, request, 'isolated project');
  await page.getByRole('button', { name: `Workspace: ${name}`, exact: true }).click();
  // Narrow the cards with the real search form, then rename the disposable project.
  const search = page.getByPlaceholder('Search projects by name or path…');
  if (await search.isVisible()) await search.fill(name);
  const card = page.getByRole('article', { name: `Project ${name}`, exact: true });
  await card.getByTitle(/Tùy chọn dự án|Project options/i).click();
  await card.getByRole('button', { name: /Đổi tên|Rename/i }).click();
  await page.getByPlaceholder('Enter new name…').fill(`${name} renamed`);
  await page.getByRole('button', { name: /Save Changes|Save Name|Lưu tên mới|Save/, exact: false }).last().click();
  await expect(page.getByRole('button', { name: `Workspace: ${name} renamed`, exact: true })).toBeVisible();
  const renamedCard = page.getByRole('article', { name: `Project ${name} renamed`, exact: true });
  await renamedCard.getByTitle(/Tùy chọn dự án|Project options/i).click();
  await renamedCard.getByRole('button', { name: /Delete Project|Xóa hoặc gỡ dự án/i }).click();
  await expect(page.getByRole('heading', { name: 'Confirm Delete Project', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect((await json(request, 'get', '/api/projects')).projects.some((p: any) => p.name === `${name} renamed`)).toBeTruthy();
  if (await search.isVisible()) await search.fill(original.name);
  await page.getByRole('article', { name: `Project ${original.name}`, exact: true }).getByRole('button', { name: 'Activate', exact: true }).click();
  await expect(page.getByRole('button', { name: `Workspace: ${original.name}`, exact: true })).toBeVisible();
  expect((await json(request, 'get', '/api/research/topics')).topics.some((t: any) => t.id === freshTopic.id)).toBeFalsy();
  await page.locator('#topic-btn').click();
  await expect(page.locator('#panel')).not.toContainText(freshTopic.title);
  expect(await page.locator('#topic-btn').innerText()).not.toContain(freshTopic.title);
});

test('critical accessibility scan of chat and settings', async ({ page }, info) => {
  await boot(page);
  for (const view of ['chat', 'settings']) {
    if (view === 'settings') await page.getByRole('button', { name: 'System Settings', exact: true }).click();
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    await info.attach(`axe-${view}.json`, { body: JSON.stringify(result, null, 2), contentType: 'application/json' });
    expect.soft(result.violations.filter(v => ['critical', 'serious'].includes(v.impact || '')).map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))).toEqual([]);
  }
});
