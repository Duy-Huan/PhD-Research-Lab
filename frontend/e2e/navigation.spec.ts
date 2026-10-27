import { test, expect, boot, topic, studio } from './live';

for (const label of ['Paper Library & Search', '5-Level Research Outline', 'Research Topics', 'Workstreams',
  'Figure Studio', 'Native code workspace', 'Intelligence & RO-Crate', 'Protocols', 'Claims & Evidence', 'Paper LaTeX', 'Code · VS Code']) {
  test(`navigation: ${label}`, async ({ page, request }, info) => {
    await boot(page);
    await topic(page, request, label);
    await studio(page, label);
    await expect(page.locator('#panel')).toBeVisible();
    await expect(page.locator('#panel .panel-b')).not.toBeEmpty();
    // Retain the actual rendered panel for explicit review, including unavailable services.
    await info.attach('panel.png', { body: await page.screenshot(), contentType: 'image/png' });
    await page.locator('#drawer-close-btn').click();
    await expect(page.locator('#panel')).toHaveCount(0);
    await expect(page.getByRole('textbox', { name: 'Ask anything, or type / for research skills…' })).toBeVisible();
  });
}

test('main views and keyboard return to chat', async ({ page }, info) => {
  await boot(page);
  for (const label of ['Library', 'Peer Review R1–R3 & LaTeX', 'System Dashboard']) {
    await page.getByRole('button', { name: label, exact: true }).first().click();
    await expect(page.locator('main')).not.toBeEmpty();
    await info.attach(`${label.replace(/[^\w]/g, '-')}.png`, { body: await page.screenshot(), contentType: 'image/png' });
    await page.getByRole('button', { name: 'Chat', exact: true }).click();
    await expect(page.locator('#view textarea')).toBeVisible();
  }
  await page.getByRole('button', { name: 'User Guide & Onboarding', exact: true }).click();
  await expect(page.locator('#panel')).toBeVisible();
  await page.locator('#drawer-close-btn').click();
  await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Expand sidebar', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Expand sidebar', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Research Studios', exact: true })).toBeVisible();
});

test('mobile chat controls and topic tabs fit the viewport', async ({ page, request }, info) => {
  await boot(page);
  await topic(page, request, 'responsive');
  for (const viewport of [{ width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 360, height: 800 }]) {
    await page.setViewportSize(viewport);
    await info.attach(`chat-${viewport.width}.png`, { body: await page.screenshot(), contentType: 'image/png' });
    const send = page.getByRole('button', { name: 'Send (Enter)', exact: true });
    const box = await send.boundingBox();
    expect(box, 'Send has a rendered box').not.toBeNull();
    expect.soft(box!.x + box!.width, `Send within ${viewport.width}px`).toBeLessThanOrEqual(viewport.width);
    expect.soft(await page.locator('#top').evaluate(el => el.scrollWidth <= el.clientWidth + 1), `Header fits ${viewport.width}px`).toBeTruthy();
    await page.locator('#topic-btn').click();
    await info.attach(`topic-${viewport.width}.png`, { body: await page.screenshot(), contentType: 'image/png' });
    expect.soft(await page.locator('#panel').evaluate(el => el.scrollWidth <= el.clientWidth + 1), `Drawer fits ${viewport.width}px`).toBeTruthy();
    await page.locator('#drawer-close-btn').click();
  }
});
