import { MODEL, test, expect, boot, json, topic } from './live';

test('four independent L1–L4 workflows execute real local inference and CPU reproduction', async ({ page, request }, info) => {
  test.setTimeout(600_000);
  await boot(page);
  const created = await topic(page, request, 'four live workflows');
  const base = `/api/research/topics/${created.id}`;
  // Explicit synthetic source/protocol fixtures, persisted by the actual backend.
  await json(request, 'post', `${base}/papers/import`, { records: [
    { source: 'arxiv', source_id: `pw-a-${Date.now()}`, title: 'Synthetic source A', abstract: 'A bounded synthetic QA protocol. No empirical scientific claim.' },
    { source: 'arxiv', source_id: `pw-b-${Date.now()}`, title: 'Synthetic source B', abstract: 'Independent synthetic QA description. Treat all conclusions as unverified.' },
  ] });
  const protocol = await json(request, 'post', `${base}/protocols`, { topic_id: created.id, hypothesis: 'Disposable CPU browser QA', dataset: { side: 8, train_count: 2, validation_count: 2, test_count: 2 }, alphas: [0.5], max_trials: 4 });
  const approved = await json(request, 'post', `${base}/protocols/${protocol.id}/approve`, { digest: protocol.digest, note: 'Simulated test-only human protocol approval' });
  const replica = await json(request, 'post', `${base}/protocols`, protocol.payload.spec);
  await json(request, 'post', `${base}/protocols/${replica.id}/approve`, { digest: replica.digest, note: 'Simulated separate reproduction approval' });
  await page.getByRole('button', { name: 'Autonomous Missions', exact: true }).click();
  await page.getByRole('button', { name: 'Workflows L1–L4', exact: true }).click();
  for (const level of ['L1', 'L2', 'L3', 'L4']) {
    await page.getByRole('combobox', { name: /^Interaction level/ }).selectOption(level);
    await page.getByRole('textbox', { name: 'Objective', exact: true }).fill(`${level}: compare the two synthetic sources in two sentences; state uncertainty. No numerical findings.`);
    for (const source of ['Synthetic source A', 'Synthetic source B']) await page.getByRole('checkbox', { name: source, exact: true }).check();
    if (level === 'L4') {
      await page.getByRole('combobox', { name: /^Approved protocol \(optional\)/ }).selectOption(approved.id);
      await page.getByRole('combobox', { name: /^Separately approved reproduction protocol/ }).selectOption(replica.id);
    }
    await page.getByRole('button', { name: 'Create draft', exact: true }).click();
    await expect(page.locator('#panel article').filter({ has: page.getByRole('heading', { name: new RegExp(`^${level} ·`) }) })).toContainText('draft');
  }
  const initial = (await json(request, 'get', `${base}/missions`)).missions;
  expect(initial).toHaveLength(4);
  expect(initial.every((m: any) => m.status === 'draft')).toBeTruthy();
  for (const level of ['L1', 'L2', 'L3', 'L4']) {
    const card = page.locator('#panel article').filter({ has: page.getByRole('heading', { name: new RegExp(`^${level} ·`) }) });
    await card.getByLabel('Review note', { exact: true }).fill('Simulated browser QA human approval after inspecting the disposable plan.');
    await card.getByRole('button', { name: 'Approve plan and run', exact: true }).click();
  }
  const states: unknown[] = [];
  const deadline = Date.now() + 480_000;
  let final: any[] = [];
  while (Date.now() < deadline) {
    final = (await json(request, 'get', `${base}/missions`)).missions;
    states.push({ at: new Date().toISOString(), missions: final.map(m => ({ id: m.id, status: m.status, tasks: m.tasks.map((t: any) => [t.id, t.status]) })) });
    for (const m of final) {
      expect(['failed', 'paused', 'interrupted', 'cancelled'], JSON.stringify(m)).not.toContain(m.status);
      const level = m.payload.spec.autonomy.level;
      const card = page.locator('#panel article').filter({ has: page.getByRole('heading', { name: new RegExp(`^${level} ·`) }) });
      if (m.status === 'awaiting_step_review') {
        await card.getByRole('button', { name: 'Accept step', exact: true }).click();
      } else if (m.status === 'awaiting_review') {
        await card.getByRole('button', { name: 'Complete review', exact: true }).click();
      }
    }
    if (final.every(m => m.status === 'completed')) break;
    await page.waitForResponse(res => res.url().endsWith(`${base}/missions`) && res.request().method() === 'GET');
  }
  await info.attach('workflow-states.json', { body: JSON.stringify(states, null, 2), contentType: 'application/json' });
  await info.attach('four-real-missions.json', { body: JSON.stringify(final, null, 2), contentType: 'application/json' });
  expect(final.every(m => m.status === 'completed')).toBeTruthy();
  for (const m of final) {
    expect(m.tasks.every((t: any) => t.status === 'completed' && t.payload.attempts === 1)).toBeTruthy();
    const output = m.tasks.find((t: any) => t.id === 'hypothesis').payload.result.output;
    expect(output).toMatchObject({ provider: 'local', model: MODEL });
    expect(output.text.trim().length).toBeGreaterThan(20);
    const card = page.locator('#panel article').filter({ has: page.getByRole('heading', { name: new RegExp(`^${m.payload.spec.autonomy.level} ·`) }) });
    await expect(card.getByRole('status')).toContainText('completed');
  }
  const l4 = final.find(m => m.payload.spec.autonomy.level === 'L4');
  expect(l4.tasks.filter((t: any) => ['experiment', 'reproduction', 'validation', 'validate_reproduction'].includes(t.id))).toHaveLength(4);
  await info.attach('completed-workflows.png', { body: await page.screenshot(), contentType: 'image/png' });
  await page.getByRole('button', { name: 'Back to Missions', exact: true }).click();
  await expect(page.locator('#panel')).toContainText('L4');
});

test('workflow cancellation and invalid draft validation do not launch a task', async ({ page, request }) => {
  await boot(page);
  await topic(page, request, 'cancel workflow');
  await page.getByRole('button', { name: 'Autonomous Missions', exact: true }).click();
  await page.getByRole('button', { name: 'Workflows L1–L4', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Create draft', exact: true })).toBeDisabled();
});
