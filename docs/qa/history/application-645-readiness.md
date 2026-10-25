# Historical application assessment, not integrated candidate certification

# Full harness release assessment — 2026-10-25

**NO-GO. The requested 100% regression/coverage and all-provider qualification have not been achieved.**
The passing cases below certify only their assertions. Missing providers, skipped cases and unsupported benchmark executors are not successes.

| Layer | Executed result | Scope |
|---|---|---|
| Backend | 805/812 pass; 0 failures, 0 errors, 7 skips | Offline unit/integration; stable source hash: True |
| Backend lines | 23543/26168 (89.97%) | All backend production sources in .coveragerc |
| Backend branches | 7027/8712 (80.66%) | Combined coverage.py figure: 87.64%, not line coverage |
| Frontend | 174/174 pass; 0 skips | Vitest/jsdom, 2 workers |
| Frontend coverage | Lines 64.25%; branches 63.46%; functions 50.34%; statements 62.77% | Whole production TS/TSX, including unimported files |
| 2D | 26 passed, 0 failed | Chromium, real HTTP/state/LM; selected journeys |
| 3D | 1 passed, 0 failed | WebGL2, camera pixels, lighting, dock, return to 2D |
| CLI | PASSED | Real child process, 8 settings groups, EN/VI persistence, actual 391 response |
| Golden Thread | 10 steps PASSED | Actual CPU synthetic experiment, replay, recomputation, real figure and compiled paper |
| Native vs wrapped | Native 6/6; wrapped 6/6 | Spark 4B, three tasks repeated twice; earlier two model-unloaded errors retained |


Canonical machine report: [evidence/2026-10-25/summary.json](evidence/2026-10-25/summary.json).
All recorded attempt/case outcomes: [attempts](evidence/2026-10-25/attempts.json), [CSV](evidence/2026-10-25/all-case-results.csv).
Raw traces, screenshots, request logs and console output remain in `output/playwright/full-20261024`; they are intentionally ignored by Git.

## Failures retained and repaired

- Frontend baseline: 173/174; native-launch accessible label fixed. A later unconstrained-worker run had two async timeouts; the bounded 2-worker run passed all 174. No assertion was removed to hide these failures.
- Backend historical failures exposed completion/cancellation races, stale gateway reconciliation and nondeterministic temporal retrieval. Stored timestamps now define temporal order; equal instants use record ID. See each attempt and exact test details in the CSV.
- 2D multi-turn chat returned 84 rather than 782 after unrelated chat context poisoned the turn. Default context no longer imports unrelated conversations; selected/folder-shared sources remain supported. Final 2D suite passed.
- Initial 3D selector was ambiguous; exact control selection fixed the test. Final WebGL2 test and screenshot inspection passed the measured behavior.
- First Golden Thread attempts failed on code-project prerequisites. Two subsequent script passes were **invalidated by visual QA**: PNG exports were fixed placeholder grids. The renderer now derives vector PDF and raster PNG from the same SVG; legacy PNG/PDF versions require regeneration. Only `golden-verified/paper.pdf` is accepted in this evidence pack.
- The first native/wrapped benchmark had two model-unloaded errors. The serial rerun passed 12/12 calls. Their cause is not established; this sample does not prove sustained provider reliability.

## Remaining work

Backend coverage has 2625 uncovered executable lines and 1685 uncovered branches. Frontend has 1358 uncovered lines and 1495 uncovered branches. Add behavior oracles without reducing denominators, mocking live runs, changing assertions to success, or weakening the 100% gate.

Complete native application window checks, full EN/VI labeling, all registered workflow execution adapters, every required viewport/control, full architectural consolidation, remaining providers, remote Windows/Linux CI, and independent scientific review. Auth/quota/services require actual external availability; subscription CLI access does not imply cloud API credentials.

The CPU experiment is an explicitly synthetic QA fixture. Its paper is a reproducibility artifact, not a claim of new research or publication readiness.
