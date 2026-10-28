# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: shell_layout.spec.ts >> UI-SHELL-SIDEBAR-001: 1024px en: brand on one line, every icon full size, nothing clipped
- Location: e2e\shell_layout.spec.ts:22:5

# Error details

```
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 9

- Array []
+ Array [
+   "brand wraps (63px)",
+   "icon squeezed (8px): Models & AI connections",
+   "icon squeezed (0px): Native code & experiments",
+   "truncated without a tooltip: Workspace: Default project",
+   "clipped text: New chat folder",
+   "clipped text: Chat options",
+   "outside the sidebar: System Settings",
+ ]
```

# Test source

```ts
  1  | import { test, expect } from './live';
  2  | import type { Page } from '@playwright/test';
  3  | 
  4  | // agent/PLAYWRIGHT_QA_CHECKLIST.md section 4.1: the shell's sidebar and the floating "Right menu" handle.
  5  | // Findings from the 6.6.3 CLI pass: at 1024px the brand wrapped onto three lines, two menu icons were squeezed to a
  6  | // dot or to nothing, the footer settings button was clipped, and the handle covered controls of the main views.
  7  | 
  8  | let originalLanguage = 'vi';
  9  | test.beforeAll(async ({ request }) => { originalLanguage = (await (await request.get('/api/config')).json()).ui?.language || 'vi'; });
  10 | test.afterAll(async ({ request }) => { await request.post('/api/config', { data: { ui: { language: originalLanguage } } }); });
  11 | 
  12 | async function open(page: Page, language: 'vi' | 'en', width: number) {
  13 |   expect((await page.request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
  14 |   await page.setViewportSize({ width, height: 860 });
  15 |   await page.goto('/dist/react.html');
  16 |   await expect(page.locator('#live.active')).toBeAttached();
  17 |   await expect(page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true })).toBeVisible();
  18 | }
  19 | 
  20 | for (const width of [1024, 1280, 1440]) {
  21 |   for (const language of ['vi', 'en'] as const) {
  22 |     test(`UI-SHELL-SIDEBAR-001: ${width}px ${language}: brand on one line, every icon full size, nothing clipped`, async ({ page }) => {
  23 |       await open(page, language, width);
  24 |       const findings = await page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true }).evaluate(side => {
  25 |         const out: string[] = [];
  26 |         const s = side.getBoundingClientRect();
  27 |         const brand = side.querySelector('.brand b') as HTMLElement;
  28 |         if (brand.getBoundingClientRect().height > 24) out.push(`brand wraps (${Math.round(brand.getBoundingClientRect().height)}px)`);
  29 |         for (const button of Array.from(side.querySelectorAll<HTMLElement>('button'))) {
  30 |           const b = button.getBoundingClientRect();
  31 |           if (!b.width || getComputedStyle(button).visibility === 'hidden' || button.closest('[hidden]')) continue;
  32 |           const name = (button.textContent || button.getAttribute('title') || '').trim().slice(0, 30);
  33 |           const icon = button.querySelector(':scope > svg') as SVGElement | null;
  34 |           if (icon && icon.getBoundingClientRect().width < 12) out.push(`icon squeezed (${Math.round(icon.getBoundingClientRect().width)}px): ${name}`);
  35 |           if (b.right > s.right + 1 || b.left < s.left - 1) out.push(`outside the sidebar: ${name}`);
  36 |           for (const el of [button, ...Array.from(button.querySelectorAll<HTMLElement>('span, b'))]) {
  37 |             if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).textOverflow !== 'ellipsis') out.push(`clipped text: ${name}`);
  38 |             if (el.scrollWidth > el.clientWidth + 1 && !(button.title || el.title)) out.push(`truncated without a tooltip: ${name}`);
  39 |           }
  40 |         }
  41 |         return [...new Set(out)];
  42 |       });
> 43 |       expect(findings).toEqual([]);
     |                        ^ Error: expect(received).toEqual(expected) // deep equality
  44 |     });
  45 |   }
  46 | }
  47 | 
  48 | const VIEWS: Array<[string, (page: Page) => Promise<void>]> = [
  49 |   ['chat', async () => {}],
  50 |   ['library', page => page.getByTitle('Paper Library & Documents', { exact: true }).click()],
  51 |   ['harness', page => page.getByRole('button', { name: 'Harness Studio', exact: true }).click()],
  52 |   ['review', page => page.getByTitle('Peer Review R1–R3 & LaTeX', { exact: true }).click()],
  53 |   ['dashboard', page => page.getByTitle('System Dashboard', { exact: true }).click()],
  54 |   ['settings', page => page.getByRole('button', { name: 'System Settings', exact: true }).click()],
  55 |   ['cli', page => page.getByRole('complementary', { name: 'Sidebar', exact: true }).getByRole('button', { name: 'CLI chat', exact: true }).click()],
  56 | ];
  57 | 
  58 | for (const width of [1024, 1440]) {
  59 |   for (const [view, go] of VIEWS) {
  60 |     test(`UI-SHELL-HANDLE-001: ${width}px ${view}: the Right menu handle covers no control`, async ({ page }) => {
  61 |       await open(page, 'en', width);
  62 |       await go(page);
  63 |       await page.waitForTimeout(400);  // let the view settle before measuring
  64 |       const covered = await page.evaluate(() => {
  65 |         const handle = document.getElementById('floating-drawer-toggle');
  66 |         if (!handle) return ['no handle'];
  67 |         const h = handle.getBoundingClientRect();
  68 |         const out: string[] = [];
  69 |         for (const el of Array.from(document.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], [role=tab], label'))) {
  70 |           if (el === handle || handle.contains(el) || el.closest('aside, #sidebar-collapsed-rail')) continue;
  71 |           const b = el.getBoundingClientRect();
  72 |           if (!b.width || !b.height || getComputedStyle(el).visibility === 'hidden') continue;
  73 |           const w = Math.min(b.right, h.right) - Math.max(b.left, h.left);
  74 |           const v = Math.min(b.bottom, h.bottom) - Math.max(b.top, h.top);
  75 |           if (w > 1 && v > 1) out.push((el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 40));
  76 |         }
  77 |         return out;
  78 |       });
  79 |       expect(covered).toEqual([]);
  80 |     });
  81 |   }
  82 | }
  83 | 
```