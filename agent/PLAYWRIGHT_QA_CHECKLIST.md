# Playwright QA/QC checklist (v6.6.3+)

Role: a strict QA/QC reviewer. Assume every screen has a defect until evidence shows otherwise. This checklist extends
`agent/UAT.md` and `agent/DEVELOPMENT_WORKFLOW.md`; it does not replace their gates, repair limit or evidence rules.

Skills to load (pinned in `skills/`, see `skills/SOURCES.json`): `playwright`, `webapp-testing`,
`playwright-explore-website`, `playwright-generate-test`, `web-design-reviewer`, `bug-reproduction-brief`,
`test-gap-audit`. Where an upstream skill conflicts with this repository (personal Chrome, cloud browsers, editing code
while reproducing), this repository wins.

A box is ticked only when a run produced evidence for it: a Playwright result, trace, screenshot or audit JSON tied to
the current source SHA. "Looked fine" is not evidence. Anything not run is NOT_RUN, never PASS.

---

## v6.6.3 release goal: CLI studio matches the current backend

Owner request (2026-10-28). Scope: `frontend/src/features/cli/ClaudeCLIStudio.tsx` and its drawer entry. Build it,
then QA it with every section of this checklist before release.

Layout:

- [ ] The prompt box sits at the bottom of the CLI panel in every viewport and drawer size, like a chat app. The
      transcript fills the space above it and scrolls; the prompt never moves when output grows. Command suggestions
      open upward from the prompt and do not cover the last message.
- [ ] The transcript area has its own visible frame (border, radius, padding), separate from the prompt frame.
- [ ] Each AI answer sits in its own framed block, visually distinct from user commands and system lines, in both
      themes.
- [ ] Before changing code, screenshot the current panel at 1440×900 and 390×844 and record why the prompt does not
      appear at the bottom today (the source already renders it last, so the cause may be the drawer container).

Backend alignment (gaps found by reading the code at `edb9c0e`):

- [ ] The provider chip the user selects (Claude Code / Codex / Gemini CLI / Antigravity) is the provider the turn is
      sent to. Today the turn uses `agent_catalog.assistant.engine` and ignores the chip.
- [ ] The provider list and states come from `GET /api/providers` (state, detail, auth) instead of a hard-coded list;
      unavailable or unauthenticated providers are shown disabled with the reason.
- [ ] Manual mode (`awaiting_launch`) offers the launch action through `POST /api/chat/sessions/{sid}/turns/{tid}/launch`
      instead of only printing a waiting line.
- [ ] Tool calls, run status and errors of a turn are shown like the chat run cards (`ChatRunCard`), not only the final
      text; a failed or cancelled turn shows its reason.
- [ ] Approvals are listed one by one with what they will do; `/accept all` still exists but shows what it approved.
- [ ] Errors appear inline in the transcript, not through `alert()`.
- [ ] Workflow chips and all labels follow the active language (today the chip labels are Vietnamese in English mode)
      and the colours follow the active theme (today they are hard-coded dark colours).
- [ ] Reload keeps the CLI session and transcript; `/new` and `/clear` behave as described in the suggestion list.

Tests:

- [ ] Unit tests in `ClaudeCLIStudio.test.tsx` for each backend alignment item (RED before the change, GREEN after).
- [ ] Playwright `frontend/e2e/cli_studio.spec.ts`: prompt is the bottom-most control of the panel
      (its bounding box bottom is within 16px of the panel bottom) at every core and wide viewport, both themes, both
      languages, with an empty transcript and with 100 entries; transcript and answer frames exist; section 2 audit is
      clean; the selected provider is the one in the posted turn.
- [ ] Contract `docs/qa/contracts/FQC-CLI-STUDIO-663.json` with RED/GREEN evidence.

## 0. Run setup

- [ ] Fresh worktree at the exact SHA under test; `git status` clean; SHA recorded in the run report.
- [ ] Frontend built from that SHA (`npm run build`); bundle hash recorded.
- [ ] Disposable `PHDLAB_DATA_DIR` (short path, e.g. `D:/qa-<run>` on Windows); never the real `data/` or `projects/`.
- [ ] Own loopback port and own Playwright browser context; never personal Chrome, cookies or accounts.
- [ ] `NO_PROXY=localhost,127.0.0.1,::1` set; the server log is captured to the run folder.
- [ ] Seed data loaded from fixtures: one empty project, one "busy" project (≥200 chats, ≥50 library items, long
      Vietnamese and English titles, a running and a failed mission, a finished paper).
- [ ] Output folder `output/playwright/qa-<version>-<run>/` holds the trace, screenshots, `audit.json`, `defects.json`
      and `report.json`.
- [ ] Every test listens for `console` errors/warnings, `pageerror`, unhandled rejections and failed requests (status
      ≥ 400 or network failure). Unexpected entries fail the test; expected ones are listed by name.

