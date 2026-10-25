import { test, expect } from '@playwright/test';

test('CI: real application shell and settings respond without provider inference', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const response = await request.get('/api/config');
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toHaveProperty('ui');
  await page.goto('/dist/react.html');
  await expect(page.locator('body')).toBeVisible();
  await expect(page.getByRole('button', { name: 'System Settings', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'System Settings', exact: true }).click();
  await expect(page.locator('.settings-studio-content')).toBeVisible();
  await page.getByRole('button', { name: 'Back to Workspace', exact: true }).click();
  await expect(page.locator('#view textarea')).toBeVisible();
  expect(errors).toEqual([]);
});
