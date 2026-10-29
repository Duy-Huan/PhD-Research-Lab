import { test, expect, boot, json, topic } from './live';
import type { Page } from '@playwright/test';
import { settle, uiAudit } from './uiAudit';

// agent/PLAN_6.6.4_L3.md A-QA: Harness Studio at L2/L3/L4 through the real UI, on every CI run, no model.
// The visual runtime still runs control flow only: research and agent nodes must report that they did not run (a
// green node without execution would be a fabricated result). Since A9 they run by compiling the canvas into a
// governed mission (HARNESS-LEVELS-004).
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

for (const level of ['L2', 'L3'] as const) {
  test(`HARNESS-LEVELS-004: an ${level} canvas compiles into a mission draft with a team bound to listed models`, async ({ page, request }) => {
    // A9: the real model list, compiler, mission store and Missions panel. The architect model's answer is the one
    // fixed part (no model on CI runners); the live Codex run is recorded separately as evidence.
    expect((await page.request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
    await json(request, 'put', '/api/research/os-settings', { enabled: true });
    await boot(page);
    const created = await topic(page, request, `harness ${level}`);
    await page.getByRole('button', { name: 'Harness Studio', exact: true }).click();
    await generate(page, level);
    await page.getByRole('button', { name: 'Load into canvas & edit', exact: true }).click();
    const listed: { id: string; available: boolean; state: string }[] = (await json(request, 'get', '/api/harness/models')).models;
    expect(listed.length).toBeGreaterThan(0);
    expect(listed.map(m => m.id)).not.toContain('cli:gemini_cli');  // providers whose terms forbid being driven
    const model = listed[0];
    await page.route('**/api/harness/team/propose', route => route.fulfill({ json: {
      agents: ['researcher', 'coder'].map(role => ({ id: role, role, purpose: `The ${role} of this canvas`, tools: [], model: model.id,
                                                    model_available: model.available, model_state: model.state })),
      rationale: 'Fixed architect answer for the browser test', architect_model: model.id, unavailable: [] } }));
    await page.locator('button[title="Build the agent team"]').click();
    await page.getByRole('combobox', { name: 'Architect model (from the model list)', exact: true }).selectOption(model.id);
    await page.getByRole('button', { name: 'Propose team with AI', exact: true }).click();
    await expect(page.getByText('The coder of this canvas', { exact: true })).toBeVisible();
    if (!model.available) await expect(page.getByRole('status').first()).toContainText('no other model is used');
    await page.getByRole('button', { name: 'Preview mission', exact: true }).click();
    await expect(page.getByText('agent.task', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('mission.report', { exact: true })).toBeVisible();
    await settle(page);
    expect(await uiAudit(page, 'en'), 'Mission team preview').toEqual([]);
    const made = page.waitForResponse(res => res.url().endsWith('/api/harness/compile') && res.request().method() === 'POST');
    await page.getByRole('button', { name: 'Create mission for approval', exact: true }).click();
    const mission = (await (await made).json()).mission;
    expect(mission.status).toBe('draft');
    const stored = await json(request, 'get', `/api/research/topics/${created.id}/missions`);
    const found = (stored.missions || stored).find((m: any) => m.id === mission.id);
    expect(found.payload.spec.autonomy.level).toBe(level);
    expect(found.payload.spec.tasks.filter((t: any) => t.capability === 'agent.task').every((t: any) => t.args.model === model.id)).toBe(true);
    await page.getByRole('button', { name: 'Open Missions to approve', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Workflows L1–L4', exact: true })).toBeVisible();  // the Missions drawer
  });
}
