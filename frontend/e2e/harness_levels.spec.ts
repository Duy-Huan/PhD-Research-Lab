import { test, expect, boot } from './live';
import type { Page } from '@playwright/test';
import { settle, uiAudit } from './uiAudit';

// agent/PLAN_6.6.4_L3.md A-QA: Harness Studio at L2/L3/L4 through the real UI, on every CI run, no model.
// Until A9 compiles the canvas into a governed mission, research and agent nodes must report that they did not
// run; a green node without execution would be a fabricated result.
const GOAL = 'Investigate whether label smoothing harms calibration: review papers, train baselines, verify ECE, write a paper';

async function studio(page: Page) {
  expect((await page.request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
  await boot(page);
  await page.getByRole('button', { name: 'Harness Studio', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Harness', exact: true })).toBeVisible();
}

async function generate(page: Page, level: 'L2' | 'L3' | 'L4') {
  await page.locator('button[title="AI Workflow Architect"]').click();
  await page.getByRole('textbox', { name: 'Research goal:', exact: true }).fill(GOAL);
  await page.getByRole('combobox', { name: 'Execution level:', exact: true }).selectOption({ index: ['L2', 'L3', 'L4'].indexOf(level) });
  await page.getByRole('button', { name: 'AI workflow design', exact: true }).click();
  await expect(page.getByText(/^✓ \d+ nodes · \d+ edges \(valid\)$/)).toBeVisible();
}

test('HARNESS-LEVELS-001: Team and AI Architect speak the interface language and pass the visual audit', async ({ page }) => {
  await studio(page);
  await page.locator('button[title="Build the agent team"]').click();
  await expect(page.getByText(/^Expert team \(\d+\)$/)).toBeVisible();
  await settle(page);
  expect(await uiAudit(page, 'en'), 'Team tab').toEqual([]);
  await generate(page, 'L3');
  await settle(page);
  expect(await uiAudit(page, 'en'), 'Architect preview').toEqual([]);
  await page.getByRole('button', { name: 'Load into canvas & edit', exact: true }).click();
  await expect(page.getByText(/^✓ Valid DAG \(\d+ nodes\)$/)).toBeVisible();
  await settle(page);
  expect(await uiAudit(page, 'en'), 'Generated canvas').toEqual([]);
});

for (const level of ['L2', 'L3', 'L4'] as const) {
  test(`HARNESS-LEVELS-002: an ${level} architect workflow runs control flow and reports every unexecuted node`, async ({ page, request }) => {
    await studio(page);
    await generate(page, level);
    await page.getByRole('button', { name: 'Load into canvas & edit', exact: true }).click();
    const executed = page.waitForResponse(res => res.url().endsWith('/api/harness/execute') && res.request().method() === 'POST');
    await page.getByRole('button', { name: 'Run Harness', exact: true }).click();
    const report = await (await executed).json();
    const steps: any[] = Object.values(report.node_results || {});
    expect(steps.length).toBeGreaterThan(2);
    for (const step of steps) {
      if (['start', 'end', 'condition'].includes(step.node_type)) continue;
      // Not executed must be visible as such, never as completed.
      if (!step.execution?.executed) expect(step.status, JSON.stringify(step)).not.toBe('completed');
    }
    expect(steps.find(s => s.node_type === 'start')?.status).toBe('completed');
    await page.getByRole('button', { name: 'Debug & logs', exact: true }).click();
    await expect(page.getByText('blocked', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/has no authorized executable adapter/).first()).toBeVisible();
    const stored = await (await request.get('/api/harness/executions')).json();
    expect(JSON.stringify(stored)).toContain(report.execution_id);  // kept with its blocked steps
  });
}

test('HARNESS-LEVELS-003: the standalone studio offers no mode switch that does nothing', async ({ page }) => {
  await studio(page);
  // "Automated Agents" only works inside Missions, where it opens the mission view.
  await expect(page.getByRole('button', { name: 'Automated Agents', exact: true })).toHaveCount(0);
});
