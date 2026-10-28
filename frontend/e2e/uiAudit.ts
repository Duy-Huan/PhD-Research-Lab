import type { Page } from '@playwright/test';

/** agent/PLAYWRIGHT_QA_CHECKLIST.md section 2: automatic visual audit of what is on screen now.
 * Returns findings as "RULE: detail" strings; an empty list means the screen passed every rule. */
export async function uiAudit(page: Page, language: 'vi' | 'en'): Promise<string[]> {
  return page.evaluate(lang => {
    const out = new Set<string>();
    const name = (el: Element) => ((el.getAttribute('aria-label') || el.textContent || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40));
    const visible = (el: HTMLElement) => {
      const b = el.getBoundingClientRect();
      if (b.width < 1 || b.height < 1) return false;
      const s = getComputedStyle(el);
      const folded = el.closest('details:not([open])') && !el.closest('summary');  // inside a closed <details>
      return !folded && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05;
    };
    // The part of an element its scrolling/clipping ancestors actually show (null = scrolled out of view).
    const shown = (el: HTMLElement) => {
      let r = el.getBoundingClientRect();
      let box = { l: r.left, t: r.top, r: r.right, b: r.bottom };
      for (let p = el.parentElement; p; p = p.parentElement) {
        const s = getComputedStyle(p);
        if (/(auto|scroll|hidden|clip)/.test(s.overflow + s.overflowX + s.overflowY)) {
          const q = p.getBoundingClientRect();
          box = { l: Math.max(box.l, q.left), t: Math.max(box.t, q.top), r: Math.min(box.r, q.right), b: Math.min(box.b, q.bottom) };
        }
      }
      box = { l: Math.max(box.l, 0), t: Math.max(box.t, 0), r: Math.min(box.r, innerWidth), b: Math.min(box.b, innerHeight) };
      return box.r - box.l > 2 && box.b - box.t > 2 ? box : null;
    };

    // VIS-HSCROLL
    const doc = document.scrollingElement as HTMLElement;
    if (doc.scrollWidth > innerWidth + 1) out.add(`VIS-HSCROLL: page ${doc.scrollWidth}px > ${innerWidth}px`);

    const controls = Array.from(document.querySelectorAll<HTMLElement>('button, a[href], input:not([type=hidden]), select, textarea, [role=tab], [role=radio], [role=checkbox], [role=switch]'))
      .filter(visible);
    for (const el of controls) {
      const box = shown(el);
      if (!box) continue;
      // VIS-OCCLUDED: the visible centre of a control must be the control itself (or its label / content).
      const x = (box.l + box.r) / 2, y = (box.t + box.b) / 2;
      const hit = document.elementFromPoint(x, y);
      // A control behind a large overlay (full-screen drawer, dialog, settings page) is hidden on purpose, not covered.
      let layer: Element | null = hit;
      while (layer && layer !== document.body) {
        const s = getComputedStyle(layer); const q = layer.getBoundingClientRect();
        if (/(fixed|absolute)/.test(s.position) && q.width * q.height >= 0.4 * innerWidth * innerHeight) break;
        layer = layer.parentElement;
      }
      const behindOverlay = !!layer && layer !== document.body && !layer.contains(el);
      if (hit && !behindOverlay && hit !== el && !el.contains(hit) && !hit.contains(el) && !(hit.closest('label')?.contains(el)) && !el.closest('label')?.contains(hit)) {
        out.add(`VIS-OCCLUDED: "${name(el)}" under "${name(hit)}"`);
      }
      // VIS-TARGET: pointer targets of at least 20 x 20 px (checkboxes and inline links excluded).
      const b = el.getBoundingClientRect();
      if (!['INPUT', 'A'].includes(el.tagName) && (b.width < 20 || b.height < 20)) out.add(`VIS-TARGET: "${name(el)}" ${Math.round(b.width)}x${Math.round(b.height)}`);
      // VIS-ICON: an icon inside a button is never squeezed.
      const icon = el.querySelector(':scope > svg');
      if (icon && icon.getBoundingClientRect().width < 10) out.add(`VIS-ICON: squeezed icon in "${name(el)}"`);
    }

    // VIS-CLIPPED: text cut off without an ellipsis, or shortened without a tooltip.
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('button, label, h1, h2, h3, h4, b, strong, span, a, th, td, p, dt, dd, .chip'))) {
      if (!visible(el) || !shown(el) || !el.textContent?.trim() || el.children.length > 2) continue;
      const s = getComputedStyle(el);
      const over = el.scrollWidth > el.clientWidth + 1 && /(hidden|clip)/.test(s.overflow + s.overflowX);
      if (!over) continue;
      if (s.textOverflow !== 'ellipsis') out.add(`VIS-CLIPPED: "${name(el)}" cut without ellipsis`);
      else if (!el.closest('[title]') && !el.closest('[aria-label]')) out.add(`VIS-CLIPPED: "${name(el)}" shortened without tooltip`);
    }

    // VIS-TEXT-JUNK and VIS-MIXED-LANG on visible UI text (user content and code excluded).
    const skip = 'code, pre, textarea, input, [contenteditable], .msg-card, [role=log], .ellipsis, [data-user-content], .katex, svg';
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const viet = /[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]/i;
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = (n.textContent || '').trim();
      const host = n.parentElement;
      if (!text || !host || host.closest(skip) || !visible(host) || !shown(host)) continue;
      if (/\b(undefined|NaN|null)\b|\[object Object\]|Invalid Date|\{\{/.test(text)) out.add(`VIS-TEXT-JUNK: "${text.slice(0, 50)}"`);
      if (/^[a-z][a-zA-Z]+(\.[a-zA-Z][a-zA-Z0-9]*){1,3}$/.test(text) && !/\.(py|md|json|ts|tsx|js|csv|tex|pdf|png|bib|txt|yml|yaml|toml|com|org|net|io|ai)$/i.test(text)) out.add(`VIS-I18N-KEY: "${text}"`);
      if (lang === 'en' && viet.test(text) && !host.closest('aside [role=listitem], aside li, [data-session-title]')) out.add(`VIS-MIXED-LANG: Vietnamese in English UI: "${text.slice(0, 50)}"`);
    }
    return [...out].sort();
  }, language);
}
