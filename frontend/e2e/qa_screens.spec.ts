import AxeBuilder from '@axe-core/playwright';
import { test, expect } from './live';
import type { Page } from '@playwright/test';
import { settle, uiAudit } from './uiAudit';

// agent/PLAYWRIGHT_QA_CHECKLIST.md section 4: every main view, Settings tab and drawer panel, opened from its normal
// entry point, audited with the section 2 rules (uiAudit) in both languages and themes, desktop and phone.
// The 3D lab runs in its own phase (office3d.spec.ts) and is not part of this inventory.
type Lang = 'vi' | 'en';
const L = (vi: string, en: string) => ({ vi, en });
const SIDEBAR = L('Thanh bên', 'Sidebar');

async function sidebar(page: Page, lang: Lang) {
  const side = page.getByRole('complementary', { name: SIDEBAR[lang], exact: true });
  const open = page.getByRole('button', { name: lang === 'vi' ? 'Mở thanh bên' : 'Open sidebar', exact: true });
  await expect(side.or(open).first()).toBeVisible();  // wait for the shell before deciding
  if (!(await side.isVisible())) await open.click();
  await expect(side).toBeVisible();
  return side;
}
const header = (title: { vi: string; en: string }) => async (page: Page, lang: Lang) =>
  page.getByTitle(title[lang], { exact: true }).first().click();
const side = (label: { vi: string; en: string }) => async (page: Page, lang: Lang) =>
  (await sidebar(page, lang)).getByRole('button', { name: label[lang], exact: true }).click();
const studio = (label: { vi: string; en: string }) => async (page: Page, lang: Lang) => {
  await (await sidebar(page, lang)).locator('#nav-toggle').click();
  await page.locator('.side-nav').getByRole('button', { name: label[lang] }).first().click();
};
const settingsTab = (label: { vi: string; en: string }) => async (page: Page, lang: Lang) => {
  await (await sidebar(page, lang)).getByRole('button', { name: lang === 'vi' ? 'Cài đặt Hệ thống' : 'System Settings', exact: true }).click();
  await page.getByRole('button', { name: new RegExp('^' + label[lang].replace(/[&]/g, '\\&')) }).first().click();
};

const SCREENS: Array<[string, (page: Page, lang: Lang) => Promise<unknown>]> = [
  ['chat', async () => {}],
  ['library-view', header(L('Thư viện Bài báo & Tài liệu', 'Paper Library & Documents'))],
  ['review', header(L('Hội đồng Bình duyệt R1–R3 & LaTeX', 'Peer Review R1–R3 & LaTeX'))],
  ['dashboard', header(L('Bảng điều khiển Hệ thống', 'System Dashboard'))],
  ['harness', async (page, lang) => page.getByRole('button', { name: 'Harness Studio', exact: true }).click()],
  ['cli', side(L('Chat CLI', 'CLI chat'))],
  ['settings-models', settingsTab(L('Mô hình & Tác nhân AI', 'Models & AI Agents'))],
  ['settings-ai-tools', settingsTab(L('Công cụ AI', 'AI tools'))],
  ['settings-engines', settingsTab(L('Công cụ Nghiên cứu', 'Research Engines'))],
  ['settings-search', settingsTab(L('Tìm kiếm & Xếp hạng', 'Search & Ranking'))],
  ['settings-hardware', settingsTab(L('Thí nghiệm & Phần cứng', 'Experiments & Hardware'))],
  ['settings-memory', settingsTab(L('Bộ nhớ & Ngữ cảnh', 'Memory & Context'))],
  ['settings-mcp', settingsTab(L('MCP & Tường lửa Bảo mật', 'MCP & Security Firewall'))],
  ['settings-skills', settingsTab(L('Kỹ năng & Tiện ích mở rộng', 'Skills & Plugins'))],
  ['settings-look', settingsTab(L('Giao diện & Ngôn ngữ', 'Appearance & Language'))],
  ['drawer-outline', header(L('Đề cương Nghiên cứu 5 Cấp độ', '5-Level Research Outline'))],
  ['drawer-library', header(L('Thư viện PDF & Tìm kiếm bài báo', 'PDF Library & Paper Search'))],
  ['drawer-figures', header(L('Xưởng Đồ họa Khoa học', 'Figure Studio'))],
  ['drawer-code', header(L('Mã nguồn & thí nghiệm native', 'Native code & experiments'))],
  ['drawer-intelligence', header(L('Trung tâm Phân tích Tri thức', 'Unified Research Intelligence'))],
  ['drawer-guide', header(L('Hướng dẫn Người dùng & Sổ tay Nghiên cứu', 'User Guide & Beginner Onboarding'))],
  ['drawer-topics', async page => page.locator('#topic-btn').click()],
  ['drawer-missions', side(L('Nhiệm vụ Tự hành', 'Autonomous Missions'))],
  ['drawer-paperorchestra', side(L('PaperOrchestra Studio', 'PaperOrchestra Studio'))],
  ['drawer-projects', async (page, lang) => (await sidebar(page, lang)).getByTitle(lang === 'vi' ? /^Không gian làm việc:/ : /^Workspace:/).click()],
  ['drawer-workstreams', studio(L('Luồng công việc', 'Workstreams'))],
  ['drawer-protocols', studio(L('Giao thức nghiên cứu', 'Protocols'))],
  ['drawer-claims', studio(L('Luận điểm & Bằng chứng', 'Claims & Evidence'))],
  ['drawer-paper', studio(L('Bản thảo LaTeX', 'Paper LaTeX'))],
];

