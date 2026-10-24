# Upgrade reconciliation validation — 2026-10-22

Baseline commit: `e539fc4`. Application remains `6.3.0-preview.1`, SQLite schema 7. Test data, harness data and browser demo were isolated from the researcher's projects. No paid inference, real GPU training or publication was performed.

| Check | Actual final result | Evidence |
|---|---|---|
| All upgrade documents | 11 files, 187 sections, 709 list/table inventory rows, 49 reviewed feature groups | [Inventory](inventory.json), [matrix](feature-matrix.md) |
| Backend full regression | **664 tests, OK; 7 skipped**, 386.086 s; 0 failures/errors | [Final log](backend-final.log), [structured result and skip reasons](backend-result.json) |
| Legacy L4/metadata compatibility regression | 59 focused tests, OK; 1 Windows symlink skip | [Compatibility log](backend-compatibility.log) |
| New reconciliation tests | 17 tests included in the full backend result | [Source](../../tests/test_upgrade_reconciliation.py) |
| Frontend regression | **137 passed, 0 skipped** | [Log](frontend.log) |
| Frontend coverage | **100% lines 4365/4365, branches 3398/3398, functions 1121/1121** across all 14 first-party scripts | [LCOV](frontend.lcov) |
| Edge interaction/visual QA | **20 checks passed, 0 JavaScript exceptions**; English/Vietnamese, desktop/mobile, 120 real backend fixture records | [General checks](browser/browser-checks.json), [upgrade checks](browser/upgrade-checks.json) |
| v6.3 harness | **8 executions passed**, three workflow families; CPU reproduction passed; hash/audit/ZIP integrity checked | [Report](harness/harness.json), [benchmark](harness/benchmark.md), [raw measurements](harness/measurements.zip) |
| Native probes | OpenScience 2.0.152 / Feynman 0.5.51; help/version exit 0 in isolated configuration | [Harness probes](harness/harness.json) |
| Local conditions | RTX 3060 12288 MiB; Docker CLI available (configuration access warning under sandbox); Zotero port not reachable; Docling/Pyzotero/Torch absent; Optuna 5.0.0 installed | [Runtime probes](runtime-probes.json), [packages](optional-packages.json) |
| Audit freshness / whitespace | `tools/audit_upgrade_specs.py --check` and `git diff --check` passed | Hashes in inventory |

No frontend script was excluded and no coverage-ignore annotations were added. Backend coverage percentage was not measured or claimed in this run. The 709 inventory rows include examples, catalogs and engineering instructions; they are not 709 independently accepted feature tests.

## Commands executed

```powershell
.venv/Scripts/python -B tools/audit_upgrade_specs.py
.venv/Scripts/python -B tools/audit_upgrade_specs.py --check
.venv/Scripts/python -B tools/run_tests.py test_upgrade_reconciliation test_literature test_research_workspace test_research_os test_governance
.venv/Scripts/python -B tools/run_tests.py test_upgrade_reconciliation test_research_workspace test_governance test_research_os
node tests/frontend/run.js
.venv/Scripts/python -B tools/research_harness.py --stage 6.3 --probe-engines --output artifacts/upgrade-reconciliation/harness
.venv/Scripts/python -B tools/demo_server.py 8801
node tools/ui_visual_check.js http://127.0.0.1:8801 artifacts/upgrade-reconciliation/browser
node tools/upgrade_ui_check.js http://127.0.0.1:8801 artifacts/upgrade-reconciliation/browser
git diff --check
```

The final full backend invocation uses the same `tools.run_tests.main([])` discovery through a recording `unittest.TextTestRunner` subclass, retaining exact skip reasons in `backend-result.json`. Earlier full runs (660 and 663 tests) passed before the final legacy-version attestation regression was added. Browser QA initially waited before the demo finished seeding; after HTTP 200 it passed. A test-tool method mismatch was corrected to the existing POST configuration API; no production endpoint was changed for that check.

## Skipped backend checks

- `test_inner_symlink_is_allowed (test_cli_workspace.Paths.test_inner_symlink_is_allowed)`: symlinks need developer mode / admin on Windows
- `test_symlink_escape_is_refused (test_cli_workspace.Paths.test_symlink_escape_is_refused)`: symlinks need developer mode / admin on Windows
- `test_create_log_read (test_live_integrations.ClearMLLive.test_create_log_read)`: set PHDLAB_CLEARML_LIVE=1 to run against a real ClearML server
- `test_read_only_run (test_live_integrations.CodexLive.test_read_only_run)`: set PHDLAB_CODEX_LIVE=1 to run one real read-only Codex task
- `test_real_sdk_through_adapter_with_bounded_socket_fixture (test_research_engines.OfficialSDKSocket.test_real_sdk_through_adapter_with_bounded_socket_fixture)`: Optional official SDK not installed; run with audited SDK source on PYTHONPATH
- `test_workspace_paths_symlinks_missing_cli_no_model (test_research_workspace.ResearchWorkspace.test_workspace_paths_symlinks_missing_cli_no_model)`: Symlink creation needs Windows Developer Mode/admin; traversal and overlap checks executed
- `test_real_gate_and_manual_unload (test_vram_gate.LMStudioLive.test_real_gate_and_manual_unload)`: set PHDLAB_LMSTUDIO_LIVE=1 (+ optional PHDLAB_LMSTUDIO_MODEL) to load/unload a real LM Studio model

## Visual evidence

[English paper controls](browser/upgrade-papers-en.png), [Vietnamese controls](browser/upgrade-papers-vi.png), [390px mobile drawer](browser/upgrade-papers-mobile.png). Screenshots were opened for inspection. Original user-authored content remains in its authored language; interface labels are localized. The demo was stopped after QA.

## Remaining qualification

Software regression success does not mean every requested research capability is production-qualified. See [scope and remaining external gates](../../docs/upgrade-reconciliation.md) and each feature-matrix row. General parallel execution, one-Mission multi-Topic execution, remote team identities, live scholarly API coverage, optional parser models, native inference/billing, real scientific pilot and Docker/GPU containment remain explicitly bounded/unqualified. Optional P1/P2 catalog entries are not silently installed or labelled complete. Autonomy flags remain opt-in.
