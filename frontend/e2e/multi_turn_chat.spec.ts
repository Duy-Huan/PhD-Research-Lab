import { test, expect, boot, json } from './live';

test.describe('Multi-turn Long Chat and Turn Recovery Suite', () => {
  test('consecutive multi-turn conversation maintains continuity without turn locking', async ({ page, request }, info) => {
    test.setTimeout(180_000);
    await boot(page);
    await page.getByRole('button', { name: 'New chat', exact: true }).click();

    // Turn 1: Math research calculation
    const create = page.waitForResponse(res => res.url().endsWith('/api/chat/sessions') && res.request().method() === 'POST');
    const input = page.getByRole('textbox', { name: 'Ask anything, or type / for research skills…' });
    await input.fill('For my tensor decomposition benchmark, calculate 17 times 23. Reply with the number.');
    await page.keyboard.press('Enter');

    const sessionRes = await (await create).json();
    const sessionId = sessionRes.id;
    expect(sessionId).toBeTruthy();

    // Wait until Turn 1 assistant message is completely done
    await expect(page.locator('.msg-card.assistant').first()).toContainText('391', { timeout: 60_000 });
    await expect.poll(async () => {
      const s = await json(request, 'get', `/api/chat/sessions/${sessionId}`);
      return s.turns.at(-1)?.status;
    }, { timeout: 30_000 }).toBe('completed');

    // Turn 2 in the same session: immediately ask consecutive turn referencing previous result
    await input.fill('Now multiply that previous result by 2. Reply with the number.');
    await page.keyboard.press('Enter');

    // Ensure NO "already running" raw alert appears
    await expect(page.locator('#view [role="alert"]:not(.msg-card)')).toHaveCount(0);

    // Wait until Turn 2 assistant message contains the calculated number (782)
    await expect(page.locator('.msg-card.assistant').nth(1)).toContainText('782', { timeout: 60_000 });
    await expect.poll(async () => {
      const s = await json(request, 'get', `/api/chat/sessions/${sessionId}`);
      return s.turns.at(-1)?.status;
    }, { timeout: 30_000 }).toBe('completed');

    const sessionAfterT2 = await json(request, 'get', `/api/chat/sessions/${sessionId}`);
    expect(sessionAfterT2.turns.length).toBe(2);
    expect(sessionAfterT2.messages.at(-1)?.content).toContain('782');

    // Turn 3 in the same session: consecutive 3rd turn
    await input.fill('Confirm our session is active by replying with READY.');
    await page.keyboard.press('Enter');

    await expect(page.locator('.msg-card.assistant').nth(2)).toContainText(/READY/i, { timeout: 60_000 });
    await expect.poll(async () => {
      const s = await json(request, 'get', `/api/chat/sessions/${sessionId}`);
      return s.turns.at(-1)?.status;
    }, { timeout: 30_000 }).toBe('completed');

    const sessionAfterT3 = await json(request, 'get', `/api/chat/sessions/${sessionId}`);
    expect(sessionAfterT3.turns.length).toBe(3);

    await info.attach('multi-turn-session.json', {
      body: JSON.stringify(sessionAfterT3, null, 2),
      contentType: 'application/json',
    });
  });

  test('an API-created fresh session accepts a real chat turn without an error banner', async ({ page, request }) => {
    test.setTimeout(90_000);
    await boot(page);

    // Create session via direct API
    const session = await json(request, 'post', '/api/chat/sessions', {
      title: 'Stale Turn Recovery Test',
      topic_id: '',
      chat_project: '',
    });

    // Navigate to session in the UI using boot then query param
    await page.goto(`/dist/react.html?chat=${session.id}`);
    await expect(page.locator('#live')).toHaveAttribute('title', 'Connected to PhD Lab server');

    const input = page.getByRole('textbox', { name: 'Ask anything, or type / for research skills…' });
    await input.fill('Reply with exactly PONG.');
    await page.keyboard.press('Enter');

    // Verify turn completes cleanly without error banner
    await expect(page.locator('.msg-card.assistant').last()).toContainText('PONG', { timeout: 60_000 });
    await expect(page.locator('#view [role="alert"]:not(.msg-card)')).toHaveCount(0);
  });
});
