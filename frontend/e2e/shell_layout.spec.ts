import { test, expect } from './live';
import type { Page } from '@playwright/test';

// agent/PLAYWRIGHT_QA_CHECKLIST.md section 4.1: the shell's sidebar and the floating "Right menu" handle.
// Findings from the 6.6.3 CLI pass: at 1024px the brand wrapped onto three lines, two menu icons were squeezed to a
// dot or to nothing, the footer settings button was clipped, and the handle covered controls of the main views.

let originalLanguage = 'vi';
test.beforeAll(async ({ request }) => { originalLanguage = (await (await request.get('/api/config')).json()).ui?.language || 'vi'; });
test.afterAll(async ({ request }) => { await request.post('/api/config', { data: { ui: { language: originalLanguage } } }); });

async function open(page: Page, language: 'vi' | 'en', width: number) {
  expect((await page.request.post('/api/config', { data: { ui: { language } } })).ok()).toBeTruthy();
  await page.setViewportSize({ width, height: 860 });
  await page.goto('/dist/react.html');
  await expect(page.locator('#live.active')).toBeAttached();
  await expect(page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true })).toBeVisible();
}

for (const width of [1024, 1280, 1440]) {
  for (const language of ['vi', 'en'] as const) {
    test(`UI-SHELL-SIDEBAR-001: ${width}px ${language}: brand on one line, every icon full size, nothing clipped`, async ({ page }) => {
      await open(page, language, width);
      const findings = await page.getByRole('complementary', { name: language === 'vi' ? 'Thanh bên' : 'Sidebar', exact: true }).evaluate(side => {
        const out: string[] = [];
        const s = side.getBoundingClientRect();
        const brand = side.querySelector('.brand b') as HTMLElement;
        if (brand.getBoundingClientRect().height > 24) out.push(`brand wraps (${Math.round(brand.getBoundingClientRect().height)}px)`);
        for (const button of Array.from(side.querySelectorAll<HTMLElement>('button'))) {
          const b = button.getBoundingClientRect();
          if (!b.width || getComputedStyle(button).visibility === 'hidden' || button.closest('[hidden]')) continue;
          const name = (button.textContent || button.getAttribute('title') || '').trim().slice(0, 30);
          const icon = button.querySelector(':scope > svg') as SVGElement | null;
          if (icon && icon.getBoundingClientRect().width < 12) out.push(`icon squeezed (${Math.round(icon.getBoundingClientRect().width)}px): ${name}`);
          if (b.right > s.right + 1 || b.left < s.left - 1) out.push(`outside the sidebar: ${name}`);
          for (const el of [button, ...Array.from(button.querySelectorAll<HTMLElement>('span, b'))]) {
            if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).textOverflow !== 'ellipsis') out.push(`clipped text: ${name}`);
            if (el.scrollWidth > el.clientWidth + 1 && !(button.title || el.title)) out.push(`truncated without a tooltip: ${name}`);
          }
        }
        return [...new Set(out)];
      });
      expect(findings).toEqual([]);
    });
  }
}

const VIEWS: Array<[string, (page: Page) => Promise<void>]> = [
  ['chat', async () => {}],
  ['library', page => page.getByTitle('Paper Library & Documents', { exact: true }).click()],
  ['harness', page => page.getByRole('button', { name: 'Harness Studio', exact: true }).click()],
  ['review', page => page.getByTitle('Peer Review R1–R3 & LaTeX', { exact: true }).click()],
  ['dashboard', page => page.getByTitle('System Dashboard', { exact: true }).click()],
  ['settings', page => page.getByRole('button', { name: 'System Settings', exact: true }).click()],
  ['cli', page => page.getByRole('complementary', { name: 'Sidebar', exact: true }).getByRole('button', { name: 'CLI chat', exact: true }).click()],
];

for (const width of [1024, 1440]) {
  for (const [view, go] of VIEWS) {
    test(`UI-SHELL-HANDLE-001: ${width}px ${view}: the Right menu handle covers no control`, async ({ page }) => {
      await open(page, 'en', width);
      await go(page);
      await page.waitForTimeout(400);  // let the view settle before measuring
      const covered = await page.evaluate(() => {
        const handle = document.getElementById('floating-drawer-toggle');
        if (!handle) return ['no handle'];
        const h = handle.getBoundingClientRect();
        const out: string[] = [];
        for (const el of Array.from(document.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], [role=tab], label'))) {
          if (el === handle || handle.contains(el) || el.closest('aside, #sidebar-collapsed-rail')) continue;
          const b = el.getBoundingClientRect();
          if (!b.width || !b.height || getComputedStyle(el).visibility === 'hidden') continue;
          const w = Math.min(b.right, h.right) - Math.max(b.left, h.left);
          const v = Math.min(b.bottom, h.bottom) - Math.max(b.top, h.top);
          if (w > 1 && v > 1) out.push((el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 40));
        }
        return out;
      });
      expect(covered).toEqual([]);
    });
  }
}
