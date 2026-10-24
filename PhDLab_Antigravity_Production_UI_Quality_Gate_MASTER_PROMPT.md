# MASTER PROMPT — PhD Research Lab Production UI Quality Gate (Antigravity)

> **Mission:** Audit, stabilize, polish, and independently verify the *actual running frontend* of this repository to a commercially credible quality bar. Do not simply redesign pages or claim success because builds pass. **No claim of “zero bugs”** is allowed. Deliver a defensible release decision, evidence, and a list of residual risks.
>
> **Project background:** PhD Research Lab is a local-first Research OS. The main user experience must remain *chat-first* and research workflows (Mission, Team, Workstreams, scientific evidence, review, context memory) must be navigable without raw JSON unless in an expert mode. The previously inspected v6.3 ZIP used a `frontend/index.html` + `frontend/assets/research.js` client with a Python/FastAPI backend, while a React + TypeScript migration has been requested. **Inspect the actual current checkout first; do not assume the migration is already complete or that historic line numbers are still valid.**

## 0 — Mission rules / hard constraints

1. Operate on a feature branch or throwaway worktree; record clean baseline, commit hash, exact lockfiles, active ports, backend mode and OS. Do not mutate real research project data, production-like databases, credentials, Git history or paid provider sessions. Use fresh isolated temp data (`PHDLAB_DATA_DIR` or its current equivalent) and stubbed AI providers.
2. Protect Python/FastAPI API semantics, context memory, evidence ledgers, scientific artifacts, permissions, provider adapters, autonomy gates and harness execution. Do not rebuild the backend merely to accommodate presentation. Backend changes require a justified contract issue, focused tests and a migration note.
3. Only count a test as PASS when it was really executed against the current source and real DOM/browser, with trace/screenshot/log evidence. Unavailable dependencies = BLOCKED; not RUN/NOT TESTED = NOT VERIFIED. Do not manufacture screenshots, counts, costs or test logs.
4. No blanket `try/catch` swallowing errors, global CSS overrides concealing issues, blanket test skips, `test.only`, arbitrary sleeps, blanket `force: true`, updating snapshots without review, disabled lint/type-check, or deleting tests to make the suite green. Do not silently change accessibility or approval UX.
5. Test with deterministic fixture providers first. Request explicit approval before enabling real CLI/API model invocations, paid usage, destructive filesystem actions or real scientific experiments. Never start paid/long-running tasks merely for visual testing.
6. Independent reviewer must evaluate working UI against actual user journeys and visually inspect screenshots after the implementer has finished. If the platform cannot spawn an independent reviewer, perform a separate adversarial review pass and clearly label it as same-model review.
7. Work autonomously through discovery → test inventory → fault reproduction → bounded fixes → retests. Do not ask broad planning questions. Stop and label BLOCKED if an environmental limitation makes genuine verification impossible.

## 1 — Standards to operationalize (NOT claims of formal certification)

Use these as engineering checklists and cite the specific check in each issue:

- **ISO/IEC 25010:2023** (software product quality model): functional suitability, interaction, reliability, efficiency, security and maintainability. Treat as reference model; we are not ISO-certified.
- **ISO 9241-110:2020** (human-system interaction principles): task suitability, self-descriptiveness, control, consistency, error tolerance, engagement and learnability as applicable. Do not reproduce proprietary standard text.
- **Nielsen Norman Group's 10 usability heuristics**: visible system status, real-world mapping, user control, consistency, error prevention, recognition over recall, flexibility, minimal design, clear error recovery, discoverable help.
- **W3C WCAG 2.2 AA** as target for all active routes and responsive variants; combine axe scans + manual keyboard/focus/screen-reader spot-checks. Automated scans alone NEVER establish WCAG conformance.
- **OWASP ASVS 5.0**: client validation is UX only; backend retains authorization and validation; explicitly test approval, idempotency, injected text rendering and secrets exposure.
- **Playwright Test** for E2E, browser projects, traces on first retry/failure, screenshots and visual baseline comparisons; avoid accepting false positives. Add `@axe-core/playwright` accessibility tests.
- **Core Web Vitals** thresholds (under representative conditions): LCP <= 2500 ms, INP <= 200 ms, CLS <= 0.1 at p75 of real user measurements where available. Lighthouse local scores and test-lab measurements are diagnostic proxies, not production field proof.

