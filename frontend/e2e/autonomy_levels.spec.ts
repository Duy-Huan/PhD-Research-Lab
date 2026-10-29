import { test, expect, boot, json, topic } from './live';
import type { Page, APIRequestContext } from '@playwright/test';

// agent/PLAN_6.6.4_L3.md phase A-QA: the four Missions L1–L4 flows through the real UI and backend, on every CI run.
// No model is called: the workflows name a model that cannot exist, so every model step fails the same way with or
// without LM Studio, and the test checks what the researcher sees. Completion with a real agent is the live suite.
const NO_MODEL = 'qa-no-model-installed';

// Everything the panel lists (sources, approved protocols) exists before it opens, as for a researcher.
async function setup(page: Page, request: APIRequestContext, name: string, withProtocols = false) {
  expect((await request.post('/api/config', { data: { ui: { language: 'en' } } })).ok()).toBeTruthy();
  // The Research OS opt-in button itself is covered by AutonomyPanel.test.tsx.
  await json(request, 'put', '/api/research/os-settings', { enabled: true });
  await boot(page);
  const created = await topic(page, request, name);
  const base = `/api/research/topics/${created.id}`;
  await json(request, 'post', `${base}/papers/import`, { records: [
    { source: 'arxiv', source_id: `al-a-${Date.now()}`, title: 'Synthetic source A', abstract: 'Synthetic QA source A. No empirical claim.' },
    { source: 'arxiv', source_id: `al-b-${Date.now()}`, title: 'Synthetic source B', abstract: 'Synthetic QA source B. No empirical claim.' },
  ] });
  const pair = withProtocols ? await protocols(request, base, created.id) : { approved: '', replica: '' };
  await page.getByRole('button', { name: 'Autonomous Missions', exact: true }).click();
  await page.getByRole('button', { name: 'Workflows L1–L4', exact: true }).click();
  await expect(page.getByRole('checkbox', { name: 'Synthetic source B', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Enable Research OS', exact: true })).toHaveCount(0);
  return { base, id: created.id, pair };
}

async function protocols(request: APIRequestContext, base: string, topicId: string) {
  const spec = { topic_id: topicId, hypothesis: 'Disposable CPU browser QA', dataset: { side: 8, train_count: 2, validation_count: 2, test_count: 2 }, alphas: [0.5], max_trials: 4 };
  const first = await json(request, 'post', `${base}/protocols`, spec);
  const approved = await json(request, 'post', `${base}/protocols/${first.id}/approve`, { digest: first.digest, note: 'Test-only protocol approval' });
  const replica = await json(request, 'post', `${base}/protocols`, first.payload.spec);
  await json(request, 'post', `${base}/protocols/${replica.id}/approve`, { digest: replica.digest, note: 'Test-only reproduction approval' });
  return { approved: approved.id as string, replica: replica.id as string };
}

async function draft(page: Page, level: string, objective: string, protocol = '', reproduction = '') {
  await page.getByRole('combobox', { name: /^Interaction level/ }).selectOption(level);
  await page.getByRole('textbox', { name: 'Objective', exact: true }).fill(objective);
  await page.getByRole('textbox', { name: 'LM Studio model', exact: true }).fill(NO_MODEL);
  for (const source of ['Synthetic source A', 'Synthetic source B']) await page.getByRole('checkbox', { name: source, exact: true }).check();
  if (protocol) await page.getByRole('combobox', { name: /^Approved protocol \(optional\)/ }).selectOption(protocol);
  if (reproduction) await page.getByRole('combobox', { name: /^Separately approved reproduction protocol/ }).selectOption(reproduction);
  await page.getByRole('button', { name: 'Create draft', exact: true }).click();
}

const card = (page: Page, level: string) =>
  page.locator('#panel article').filter({ has: page.getByRole('heading', { name: new RegExp(`^${level} ·`) }) });

async function missions(request: APIRequestContext, base: string) {
  return (await json(request, 'get', `${base}/missions`)).missions as any[];
}

async function settled(request: APIRequestContext, base: string, level: string, states: string[]) {
  let mission: any;
  await expect.poll(async () => {
    mission = (await missions(request, base)).find(m => m.payload.spec.autonomy?.level === level);
    return mission?.status;
  }, { timeout: 60_000 }).toMatch(new RegExp(`^(${states.join('|')})$`));
  return mission;
}

async function approve(page: Page, level: string) {
  const c = card(page, level);
  const run = c.getByRole('button', { name: 'Approve plan and run', exact: true });
  await expect(run).toBeDisabled();  // a review note is required first
  await c.getByLabel('Review note', { exact: true }).fill(`Test-only ${level} approval after reading the plan.`);
  await run.click();
}

test('UI-AUTONOMY-001: each level drafts its own plan and L4 refuses a draft without a separate reproduction', async ({ page, request }) => {
  const { base, pair } = await setup(page, request, 'autonomy plans', true);
  await draft(page, 'L1', 'L1: compare the two synthetic sources.');
  await draft(page, 'L2', 'L2: compare the two synthetic sources.');
  await draft(page, 'L3', 'L3: compare the sources, then run the approved CPU protocol.', pair.approved);
  // L4 without its reproduction protocol: the panel explains and creates nothing.
  await draft(page, 'L4', 'L4: closure without reproduction.', pair.approved);
  await expect(page.locator('#panel').getByRole('alert')).toContainText('separately approved reproduction');
  await page.getByRole('combobox', { name: /^Separately approved reproduction protocol/ }).selectOption(pair.replica);
  await page.getByRole('button', { name: 'Create draft', exact: true }).click();
  await expect.poll(async () => (await missions(request, base)).length).toBe(4);

  const byLevel = Object.fromEntries((await missions(request, base)).map(m => [m.payload.spec.autonomy.level, m]));
  expect(Object.keys(byLevel).sort()).toEqual(['L1', 'L2', 'L3', 'L4']);
  const ids = (level: string) => byLevel[level].tasks.map((t: any) => t.id).sort();
  expect(ids('L1')).toEqual(['grounding', 'hypothesis']);
  expect(ids('L2')).toEqual(['grounding', 'hypothesis', 'integrity', 'report']);
  expect(ids('L3')).toEqual(['experiment', 'grounding', 'hypothesis', 'integrity', 'report', 'validation']);
  expect(ids('L4')).toEqual(['experiment', 'grounding', 'hypothesis', 'integrity', 'report', 'reproduction', 'validate_reproduction', 'validation']);
  for (const level of ['L1', 'L2', 'L3', 'L4']) {
    expect(byLevel[level].status).toBe('draft');
    expect(byLevel[level].tasks.every((t: any) => t.status === 'pending')).toBeTruthy();  // nothing runs before approval
    await expect(card(page, level).getByRole('status')).toContainText('draft');
  }
});

test('UI-AUTONOMY-002: L1 stops for review after every step and shows why a model step failed', async ({ page, request }) => {
  const { base } = await setup(page, request, 'autonomy L1');
  await draft(page, 'L1', 'L1: compare the two synthetic sources.');
  await approve(page, 'L1');
  let m = await settled(request, base, 'L1', ['awaiting_step_review']);
  expect(m.tasks.find((t: any) => t.id === 'grounding').status).toBe('completed');
  expect(m.tasks.find((t: any) => t.id === 'hypothesis').status).toBe('pending');  // waits for the researcher
  const c = card(page, 'L1');
  await c.getByLabel('Review note', { exact: true }).fill('');
  await expect(c.getByRole('button', { name: 'Accept step', exact: true })).toBeDisabled();  // a note is required
  await c.getByLabel('Review note', { exact: true }).fill('Grounding inspected; continue.');
  await c.getByRole('button', { name: 'Accept step', exact: true }).click();
  m = await settled(request, base, 'L1', ['failed', 'paused']);
  expect(m.tasks.find((t: any) => t.id === 'hypothesis').status).toBe('failed');
  // The researcher sees which step failed and the provider's own reason, not only "failed".
  // The wording is the provider's own (LM Studio missing, model not loaded, ...), so only its presence is required.
  await expect(c.getByRole('alert')).toContainText(/Step hypothesis failed: \S+/);
});

test('UI-AUTONOMY-003: L2 rejecting a step result cancels the workflow before the next step', async ({ page, request }) => {
  const { base } = await setup(page, request, 'autonomy L2');
  await draft(page, 'L2', 'L2: compare the two synthetic sources.');
  await approve(page, 'L2');
  await settled(request, base, 'L2', ['awaiting_step_review']);
  const c = card(page, 'L2');
  await c.getByLabel('Review note', { exact: true }).fill('Grounding does not cover the question; stop.');
  await c.getByRole('button', { name: 'Reject step', exact: true }).click();
  const m = await settled(request, base, 'L2', ['cancelled']);
  expect(m.tasks.filter((t: any) => t.id !== 'grounding').every((t: any) => t.status === 'pending')).toBeTruthy();
  await expect(c.getByRole('status')).toContainText('cancelled');
  await expect(c.getByRole('button', { name: 'Cancel workflow', exact: true })).toHaveCount(0);
});

test('UI-AUTONOMY-004: L3 coordinates without per-step review and reports the failing step', async ({ page, request }) => {
  const { base } = await setup(page, request, 'autonomy L3');
  await draft(page, 'L3', 'L3: compare the two synthetic sources.');
  await approve(page, 'L3');
  const m = await settled(request, base, 'L3', ['failed', 'paused', 'awaiting_review']);
  expect(m.status).not.toBe('awaiting_step_review');  // L3 has no per-step review
  expect(m.tasks.find((t: any) => t.id === 'grounding').status).toBe('completed');
  expect(m.tasks.find((t: any) => t.id === 'hypothesis').status).toBe('failed');
  expect(['report', 'integrity'].map(id => m.tasks.find((t: any) => t.id === id).status)).toEqual(['pending', 'pending']);
  const c = card(page, 'L3');
  await expect(c.getByRole('alert')).toContainText(/Step hypothesis failed: \S+/);
  await expect(c.getByRole('button', { name: 'Complete review', exact: true })).toHaveCount(0);  // nothing to sign off
});

test('UI-AUTONOMY-005: cancelling an L4 draft launches no task', async ({ page, request }) => {
  const { base, pair } = await setup(page, request, 'autonomy L4 cancel', true);
  await draft(page, 'L4', 'L4: closure, then cancel before approval.', pair.approved, pair.replica);
  await settled(request, base, 'L4', ['draft']);
  await card(page, 'L4').getByRole('button', { name: 'Cancel workflow', exact: true }).click();
  const m = await settled(request, base, 'L4', ['cancelled']);
  expect(m.tasks.every((t: any) => t.status === 'pending')).toBeTruthy();
  expect(m.payload.approval ?? null).toBeNull();  // never approved
});
