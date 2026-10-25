import AxeBuilder from '@axe-core/playwright';
import { test, expect, boot } from './live';

test.beforeEach(async ({ request }) => {
  expect((await request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
});

test('UI-MODEL-RULES-001: cloud preconnection and context budgets persist through the real settings API', async ({ page, request }) => {
  const original = await (await request.get('/api/config')).json();
  try {
    expect((await request.post('/api/config', { data: { lifecycle: { cloud_preconnect: false } } })).ok()).toBeTruthy();
    await boot(page);
    await page.getByRole('button', { name: 'System Settings', exact: true }).click();
    await page.getByRole('button', { name: /Models & AI Agents/ }).click();
    const preconnect = page.getByRole('checkbox', { name: 'Preconnect Cloud when saving a model', exact: true });
    await expect(preconnect).not.toBeChecked();
    await preconnect.check();
    await expect.poll(async () => (await (await request.get('/api/config')).json()).lifecycle.cloud_preconnect).toBe(true);
    await page.reload();
    await page.getByRole('button', { name: 'System Settings', exact: true }).click();
    await expect(preconnect).toBeChecked();
    const history = page.getByRole('spinbutton', { name: 'Chat history budget (estimated tokens)', exact: true });
    for (const [input, expected] of [['399', 400], ['40000', 32000]] as const) {
      await history.fill(input);
      await history.blur();
      await expect.poll(async () => (await (await request.get('/api/config')).json()).aiws.history_budget_tokens).toBe(expected);
      await expect(history).toHaveValue(String(expected));
    }
    await page.reload();
    await page.getByRole('button', { name: 'System Settings', exact: true }).click();
    await expect(history).toHaveValue('32000');
    await preconnect.uncheck();
    await expect.poll(async () => (await (await request.get('/api/config')).json()).lifecycle.cloud_preconnect).toBe(false);
  } finally {
    expect((await request.post('/api/config', { data: {
      lifecycle: { cloud_preconnect: original.lifecycle?.cloud_preconnect ?? false },
      aiws: { history_budget_tokens: original.aiws?.history_budget_tokens ?? 4000 },
    } })).ok()).toBeTruthy();
  }
});

for (const width of [375, 768]) {
  test(`UI-MOBILE-SETTINGS-001: Settings dismisses mobile sidebar at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/dist/react.html');
    await expect(page.locator('#live')).toHaveAttribute('title', 'Connected to PhD Lab server');
    await expect(page.locator('#view textarea')).toBeVisible();
    await page.getByRole('button', { name: 'Open sidebar', exact: true }).click();
    await page.getByRole('button', { name: 'System Settings', exact: true }).click();
    await expect(page.locator('.settings-studio-content')).toBeVisible();
    await expect(page.getByRole('complementary', { name: 'Sidebar', exact: true })).toBeHidden();
    await page.getByRole('button', { name: 'Back to Workspace', exact: true }).click();
    await expect(page.locator('#view textarea')).toBeVisible();
  });
}

test('UI-DESKTOP-SETTINGS-001: Settings preserves desktop navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await boot(page);
  await page.getByRole('button', { name: 'System Settings', exact: true }).click();
  await expect(page.locator('.settings-studio-content')).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Sidebar', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Back to Workspace', exact: true }).click();
  await expect(page.locator('#view textarea')).toBeVisible();
});

for (const language of ['en', 'vi']) {
  test(`UI-ACCESSIBLE-NAMES-001: WCAG automated scan of workspace and settings (${language})`, async ({ page, request }, info) => {
    expect((await request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
    const findings: unknown[] = [];
    for (const width of [375, 768, 1280, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/dist/react.html');
      await expect(page.locator('#view textarea')).toBeVisible();
      for (const surface of ['workspace', 'settings']) {
        if (surface === 'settings') {
          const settings = page.getByRole('button', { name: language === 'vi' ? 'Cài đặt Hệ thống' : 'System Settings', exact: true });
          if (!await settings.isVisible()) await page.locator('#side-open').click();
          await settings.click();
          await expect(page.locator('.settings-studio-content')).toBeVisible();
        }
        const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
        findings.push({ language, width, surface, violations: result.violations, incomplete: result.incomplete });
        expect.soft(result.violations, `${surface} ${language} ${width}px`).toEqual([]);
        expect.soft(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No document overflow').toBeTruthy();
        await info.attach(`${surface}-${language}-${width}.png`, { body: await page.screenshot(), contentType: 'image/png' });
      }
    }
    await info.attach(`accessibility-${language}.json`, { body: JSON.stringify({ mode: 'REAL_LOCAL', limitation: 'Automated checks do not certify all WCAG criteria or visual correctness', findings }), contentType: 'application/json' });
  });
}
