import { test, expect, boot, json, topic } from './live';
import { settle, uiAudit } from './uiAudit';

// agent/PLAN_6.6.4_L3.md A8, found in the live Codex run (docs/qa/evidence/cli-agent-registry-662/live-codex.md):
// a mission the agent created appeared only after a reload, a reload dropped the selected Topic, and a narrow drawer
// squeezed the Topic and Missions headers. Real UI and backend, no model.

test('MISSIONS-LIVE-001: a mission created outside the UI appears in the open Missions drawer without a reload', async ({ page, request }) => {
  expect((await request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
  await boot(page);
  const created = await topic(page, request, 'missions live');
  await page.getByRole('button', { name: 'Autonomous Missions', exact: true }).click();
  const objective = `Agent-created mission ${Date.now()}`;
  // The same route the agent's mission tools use; the page is not reloaded afterwards.
  await json(request, 'post', `/api/research/topics/${created.id}/missions`, {
    topic_id: created.id, objective, tasks: [{ id: 'inspect', capability: 'paper.inspect' }] });
  // The drawer's mission selector picks it up live (it is an option of that select).
  await expect(page.locator('select', { has: page.locator('option', { hasText: objective }) })).toHaveCount(1, { timeout: 10_000 });
});

test('TOPIC-RELOAD-001: the selected Topic survives a page reload', async ({ page, request }) => {
  expect((await request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
  await boot(page);
  const created = await topic(page, request, 'reload');
  await page.reload();
  await expect(page.locator('#live')).toHaveAttribute('title', 'Connected to PhD Lab server');
  await expect(page.locator('#topic-btn')).toContainText(created.title);
});

for (const width of [1024, 1280]) {
  test(`NARROW-DRAWER-001: Topic and Missions drawers pass the visual audit at ${width} px`, async ({ page, request }) => {
    expect((await request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
    await page.setViewportSize({ width, height: 800 });
    await boot(page);
    await topic(page, request, `narrow ${width}`);
    await page.locator('#topic-btn').click();
    await settle(page);
    expect(await uiAudit(page, 'en'), `Topics drawer at ${width}px`).toEqual([]);
    await page.locator('#drawer-close-btn').click();
    await page.getByRole('button', { name: 'Autonomous Missions', exact: true }).click();
    await settle(page);
    expect(await uiAudit(page, 'en'), `Missions drawer at ${width}px`).toEqual([]);
    // Found live: the header title was squeezed to three lines beside the mode switch.
    const title = await page.getByRole('heading', { name: 'Autonomous Research Missions', exact: true }).boundingBox();
    expect(title!.height, 'Missions title on one line').toBeLessThanOrEqual(28);
  });
}
