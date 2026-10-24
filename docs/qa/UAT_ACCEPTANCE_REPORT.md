# Browser and AI-UAT acceptance checkpoint

Date: 2026-10-25 task date (Asia/Saigon). Version under development: 6.5.0, separate governance worktree. **Decision: BLOCKED / not release-qualified.** This is an execution checkpoint, not a completion certificate.

## Installed and inspected

Official browser-harness revision `6d1c39adbcba5599a35182a19bcfbb0859e50abb` and browser-use revision `3df5806a0d097a1546d92c49bcf1b28c9972c3bd` were inspected. Browser Harness's personal Chrome default and upstream QA skill's cloud-only/default scoring flow were not adopted. Official Browser Use open-source reference skill and license were installed under skills/ with pinned provenance. Browser Use 0.13.11 was installed in a dedicated Python 3.12 environment from hash-locked requirements-uat.lock. No Browser Use cloud subscription/key was used.

Playwright remains the authoritative regression runner. Actual browser tested here: Chromium on Windows, headless. No Firefox/WebKit/mobile-browser/device certification is claimed.

## Executed deterministic results

| Check | Actual result | Evidence |
|---|---|---|
| Development verifier policy | 17/17 unit behavior tests pass | governance targeted-fixed report; functional malformed-contract RED/GREEN retained |
| Native dev auto-merge policy | 20/20 controlled Node tests pass | `.github/scripts/automerge.test.cjs`; this is not an actual GitHub merge |
| UAT policy | 6/6 tests pass | browser-uat-audit functional RED/GREEN; fractional/string bounds reproduced and corrected |
| Original real app smoke | 1/1 pass | Actual server/browser, Settings and return to workspace, no LLM |
| Extended browser self-test first attempt | 5/7 pass, 2 fail | Wrong EN selector and subsequent leaked VI fixture state; retained raw traces |
| Extended browser self-test corrected | **7/7 pass** | browser-uat-audit/selftest-fixed.log and unique ci/browser run artifacts |
| Clean Python installs | 3.11.17 and 3.12.15 hash-locked installs pass | clean-install logs; compileall exposed and then verified fixes for three 3.12-only f-string escapes |

The EN/ENG selector mistake was a test defect; no app bug was fabricated. Test setup/cleanup now resets language in the disposable backend. Injected console/rejection/network/broken-button fixtures are marked MOCKED and do not count as production failures or repaired application bugs.

## Actual local AI exploration

The Browser Use adapter launched its own browser and application, with a dedicated profile and origin-only proxy. An actual browser fetch to `http://example.invalid/uat-canary` was denied; its expected CORS/network errors are fault-injection evidence.

Initial adapter setup encountered missing-home configuration under the deliberately stripped worker environment. The configuration/cache paths were isolated; USERPROFILE is retained unchanged for library path calculation, while Python worker file/network/process access is restricted. The first canonical model run opened Settings using actual Spark inference but repeated structured JSON output truncation at the adapter's 1,800-token cap. That was an infrastructure budget defect, not evidence of weak application intelligence. The next bounded run used 6,000 output tokens, opened Settings and executed a Vietnamese language change with HTTP 200, then hit the 180-second total deadline before the required English restoration/completion.

| Run | Result | Qualified scope |
|---|---|---|
| browser-uat-runs initial probe | BLOCKED (adapter initialization) | Owned browser readiness/egress only |
| governance/uat-canonical-1 | BLOCKED (worker initialization) | No completed AI journey |
| governance/uat-canonical-2 | BLOCKED (truncated output and shutdown timeout) | Actual inference + Settings navigation; incomplete acceptance |
| governance/uat-canonical-3 | BLOCKED (deadline) | Actual inference, Settings and VI POST 200; required VI -> EN journey incomplete |

Full logs, model actions where available, browser evidence, trace and final screenshot are preserved under the worktree's output/playwright/. The last screenshot was visually inspected: it shows Vietnamese Settings and the disposable project path. It does not prove exhaustive UX quality. Per-step history preservation on timeout and a narrower settings-only backend capability fence were added afterward and remain separately subject to validation; no additional model run was silently performed after the budget was exhausted.

