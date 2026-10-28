# 6.6.4 A-QA: L1–L4 and Harness levels in CI, evidence

Plan: [agent/PLAN_6.6.4_L3.md](../../../../agent/PLAN_6.6.4_L3.md), phase A-QA (owner request 2026-10-28: Playwright for
all four L1–L4 flows, added to CI/CD). Contract: `docs/qa/contracts/FQC-AUTONOMY-QA-664.json`.

Environment:
- Disposable `PHDLAB_DATA_DIR` (`D:/qa663`) on loopback port 8791, restarted after the backend change; `/api/version` 6.6.3.
- Chromium headless.

## Before this change

Routine CI ran no L1–L4 flow. `workflows.spec.ts` (L1–L4) and `harness_ide.spec.ts` are marked `needs_model: true`,
so `--offline-all` skipped them.

## New specs (no model, selected by every CI run)

- **`frontend/e2e/autonomy_levels.spec.ts`**, Missions → Workflows L1–L4 through the real UI and backend:
  - 001: each level drafts its own task plan; L4 refuses a draft without a separately approved reproduction; nothing runs before approval.
  - 002: L1 stops for review after a step; accepting runs the next step; a failed model step shows its name and reason.
  - 003: L2 rejecting a step cancels the workflow before the next step.
  - 004: L3 runs without per-step review and reports the failing step; there is nothing to sign off.
  - 005: cancelling an L4 draft launches no task.
  - The workflows name a model that cannot exist (`qa-no-model-installed`), so model steps fail the same way with or without LM Studio.
- **`frontend/e2e/harness_levels.spec.ts`**, Harness Studio:
  - 001: the Team tab, the AI Architect preview and the generated canvas pass `uiAudit` in English.
  - 002 (L2, L3, L4): an architect workflow runs; control flow completes; every unexecuted research or agent node is reported as not completed, with its reason, and the execution is stored.
  - 003: the standalone studio has no mode switch that does nothing.

## Defects found and fixed

| Found by | Defect | Fix |
|---|---|---|
| autonomy 002/004 | A failed L1–L4 workflow showed only "failed"; the reason stayed in the raw JSON | The card names the failed step and the provider's reason |
| autonomy setup | "Enable Research OS" flashed while the setting was loading and could be clicked | Shown only once the setting has loaded as disabled |
| harness 001 | Team tab: the 6 preset agents in Vietnamese in the English interface | `name_en` / `purpose_en` |
| harness 001 | AI Architect description, node names and run log in Vietnamese | `description_en`, `label_en`; English blocked summary |
| harness 003 | "Automated Agents" did nothing outside Missions | Mode switch only where the automated view exists |
| local gate `pr-664a` (qa_screens, AI tools en light 1440) | axe contrast on the first registry row; repeated 5x: 7 of 25 failed (contrast mid fade-in, card header 9 px mid layout animation). Cause: `/api/tools` takes about 1 s while the rest of the tab loads in milliseconds, so the screen was measured before the list arrived and while it animated in | The registry list is `aria-busy` with "Loading tools…" until it arrives; `settle()` never treats a busy screen as quiet and also watches inline opacity (JavaScript fades). Repeated 5x: 25/25 |

## Results

- `tests/test_autonomy_qa_664.py`: RED 5 of 6 failing on `49df2d0` (`red.json`; the speed check passes on both); GREEN 6/6 (`green.json`).
- Playwright:
  - first runs: autonomy 5/5 failed in setup or on the failure reason; harness 2/5 failed;
  - final: autonomy 5/5 (three runs), harness 5/5;
  - with the related `qa_screens` screens: 23/23.
- Vitest 246/246, TypeScript clean.
- The offline CI plan now holds `autonomy_levels.spec.ts` and `harness_levels.spec.ts` in the 2D group.

Not covered here: completing the flows with a real model. That is the live suite, with Codex per the owner (A9 / phase C).
