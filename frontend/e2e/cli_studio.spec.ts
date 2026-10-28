import { test, expect } from './live';
import type { Page } from '@playwright/test';

// FQC-CLI-STUDIO-663: the CLI studio fills the main area, its prompt stays at the bottom, the transcript and every AI
// answer are framed, and nothing overlaps, clips or scrolls sideways (agent/PLAYWRIGHT_QA_CHECKLIST.md section 2).
// The 100-message conversation is a MOCKED fixture served by page.route; it checks layout, not model output.
const SID = 'as-0000c11663';
const LONG = 'Kết quả: label smoothing tăng độ chính xác 1,2–1,9 điểm nhưng ECE tăng 0,10–0,13. '.repeat(4);

let originalLanguage = 'vi';
test.beforeAll(async ({ request }) => { originalLanguage = (await (await request.get('/api/config')).json()).ui?.language || 'vi'; });
test.afterAll(async ({ request }) => { await request.post('/api/config', { data: { ui: { language: originalLanguage } } }); });

async function openCli(page: Page, language: 'vi' | 'en', theme: 'light' | 'dark', messages = 0) {
  // Language is a server setting; the theme is saved in the browser and restored at start-up.
  expect((await page.request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
  await page.addInitScript(([key, sid, th, n]) => {
    localStorage.setItem('pl.theme', th as string);
    if (n) localStorage.setItem(key as string, sid as string); else localStorage.removeItem(key as string);
  }, ['phdlab_cli_session', SID, theme, messages]);
  if (messages) {
    await page.route(`**/api/chat/sessions/${SID}`, route => route.fulfill({ json: {
      id: SID, title: 'CLI', settings: { provider: 'cli:codex' }, turns: [], approvals: [],
      messages: Array.from({ length: messages }, (_, i) => i % 2
        ? { id: `m${i}`, role: 'assistant', provider: 'cli:codex', content: `${i}. ${LONG}https://example.org/${'a'.repeat(120)}` }
        : { id: `m${i}`, role: 'user', content: `/lit câu hỏi số ${i} ${'x'.repeat(i === 0 ? 300 : 10)}` }),
    } }));
  }
  await page.goto('/dist/react.html');  // boot() expects English labels; this spec runs both languages
  await expect(page.locator('#live.active')).toBeAttached();
  const name = language === 'vi' ? 'Chat CLI' : 'CLI chat';
  const sidebar = page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true });
  const openSidebar = page.getByRole('button', { name: language === 'vi' ? 'Mở thanh bên' : 'Open sidebar', exact: true });
  await expect(sidebar.or(openSidebar).first()).toBeVisible();  // wait for the shell before deciding
  if (!(await sidebar.isVisible())) await openSidebar.click();
  await sidebar.getByRole('button', { name, exact: true }).click();
  const prompt = page.getByRole('form', { name: language === 'vi' ? 'Lệnh CLI' : 'CLI command' });
  await expect(prompt).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
  return prompt;
}

