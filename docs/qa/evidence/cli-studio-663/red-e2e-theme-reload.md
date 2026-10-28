# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cli_studio.spec.ts >> UI-CLI-LAYOUT-001: 360x740 en dark: prompt at the bottom, framed, nothing overlaps
- Location: e2e\cli_studio.spec.ts:106:7

# Error details

```
Error: expect(locator).toHaveAttribute(expected) failed

Locator:  locator('html')
Expected: "dark"
Received: ""
Timeout:  15000ms

Call log:
  - Expect "toHaveAttribute" locator('html') with timeout 15000ms
  - waiting for locator('html')
    33 × locator resolved to <html lang="en">…</html>
       - unexpected value "null"

```

```yaml
- document:
  - main
```

# Test source

```ts
  1   | import { test, expect } from './live';
  2   | import type { Page } from '@playwright/test';
  3   | 
  4   | // FQC-CLI-STUDIO-663: the CLI studio fills the main area, its prompt stays at the bottom, the transcript and every AI
  5   | // answer are framed, and nothing overlaps, clips or scrolls sideways (agent/PLAYWRIGHT_QA_CHECKLIST.md section 2).
  6   | // The 100-message conversation is a MOCKED fixture served by page.route; it checks layout, not model output.
  7   | const SID = 'as-0000c11663';
  8   | const LONG = 'Kết quả: label smoothing tăng độ chính xác 1,2–1,9 điểm nhưng ECE tăng 0,10–0,13. '.repeat(4);
  9   | 
  10  | let originalLanguage = 'vi';
  11  | test.beforeAll(async ({ request }) => { originalLanguage = (await (await request.get('/api/config')).json()).ui?.language || 'vi'; });
  12  | test.afterAll(async ({ request }) => { await request.post('/api/config', { data: { ui: { language: originalLanguage } } }); });
  13  | 
  14  | async function openCli(page: Page, language: 'vi' | 'en', theme: 'light' | 'dark', messages = 0) {
  15  |   // Language is a server setting; the theme is saved in the browser and restored at start-up.
  16  |   expect((await page.request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
  17  |   await page.addInitScript(([key, sid, th, n]) => {
  18  |     localStorage.setItem('pl.theme', th as string);
  19  |     if (n) localStorage.setItem(key as string, sid as string); else localStorage.removeItem(key as string);
  20  |   }, ['phdlab_cli_session', SID, theme, messages]);
  21  |   if (messages) {
  22  |     await page.route(`**/api/chat/sessions/${SID}`, route => route.fulfill({ json: {
  23  |       id: SID, title: 'CLI', settings: { provider: 'cli:codex' }, turns: [], approvals: [],
  24  |       messages: Array.from({ length: messages }, (_, i) => i % 2
  25  |         ? { id: `m${i}`, role: 'assistant', provider: 'cli:codex', content: `${i}. ${LONG}https://example.org/${'a'.repeat(120)}` }
  26  |         : { id: `m${i}`, role: 'user', content: `/lit câu hỏi số ${i} ${'x'.repeat(i === 0 ? 300 : 10)}` }),
  27  |     } }));
  28  |   }
  29  |   await page.goto('/dist/react.html');  // boot() expects English labels; this spec runs both languages
  30  |   await expect(page.locator('#live.active')).toBeAttached();
  31  |   const name = language === 'vi' ? 'Chat CLI' : 'CLI chat';
  32  |   const sidebar = page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true });
  33  |   const openSidebar = page.getByRole('button', { name: language === 'vi' ? 'Mở thanh bên' : 'Open sidebar', exact: true });
  34  |   await expect(sidebar.or(openSidebar).first()).toBeVisible();  // wait for the shell before deciding
  35  |   if (!(await sidebar.isVisible())) await openSidebar.click();
  36  |   await sidebar.getByRole('button', { name, exact: true }).click();
  37  |   const prompt = page.getByRole('form', { name: language === 'vi' ? 'Lệnh CLI' : 'CLI command' });
  38  |   await expect(prompt).toBeVisible();