const MATRIX: Array<{ lang: Lang; theme: 'light' | 'dark'; width: number; height: number; axe?: boolean }> = [
  { lang: 'en', theme: 'light', width: 1440, height: 900, axe: true },
  { lang: 'en', theme: 'dark', width: 1440, height: 900 },
  { lang: 'en', theme: 'light', width: 390, height: 844 },
  { lang: 'vi', theme: 'light', width: 1440, height: 900, axe: true },
  { lang: 'vi', theme: 'dark', width: 390, height: 844 },
];

let originalLanguage = 'vi';
test.beforeAll(async ({ request }) => { originalLanguage = (await (await request.get('/api/config')).json()).ui?.language || 'vi'; });
test.afterAll(async ({ request }) => { await request.post('/api/config', { data: { ui: { language: originalLanguage } } }); });

// Panels whose content appears only once a research topic is selected (disposable topic created through the API).
const TOPIC_SCREENS = SCREENS.filter(([name]) => ['drawer-figures', 'drawer-intelligence', 'drawer-workstreams', 'drawer-claims',
  'drawer-protocols', 'drawer-missions', 'drawer-outline', 'drawer-code', 'drawer-library', 'drawer-paper', 'drawer-topics', 'chat']
  .includes(name)).map(([name, open]) => [name + '+topic', open] as [string, typeof open]);
const TOPIC_MATRIX = MATRIX.filter(cell => cell.theme === 'light');
let topicTitle = '';
test.beforeAll(async ({ request }) => {
  topicTitle = `QA 6.6.3 diffusion calibration ${Date.now()}`;
  // One project holds exactly one paper/topic, so the QA topic gets its own disposable project (as live.ts does).
  expect((await request.post('/api/projects', { data: { name: `qa-663-${Date.now()}` } })).ok()).toBeTruthy();
  const response = await request.post('/api/research/topics', { data: {
    title: topicTitle, description: 'Disposable QA topic: label smoothing and calibration of diffusion classifiers',
    keywords: ['calibration', 'label smoothing'], sources: ['arxiv'] } });
  expect(response.ok(), await response.text()).toBeTruthy();
});

async function selectTopic(page: Page) {
  await page.locator('#topic-btn').click();
  await page.locator('#panel').getByText(topicTitle, { exact: true }).click();
  await expect(page.locator('#topic-btn')).toContainText(topicTitle.slice(0, 12));
  await page.locator('#drawer-close-btn').click();
}

const RUNS: Array<[typeof MATRIX[number], string, (page: Page, lang: Lang) => Promise<unknown>, boolean]> = [
  ...MATRIX.flatMap(cell => SCREENS.map(([n, o]) => [cell, n, o, false] as [typeof cell, string, typeof o, boolean])),
  ...TOPIC_MATRIX.flatMap(cell => TOPIC_SCREENS.map(([n, o]) => [cell, n, o, true] as [typeof cell, string, typeof o, boolean])),
];

for (const [cell, screen, open, withTopic] of RUNS) {
  {
    test(`UI-QA-SCREEN-001: ${screen} ${cell.lang} ${cell.theme} ${cell.width}px`, async ({ page }, info) => {
      expect((await page.request.post('/api/config', { data: { ui: { language: cell.lang } } })).ok()).toBeTruthy();
      await page.addInitScript(theme => localStorage.setItem('pl.theme', theme), cell.theme);
      await page.setViewportSize({ width: cell.width, height: cell.height });
      await page.goto('/dist/react.html');
      await expect(page.locator('#live.active')).toBeAttached();
      await expect(page.locator('html')).toHaveAttribute('data-theme', cell.theme);
      if (withTopic) await selectTopic(page);
      await open(page, cell.lang);
      await settle(page);  // measure once data has loaded and enter animations have finished
      const findings = await uiAudit(page, cell.lang);
      if (cell.axe) {
        const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).exclude('canvas').analyze();
        for (const v of axe.violations.filter(v => ['serious', 'critical'].includes(v.impact || ''))) {
          findings.push(`AXE-${v.id}: ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(' ')}`.slice(0, 200));
        }
      }
      await info.attach(`${screen}.png`, { body: await page.screenshot(), contentType: 'image/png' });
      await info.attach('findings.json', { body: JSON.stringify(findings, null, 2), contentType: 'application/json' });
      expect(findings).toEqual([]);
    });
  }
}