## 1. Environment matrix

Run the full screen inventory (section 4) on the **core matrix**; run the journeys (section 5) on the **wide matrix**.

| Axis | Core | Wide adds |
|---|---|---|
| Viewport | 1440×900, 390×844 | 360×740, 768×1024, 1024×768, 1280×800, 1920×1080, 2560×1440 |
| Theme | light, dark | system; every theme package listed in Settings → Appearance |
| Language | vi, en | switch language in the middle of a flow |
| Zoom / text | 100% | 125%, 150%, 200% (`deviceScaleFactor` plus CSS zoom), browser minimum font 16px |
| Motion | default | `prefers-reduced-motion: reduce` |
| Input | mouse | keyboard only; touch (`hasTouch`, `isMobile`) |
| Network | normal | slow 3G profile, offline mid-action, backend stopped/restarted |
| Browser | Chromium | Firefox and WebKit as smoke only (informational) |

## 2. Automatic visual audit (run on every screen, every matrix cell)

A shared helper (`frontend/e2e/uiAudit.ts`) runs after a screen settles and writes findings to `audit.json`. Each
rule has an ID so a defect can be traced back to it. Tolerance is 1px unless stated.

- [ ] **VIS-OVERLAP**: two visible text nodes or interactive elements intersect each other (not parent/child, not an
      intentional badge declared with `data-overlay-ok`).
- [ ] **VIS-OCCLUDED**: `document.elementFromPoint` at the centre of each visible button, link, input and tab returns
      something other than the element or its descendant (covered by a toast, sticky header, drawer, tooltip, 3D canvas,
      modal backdrop).
- [ ] **VIS-CLIPPED**: text with `scrollWidth > clientWidth` or `scrollHeight > clientHeight` and `overflow:hidden`
      without an ellipsis **and** a `title`/tooltip showing the full text.
- [ ] **VIS-HSCROLL**: `document.scrollingElement.scrollWidth > innerWidth` (horizontal page scroll), or any panel
      scrolls horizontally when it should wrap.
- [ ] **VIS-OFFSCREEN**: an interactive element, menu, dropdown, popover or tooltip sits partly outside the viewport
      or outside its scroll container with no way to scroll to it.
- [ ] **VIS-ZERO**: an interactive element with width or height 0, or `opacity:0` while still focusable.
- [ ] **VIS-TARGET**: pointer targets smaller than 24×24 CSS px (WCAG 2.5.8); 44×44 on touch viewports for primary
      actions.
- [ ] **VIS-TEXT-JUNK**: visible text contains `undefined`, `null`, `NaN`, `[object Object]`, `Invalid Date`, `{{`,
      raw i18n keys (pattern `^[a-z]+(\.[a-zA-Z0-9]+)+$`, e.g. `aiTools.tab`), or a stack trace.
- [ ] **VIS-MIXED-LANG**: in `vi` mode no English UI chrome (labels, buttons, headings, empty states), and the reverse;
      user content and proper nouns are excluded.
- [ ] **VIS-IMG**: broken images (`naturalWidth === 0`), stretched images (aspect ratio off by >2%), SVG icons without
      size.
- [ ] **VIS-CONTRAST**: axe `color-contrast`, in both themes, including disabled, placeholder, hover and focus states.
- [ ] **VIS-FOCUS**: every focusable element shows a visible focus ring (outline or box-shadow differs from unfocused).
- [ ] **VIS-SHIFT**: cumulative layout shift > 0.1 while the screen loads, or a button moves while the user aims at it.
- [ ] **VIS-STACK**: more than one scroll bar on the same axis in nested containers; double scroll bars in modals.
- [ ] **VIS-EMPTY-BOX**: a visible container with border/background but no content and no empty-state message.
- [ ] **VIS-SNAPSHOT**: screenshot compared with the approved baseline for that matrix cell; diff > 0.2% of pixels is
      reviewed by a person, and the reason (intended change or defect) is recorded.

Automation catches most issues, not all. For every screen also look at the screenshot yourself in both themes at 390px
and 1440px, and record what you looked at.

## 3. Interaction states (every component that has them)

- [ ] Loading: skeleton or spinner appears within 300ms; no flash of an empty state before data arrives.
- [ ] Empty: a clear message and the one next action; no blank panel.
- [ ] Error: API 4xx/5xx/timeout shows a readable message in the active language, a retry, and no raw JSON.
- [ ] Partial: some items failed and others loaded; the failure is visible next to the item.
- [ ] Disabled: explains why (tooltip or helper text); a disabled button cannot be activated by keyboard.
- [ ] Busy: double-click and double Enter do not submit twice; the button shows progress.
- [ ] Success: confirmation is visible and does not cover the next action; toasts disappear or can be closed.
- [ ] Long content: 200-character titles, 10,000-character messages, 1,000-row lists, deep markdown (tables, code,
      LaTeX, nested lists), Vietnamese diacritics, emoji, RTL text, unbroken 300-character URLs.
