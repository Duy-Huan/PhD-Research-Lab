import { test, expect, boot, studio } from './live';

test('Harness Studio All-in-One IDE: Templates, Team Builder, Node Inspector and AI Architect', async ({ page }) => {
  test.setTimeout(120_000);
  await boot(page);

  // 1. Navigate to Harness Studio Full Space
  await page.getByRole('button', { name: 'Harness Studio', exact: true }).click();
  await expect(page.getByText(/Harness Studio & (Thiết kế Quy trình|Workflow Builder)/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('button', { name: /Chạy Harness|Run Harness/i })).toBeVisible();

  // 2. Explore Template Library & Load a Template into Canvas
  await page.getByRole('button', { name: 'Templates', exact: true }).click();
  await expect(page.getByText(/7 Mẫu quy trình nghiên cứu khoa học chuẩn/i)).toBeVisible();
  await expect(page.locator('b').filter({ hasText: /Idea to Hypothesis/i }).first()).toBeVisible();
  await expect(page.locator('b').filter({ hasText: /Literature Review/i }).first()).toBeVisible();

  // Load "Idea to Hypothesis" template into Canvas
  const loadTemplateBtn = page.getByRole('button', { name: 'Tải vào Canvas', exact: true }).first();
  await loadTemplateBtn.click();
  // Verify React Flow canvas has rendered nodes (Idea to Hypothesis template has 7 nodes)
  await expect(page.locator('.react-flow__node')).toHaveCount(7, { timeout: 10_000 });

  // 3. Inspect Node details
  await expect(page.getByRole('button', { name: 'Cấu hình Node', exact: true })).toBeVisible();
  const firstNode = page.locator('.react-flow__node').first();
  await firstNode.click();
  await expect(page.getByText(/Cấu hình \(/i)).toBeVisible();

  // 4. Dynamic Agent Team Builder: Create a custom agent profile and add to canvas
  await page.getByRole('button', { name: 'Team', exact: true }).click();
  await expect(page.getByRole('button', { name: '+ Tạo Agent', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '+ Tạo Agent', exact: true }).click();

  // Fill in agent creation modal
  await expect(page.getByRole('heading', { name: 'Tạo Chuyên gia AI Nghiên cứu Mới' })).toBeVisible();
  const agentName = `Quantum Specialist ${Date.now()}`;
  await page.getByPlaceholder('VD: Chuyên gia Phân tích Thống kê').fill(agentName);
  await page.getByPlaceholder('Mô tả phạm vi trách nhiệm của agent...').fill('Phân tích thuật toán VQE và lượng tử hóa Hamiltonian');
  await page.getByRole('button', { name: 'Lưu Agent Profile', exact: true }).click();

  // Verify new agent is listed in the team
  await expect(page.getByText(agentName)).toBeVisible({ timeout: 10_000 });
  // Add agent as task node to canvas
  const agentCard = page.locator('div').filter({ hasText: agentName }).last();
  const addToCanvasBtn = agentCard.getByRole('button', { name: '+ Canvas', exact: true });
  if (await addToCanvasBtn.isVisible()) {
    await addToCanvasBtn.click();
    // Count should increase to 8
    await expect(page.locator('.react-flow__node')).toHaveCount(8, { timeout: 10_000 });
  }

  // 5. AI Workflow Architect: Generate DAG from research objective
  await page.getByRole('button', { name: 'AI Architect', exact: true }).click();
  await page.getByPlaceholder('VD: Khảo sát và tối ưu hóa suy luận mô hình DeepSeek R1 trên phần cứng biên...').fill('Tự động hóa nghiên cứu và thực nghiệm benchmark giải thuật lượng tử VQE trên phân tử H2O');
  
  const generateBtn = page.getByRole('button', { name: 'AI Thiết kế Quy trình', exact: true });
  await expect(generateBtn).toBeEnabled();
  await generateBtn.click();

  // Expect generated workflow card to appear
  await expect(page.getByText(/Tải vào Canvas & Chỉnh sửa/i)).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Tải vào Canvas & Chỉnh sửa', exact: true }).click();

  // Verify newly architected DAG loaded into canvas
  const nodeCount = await page.locator('.react-flow__node').count();
  expect(nodeCount).toBeGreaterThanOrEqual(4);
});