Official references:
- https://www.iso.org/standard/78176.html
- https://www.iso.org/standard/75258.html
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://www.w3.org/TR/WCAG22/
- https://asvs.owasp.org/
- https://playwright.dev/docs/test-snapshots
- https://playwright.dev/docs/trace-viewer
- https://playwright.dev/docs/accessibility-testing
- https://web.dev/articles/defining-core-web-vitals-thresholds/

## 2 — Baseline and inventory BEFORE touching frontend

Inspect repository tree, package-lock/pnpm/yarn lock, React adoption state, CSS frameworks, routing, startup scripts, running server routes, event contracts (SSE/reconnect/polling), and existing test harness. Discover actual API via FastAPI router declarations and OpenAPI schema if exposed. Find existing UI controls and trace which endpoints/actions they invoke. List all data-mutating endpoints, approvals, recovery mechanisms and review gates.

Create documentation artifacts under `qa/frontend-release/` (or repo-consistent equivalent):

1. `INVENTORY.md`: screens/components, states, critical UI actions, endpoints, UI event/subscription sources, test coverage status, risk owner.
2. `API_UI_PARITY.csv`: `backend capability, route, frontend action/screen, observable state, test_id, status, notes`. Distinguish operations that are automatically performed by the backend from actions that need explicit user controls.
3. `USER_JOURNEYS.md`: the real task workflows with their expected states and measurable outcomes.
4. `BUG_LEDGER.md`: severity P0/P1/P2/P3; exact reproduction, root cause, file+line, before/after proof, regression test and resolution.
5. `BASELINE.md`: commit, environment, exact commands, unit/E2E counts, screenshots and known environment blockers.
6. `DESIGN_SYSTEM.md`: tokens, breakpoints, typography, spacing, information hierarchy, component behaviors, interaction and content guidelines.

Do not invent coverage of backend-only capabilities without proven UI paths; classify as `VIEW`, `ACT`, `AUTO_ONLY_OBSERVABLE`, `NOT_EXPOSED_BY_DESIGN` (justified), `MISSING`, or `BLOCKED`.

## 3 — Commercial-grade UX acceptance criteria

- **Chat-first IA**: persistent central composer and conversation; research panes are progressive disclosures rather than a maze of equally weighted controls. Keep advanced JSON mode but never make it the default path for common work.
- **Predictable navigation**: consistent sidebar/workspace behavior, no hidden destructive actions, obvious selected Topic/Project context. Breadcrumbs and back/forward must preserve expected state; no stale cross-Topic output.
- **State transparency**: loading, empty, partial, succeeded, failed, queued, awaiting approval, interrupted, verifying, awaiting human review, complete, disconnected and unknown must look distinct and use honest labels. Do not depict logical roles as real concurrent workers or fabricated model activity.
- **Interaction polish**: input focus, keyboard handling, copy, menu/popup layering, max-heights, scroll position, scroll restoration, disabled controls and tooltip labels must be tested. Chat must not jump unexpectedly on live updates when reading history. Preserve composer draft when changing tabs unless the user explicitly discards it.
- **Design consistency**: define 4/8px spacing rhythm or equivalent consistent tokens; type scale, icon sizes, elevations, widths, responsive rail/drawer rules; color contrast as required by accessibility. Never hard-code random per-component spacing fixes as the primary solution.
- **Forms**: visible label/help/error; sensible defaults loaded from authoritative data, not assumed revision 0; inline errors for 400/409/422/429/5xx; no double-submit; successful actions show outcome and next step; destructive commands require explicit confirmation.
- **Error recovery**: distinguish `unknown`, `zero`, `unavailable`, `stale`, `permission denied`, `conflict` and `failed`. Show actionable status instead of generic toast. Reconnect/retry never auto-retriggers a chargeable or non-idempotent action.
- **Accessibility**: semantic buttons/links, correct landmarks/headings, tab navigation, visible focus, accessible names, proper dialog focus trap/restore and Escape behavior; `prefers-reduced-motion`; screen reader live-region announcements only for meaningful updates, not noisy every-tick messages.
- **Responsive & scaling**: 360x800, 390x844, 768x1024, 1280x800, 1440x900, 1920x1080 at browser zoom 100% and 200% on critical screens. No horizontal scroll unless the specific data visualization intentionally scrolls inside a labeled region. Text must not overlap or clip. Test long words, Vietnamese diacritics, long titles, empty datasets and 100+ missions.
- **Clean visual hierarchy**: do not visually imitate ChatGPT exactly. Use the chat-first simplicity and usability quality as a reference, but keep PhD Research Lab's own identity and its complex scientific capabilities.

