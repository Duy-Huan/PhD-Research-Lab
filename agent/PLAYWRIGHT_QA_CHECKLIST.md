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

Owner requests (2026-10-28): prompt at the bottom, framed transcript and AI answers, aligned with the backend; then
"CLI takes the main chat area" and "the CLI must also work with the cmd console" ("Open in cmd" continues the same
conversation). Evidence: `docs/qa/evidence/cli-studio-663/`, contract `FQC-CLI-STUDIO-663`. Ticked = evidence exists.

Layout:

- [x] Chat CLI opens in the main area (not the right drawer); the prompt is the bottom block at 1440/1024/390/360 px,
      both themes and languages, empty and with 100 messages; suggestions open upward (`cli_studio.spec.ts`).
- [x] The transcript has its own frame; each AI answer has its own frame labelled with the provider that wrote it.
- [x] Before the change: screenshots at 1280 and 390 (prompt was already last; the narrow drawer clipped the provider
      chip, workflow chips and placeholder, and glued the footer text).

Backend alignment:

- [x] The selected provider is sent with the turn and saved as the conversation's provider (live: Codex turn stored
      `provider: cli:codex`).
- [x] Providers come from `/api/models` (`transport: cli`), unavailable ones disabled with the reason. (`/api/providers`
      lists research engines only, not the CLIs.)
- [x] Manual launch button; inline failures; run cards; per-item approvals; `/accept all` reports what it approved.
- [x] Labels follow the language, colours follow the theme; reload keeps the CLI conversation.
- [x] "Open in cmd" opens `phdlab chat --session <id>` in a real cmd console on the same conversation (live run).
- [x] Claude Code in the container uses this computer's sign-in (access token only, never the refresh token) and readiness
      is CONNECTED only when the container can sign in (`FQC-CLAUDE-SIGNIN-663`; live turn completed after the fix).

Found by this checklist and fixed in 6.6.3: sidebar stayed over the CLI on phones; floating "Right menu" handle
covered the header (icon-only at 820px and narrower); title truncated at 360px; the saved theme was not applied after
a reload (every reload fell back to the system theme).

Also fixed (`shell_layout.spec.ts`): sidebar at 1024–1280px (brand wrapped, icons squeezed by the shared `.btn svg` rule,
footer buttons outside the sidebar, truncation without tooltip); the "Right menu" handle covered Upload PDF in the
Library and is now icon-only. Settings never rendered the CLI connections panel (imported since 6.5.10); it is now in
Models & AI Agents with the Claude long-lived token (`claude setup-token`). Still open: the first `/api/models` call
takes several seconds.

## 6.6.3 QA run record

Evidence: `docs/qa/evidence/ui-qa-663/`, `docs/qa/evidence/cli-studio-663/` and `docs/qa/evidence/claude-signin-663/`. Contracts: `FQC-UI-QA-663`, `FQC-CLI-STUDIO-663`, `FQC-CLAUDE-SIGNIN-663` and `FQC-SOURCE-POLICY-663`.

Ran (with evidence):

- Sections 0–2: disposable data folder, port and browser. Audit rules in `frontend/e2e/uiAudit.ts`. Matrix: en and vi, light and dark, 1440 and 390 px; 1024 and 360 px for the CLI and the shell.
- Section 4: every main view, Settings tab and drawer panel, without and with a topic (`qa_screens.spec.ts`, 181 tests); the CLI studio (19 tests); the shell (20 tests).
- Section 6: axe WCAG 2.1 AA (serious and critical) on every screen in both languages.
- Section 5 J12 (live): Codex and Claude Code CLI turns completed; "Open in cmd" was checked in a real `cmd.exe`.
- Existing deterministic journeys (`journeys`, `workflows`, `navigation` and the other specs) run inside `verify.py --profile pr`.

Not run in 6.6.3 (left for the next pass; none of these is claimed to pass):

- Firefox and WebKit.
- 125–200 % zoom and minimum font size.
- Keyboard-only versions of J1 and J6.
- Offline and slow-network journeys (J9).
- Two-tab concurrency (J10).
- Performance budgets (section 7).
- XSS probes through the UI (section 8).
- Visual baselines (VIS-SNAPSHOT).

## 0. Run setup

- [ ] Fresh worktree at the exact SHA under test; `git status` clean; SHA recorded in the run report.
- [ ] Frontend built from that SHA (`npm run build`); bundle hash recorded.
- [ ] Server restarted after the last backend change. `GET /api/version` returns the version under test before any
      run counts. In 6.6.3, two repeated runs went to a server started before the version bump: the backend fixes,
      such as `label_en`, were not loaded, and Settings showed "v6.6.2".
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
