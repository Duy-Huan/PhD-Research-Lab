# Frontend workflow verification — 2026-10-22

**PASS** for the bounded implementation and regression scope below. Application remains `6.3.0-preview.1`.

| Check | Measured result | Evidence |
|---|---|---|
| Full backend regression | 683 tests; 676 passed, 7 skipped; zero failures; 410.534 s | [raw log](backend-regression.log) |
| Full frontend regression | 142 tests passed, zero skips/failures | [raw log](frontend-regression.log) |
| All 14 first-party frontend scripts | 4,478/4,478 lines, 3,463/3,463 branches, 1,140/1,140 functions covered: **100%** | [LCOV](frontend.lcov), [per-file counts](coverage-summary.json) |
| Edge shell, themes, projects, pins, mobile and localization | 12 checks, zero browser errors | [receipts](shell/browser-checks.json) |
| Edge agent-source/model filters, MCP contract, keyboard, independent-engine controls and major panels | 13 checks, zero browser errors | [receipts](workflows/workflow-checks.json) |
| Edge research filters/tags/pagination/citations/archive/restore and mobile | 8 checks, zero browser errors | [receipts](research/upgrade-checks.json) |
| Upgrade source inventory | 11 documents, 49 reviewed groups; regenerated hashes and `--check` passed | [matrix](../upgrade-reconciliation/feature-matrix.md) |

Commands executed from the repository root:

```powershell
.venv/Scripts/python -B tools/run_tests.py
node tests/frontend/run.js
node tools/ui_visual_check.js http://127.0.0.1:8802 artifacts/workflow-ux/shell
node tools/workflow_ui_check.js http://127.0.0.1:8802 artifacts/workflow-ux/workflows
node tools/upgrade_ui_check.js http://127.0.0.1:8802 artifacts/workflow-ux/research
.venv/Scripts/python -B tools/audit_upgrade_specs.py --check
```

Browser checks used an isolated `tools/demo_server.py` instance and synthetic records. They performed deterministic UI/API operations, with no paid inference, live scholarly requests or native interactive windows. The historical `artifacts/ui-refinement/frontend.lcov` and acceptance snapshot were restored; this directory retains the current evidence.

Regression includes provider-source resets in either patch-key order, default-cloud aliases, masked credentials, invalid MCP config, JSON/SSE/session handling, split UTF-8 replies, pagination, rejected non-inference schemas, uncorrelated/error/empty/oversize/redirect replies, agent call/stream dispatch, and Stop/deadline interruption before any output. Native launch tests assert encoded arguments, exact cwd, credential isolation, duplicate detection, project-scoped VS Code launch and failure paths. Installed OpenScience/Feynman help was probed; the initial OpenScience sandbox access failure was resolved for the read/help probe with appropriate filesystem access.

The 7 backend skips remain environment/opt-in gates, including live integrations, optional SDK and Windows symlink permissions. No skipped test is counted as executed. Library PDF naming, chat/projects/pins, skills/plugins/themes, writing/review/exports, existing mission/team/workstream contracts and CPU harness/adversarial tests remain in the full regression suite.

Native authentication, real model quality/quota, generic MCP stdio servers, remote-server compute cancellation and live scientific/GPU qualification are outside these measured results. MCP supports an explicitly configured compatible HTTP inference tool; responses are delivered after completion. Opening an engine acknowledges the local window/process, without certifying its model connection. Existing Research OS flags and scientific review gates were not promoted or enabled.

Review [workflow findings and operating instructions](../../docs/FRONTEND_WORKFLOW_REVIEW.md), [model resource contracts](../../docs/MODEL_RESOURCES.md), [machine-readable results](summary.json) and [reviewed source hashes](source-identity.json).

Selected captures: [desktop models](workflows/models-desktop.png), [mobile models](workflows/models-mobile.png), [Vietnamese models](workflows/models-vietnamese.png), [independent workspaces](workflows/engine-workspaces.png), [library](workflows/library.png), [mobile chat](shell/after-mobile-chat.png), [dark themes](shell/after-themes-dark.png), [research mobile](research/upgrade-papers-mobile.png).