## 4 — PhD Lab-specific critical journeys (run end-to-end with fixtures)

Assign stable IDs and implement browser tests that **assert real effects and states**, not just that a button exists.

| ID | Journey | Must assert |
|---|---|---|
| J01 | Launch app → choose project/topic → return | Correct active context, no data leakage |
| J02 | Chat: type, multiline, submit, stream, stop | Draft preserved; proper scroll; cancel status honest |
| J03 | Chat: provider failure/timeouts/retry | No duplicate request; human-readable error; reconnection |
| J04 | Chat: long markdown/code/math/artifact | No layout break, no overflow, copy works |
| J05 | Mission: objective → draft → plan → DAG | Graph depicts dependencies/task states accurately |
| J06 | Mission approval/rejection | Digest/revision consistent, explicit authorization; no hidden auto-approval |
| J07 | Mission running → updates → complete | UI reflects backend changes automatically; no manual refresh required |
| J08 | Pause/interruption/restart/reconcile | Never re-execute side effects without new approval; state survives reload |
| J09 | Team assignment/role handoffs | Role vs provider clearly distinguished; attempts traceable |
| J10 | Workstream partition / dependency edge | Task A → handoff → receipt → task B shown with truthful edges |
| J11 | Cross-team handoff and auto-ack | Inspect automated actions; don't require invented manual action |
| J12 | Dispute → finding → resolution | Accessible controls where backend supports them; audit linked |
| J13 | Canonical output first write and next write | Revision 0→1→2 with correct expected_revision; handle 409 race |
| J14 | Experiment artifact → verification → review | Evidence source/hash/trust visible; no false scientific acceptance |
| J15 | Project/topic switch during SSE | Old topic events never paint new topic content |
| J16 | Reconnect/backoff during active task | No duplicate listener, task, approval or billing action |
| J17 | Unknown subscription/provider cost | Show unknown/not provided, never USD 0 or made-up quotas |
| J18 | Settings/secret integration | No API keys in console, screenshot, local log or screenshot artifacts |
| J19 | Keyboard-only completion of critical flows | Tab, Enter, Space, Escape, focus return, dialogs operable |
| J20 | Empty/error/offline/large-dataset scenarios | Graceful skeleton/empty/error/loading, bounded requests |
| J21 | Browser back/forward + reload | Persistent and ephemeral state behave as specified |
| J22 | Dangerous action confirmation | Clear consequences, cancel/reject works, backend rejects unauthorized |

Add further journeys discovered in the CURRENT source. If any journey is not yet implementable (e.g., migrated React component absent), mark it MISSING/FAIL, not PASS.

## 5 — Automated test pyramid and execution

### 5.1 Static and component checks