The persistent `TASK-UAT-LOCAL-ADAPTER` repair ledger is **3 failures, can_repair=false**. Automatic exploratory model retries for this task have stopped. Required high/critical AI-UAT remains BLOCKED. No independent acceptance review or scientific/release approval has been invented.

## Required self-test traceability

| Requested capability | Evidence / current state |
|---|---|
| Open app, navigate route | Real smoke PASS |
| Complete form, button reaches backend | Actual language POST + persisted API state PASS |
| Failed action produces artifacts | Controlled missing-button test stores screenshot, trace and actual/expected report PASS |
| Console/unhandled rejection detection | Explicit controlled injection captured PASS |
| Network failure and recovery | Actual request abort + release + reload PASS |
| Persistence after refresh | Language API state and rendered English navigation PASS |
| Defect -> regression -> corrected behavior | Controlled broken/fixed fixture demonstration PASS; not a product bug claim |
| Required failed checks block merge | Controlled aggregate/auto-merge policy tests PASS; live acceptance PR red->green->merge not executed |
| Playwright without LLM | 7 browser self-tests PASS |
| Missing exploration is not PASS | UAT policy tests and real BLOCKED attempts |
| Concurrent browser isolation | Distinct contexts' cookies/storage verified; separate run-space/server allocation implemented, multi-agent live run not yet certified |
| Five personas and complete product exploration | Five persona definitions and feature selector implemented; only settings exploratory adapter exists; full exploration NOT RUN |

## CI and release limits

GitHub main/dev/qa protections and owner-enabled repository auto-merge are real API-verified settings. The new workflow definition, high-risk UAT evidence integration, trusted live producer, final local feature run, push/PR and GitHub acceptance execution are still being completed. The new workflow_run auto-merge handler is inactive until its trusted code reaches protected default main through the approved flow. No automatic dev merge is claimed operational yet.

Known production coverage remains below the required 100%; earlier 6.4.4 coverage and Golden Thread reports do not certify modified source. Full 2D/3D/CLI/provider/scientific qualification and independent/human review remain mandatory before release.

## Additional executed checkpoint

- Policy suite: 36/36 PASS (17 development harness, 6 UAT bounds/truth, 5 acceptance gate, 6 feature/persona/defect selection, 2 wrapped failure reporting). Separate real disposable server/browser/worker boundary suite: 3/3 PASS, no model. The new worker mutation test reproduced an actual missing delete fence using a private canary; after correction the canary is retained and outside removal is denied. These controls are not whole-machine containment certification.
- Malformed `browser_acceptance` fields previously bypassed validation; functional RED/GREEN is retained. Required fields now reject string booleans, missing/string journeys and malformed path/review types. The selector consults unchanged affected contracts too. Five persona configurations reference actual existing Playwright suites; routine CI excludes inference workflows; unsupported exploratory adapters remain explicit.
- Failure fingerprints now group 50 wrapped database errors by the originating exception and prioritize actual errors over large skip groups. Both behaviors have recorded functional RED/GREEN.
- Actual strict backend checkpoint: 835 executed, 826 PASS, 1 environment error, 8 SKIP. Coverage 23559/26218 lines and 7053/8712 branches (87.64% combined), FAIL. The SQLAlchemy DLL error passed only in a subsequent focused Optuna test after an official same-version pure-Python build. No full recertification implied.
- Actual strict frontend: 174/174 assertions PASS; lines 2439/3799 (64.20%), statements2568/4094 (62.72%), functions731/1454 (50.27%), branches2592/4092 (63.34%); strict coverage FAIL.
- 74 library/memory/dependency/project compatibility tests PASS. Nonsecurity legacy SHA1 identifiers were annotated explicitly, without invalidating keys; evidence integrity still uses SHA256. High/high Bandit and actual pip-audit over70 resolved dependencies PASS; these are bounded scans, not a security certification.
- Final feature/current-source browser run, commit/push and GitHub Actions status must be appended after execution. Trusted live producer remains absent; the QA evidence checker blocks it rather than faking a successful workflow.

