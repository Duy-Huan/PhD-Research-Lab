# CODEX MASTER MISSION
# PhD Research Lab — Exhaustive Production Hardening & Quality Audit

Act as a Principal Software Quality Architect, Senior UI/UX Engineer, Full-Stack SDET, Concurrency Engineer, and Production Release Manager.

## MISSION

Perform the most comprehensive practical production-quality audit possible on the EXISTING PhD Research Lab application.

The application is an All-in-One AI Research OS with:
- React or existing frontend technology.
- Python backend.
- Unified research chatbox.
- L2/L3/L4 research orchestration.
- Dynamic multi-agent Harness.
- Visual workflow builder.
- Preset and custom research workflows.
- Multiple CLI, cloud, MCP and local AI providers.
- Research engines such as Feynman, OpenScience and OpenCode.
- Long-term context memory.
- Research artifacts and experimentation.

Your objective is to identify, reproduce, repair and permanently prevent defects throughout the application, including small visual, linguistic, interaction, asynchronous and consistency issues.

Do not add unrelated features.

Do not redesign the application's established product philosophy.

Do not declare success merely because existing automated tests pass.

# PHASE 0 — PROTECT THE EXISTING PRODUCT

Before modification:

1. Inspect Git status.
2. Preserve existing uncommitted work.
3. Create a dedicated production-hardening branch.
4. Inspect application startup, database configuration and data directories.
5. Establish isolated test storage and disposable research projects.
6. Never delete or overwrite real research data.
7. Never expose credentials or provider tokens.
8. Establish a reproducible baseline.

Feature freeze: fix defects, improve consistency and add tests only.

Any behavioral redesign requires explicit justification.

# PHASE 1 — COMPLETE APPLICATION INVENTORY

Inspect actual frontend source, routing, components, backend endpoints, workflow registry, provider registry, settings and persisted data structures.

Build a machine-readable inventory containing:

- Every page and route.
- Every visible control.
- Every form field.
- Every dialog and popup.
- Every dropdown and menu item.
- Every navigation transition.
- Every notification and status indicator.
- Every user-facing text string.
- Every loading, empty, error and success state.
- Every workflow preset.
- Every custom workflow capability.
- Every implemented node type.
- Every provider configuration surface.
- Every frontend-to-backend interaction.

Each identified feature must receive a stable test ID and an explicit expected behavior.

Produce a feature-to-test traceability matrix.

Do not mark untested features as passing.

# PHASE 2 — REAL BROWSER SETUP

Inspect existing browser testing infrastructure.

Install or repair:
- Playwright Test.
- Chromium.
- Browser dependencies.
- @axe-core/playwright.
- Screenshot regression tooling.
- Appropriate i18n lint tools.
- Backend integration testing utilities.

Start the REAL application.

Use actual frontend and backend processes.

Verify browser connectivity, frontend rendering, backend readiness and WebSocket availability.

Collect console, page errors, request failures and backend logs.

Do not treat DOM snapshots alone as complete visual validation.

# PHASE 3 — PIXEL-LEVEL UI AUDIT

Inspect every route at relevant viewport sizes:

- 1920 × 1080
- 1440 × 900
- 1366 × 768
- 1024 × 768
- 768 × 1024
- 390 × 844

Evaluate applicable layouts and document unsupported screen classes.

Audit:

1. Typography and font consistency.
2. Text hierarchy and readability.
3. Padding and margin consistency.
4. Alignment and centering.
5. Button size and hit targets.
6. Icon alignment.
7. Border radius consistency.
8. Colors and contrast.
9. Hover and focus states.
10. Selected and disabled states.
11. Dropdown positioning and layering.
12. Modal boundaries and scrolling.
13. Sidebar and panel resizing.
14. Text truncation and wrapping.
15. Horizontal and vertical overflow.
16. Long filenames and research titles.
17. Empty and sparse content layouts.
18. Dense data tables.
19. Graph and canvas rendering.
20. Dark/light theme consistency.
21. Browser zoom and high-DPI rendering.
22. Tooltips and contextual menus.
23. Loading skeletons and progress indicators.
24. Notification stacking and dismissal.
25. Layout shifts during streaming.

Use screenshot comparisons against reviewed, approved visual baselines.

Use DOM geometry checks for clipped, overlapping, inaccessible and offscreen interactive elements.

Do not automatically accept the first screenshot as a correct design.

Do not silently update snapshots to make regressions pass.

Repair confirmed UI defects and verify them visually.