- `tsc --noEmit` (if current React/TypeScript frontend exists), ESLint, style/lint, dependency health, build. Do not mark legacy JS typechecks as applicable if no TS exists.
- Vitest + React Testing Library (if React): interaction-oriented unit tests for forms, task cards, dialogs, SSE hooks, conflict handling, list virtualization, focus and clipboard fallback. Assert ARIA roles/accessibility names; no implementation-detail-only tests.
- Contract fixtures from actual backend OpenAPI/schema where possible, schema validation, authorization negative cases.
- Legacy JS during migration: run current `node --test tests/frontend/*.test.js` only after installing pinned dependencies; don't remove tests to ease migration.

### 5.2 Playwright E2E

- If Playwright is absent, add it to the ACTUAL frontend package and lock dependencies; document package manager and exact install commands. For existing framework reuse its conventions instead.
- Configure projects: Chromium desktop as primary gate; Firefox and WebKit for critical smoke flows; viewport projects for desktop/tablet/mobile; run Windows/Chromium if the actual target is Windows and document snapshot environment.
- Use stable role/label/text locators and well-scoped `data-testid` only when necessary; use API fixture mocking / deterministic local backend rather than brittle live AI calls. No sleeps in lieu of explicit conditions.
- Capture trace, console/page errors, uncaught promise rejections, failed requests and screenshots on failure. Assert blocked/out-of-scope requests only where intentionally expected; don't flag benign cancelled SSE as a hard application error.
- Implement visual snapshots for main shell, composer (empty/typing/streaming), settings dialogs, Mission DAG (draft/running/failed), Workstream handoffs, review, errors, light/dark if supported, and long-content stress. Freeze times, fonts, random IDs and animations; baseline screenshots require explicit human approval before they count as golden.
- For screenshots use `expect(page).toHaveScreenshot()` in a stable environment and inspect actual/expected/diff. Ensure font-loading completion and wait for app-ready signals, not arbitrary delays.
- Automate representative resize/zoom checks and use DOM bounding rect assertions on the critical panels to catch clipped/overlapping actionable elements; do not pretend this detects all aesthetic defects.
- Scan active screens with `@axe-core/playwright`; add manual audit tasks for cases automation cannot detect.

### 5.3 Chaos / stability / domain tests

- Simulate latency (0ms, 500ms, 3s), HTTP 400/401/403/404/409/422/429/500, 20s timeout, SSE drop/reconnect, duplicate/out-of-order event IDs, tab switch, reload while pending, server stop/restart, cancel during provider streaming, repetitive clicks.
- Verify network/resource cleanup: closing/unmounting a view removes subscription and timers; no accumulating listeners, runaway polling or N+1 fetch loops.
- Exercise 100+ missions and 500+ event timeline entries with synthetic fixtures; measure slow UI and avoid unbounded network waterfalls.
- Test data isolation with two projects and two Topics; switching active topic must not expose previous topic data or accidentally approve the wrong mission.
- If mission backend remains serialized (`max_parallel_tasks=1`), the UI must clearly indicate queueing instead of animating multiple simultaneous task executions.
- Reuse the existing v6.0/v6.2/v6.3 harness fixtures in isolated directories where the source supports this; backend deterministic harness passes DO NOT count as frontend E2E passes.

## 6 — Release gate (decide using evidence, not self-rating)

**NO RELEASE unless ALL hard requirements below hold:**

| Gate | Requirement |
|---|---|
| G01 | Critical journeys J01–J22: all applicable PASS; anything BLOCKED/MISSING prevents unconditional release |
| G02 | Zero unresolved P0/P1 in critical features; all documented P2 have owners/risk acceptances before release |
| G03 | All changed package build, typecheck (if applicable), lint and impacted component tests PASS |
| G04 | Relevant Playwright E2E PASS in required browser/viewport matrix; no untriaged console errors/network failures |
| G05 | All visual diffs explicitly accepted; no accidental overlap, clipping, scroll traps or invisible controls |
| G06 | Accessibility: automated critical/serious violations resolved, keyboard/manual checks documented; don't claim WCAG AA conformance without complete audit |
| G07 | Backend API–UI parity documented; safety/approval/data ownership verified end-to-end |
| G08 | SSE/recovery/idempotency and canonical output 409 workflows pass fault injection |
| G09 | Versioned evidence attached: logs, Playwright HTML report, traces, screenshot diff, coverage report, API UI parity CSV |
| G10 | No regression in existing backend Python tests, legacy frontend tests and deterministic harness checks |