- [ ] Hover, focus, active, selected and visited states are distinguishable in both themes.

## 4. Screen inventory

Each screen: open it from its normal entry point, run section 2 and section 3, exercise every control once, then
close it. Tick only after the audit and the controls ran.

### 4.1 Shell
- [ ] Header: project switcher, language, theme, settings, notifications; titles truncate with tooltip.
- [ ] Sidebar: new chat, search, pinned, folders (create/rename/delete/move chat), very long folder names, 200+ chats
      scroll; collapse/expand; on mobile it opens as an overlay, closes on outside tap and on navigation.
- [ ] Contextual drawer: open, close, resize (if supported), switch panels; it never covers the composer send button;
      at 390px it is full screen with a visible close.
- [ ] Browser back/forward and reload keep the current project, chat, topic and drawer panel (known gap from the live
      Codex run: reload loses the selected topic).
- [ ] Deep link to each panel opens it directly.

### 4.2 Chat and composer
- [ ] Send, stop, retry, edit and resend; Enter vs Shift+Enter; IME composition (Vietnamese Telex) does not send early.
- [ ] Streaming: auto-scroll follows unless the user scrolled up; "jump to latest" appears; no layout jump at the end.
- [ ] Run cards (`ChatRunCard`): status, tool calls, errors, long tool output collapses; copy buttons work.
- [ ] Markdown: code blocks scroll horizontally inside the block, not the page; tables do not overflow; math renders.
- [ ] Attachments: add, remove, oversized file, unsupported type, upload failure.
- [ ] Model/agent picker: every option visible at 390px; disabled providers say why.
- [ ] Multi-turn: 50 turns stay responsive (input latency < 100ms).

### 4.3 Drawer panels (`ContextualDrawer` cases)
- [ ] projects  - [ ] topics  - [ ] library  - [ ] missions  - [ ] workstreams  - [ ] figures
- [ ] opencode  - [ ] intelligence  - [ ] agent-status (incl. Office 3D and agent profile modal)  - [ ] protocols
- [ ] claims / evidence review  - [ ] dashboard (model usage)  - [ ] settings  - [ ] review  - [ ] outline
- [ ] code  - [ ] paper (PaperOrchestra)  - [ ] guide  - [ ] harness (custom harness studio, node graph)  - [ ] cli

Per panel, in addition to sections 2 and 3:

- [ ] Every list: empty, one item, many items, search/filter with no match, sort, pagination or virtual scroll.
- [ ] Every form: required fields, invalid input, max length, paste of long text, submit with Enter, cancel discards.
- [ ] Every destructive action asks for confirmation, names the item, and can be cancelled with Esc.
- [ ] Live data (missions, workstreams, agent status) refreshes without a reload (known gap: Missions panel).
- [ ] Graph/canvas views (MissionDAG, harness, Office 3D): nodes do not overlap labels, zoom/pan works, fit-to-screen
      works, canvas does not capture page scroll or cover controls, WebGL failure shows a fallback.

### 4.4 Settings (all 8 tabs)
- [ ] models  - [ ] ai-tools (every backend permission has a toggle)  - [ ] engines  - [ ] search  - [ ] hardware
- [ ] memory  - [ ] mcp (security firewall)  - [ ] skills  - [ ] look (appearance and language)

Per tab:

- [ ] Changes persist after reload (checked through the real settings API, not only the UI).
- [ ] Unsaved changes are not lost silently when switching tab or closing.
- [ ] Secrets are masked, never echoed into the DOM in full, never in console or screenshots.
- [ ] Tab list scrolls or wraps at 390px; long descriptions do not push controls off screen.

### 4.5 Modals, menus and overlays
- [ ] Focus moves into the modal, is trapped, and returns to the trigger on close; Esc closes; backdrop click rule is
      consistent.
- [ ] Only one modal at a time; the page behind does not scroll.
- [ ] Menus and dropdowns flip when near an edge; long option text wraps or truncates with tooltip.
- [ ] Toasts stack without covering primary actions; they are announced (`role=status`/`alert`).

## 5. End-to-end journeys

Deterministic journeys run without an LLM (stub provider). Live journeys use the owner's model and are marked LIVE.

- [ ] J1 First run: empty data folder → onboarding/guide → create project → first chat → answer shown.
- [ ] J2 Research loop: project → topic → library search/import → evidence review → claim accepted/rejected.
- [ ] J3 Mission: build mission → run → watch DAG and task inspector → cancel → resume → finished state.
- [ ] J4 Experiment: run code/experiment → tracking shows metrics → figure created in Figure Studio.
- [ ] J5 Paper: outline → PaperOrchestra draft → quality gates → review → export; failed gates are shown, not hidden.
- [ ] J6 Settings round trip: change language, theme, model routing and AI tool permissions → reload → still applied →
      reset.
