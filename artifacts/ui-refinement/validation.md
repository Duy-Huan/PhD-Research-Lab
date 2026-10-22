# UI refinement validation — 2026-10-22

Scope: the existing chat-centric frontend, project browsing, message pins, calendar dates, local color-theme packages, bilingual labels and Library PDF naming. Base revision: `459fc13`.

## Frontend regression and coverage

`node tests/frontend/run.js` passes **132 tests**, with no failures or skips. [Final output](frontend-final.log), [LCOV](frontend.lcov).

| Measure | Covered / total | Coverage |
| --- | ---: | ---: |
| Lines | 4,296 / 4,296 | 100% |
| Branches | 3,375 / 3,375 | 100% |
| Functions | 1,114 / 1,114 | 100% |
| First-party scripts | 14 / 14 | All measured |

The runner checks every `.js` file in `frontend/assets/`, fails on missing scripts and counts uncovered functions as well as lines and branches. Zero and unknown branch counts both fail the gate. The first-paint code was moved from inline HTML into a measured script. There are no coverage ignore annotations, module exclusions or skipped frontend tests. Vendor code and CSS are outside the JavaScript measurement; browser checks below cover the visual behavior.

The [baseline](coverage-before.log) was 97.06% lines, 93.81% branches and 89.98% functions across 99 passing tests. The baseline gate failed, as expected.

New regressions cover slow and stale API responses, failed saves, blocked storage, cold initialization, keyboard controls, source selection, mission approvals, protocol/claim review, team/workstream controls, malformed chart data, responsive charts, PDF exports, persistent pins, project isolation and theme package validation/install/remove.

## Real-browser regression

`node tools/ui_visual_check.js http://127.0.0.1:8799 artifacts/ui-refinement` passes **12 checks** in real headless Edge, with **zero JavaScript errors**. The server is `tools/demo_server.py`, using temporary data and a fake model. [Check results](browser-checks.json).

- [Before](before.png) / [after](after.png): matching desktop window and preserved layout.
- [Chat pins](after-chat-pins.png), [project groups](after-projects.png).
- [Light themes](after-themes-light.png), [dark themes](after-themes-dark.png).
- [Mobile settings](after-mobile-settings.png), [mobile chat](after-mobile-chat.png): 390 × 844; no horizontal page overflow or overlapping header actions.
- [English settings](after-english-settings.png): translated controls with preserved user-authored project/chat names.

The checks verify pin persistence and immediate unpin rendering, project grouping, theme tokens and the selected dropdown, keyboard focus, readable mobile tabs, translated settings, reduced motion and responsive geometry. Screenshots were inspected after capture.

## Backend regression

The final full backend regression passes **647 tests, with 7 skips**, in 396.605 seconds. [Full log](backend-full.log). The final focused API run passes **36 tests** ([log](backend-final-focused.log)); the PDF-focused run passes **6 tests** ([log](backend-pdf-final.log)). The final full run also includes the additional uppercase-extension regression.

The focused API run passes 36 tests. The [cold-run diagnostic](chat-api-diagnostic.log) exposed a chat test that previously assumed completion after at most six seconds and could read a null context manifest on a cold run. It now waits for an explicit terminal state with a 30-second deadline and asserts completion before reading context. No production timeout or error behavior was weakened.

PDF regressions verify matching upload/download filenames, duplicate-content reuse, different content with identical original filenames, original-name provenance, safe filename components, temporary-file cleanup, metadata-only upgrades, removal of stale records during ingestion, invalid-file isolation, and `.PDF`/`.pdf` path aliasing on Windows.

## Practical boundaries

Theme import supports local color JSON, not executable VSIX extensions or an online marketplace. Packages are browser-local. Existing curated PDF filenames and SKB content-addressed objects remain stable. Coverage proves the measured test paths were executed; it does not establish scientific validity or replace the recorded real-browser checks.
