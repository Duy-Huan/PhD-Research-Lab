# 6.6.3 full-app Playwright QA: evidence

Process: `agent/PLAYWRIGHT_QA_CHECKLIST.md`. Contract: `docs/qa/contracts/FQC-UI-QA-663.json`. Disposable data folder `D:/qa663` on loopback port 8791, with a disposable QA project and topic created through the API.

## What ran

- **Spec:** `frontend/e2e/qa_screens.spec.ts` with the shared audit `frontend/e2e/uiAudit.ts` (checklist section 2).
- **Screens:** 29, each opened from its normal entry point. They cover chat, the library view, review, dashboard, harness, CLI, the 9 Settings tabs and every drawer panel. The 3D lab has its own phase.
- **Cells:** en light 1440, en dark 1440, en light 390, vi light 1440 and vi dark 390. A further 12 screens run with a topic selected, in the three light cells. 181 tests in total.
- **Rules:**
  - VIS-HSCROLL: sideways page scroll.
  - VIS-OCCLUDED: a control's visible centre is covered by something else. Controls behind a full-screen overlay are ignored.
  - VIS-TARGET: targets of at least 20×20 px.
  - VIS-ICON: icon squeezed.
  - VIS-CLIPPED: cut text, or shortened text without a tooltip.
  - VIS-TEXT-JUNK and VIS-I18N-KEY.
  - VIS-MIXED-LANG: Vietnamese interface text in English mode; user content and code are excluded.
  - axe WCAG 2.1 AA, serious and critical only.
- **Companion specs:** `cli_studio.spec.ts` and `shell_layout.spec.ts`.

## RED

| Run | Result | Raw findings |
|---|---|---|
| 1 (before fixes) | 128 of 145 failed | `red-run1-findings.txt` |
| 3 (topic selected, after the first fixes) | 26 of 181 failed | `red-run3-with-topic-findings.txt` |
| Stability run A | 2 of 220 failed | timing-dependent defects in the Paper tabs and the AI tools list (see below) |
| Stability runs C and D | 3 of 220 failed, the same 3 both times | the AI tools registry in the three desktop cells showed tool ids such as `mission.code.implement` as plain text (VIS-I18N-KEY). These runs also used a server started before the 6.6.3 backend changes (`/api/version` returned 6.6.2), so they do not count toward the release. |
| CI on Linux, commit `8defb4a` | 6 audit failures, then the browser step timed out | Linux fonts are wider than on Windows. The Harness node badge "PhDLab Research Harness" was shortened without a tooltip (VIS-CLIPPED). The AI tools card headers were 18 px tall (VIS-TARGET). The 181-screen audit shared one 600 s Playwright invocation with every other suite and ran out of time. |

The first run's 471 occlusions were mostly a rule error. On phones the full-screen drawer covers the screen behind it on purpose, so the rule now skips controls behind large overlays. The occlusion that remained ("Colab GPU / Local GPU / Docker") was inside a closed `<details>`, and closed `<details>` content is now skipped as well.

## Defects found and fixed

- **Language:** English mode showed Vietnamese in these places, which now follow the active language:
  - the whole Dashboard (27 strings) and Harness Studio (75 strings);
  - the Topics, Figures, Intelligence, Workstreams and Claims panels;
  - the skill, plugin and Harness preset names, which now use their existing `*_en` fields;
  - the agent descriptions, through a new `label_en`;
  - the Docker and Python engine texts, now in English like the other engines.
- **Contrast (WCAG 1.4.3):**
  - The "Tools panel" header button, the selected project name and the success chip `--ok` (darker green).
  - The amber text in the Paper panel, which now uses `--warn`.
  - The muted text of the selected topic.
- **Names and keyboard (WCAG 4.1.2 / 2.1.1):**
  - Labels added to the Appearance selects, the Paper selects, the Harness saved-workflow select and the Skills editor.
  - The Skills table and the AI tools list can now be focused.
  - The AI tools status dots now carry an image role.
- **Target size:** the Reasoning select (17 px) and the scale select (18 px) are now at least 24 px.
- **Layout:** the five Paper tabs overflowed a narrow drawer, so the page scrolled sideways and the icons were squeezed. The tabs now wrap.
- **Naming:**
  - The sidebar menu "Công cụ Nghiên cứu" had the same Vietnamese name as the Settings tab "Research Engines". It is now "Xưởng nghiên cứu".
  - The Dashboard's VRAM error was shown with `alert()`. It is now shown on the page.
  - The AI tools registry listed bare tool ids, with the description only in a tooltip. Each id is now marked as code (`<code>`), followed by its plain-language description. Unit test: `AiToolsSettings.test.tsx`.
- **Found by CI on Linux:**
  - The Harness node badge now carries its full name as a tooltip (`HarnessNodeComponent.test.tsx`).
  - The AI tools card headers are at least 24 px tall (`AiToolsSettings.test.tsx`).
- **Audit run time:**
  - `qa_screens.spec.ts` now waits until the screen stops changing (`settle()` in `uiAudit.ts`) instead of a fixed 1.5 s pause. Locally this went from about 2.7 s to 2.15 s per screen.
  - The audit runs as its own `2d-audit` Playwright invocation (`execution_groups` in `devtools/verification/journeys.py`, tested in `tests/test_dynamic_discovery.py`). The 600 s per-invocation limit is unchanged.

## GREEN

- `green.json`: `tests/test_ui_language_data.py`, 4/4.
- `red.json`: the same tests on `f4ea965`, with 14 failures.
- `qa_screens.spec.ts`: 181/181 on the final build. The results of the two repeated runs of all three specs are in `final-runs.txt`.
- Vitest: all tests pass. TypeScript: no errors.