> 39  |   await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      |                                      ^ Error: expect(locator).toHaveAttribute(expected) failed
  40  |   return prompt;
  41  | }
  42  | 
  43  | async function layoutFindings(page: Page) {
  44  |   return page.evaluate(() => {
  45  |     const out: string[] = [];
  46  |     const form = document.querySelector('form[aria-label]') as HTMLElement;
  47  |     const root = form.parentElement as HTMLElement;
  48  |     const log = root.querySelector('[role=log]') as HTMLElement;
  49  |     const r = root.getBoundingClientRect(), f = form.getBoundingClientRect();
  50  |     if (r.bottom - f.bottom > 16) out.push(`prompt ${Math.round(r.bottom - f.bottom)}px above the bottom`);
  51  |     if (root.lastElementChild !== form) out.push('prompt is not the last block');
  52  |     if (getComputedStyle(log).borderTopWidth !== '1px') out.push('transcript has no frame');
  53  |     for (const a of Array.from(log.querySelectorAll('article'))) {
  54  |       if (getComputedStyle(a).borderTopWidth !== '1px') { out.push('answer has no frame'); break; }
  55  |     }
  56  |     const page = document.scrollingElement as HTMLElement;
  57  |     if (page.scrollWidth > innerWidth + 1) out.push(`page scrolls sideways ${page.scrollWidth}>${innerWidth}`);
  58  |     if (root.scrollWidth > root.clientWidth + 1) out.push(`studio scrolls sideways ${root.scrollWidth}>${root.clientWidth}`);
  59  |     for (const el of Array.from(root.querySelectorAll<HTMLElement>('button, input, label, [role=radio]'))) {
  60  |       const b = el.getBoundingClientRect();
  61  |       if (!b.width || !b.height || getComputedStyle(el).visibility === 'hidden') continue;
  62  |       // Items of a scrolling region (transcript, one-line strips on phones) may sit outside the view; the region may not.
  63  |       const inScroller = log.contains(el) || !!el.closest('.cli-strip');
  64  |       if (!inScroller && (b.left < -1 || b.right > innerWidth + 1 || b.top < -1 || b.bottom > innerHeight + 1)) {
  65  |         out.push(`off screen: ${el.textContent?.trim().slice(0, 30) || el.getAttribute('aria-label')}`);
  66  |         continue;
  67  |       }
  68  |       if (inScroller) continue;
  69  |       const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
  70  |       if (hit && hit !== el && !el.contains(hit) && !hit.contains(el) && !(el.tagName === 'INPUT' && hit.closest('label')?.contains(el))) {
  71  |         out.push(`covered: ${el.textContent?.trim().slice(0, 30) || el.getAttribute('aria-label')} by ${hit.textContent?.trim().slice(0, 30)}`);
  72  |       }
  73  |     }
  74  |     // VIS-OVERLAP: visible text and controls outside the scrolling regions never intersect each other.
  75  |     const handle = document.getElementById('floating-drawer-toggle');
  76  |     const boxes = [...Array.from(root.querySelectorAll<HTMLElement>('header h2, header span, header button, form button, form input, form > div > div')),
  77  |       ...(handle ? [handle] : [])]
  78  |       .filter(el => !el.closest('.cli-strip') && getComputedStyle(el).display !== 'none')
  79  |       .map(el => ({ el, b: el.getBoundingClientRect() })).filter(x => x.b.width && x.b.height);
  80  |     for (let i = 0; i < boxes.length; i++) {
  81  |       for (let j = i + 1; j < boxes.length; j++) {
  82  |         const [p, q] = [boxes[i], boxes[j]];
  83  |         if (p.el.contains(q.el) || q.el.contains(p.el)) continue;
  84  |         const w = Math.min(p.b.right, q.b.right) - Math.max(p.b.left, q.b.left);
  85  |         const h = Math.min(p.b.bottom, q.b.bottom) - Math.max(p.b.top, q.b.top);
  86  |         if (w > 1 && h > 1) out.push(`overlap: ${p.el.textContent?.trim().slice(0, 20)} / ${q.el.textContent?.trim().slice(0, 20) || q.el.getAttribute('aria-label')}`);
  87  |       }
  88  |     }
  89  |     for (const strip of Array.from(root.querySelectorAll<HTMLElement>('.cli-strip'))) {
  90  |       const b = strip.getBoundingClientRect();
  91  |       if (b.left < -1 || b.right > innerWidth + 1) out.push(`strip off screen: ${strip.getAttribute('aria-label')}`);
  92  |     }
  93  |     for (const el of Array.from(root.querySelectorAll<HTMLElement>('button, label, h2'))) {
  94  |       if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).textOverflow !== 'ellipsis') out.push(`clipped: ${el.textContent?.trim().slice(0, 30)}`);
  95  |     }
  96  |     const title = root.querySelector('header h2') as HTMLElement;
  97  |     if (title.scrollWidth > title.clientWidth + 1) out.push(`title truncated to ${Math.round(title.clientWidth)}px`);
  98  |     if (/undefined|NaN|\[object Object\]/.test(root.innerText)) out.push('junk text');
  99  |     return out;
  100 |   });
  101 | }
  102 | 
  103 | for (const [width, height] of [[1440, 900], [1024, 768], [390, 844], [360, 740]] as const) {
  104 |   for (const language of ['vi', 'en'] as const) {
  105 |     for (const theme of ['light', 'dark'] as const) {
  106 |       test(`UI-CLI-LAYOUT-001: ${width}x${height} ${language} ${theme}: prompt at the bottom, framed, nothing overlaps`, async ({ page, request }, info) => {
  107 |         expect((await request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
  108 |         await page.setViewportSize({ width, height });
  109 |         await openCli(page, language, theme);
  110 |         expect(await layoutFindings(page)).toEqual([]);
  111 |         if (language === 'en') await expect(page.locator('form[aria-label]').locator('..')).not.toContainText(/Khảo sát|Đề cương|Quy trình|Xóa màn hình/);
  112 |         await info.attach(`cli-${width}-${language}-${theme}.png`, { body: await page.screenshot(), contentType: 'image/png' });
  113 |       });
  114 |     }
  115 |   }
  116 | }
  117 | 
  118 | for (const [width, height] of [[1440, 900], [390, 844]] as const) {
  119 |   test(`UI-CLI-LAYOUT-002: ${width}px with 100 messages keeps the prompt fixed and scrolls the transcript`, async ({ page, request }, info) => {
  120 |     expect((await request.post('/api/config', { data: { ui: { language: 'vi' } } })).ok()).toBeTruthy();
  121 |     await page.setViewportSize({ width, height });
  122 |     await openCli(page, 'vi', 'light', 100);
  123 |     const log = page.getByRole('log', { name: 'Hội thoại CLI' });
  124 |     await expect(log.getByRole('article')).toHaveCount(50);
  125 |     await expect.poll(() => log.evaluate(el => el.scrollHeight - el.clientHeight - el.scrollTop)).toBeLessThan(4);
  126 |     expect(await layoutFindings(page)).toEqual([]);
  127 |     await expect(log.getByRole('article').last()).toContainText('ChatGPT (OpenAI Codex CLI)');
  128 |     await info.attach(`cli-100-${width}.png`, { body: await page.screenshot(), contentType: 'image/png' });
  129 |   });
  130 | }
  131 | 
  132 | test('UI-CLI-SUGGEST-001: command suggestions open above the prompt and stay on screen', async ({ page, request }) => {
  133 |   expect((await request.post('/api/config', { data: { ui: { language: 'vi' } } })).ok()).toBeTruthy();
  134 |   await page.setViewportSize({ width: 390, height: 844 });
  135 |   const prompt = await openCli(page, 'vi', 'light');
  136 |   await prompt.getByRole('textbox').fill('/');
  137 |   const list = page.getByRole('listbox', { name: 'Gợi ý lệnh' });
  138 |   await expect(list).toBeVisible();
  139 |   const [l, p] = [await list.boundingBox(), await prompt.boundingBox()];
```