async function layoutFindings(page: Page) {
  return page.evaluate(() => {
    const out: string[] = [];
    const form = document.querySelector('form[aria-label]') as HTMLElement;
    const root = form.parentElement as HTMLElement;
    const log = root.querySelector('[role=log]') as HTMLElement;
    const r = root.getBoundingClientRect(), f = form.getBoundingClientRect();
    if (r.bottom - f.bottom > 16) out.push(`prompt ${Math.round(r.bottom - f.bottom)}px above the bottom`);
    if (root.lastElementChild !== form) out.push('prompt is not the last block');
    if (getComputedStyle(log).borderTopWidth !== '1px') out.push('transcript has no frame');
    for (const a of Array.from(log.querySelectorAll('article'))) {
      if (getComputedStyle(a).borderTopWidth !== '1px') { out.push('answer has no frame'); break; }
    }
    const page = document.scrollingElement as HTMLElement;
    if (page.scrollWidth > innerWidth + 1) out.push(`page scrolls sideways ${page.scrollWidth}>${innerWidth}`);
    if (root.scrollWidth > root.clientWidth + 1) out.push(`studio scrolls sideways ${root.scrollWidth}>${root.clientWidth}`);
    for (const el of Array.from(root.querySelectorAll<HTMLElement>('button, input, label, [role=radio]'))) {
      const b = el.getBoundingClientRect();
      if (!b.width || !b.height || getComputedStyle(el).visibility === 'hidden') continue;
      // Items of a scrolling region (transcript, one-line strips on phones) may sit outside the view; the region may not.
      const inScroller = log.contains(el) || !!el.closest('.cli-strip');
      if (!inScroller && (b.left < -1 || b.right > innerWidth + 1 || b.top < -1 || b.bottom > innerHeight + 1)) {
        out.push(`off screen: ${el.textContent?.trim().slice(0, 30) || el.getAttribute('aria-label')}`);
        continue;
      }
      if (inScroller) continue;
      const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
      if (hit && hit !== el && !el.contains(hit) && !hit.contains(el) && !(el.tagName === 'INPUT' && hit.closest('label')?.contains(el))) {
        out.push(`covered: ${el.textContent?.trim().slice(0, 30) || el.getAttribute('aria-label')} by ${hit.textContent?.trim().slice(0, 30)}`);
      }
    }
    // VIS-OVERLAP: visible text and controls outside the scrolling regions never intersect each other.
    const handle = document.getElementById('floating-drawer-toggle');
    const boxes = [...Array.from(root.querySelectorAll<HTMLElement>('header h2, header span, header button, form button, form input, form > div > div')),
      ...(handle ? [handle] : [])]
      .filter(el => !el.closest('.cli-strip') && getComputedStyle(el).display !== 'none')
      .map(el => ({ el, b: el.getBoundingClientRect() })).filter(x => x.b.width && x.b.height);
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const [p, q] = [boxes[i], boxes[j]];
        if (p.el.contains(q.el) || q.el.contains(p.el)) continue;
        const w = Math.min(p.b.right, q.b.right) - Math.max(p.b.left, q.b.left);
        const h = Math.min(p.b.bottom, q.b.bottom) - Math.max(p.b.top, q.b.top);
        if (w > 1 && h > 1) out.push(`overlap: ${p.el.textContent?.trim().slice(0, 20)} / ${q.el.textContent?.trim().slice(0, 20) || q.el.getAttribute('aria-label')}`);
      }
    }
    for (const strip of Array.from(root.querySelectorAll<HTMLElement>('.cli-strip'))) {
      const b = strip.getBoundingClientRect();
      if (b.left < -1 || b.right > innerWidth + 1) out.push(`strip off screen: ${strip.getAttribute('aria-label')}`);
    }
    for (const el of Array.from(root.querySelectorAll<HTMLElement>('button, label, h2'))) {
      if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).textOverflow !== 'ellipsis') out.push(`clipped: ${el.textContent?.trim().slice(0, 30)}`);
    }
    const title = root.querySelector('header h2') as HTMLElement;
    if (title.scrollWidth > title.clientWidth + 1) out.push(`title truncated to ${Math.round(title.clientWidth)}px`);
    if (/undefined|NaN|\[object Object\]/.test(root.innerText)) out.push('junk text');
    return out;
  });
}

for (const [width, height] of [[1440, 900], [1024, 768], [390, 844], [360, 740]] as const) {
  for (const language of ['vi', 'en'] as const) {
    for (const theme of ['light', 'dark'] as const) {
      test(`UI-CLI-LAYOUT-001: ${width}x${height} ${language} ${theme}: prompt at the bottom, framed, nothing overlaps`, async ({ page, request }, info) => {
        expect((await request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
        await page.setViewportSize({ width, height });
        await openCli(page, language, theme);
        expect(await layoutFindings(page)).toEqual([]);
        if (language === 'en') await expect(page.locator('form[aria-label]').locator('..')).not.toContainText(/Khảo sát|Đề cương|Quy trình|Xóa màn hình/);
        await info.attach(`cli-${width}-${language}-${theme}.png`, { body: await page.screenshot(), contentType: 'image/png' });
      });
    }
  }
}

for (const [width, height] of [[1440, 900], [390, 844]] as const) {
  test(`UI-CLI-LAYOUT-002: ${width}px with 100 messages keeps the prompt fixed and scrolls the transcript`, async ({ page, request }, info) => {
    expect((await request.post('/api/config', { data: { ui: { language: 'vi' } } })).ok()).toBeTruthy();
    await page.setViewportSize({ width, height });
    await openCli(page, 'vi', 'light', 100);
    const log = page.getByRole('log', { name: 'Hội thoại CLI' });
    await expect(log.getByRole('article')).toHaveCount(50);
    await expect.poll(() => log.evaluate(el => el.scrollHeight - el.clientHeight - el.scrollTop)).toBeLessThan(4);
    expect(await layoutFindings(page)).toEqual([]);
    await expect(log.getByRole('article').last()).toContainText('ChatGPT (OpenAI Codex CLI)');
    await info.attach(`cli-100-${width}.png`, { body: await page.screenshot(), contentType: 'image/png' });
  });
}

test('UI-CLI-SUGGEST-001: command suggestions open above the prompt and stay on screen', async ({ page, request }) => {
  expect((await request.post('/api/config', { data: { ui: { language: 'vi' } } })).ok()).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  const prompt = await openCli(page, 'vi', 'light');
  await prompt.getByRole('textbox').fill('/');
  const list = page.getByRole('listbox', { name: 'Gợi ý lệnh' });
  await expect(list).toBeVisible();
  const [l, p] = [await list.boundingBox(), await prompt.boundingBox()];
  expect(l!.y + l!.height).toBeLessThanOrEqual(p!.y + 1);
  expect(l!.y).toBeGreaterThanOrEqual(0);
  await prompt.getByRole('textbox').press('Escape');
  await expect(list).toBeHidden();
});