Further security regression: a real settings-only server initially inherited canary provider/GitHub keys. Safe functional RED/GREEN records (`server-env-red-safe.json`, `server-env-green.json`) verify that application and Node/browser children now receive an environment allowlist. No user key was put in the fixture. The original private diagnostic is excluded from publication. The auto-merge handler also now returns an explicit BLOCKED decision if protection cannot be independently read; a separate Administration:read policy credential is an unprovisioned prerequisite. The 20th controlled Node test verifies this fail-closed path, not actual token provisioning.

The first final feature attempt completed 799 backend cases (791 pass/8 skip), frontend174/174 and Playwright20/20 plus actual boundary3/3, but remains BLOCKED because source changed during the security audit. It is not a matching-source final gate. Comparing its selected backend IDs with strict discovery exposed49 omitted nested-package tests. A new functional RED/GREEN confirms recursive package-aware selection; final verification must rerun with those cases included. This correction saves no tokens by dropping tests.

The initial recursive correction over-selected unpackaged legacy live_e2e modules. That verifier process tree was stopped deliberately at a negative unreachable-model case; `feature-stable-final/ABORTED.json` records it. The selector now follows recursive ordinary unittest packages, records known legacy live modules separately as NOT_RUN, and blocks unknown unpackaged test directories. Functional RED/GREEN demonstrates all three boundaries. This does not reduce mandatory offline coverage or qualify the separate real-provider/scientific layer. The definitive local attempt will be `feature-qualified-local`.

The aborted legacy selection appended9 local-call ledger entries labeled phi-4 and one mission event. They are retained under output/playwright/governance/aborted-legacy-live and explicitly UNQUALIFIED; they do not certify Spark or the Browser Use journey. Checked-in ledgers were restored only after verifying their unchanged baseline prefix (LF/CRLF normalized) and preserving complete appended files. This unintended selection error is now covered by a regression; no result from that run satisfies a merge/release gate.

`feature-qualified-local` ran850 backend cases (842 PASS/8 SKIP), frontend174/174, Playwright20/20 and real boundary3/3 with stable source, but correctly failed overall because Windows could not remove a still-open temporary SQLite database after unit completion. The worker now owns a separate test child process, waits for its exit to release handles, then cleans its verified temporary allocation. A real held-SQLite connection fixture has functional RED/GREEN evidence; cleanup failure is not suppressed. The definitive rerun is `feature-process-cleanup-final`.

## Definitive local feature result

`feature-index-stable`: **PASS for feature/all**, stable source and Git index. Backend851 cases:843 PASS,8 SKIP,0 FAIL/ERROR; cleanup complete. Frontend174/174, actual Playwright20/20 and boundary3/3 PASS. Combined1040 PASS/8 SKIP. The raw current-source report is checked in at evidence/governance/feature-index-stable.json.39 development verification policy/worker tests and20 controlled Node policy tests passed. The8 skips are not live qualification and do not satisfy strict PR/full/release completeness.

The preceding all-green test execution remained BLOCKED because staging deleted workflows changed the verifier's Git input inventory; only those two absent keys differed, with no source-file content change. It was rerun, rather than relabeled. Required exploration, independent review, global100% coverage and research/provider gates remain unmet. GitHub execution and commit/PR identifiers are recorded in the PR and latest local STATE after publishing.

## First actual GitHub execution

PR7, commit947d993, run40136777730: contract/workflow policy and security/dependency checks PASS. Required UAT correctly blocks missing qualified evidence. Browser startup FAIL on Linux: Chromium was installed, then XDG_CACHE_HOME isolation changed its lookup directory. A shared explicit PLAYWRIGHT_BROWSERS_PATH for install/runtime is being validated; profiles remain private. Raw job logs and browser artifact are retained under output/playwright/governance/github-ci. This failure is not counted as a product UI bug or a completed Linux browser journey.

The explicit Chromium binary-path correction passed fresh local feature/all verification (`feature-ci-browser-cache`):1040 PASS/8 unqualified SKIP, stable source/index;851 backend,174 frontend,20 Playwright and3 actual boundary checks. It remains an unreleased6.5.0 PR correction. A new Linux CI execution is required; the failed947d993 run remains retained.
