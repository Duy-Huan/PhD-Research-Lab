import { MODEL, test, expect, boot, json, topic } from './live';

test('harness run does not invent evaluation metrics when adapters are unavailable', async ({ page }, info) => {
  await boot(page);
  await page.getByRole('button', { name: 'Harness Studio', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Harness', exact: true })).toBeEnabled();
  const response = page.waitForResponse(res => res.url().endsWith('/api/harness/execute') && res.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run Harness', exact: true }).click();
  const report = await (await response).json();
  await info.attach('actual-harness-report.json', { body: JSON.stringify(report, null, 2), contentType: 'application/json' });
  expect(report.passed).toBe(false);
  expect(report.status).toBe('blocked');
  expect(Object.values(report.node_results).every((n: any) => !n.passed && Object.keys(n.metrics).length === 0)).toBeTruthy();
  await expect(page.locator('#panel')).toContainText(/not configured|unavailable/i);
});

test('ledger UI renders actual ledger events and verified API status', async ({ page, request }) => {
  await boot(page);
  const created = await topic(page, request, 'ledger display');
  const ledger = await json(request, 'get', `/api/research/topics/${created.id}/ledger`);
  expect(ledger.events.length).toBeGreaterThan(0);
  await page.locator('#topic-btn').click();
  await page.getByRole('button', { name: 'Sổ cái Bất biến (Ledger)', exact: true }).click();
  await expect(page.locator('#panel')).toContainText(ledger.events[0].kind);
  await expect(page.locator('#panel')).toContainText('HASH CHAIN VERIFIED');
});

test('real Codex CLI chat follows the provider selected in settings', async ({ page, request }, info) => {
  const auth = await json(request, 'get', '/api/providers/codex/auth-status').catch(() => null);
  if (!auth?.ready) {
    test.skip(true, `Codex CLI is not authenticated (${auth?.detail || 'not logged in'}); skipped real external CLI call per Phase 6 policy`);
    return;
  }
  test.setTimeout(240_000);
  await boot(page);
  try {
    await page.getByRole('button', { name: 'System Settings', exact: true }).click();
    await page.getByRole('combobox', { name: 'assistant provider', exact: true }).selectOption('codex');
    await expect.poll(async () => (await json(request, 'get', '/api/config')).agent_modes.assistant).toBe('codex');
    await page.getByRole('button', { name: 'Back to Workspace', exact: true }).click();
    await expect(page.locator('#view select').last()).toHaveAttribute('title', /Codex|codex/);
    const response = page.waitForResponse(res => res.url().endsWith('/api/chat/sessions') && res.request().method() === 'POST');
    await page.locator('#view textarea').fill('Compute 17 plus 8. Respond with the number only. Do not use tools.');
    await page.keyboard.press('Enter');
    const session = await (await response).json();
    await expect(page.locator('.msg-card.assistant').last()).toContainText('25', { timeout: 180_000 });
    await expect.poll(async () => {
      const s = await json(request, 'get', `/api/chat/sessions/${session.id}`);
      return s.turns?.at(-1)?.status;
    }, { timeout: 120_000, intervals: [1000, 2000] }).toBe('completed');
    const saved = await json(request, 'get', `/api/chat/sessions/${session.id}`);
    await info.attach('codex-real-session.json', { body: JSON.stringify(saved, null, 2), contentType: 'application/json' });
    expect(saved.turns.at(-1).status).toBe('completed');
    expect(saved.messages.at(-1).provider).toBe('cli:codex');
  } finally {
    await json(request, 'post', '/api/config', { agent_modes: { assistant: 'local' }, agent_models: { assistant: MODEL } });
  }
});