# PHASE 4 — BILINGUAL LANGUAGE CONSISTENCY

Audit all user-facing Vietnamese and English text.

Find:
- Mixed-language navigation.
- English labels inside Vietnamese interfaces.
- Untranslated tooltips.
- Missing translation keys.
- Duplicate or contradictory terminology.
- Hardcoded strings bypassing localization.
- Incorrect diacritics.
- Spelling and grammar errors.
- Inconsistent capitalization.
- Ambiguous technical terminology.
- Incorrect plurals and placeholders.
- Wrong date, time, number and currency formatting.
- Locale persistence bugs.
- Truncated translated text.
- Backend error messages bypassing localization.

Define a consistent terminology glossary.

Examples:
- Workflow
- Harness
- Agent
- Research Provider
- Research Engine
- Checkpoint
- Experiment
- Research Memory

Use an explicit glossary and locale policy.

Do not translate technical proper nouns inconsistently.

If both Vietnamese and English locales are supported, validate each independently.

Verify language switching does not:
- Lose unsaved work.
- Reset workflow state.
- Change identifiers.
- Interrupt active execution.
- Mix old and new translations.

Preserve the selected locale after application restart.

Do not globally translate scientific user content or stored research results.

# PHASE 5 — INTERACTION MICRO-TESTING

Test every interactive control.

For each relevant control, test:
- Single click.
- Double click.
- Rapid repeated click.
- Keyboard activation.
- Disabled behavior.
- Slow response.
- Failed response.
- Navigation during execution.
- Refresh during execution.
- Cancellation when available.

For every form:
- Empty input.
- Valid input.
- Invalid input.
- Boundary-length input.
- Unicode and Vietnamese text.
- Special characters.
- Duplicate submissions.
- Unsaved changes.
- Validation messages.
- Save and reload persistence.

Verify observable results, not merely successful clicks.

A button that visually responds without producing the expected backend or application-state change must fail its test.

# PHASE 6 — ASYNC, CONCURRENCY AND STATE RACES

Prioritize detection of subtle asynchronous bugs.

Test:

- Out-of-order API responses.
- Stale responses overwriting newer state.
- Rapid project switching.
- Rapid conversation switching.
- Simultaneous workflow actions.
- Double-submitted execution requests.
- WebSocket reconnection.
- Duplicate streamed messages.
- Lost or reordered streaming chunks.
- Cancellation during an API request.
- UI unmount during pending requests.
- Delayed backend state updates.
- Multiple browser tabs editing the same workflow.
- Optimistic updates failing to reconcile.
- Loading states that never terminate.
- Race conditions between save and navigation.
- Provider switching during execution.
- Process interruption and restart.

Use reproducible controlled-delay tests in an isolated environment.

Combine deterministic fault-injection tests with real-backend integration tests.

Verify idempotency, consistency and recovery.

Never rely on arbitrary sleep delays as proof of correctness.

# PHASE 7 — HARNESS STUDIO EXHAUSTIVE VALIDATION

Audit every implemented feature of the Harness Studio and Workflow Builder.

Include:

- Workflow templates.
- Custom workflow creation.
- Visual drag and drop.
- Node configuration.
- Node and edge deletion.
- Graph validation.
- Conditional branching.
- Parallel execution.
- Bounded loops.
- Dynamic agent-team creation.
- Agent roles and provider assignment.
- L2/L3/L4 mode changes.
- Human approval.
- Save and reload.
- Workflow import/export.
- Run, pause, resume, cancel and retry.
- Execution progress.
- Event logs.
- Artifacts and evidence.
- Crash recovery.

Discover registered workflow definitions and test them systematically.

Distinguish:
- Schema validation.
- Browser interaction tests.
- Runtime execution tests.
- Full research end-to-end tests.

Use graph and state-transition coverage to control the growing number of workflows.

Verify that the displayed execution status matches the actual backend state.

# PHASE 8 — PROVIDER & RESEARCH INTEGRATION

Audit actual registered provider adapters.

For each available provider, verify:
- Connection status.
- Authentication readiness.
- Configuration persistence.
- Request execution.
- Response streaming.
- Cancellation.
- Timeout.
- Error propagation.
- Retry policy.
- Usage accounting.
- Provider switching.
- Resource cleanup.

Use local Phi-4 for suitable real-model tests.

Perform real cloud-provider tests only when credentials, authorization and usage limits permit.

Never claim an unavailable provider passed.