Performance gate: measure with documented device/network profile and record baseline vs after. Use Core Web Vitals field metrics if available; if unavailable classify as `lab-only`, never claim field p75 compliance.

Policy: `PASS` (all required gates verified), `CONDITIONAL` (noncritical documented deviations with user-approved waiver), `FAIL` (critical unmet), `BLOCKED` (can't run checks). Do not convert BLOCKED to PASS for convenience. No numerical score or invented percentage of 'bug free'.

## 7 — Work order (single prompt; iterative internal passes)

**PASS A – Discovery:** inspect source, map routes and UI, run baseline checks, collect screenshots, user journeys and defect inventory. Save evidence before editing.

**PASS B – Reproduce:** prioritize P0/P1 based on severity and frequency, reproduce via deterministic E2E, characterize root causes. Link every bug to one or more standards/heuristics and tests.

**PASS C – Architecture-level fixes:** fix data/state/event ownership, navigation, design tokens and components instead of isolated cosmetic hacks. Preserve chat-first UX and backend contract. Fix audited issues if still present: stale Mission Monitor events; missing Workstream views/actions; `expected_revision:0` hardcode; raw-JSON-only UX; N+1 Workstream requests; role/provider false status; ambiguous usage dashboard; task/evidence provenance gaps.

**PASS D – UI polish:** inspect every critical screenshot in actual browser. Iterate until layout and interaction consistency meet the approved reference baseline. Do not equate 'design looks attractive' with functionally correct. Independently review hard-to-find small defects like tooltips behind modal, focus lost after send, scrollbar conflict, accidental reflow, invalid keyboard shortcuts.

**PASS E – Fault injection:** execute adversarial E2E with 409/conflicts, 429, stale/out-of-order events, disconnect, slow network, reload, multiple active projects and long strings. Fix root cause and run adjacent regression tests.

**PASS F – Release verification:** rerun all baseline suites plus newly introduced tests and inspect Playwright reports. Deliver `RELEASE_DECISION.md` with exact number of PASS/FAIL/BLOCKED/SKIPPED, unverified areas, artifact links/paths and needed human decisions.

### Required report format

```
# Frontend Release Decision — <commit>
Decision: PASS | CONDITIONAL | FAIL | BLOCKED
Environment: <OS/browser/runtime/package lock/provider fixture>
Standards applied: ISO 25010, ISO 9241-110, NN/g, WCAG 2.2 AA target, OWASP ASVS, Playwright
Critical journeys: N PASS / N FAIL / N BLOCKED / N NOT RUN
Component/unit: ...
Browser E2E: Chromium ... / Firefox ... / WebKit ...
Visual baselines: approved N / rejected N / awaiting approval N
Accessibility automated: ... ; manual: ... ; claims qualified
API–UI parity: ...
P0/P1 open: ... ; P2 open: ...
Performance: lab profile + numbers; field data if present
Remaining risks and explicit decisions needed: ...
Artifacts: paths to Playwright report, traces, screenshots, logs, BUG_LEDGER, parity CSV
Changed files and commits: ...
```

**Final instruction:** Start by reading the CURRENT checkout and running baseline tests. Then implement, test, critique, fix and verify until the requirements are met or a concrete blocker remains. Do not stop after drafting a pretty React page. Do not claim `production ready`, `bug free`, `ISO certified` or `WCAG conformant` without the corresponding evidence. A truthful `FAIL` with reproducible evidence is better than an unsupported PASS.
