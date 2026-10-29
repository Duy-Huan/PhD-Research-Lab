# Full-app QA for 6.6.4

Date: 2026-10-29. Each server was freshly started at version 6.6.4 (`GET /api/version` returned `6.6.4`) and used its own
disposable data folder. The browser was Chromium with its own Playwright context, run from the built bundle of the
working tree that was committed afterwards.

## Offline suite: two runs, both 264/264

| Run | Server | Result |
|---|---|---|
| A | `D:/qa664`, port 8792 | 264 passed, 0 failed, 0 skipped (8.5 min) — `qa-664-A.txt` |
| B | same server, run again | 264 passed, 0 failed, 0 skipped (9.0 min) — `qa-664-B.txt` |

The suite runs the 12 specs that need no model:

- `autonomy_levels`
- `ci_smoke`
- `cli_studio`
- `harness_levels`, including HARNESS-LEVELS-004 at L2 and L3 (canvas → mission)
- `missions_live`, with the live mission update, the Topic surviving a reload, and narrow drawers at 1024 and 1280 px
- `navigation`
- `office3d`
- `paper_integrity`
- `qa_screens`, which covers every main view, Settings tab and drawer panel:
  - in both languages and both themes;
  - at 1440 and 390 px;
  - with the uiAudit rules and axe WCAG 2.1 AA (serious and critical findings);
- `shell_layout`
- `uat_harness`
- `ui_quality`

## Model specs: the same 9 failures on 6.6.3 and 6.6.4

These five specs need a model and are not part of routine CI: `journeys`, `multi_turn_chat`, `workflows`,
`harness_ide` and `tools`. They ran on a new server with fresh data and English set (port 8793, `D:/qa664live`), using
the LM Studio model on this machine (`nvidia/nemotron-3-nano-4b`). The result was 4 passed and 9 failed
(`qa-664-live3.txt`).

To check for regressions, the same five specs at 6.6.3 (tag `v6.6.3`, `66b7311`) were run against a 6.6.3 server on
fresh data (port 8794). The same 9 tests failed there (`qa-663-cmp.txt`). These failures existed before 6.6.4 and were
not introduced by it. The failing tests are:

1. `harness_ide.spec.ts`: Harness Studio All-in-One IDE
2. `journeys.spec.ts`: real selected local-model chat, SSE, pin, memory save and reload
3. `journeys.spec.ts`: provider settings persist, memory navigation and responsive settings
4. `journeys.spec.ts`: project create, rename, delete cancellation and switch isolate topics
5. `multi_turn_chat.spec.ts`: consecutive multi-turn conversation maintains continuity
6. `multi_turn_chat.spec.ts`: an API-created fresh session accepts a real chat turn
7. `tools.spec.ts`: ledger UI renders actual ledger events and verified API status
8. `tools.spec.ts`: real Codex CLI chat follows the provider selected in settings
9. `workflows.spec.ts`: four independent L1–L4 workflows execute real local inference

Several of these look for exact answers from a larger model, such as "42", "391" or "PONG", or for a provider choice
made in a different setup. They are kept as a follow-up for live qualification (phase C): they are listed here, not
passed. The live Codex agent-team runs for 6.6.4 are recorded in `docs/qa/evidence/harness-team-664/`.

## Not run (none claimed)

- Firefox and WebKit.
- 125–200 % zoom.
- Keyboard-only journeys.
- Offline or slow-network journeys.
- Two-tab concurrency.
- Performance budgets.
- XSS probes through the UI.
- Visual baselines.
- A real PDF compile on this machine, which needs your permission to run the downloaded Tectonic. The CI installer
  jobs ran `tectonic --version` from the built installers.
