import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => { expect((await request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy(); });
test.afterEach(async ({ request }) => { await request.post('/api/config', { data: { ui: { language: 'en' } } }); });

test('UAT harness: real language form reaches backend and persists after refresh without LLM', async ({ page, request }) => {
  await page.goto('/dist/react.html');
  await page.getByRole('button', { name: 'System Settings', exact: true }).click();
  const vi = page.waitForResponse(r => r.url().endsWith('/api/config') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'VI', exact: true }).click();
  expect((await vi).ok()).toBeTruthy();
  await expect.poll(async () => (await (await request.get('/api/config')).json()).ui.language).toBe('vi');
  await page.getByRole('button', { name: 'ENG', exact: true }).click();
  await expect.poll(async () => (await (await request.get('/api/config')).json()).ui.language).toBe('en');
  await page.reload();
  await expect(page.getByRole('button', { name: 'System Settings', exact: true })).toBeVisible();
  expect((await (await request.get('/api/config')).json()).ui.language).toBe('en');
});

test('UAT harness: separate browser contexts do not share cookies or local storage', async ({ browser, baseURL }) => {
  const first = await browser.newContext();
  const second = await browser.newContext();
  try {
    const a = await first.newPage(), b = await second.newPage();
    await a.goto(baseURL + '/dist/react.html');
    await b.goto(baseURL + '/dist/react.html');
    await a.evaluate(() => localStorage.setItem('uat-private-marker', 'first-only'));
    await first.addCookies([{ name: 'uat-private', value: 'first-only', url: baseURL! }]);
    expect(await b.evaluate(() => localStorage.getItem('uat-private-marker'))).toBeNull();
    expect((await second.cookies()).find(c => c.name === 'uat-private')).toBeUndefined();
  } finally { await first.close(); await second.close(); }
});

test('UAT harness: controlled console error and unhandled rejection produce evidence', async ({ page }, info) => {
  const events: { kind: string; text: string }[] = [];
  page.on('console', m => { if (m.type() === 'error') events.push({ kind: 'console', text: m.text() }); });
  page.on('pageerror', error => events.push({ kind: 'pageerror', text: error.message }));
  await page.goto('/dist/react.html');
  await page.evaluate(() => {
    console.error('UAT_CONTROLLED_CONSOLE_ERROR');
    void Promise.reject(new Error('UAT_CONTROLLED_REJECTION'));
  });
  await expect.poll(() => events.some(e => e.text.includes('UAT_CONTROLLED_REJECTION'))).toBeTruthy();
  expect(events.some(e => e.text.includes('UAT_CONTROLLED_CONSOLE_ERROR'))).toBeTruthy();
  await info.attach('controlled-fault-evidence.json', { body: JSON.stringify({ mode: 'MOCKED', injection: true, events }), contentType: 'application/json' });
});

test('UAT harness: injected config-network failure is recorded and reload recovers', async ({ page }) => {
  const failed: string[] = [];
  page.on('requestfailed', r => failed.push(r.url()));
  await page.route('**/api/config', route => route.abort('failed'));
  await page.goto('/dist/react.html');
  await expect.poll(() => failed.some(url => url.endsWith('/api/config'))).toBeTruthy();
  await page.unroute('**/api/config');
  await page.reload();
  await expect(page.getByRole('button', { name: 'System Settings', exact: true })).toBeVisible();
});

test('UAT harness: failed action preserves screenshot and reproducible actual/expected report', async ({ page }, info) => {
  await page.route('**/__uat_fixture', route => route.fulfill({ contentType: 'text/html', body: '<h1>Controlled harness fixture</h1><button>Save fixture</button>' }));
  await page.goto('/__uat_fixture');
  let failure = '';
  try { await page.getByRole('button', { name: 'Missing controlled action' }).click({ timeout: 250 }); }
  catch (error) { failure = String(error); }
  expect(failure).toContain('Timeout');
  await info.attach('controlled-defect.json', { body: JSON.stringify({ mode: 'MOCKED', fixture: true, status: 'REPRODUCED', expected: 'Requested control is available', actual: failure, actions: ['open /__uat_fixture', 'click Missing controlled action'], product_bug: false }), contentType: 'application/json' });
  await info.attach('controlled-failure.png', { body: await page.screenshot(), contentType: 'image/png' });
});

test('UAT harness: a controlled broken fixture fails its regression then corrected fixture passes', async ({ page }, info) => {
  let fixed = false;
  await page.route('**/__uat_fixture', route => route.fulfill({ contentType: 'text/html', body: `<button onclick="${fixed ? "document.querySelector('output').textContent='Saved'" : ''}">Save fixture</button><output>Pending</output>` }));
  await page.goto('/__uat_fixture');
  await page.getByRole('button', { name: 'Save fixture' }).click();
  let failed = false;
  try { await expect(page.locator('output')).toHaveText('Saved', { timeout: 250 }); } catch { failed = true; }
  expect(failed).toBeTruthy();
  fixed = true;
  await page.reload();
  await page.getByRole('button', { name: 'Save fixture' }).click();
  await expect(page.locator('output')).toHaveText('Saved');
  await info.attach('fixture-regression.json', { body: JSON.stringify({ mode: 'MOCKED', fixture: true, before: 'FAIL', after: 'PASS', product_bug_fixed: false }), contentType: 'application/json' });
});
