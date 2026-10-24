import { test as base, expect, type Page, type APIRequestContext } from '@playwright/test';

export const test = base.extend<{ audit: void }>({
  audit: [async ({ page, browser }, use, info) => {
    const events: unknown[] = [];
    const errors: string[] = [];
    page.on('console', msg => { if (['error', 'warning'].includes(msg.type())) events.push({ kind: 'console', level: msg.type(), text: msg.text() }); });
    page.on('pageerror', error => { errors.push(error.message); events.push({ kind: 'pageerror', text: error.message }); });
    page.on('requestfailed', req => events.push({ kind: 'failed', method: req.method(), url: req.url(), error: req.failure() }));
    page.on('response', res => { if (res.url().includes('/api/')) events.push({ kind: 'http', method: res.request().method(), url: res.url(), status: res.status() }); });
    await use();
    await info.attach('browser-and-network.json', { body: JSON.stringify({ browser: browser.version(), events, errors }, null, 2), contentType: 'application/json' });
    await info.attach('rendered-ui.txt', { body: await page.locator('body').innerText().catch(() => 'page closed'), contentType: 'text/plain' });
    expect(errors, 'No rendering exceptions').toEqual([]);
  }, { auto: true }],
});
export { expect };

export async function boot(page: Page) {
  await page.goto('/dist/react.html');
  await expect(page.locator('#live')).toHaveAttribute('title', 'Connected to PhD Lab server');
  await expect(page.getByRole('button', { name: 'New chat', exact: true })).toBeAttached();
}

export async function json(request: APIRequestContext, method: 'get'|'post'|'put', path: string, data?: unknown) {
  const response = await request[method](path, { data });
  expect(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json();
}

export async function topic(page: Page, request: APIRequestContext, suffix: string) {
  const created = await json(request, 'post', '/api/research/topics', {
    title: `PW ${suffix} ${Date.now()}`, description: 'Disposable synthetic browser QA data', keywords: ['synthetic'], sources: ['arxiv'],
  });
  await page.locator('#topic-btn').click();
  await page.getByText(created.title, { exact: true }).click();
  await expect(page.locator('#topic-btn')).toContainText(created.title);
  await page.locator('#drawer-close-btn').click();
  return created;
}

export async function studio(page: Page, label: string) {
  if (await page.locator('#drawer-close-btn').isVisible()) await page.locator('#drawer-close-btn').click();
  await page.getByRole('button', { name: 'Research Studios', exact: true }).click();
  await page.getByRole('complementary', { name: 'Sidebar', exact: true }).getByRole('button', { name: label, exact: true }).click();
}