Never replace provider integrations with mocks without explicitly labeling the test.

# PHASE 9 — ACCESSIBILITY AND USABILITY

Use axe-core and browser-based keyboard tests.

Check:
- Semantic controls.
- Accessible names.
- Keyboard navigation.
- Focus trapping.
- Focus restoration.
- Contrast.
- Form labels.
- Dialog accessibility.
- Error identification.
- Screen-reader-relevant status messages.
- Canvas keyboard alternatives where applicable.

Also audit:
- Unnecessary clicks.
- Confusing terminology.
- Dead-end navigation.
- Hidden actions.
- Inconsistent save behavior.
- Missing feedback after operations.
- Unclear destructive actions.
- Excessively dense controls.

Accessibility automation is incomplete by nature. Record manual-review requirements separately.

# PHASE 10 — AUTONOMOUS BUG REPAIR LOOP

For every confirmed defect:

1. Capture exact reproduction steps.
2. Store screenshot, trace and relevant logs.
3. Classify severity and affected features.
4. Create a regression test reproducing the defect.
5. Identify the root cause.
6. Make the smallest appropriate code fix.
7. Run affected tests.
8. Perform a real-browser visual inspection when relevant.
9. Rerun related regression scenarios.
10. Record the outcome and commit the fix.

Do not fix symptoms by suppressing error messages.

Do not weaken assertions, skip tests, or auto-approve visual baselines to obtain PASS.

Use bounded repair iterations.

Escalate unresolved defects instead of retrying indefinitely.

# PHASE 11 — QUALITY METRICS

Measure separately:

- Route coverage.
- Component interaction coverage.
- User-visible string coverage.
- Locale-key coverage.
- Visual state coverage.
- API contract coverage.
- Async scenario coverage.
- Workflow node and branch coverage.
- Provider integration coverage.
- Real E2E workflow coverage.
- Line and branch code coverage.
- Accessibility violations.
- Known defects by severity.
- Flaky test rate.

Report exact numerators and denominators, not unsupported percentages.

For each unverified feature, report a reason.

# PHASE 12 — PERMANENT QA FRAMEWORK

Commit permanent automated tests into the repository.

Create or extend:

- Playwright browser test suite.
- Visual regression baselines.
- Localization audits.
- Accessibility tests.
- Async and race-condition tests.
- Backend integration tests.
- Workflow runtime tests.
- Research E2E tests.
- Release qualification scripts.
- GitHub Actions workflows.
- AGENTS.md QA policies.

Provide reproducible commands to run smoke, targeted, full and release suites.

# PHASE 13 — PRODUCTION RELEASE GATE

Do not declare READY until:

- All identified release-critical interactions pass.
- No known P0/P1 defects remain.
- No critical unsaved-state or data-loss defects remain.
- Required Vietnamese and English UI checks pass.
- Approved visual baselines pass.
- Mandatory L2/L3/L4 research flows have verified execution evidence.
- Required provider integrations have documented compatibility results.
- All critical workflow state transitions pass.
- Restart and persistence scenarios pass.
- Mandatory security and accessibility gates are satisfied.
- All blocked tests and accepted residual risks are documented.

Run relevant suites multiple times to detect instability.

Any unresolved mandatory test results in NO-GO.

# PHASE 14 — REPORT AND COMMIT

Generate:

docs/qa/FEATURE_INVENTORY.md
docs/qa/UI_UX_AUDIT.md
docs/qa/I18N_AUDIT.md
docs/qa/ASYNC_RACE_AUDIT.md
docs/qa/HARNESS_COVERAGE.md
docs/qa/BUG_REGISTER.md
docs/qa/RELEASE_READINESS.md

Each bug must have:
- Unique ID.
- Severity.
- Reproduction evidence.
- Root cause.
- Fix commit.
- Regression test.
- Verification status.

Commit implementation and tests to a dedicated branch.

Never overwrite unrelated uncommitted work.

Do not push or merge without permission.

Report actual commit hashes, test counts, coverage, remaining defects and release status.

# EXECUTION DIRECTIVE

Do not merely inspect code.

Run the REAL application, interact through a REAL Chromium browser, inspect rendered screenshots, reproduce defects, fix source code, and verify results.

Prioritize actual observed defects and preserve all existing product functionality.

Do not stop at a positive test summary.

Complete as much of the audit as can be verified in the current execution environment and report the remaining work explicitly.

The goal is a production-quality application with zero KNOWN release-blocking defects, not an impossible guarantee of zero bugs.