- [ ] J7 CLI/harness: open CLI studio → run allowed command → denied command is refused with a clear reason.
- [ ] J8 Project switching: two projects with different data; nothing leaks between them; the active project is shown.
- [ ] J9 Failure recovery: stop the backend mid-request → UI shows offline state → restart → UI recovers without reload;
      no duplicate sends.
- [ ] J10 Concurrency: two tabs on the same project; actions in one appear in the other or a conflict is explained.
- [ ] J11 Keyboard only: complete J1 and J6 without a mouse.
- [ ] J12 LIVE: owner's Codex agent runs a topic to a manuscript (see `memory: live-agent-testing`); record each UI defect
      seen during the run.

## 6. Accessibility

- [ ] axe scan (`@axe-core/playwright`, tags wcag2a, wcag2aa, wcag21aa, wcag22aa) on every screen and modal, both
      themes, both languages; zero serious/critical violations.
- [ ] Every control has an accessible name in the active language; icons-only buttons have `aria-label`.
- [ ] Headings form a logical outline; landmarks (`banner`, `navigation`, `main`, `complementary`) exist once.
- [ ] `lang` attribute follows the selected language.
- [ ] Live regions announce streaming completion and errors without announcing every token.
- [ ] Content usable at 200% zoom and 320px width without horizontal scroll (WCAG 1.4.10).

## 7. Performance budgets (1440×900, Chromium, built bundle)

- [ ] Initial load to interactive < 2.5s on the seeded busy project; record LCP, CLS, long tasks.
- [ ] Opening any drawer panel < 500ms to first content.
- [ ] Typing in the composer: no frame > 50ms with 50 turns loaded.
- [ ] Sidebar with 1,000 chats scrolls at ≥ 50 fps (no long tasks > 100ms while scrolling).
- [ ] No memory growth > 50MB after opening and closing every panel 10 times.

## 8. Security as seen from the UI

- [ ] XSS probes (`<img src=x onerror=alert(1)>`, `javascript:` links, markdown HTML) in chat, titles, folder names,
      library metadata and paper text are rendered inert.
- [ ] External links open with `rel="noopener noreferrer"`; no link opens a non-allowlisted origin silently.
- [ ] Denied tool permissions and the source-code gateway show a clear message, not a silent failure.
- [ ] No secret appears in DOM, console, network responses to the browser, traces or screenshots.

## 9. Defect handling

1. Reproduce with the smallest steps (skill `bug-reproduction-brief`); run it twice. Until reproduced it is UNCONFIRMED.
2. Record in `defects.json`: ID, screen, matrix cell, audit rule ID, steps, expected, actual, screenshot/trace paths,
   source SHA, classification (product / test / environment), severity.
3. Severity:
   - **S1** blocks a journey, loses data, leaks a secret, or crashes the page.
   - **S2** a feature is wrong or unusable in one matrix cell (e.g. button covered at 390px).
   - **S3** visible defect with a workaround: clipped text, overlap, wrong language, bad contrast.
   - **S4** polish: spacing, alignment, inconsistent icon size.
4. Write a failing Playwright test (or audit rule) first, then fix, then rerun the failing and affected suites.
   Max three repair cycles per defect group, recorded in `agent/repair-ledgers/ledger.json`.

## 10. Exit criteria for a release

- [ ] Sections 0–8 ticked with evidence for the core matrix; wide matrix ran for section 5.
- [ ] Zero open S1/S2; every S3 either fixed or accepted by the owner in writing; S4 listed.
- [ ] `audit.json` has zero findings, or each finding is linked to an accepted defect.
- [ ] Visual baselines updated only for intended changes, each with a reason.
- [ ] `python scripts/verify.py --profile pr --component all` PASS and CI green on the exact SHA.
- [ ] Report lists what was NOT run and why.

## 11. Mapping to Playwright files

| Area | Spec |
|---|---|
| Audit helper and rules | `frontend/e2e/uiAudit.ts` |
| Screen inventory × matrix | `frontend/e2e/qa_screens.spec.ts` |
| Journeys J1–J11 | `frontend/e2e/qa_journeys.spec.ts` (extends `journeys.spec.ts`, `workflows.spec.ts`) |
| Accessibility | `frontend/e2e/ui_quality.spec.ts` (extend) |
| Visual baselines | `frontend/e2e/qa_visual.spec.ts` with `toHaveScreenshot` per matrix cell |
| Failure recovery | `frontend/e2e/qa_resilience.spec.ts` |

Test IDs follow the existing pattern: `UI-<AREA>-<RULE>-NNN` (for example `UI-CHAT-VIS-OCCLUDED-001`).
