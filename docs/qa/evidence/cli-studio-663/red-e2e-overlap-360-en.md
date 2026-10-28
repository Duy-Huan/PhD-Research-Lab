# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cli_studio.spec.ts >> UI-CLI-LAYOUT-001: 360x740 en dark: prompt at the bottom, framed, nothing overlaps
- Location: e2e\cli_studio.spec.ts:93:7

# Error details

```
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 3

- Array []
+ Array [
+   "overlap: CLI chat / Open in cmd",
+ ]
```

# Page snapshot

```yaml
- main [ref=e7]:
  - generic [ref=e8]:
    - generic [ref=e9]:
      - button "Open sidebar" [ref=e10] [cursor=pointer]
      - button "Topic SKB" [ref=e12] [cursor=pointer]
    - generic [ref=e16]:
      - button "Chat" [ref=e17] [cursor=pointer]
      - button "Library" [ref=e20] [cursor=pointer]
      - button "3D Lab" [ref=e23] [cursor=pointer]
      - button "Harness Studio" [ref=e27] [cursor=pointer]
      - button "Peer Review R1–R3 & LaTeX" [ref=e29] [cursor=pointer]
      - button "System Dashboard" [ref=e33] [cursor=pointer]
    - generic [ref=e37]:
      - generic [ref=e38]:
        - button "5-Level Research Outline" [ref=e39] [cursor=pointer]
        - button "PDF Library & Paper Search" [ref=e43] [cursor=pointer]
        - button "Figure Studio" [ref=e46] [cursor=pointer]
        - button "Native code & experiments" [ref=e49] [cursor=pointer]
        - button "Unified Research Intelligence" [ref=e52] [cursor=pointer]
      - button "EN — Switch language VI / ENG" [ref=e56] [cursor=pointer]: EN
      - button "100% — UI Display Scale" [ref=e57] [cursor=pointer]:
        - generic [ref=e61]: 100%
      - button "User Guide & Beginner Onboarding" [ref=e62] [cursor=pointer]
      - generic "Connected to PhD Lab server" [ref=e66]
      - button "Tools panel — Inspector Drawer" [ref=e67] [cursor=pointer]:
        - generic [ref=e71]: Tools panel
  - generic [ref=e72]:
    - generic [ref=e73]:
      - generic [ref=e74]:
        - generic [ref=e75]:
          - heading "CLI chat" [level=2] [ref=e78]
          - generic "Default project"
        - generic [ref=e79]:
          - button "Open in cmd" [ref=e80] [cursor=pointer]
          - button "Clear screen" [ref=e83] [cursor=pointer]
          - button "New session" [ref=e87] [cursor=pointer]
      - generic [ref=e89]:
        - radiogroup "CLI provider" [ref=e90]:
          - status [ref=e91]: Checking CLI tools…
        - button "Open external terminal" [ref=e92] [cursor=pointer]
      - group "Workflows" [ref=e95]:
        - button [ref=e96] [cursor=pointer]:
          - generic [ref=e99]:
            - text: Literature
            - code [ref=e100]: /lit
        - button [ref=e101] [cursor=pointer]:
          - generic [ref=e105]:
            - text: Outline
            - code [ref=e106]: /outline
        - button [ref=e107] [cursor=pointer]:
          - generic [ref=e111]:
            - text: Experiment
            - code [ref=e112]: /code
        - button [ref=e113] [cursor=pointer]:
          - generic [ref=e117]:
            - text: Paper
            - code [ref=e118]: /paper
        - button [ref=e119] [cursor=pointer]:
          - generic [ref=e123]:
            - text: Review
            - code [ref=e124]: /review
        - button [ref=e125] [cursor=pointer]:
          - generic [ref=e129]:
            - text: Deep research
            - code [ref=e130]: /deepresearch
        - button [ref=e131] [cursor=pointer]:
          - generic [ref=e133]:
            - text: Harness
            - code [ref=e134]: /harness list
        - button [ref=e135] [cursor=pointer]:
          - generic [ref=e140]:
            - text: All commands
            - code [ref=e141]: /workflow list
      - log "CLI conversation" [ref=e142]:
        - generic [ref=e143]: Type a question, or type / for the command list (/lit, /outline, /code, /paper, /review…). The AI answers appear here.
      - form "CLI command" [ref=e145]:
        - generic [ref=e146]:
          - generic [aria-hidden] [ref=e147]: ❯
          - textbox "CLI command" [ref=e148]:
            - /placeholder: Ask, or type / for commands…
          - button "Send" [disabled] [ref=e149]
        - generic [ref=e153]: Enter to send · / for commands · sends to Claude Code
    - button "Right Menu — Open right menu" [ref=e154] [cursor=pointer]:
      - generic [ref=e158]: Right Menu
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
  10  | async function openCli(page: Page, language: 'vi' | 'en', theme: 'light' | 'dark', messages = 0) {
  11  |   await page.addInitScript(([key, sid, th, n]) => {
  12  |     localStorage.setItem('pl.theme', th as string);
  13  |     if (n) localStorage.setItem(key as string, sid as string); else localStorage.removeItem(key as string);
  14  |   }, ['phdlab_cli_session', SID, theme, messages]);
  15  |   if (messages) {
  16  |     await page.route(`**/api/chat/sessions/${SID}`, route => route.fulfill({ json: {
  17  |       id: SID, title: 'CLI', settings: { provider: 'cli:codex' }, turns: [], approvals: [],
  18  |       messages: Array.from({ length: messages }, (_, i) => i % 2
  19  |         ? { id: `m${i}`, role: 'assistant', provider: 'cli:codex', content: `${i}. ${LONG}https://example.org/${'a'.repeat(120)}` }
  20  |         : { id: `m${i}`, role: 'user', content: `/lit câu hỏi số ${i} ${'x'.repeat(i === 0 ? 300 : 10)}` }),
  21  |     } }));
  22  |   }
  23  |   await page.goto('/dist/react.html');  // boot() expects English labels; this spec runs both languages
  24  |   await expect(page.locator('#live.active')).toBeAttached();
  25  |   const name = language === 'vi' ? 'Chat CLI' : 'CLI chat';
  26  |   const sidebar = page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true });
  27  |   if (!(await sidebar.isVisible())) await page.getByRole('button', { name: language === 'vi' ? 'Mở thanh bên' : 'Open sidebar', exact: true }).click();
  28  |   await sidebar.getByRole('button', { name, exact: true }).click();
  29  |   const prompt = page.getByRole('form', { name: language === 'vi' ? 'Lệnh CLI' : 'CLI command' });
  30  |   await expect(prompt).toBeVisible();
  31  |   return prompt;
  32  | }
  33  | 
  34  | async function layoutFindings(page: Page) {
  35  |   return page.evaluate(() => {
  36  |     const out: string[] = [];
  37  |     const form = document.querySelector('form[aria-label]') as HTMLElement;
  38  |     const root = form.parentElement as HTMLElement;
  39  |     const log = root.querySelector('[role=log]') as HTMLElement;
  40  |     const r = root.getBoundingClientRect(), f = form.getBoundingClientRect();
  41  |     if (r.bottom - f.bottom > 16) out.push(`prompt ${Math.round(r.bottom - f.bottom)}px above the bottom`);
  42  |     if (root.lastElementChild !== form) out.push('prompt is not the last block');
  43  |     if (getComputedStyle(log).borderTopWidth !== '1px') out.push('transcript has no frame');
  44  |     for (const a of Array.from(log.querySelectorAll('article'))) {
  45  |       if (getComputedStyle(a).borderTopWidth !== '1px') { out.push('answer has no frame'); break; }
  46  |     }
  47  |     const page = document.scrollingElement as HTMLElement;
  48  |     if (page.scrollWidth > innerWidth + 1) out.push(`page scrolls sideways ${page.scrollWidth}>${innerWidth}`);
  49  |     if (root.scrollWidth > root.clientWidth + 1) out.push(`studio scrolls sideways ${root.scrollWidth}>${root.clientWidth}`);
  50  |     for (const el of Array.from(root.querySelectorAll<HTMLElement>('button, input, label, [role=radio]'))) {
  51  |       const b = el.getBoundingClientRect();
  52  |       if (!b.width || !b.height || getComputedStyle(el).visibility === 'hidden') continue;
  53  |       // Items of a scrolling region (transcript, one-line strips on phones) may sit outside the view; the region may not.
  54  |       const inScroller = log.contains(el) || !!el.closest('.cli-strip');
  55  |       if (!inScroller && (b.left < -1 || b.right > innerWidth + 1 || b.top < -1 || b.bottom > innerHeight + 1)) {
  56  |         out.push(`off screen: ${el.textContent?.trim().slice(0, 30) || el.getAttribute('aria-label')}`);
  57  |         continue;
  58  |       }
  59  |       if (inScroller) continue;
  60  |       const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
  61  |       if (hit && hit !== el && !el.contains(hit) && !hit.contains(el) && !(el.tagName === 'INPUT' && hit.closest('label')?.contains(el))) {
  62  |         out.push(`covered: ${el.textContent?.trim().slice(0, 30) || el.getAttribute('aria-label')} by ${hit.textContent?.trim().slice(0, 30)}`);
  63  |       }
  64  |     }
  65  |     // VIS-OVERLAP: visible text and controls outside the scrolling regions never intersect each other.
  66  |     const boxes = Array.from(root.querySelectorAll<HTMLElement>('header h2, header span, header button, form button, form input, form > div > div'))
  67  |       .filter(el => !el.closest('.cli-strip') && getComputedStyle(el).display !== 'none')
  68  |       .map(el => ({ el, b: el.getBoundingClientRect() })).filter(x => x.b.width && x.b.height);
  69  |     for (let i = 0; i < boxes.length; i++) {
  70  |       for (let j = i + 1; j < boxes.length; j++) {
  71  |         const [p, q] = [boxes[i], boxes[j]];
  72  |         if (p.el.contains(q.el) || q.el.contains(p.el)) continue;
  73  |         const w = Math.min(p.b.right, q.b.right) - Math.max(p.b.left, q.b.left);
  74  |         const h = Math.min(p.b.bottom, q.b.bottom) - Math.max(p.b.top, q.b.top);
  75  |         if (w > 1 && h > 1) out.push(`overlap: ${p.el.textContent?.trim().slice(0, 20)} / ${q.el.textContent?.trim().slice(0, 20) || q.el.getAttribute('aria-label')}`);
  76  |       }
  77  |     }
  78  |     for (const strip of Array.from(root.querySelectorAll<HTMLElement>('.cli-strip'))) {
  79  |       const b = strip.getBoundingClientRect();
  80  |       if (b.left < -1 || b.right > innerWidth + 1) out.push(`strip off screen: ${strip.getAttribute('aria-label')}`);
  81  |     }
  82  |     for (const el of Array.from(root.querySelectorAll<HTMLElement>('button, label, h2'))) {
  83  |       if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).textOverflow !== 'ellipsis') out.push(`clipped: ${el.textContent?.trim().slice(0, 30)}`);
  84  |     }
  85  |     if (/undefined|NaN|\[object Object\]/.test(root.innerText)) out.push('junk text');
  86  |     return out;
  87  |   });
  88  | }
  89  | 
  90  | for (const [width, height] of [[1440, 900], [1024, 768], [390, 844], [360, 740]] as const) {
  91  |   for (const language of ['vi', 'en'] as const) {
  92  |     for (const theme of ['light', 'dark'] as const) {
  93  |       test(`UI-CLI-LAYOUT-001: ${width}x${height} ${language} ${theme}: prompt at the bottom, framed, nothing overlaps`, async ({ page, request }, info) => {
  94  |         expect((await request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
  95  |         await page.setViewportSize({ width, height });
  96  |         await openCli(page, language, theme);
> 97  |         expect(await layoutFindings(page)).toEqual([]);
      |                                            ^ Error: expect(received).toEqual(expected) // deep equality
  98  |         if (language === 'en') await expect(page.locator('form[aria-label]').locator('..')).not.toContainText(/Khảo sát|Đề cương|Quy trình|Xóa màn hình/);
  99  |         await info.attach(`cli-${width}-${language}-${theme}.png`, { body: await page.screenshot(), contentType: 'image/png' });
  100 |       });
  101 |     }
  102 |   }
  103 | }
  104 | 
  105 | for (const [width, height] of [[1440, 900], [390, 844]] as const) {
  106 |   test(`UI-CLI-LAYOUT-002: ${width}px with 100 messages keeps the prompt fixed and scrolls the transcript`, async ({ page, request }, info) => {
  107 |     expect((await request.post('/api/config', { data: { ui: { language: 'vi' } } })).ok()).toBeTruthy();
  108 |     await page.setViewportSize({ width, height });
  109 |     await openCli(page, 'vi', 'light', 100);
  110 |     const log = page.getByRole('log', { name: 'Hội thoại CLI' });
  111 |     await expect(log.getByRole('article')).toHaveCount(50);
  112 |     await expect.poll(() => log.evaluate(el => el.scrollHeight - el.clientHeight - el.scrollTop)).toBeLessThan(4);
  113 |     expect(await layoutFindings(page)).toEqual([]);
  114 |     await expect(log.getByRole('article').last()).toContainText('ChatGPT (OpenAI Codex CLI)');
  115 |     await info.attach(`cli-100-${width}.png`, { body: await page.screenshot(), contentType: 'image/png' });
  116 |   });
  117 | }
  118 | 
  119 | test('UI-CLI-SUGGEST-001: command suggestions open above the prompt and stay on screen', async ({ page, request }) => {
  120 |   expect((await request.post('/api/config', { data: { ui: { language: 'vi' } } })).ok()).toBeTruthy();
  121 |   await page.setViewportSize({ width: 390, height: 844 });
  122 |   const prompt = await openCli(page, 'vi', 'light');
  123 |   await prompt.getByRole('textbox').fill('/');
  124 |   const list = page.getByRole('listbox', { name: 'Gợi ý lệnh' });
  125 |   await expect(list).toBeVisible();
  126 |   const [l, p] = [await list.boundingBox(), await prompt.boundingBox()];
  127 |   expect(l!.y + l!.height).toBeLessThanOrEqual(p!.y + 1);
  128 |   expect(l!.y).toBeGreaterThanOrEqual(0);
  129 |   await prompt.getByRole('textbox').press('Escape');
  130 |   await expect(list).toBeHidden();
  131 | });
  132 | 
```