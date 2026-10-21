# v5.3 preview acceptance (2026-10-21)

Environment: Windows, PowerShell, Python 3.14.8 in `.venv`, Node 24.22.0. Baseline branch/HEAD and initial capabilities are in `00_AUDIT_AND_GAP_ANALYSIS.md`. No user dataset, real native scientific session or paid LLM inference was used for the new acceptance tests.

## Evidence and repeatable commands

```powershell
.venv/Scripts/python -B start.py --check
.venv/Scripts/python -B tools/run_tests.py test_research_workspace
.venv/Scripts/python -B tools/run_tests.py test_research_workspace test_literature test_context_cache test_research_engines test_entrypoints test_api test_config test_skills test_orchestrator test_memory_migration test_provenance test_v42_shared_backend
node --test tests/frontend/*.test.js
```

- Installation check: files/version agree at `5.3.0-preview.1`; required packages OK.
- New backend acceptance: 24 tests, OK with 1 Windows symlink privilege skip, including reset of L4 after new versions and retention of historical citation IDs after reparse. Actual Optuna 5.0.0 executed a labelled mathematical objective: 3 trials, resume to a capped total of 10. This establishes adapter resume/budget behavior, not scientific training quality.
- Focused integration run: 128 tests, OK with 2 explicit environment/dependency skips (symlink privilege and optional official OpenScience SDK), including the parser subprocess, legacy memory migration, provenance, config, skills and shared backend. Raw output is in `artifacts/v53/backend-focused.log`.
- Frontend: 94 tests passed using actual application scripts in jsdom, including 6 new workspace tests. Raw output is in `artifacts/v53/frontend.log`. This verifies DOM interactions and API routing, not pixel layout.
- Final corpus/review hardening rerun: 49 tests passed with 1 symlink privilege skip (`test_research_workspace test_literature test_orchestrator`), after the broader 128-test run. Raw output: `artifacts/v53/backend-final.log`. Python source syntax and `git diff --check` also passed.
- Earlier broad run: 574 tests, 1 failure, 1 error, 6 skips. The PDF size-limit regression introduced during implementation was fixed and the literature tests passed on rerun. The remaining browser-PDF error is an environment integration failure: installed Edge's GPU child process exits with access-denied status and no PDF is produced. Application export implementation was not changed.

`tools/shot.js` was attempted for desktop/mobile screenshots; it exited without producing images. A diagnostic headless Edge run failed with GPU process exit `-1073741790` / fatal GPU initialization. Browser automation inventory also contained no enabled browser surfaces. **No screenshot or manual visual QA success is claimed.** Responsive DOM behavior is covered by existing/new jsdom checks; visual review on a working browser remains a gate.

## Acceptance mapping

| Scenario | Evidence / result |
|---|---|
| Two Topics, distinct native workspaces, no cross-Topic artifacts | Offline workspace tests passed |
| Work saved with PhD Lab offline, then reconciled | File created before sync; recorded by deterministic inventory |
| Repeat sync is idempotent; modification preserves version history | Passed; no duplicate artifact events |
| Deletion preserves history; incomplete scans do not tombstone | Passed |
| Large checkpoint is metadata-only | 33 MB sparse fixture registered without hash/copy |
| Safe path boundaries / overlap / native argv with spaces | Passed; symlink creation test explicitly skipped when OS denies privilege |
| CLI missing / independent siblings / no private-session fabrication | Capability and launcher contract tests passed; live native browser/REPL not launched |
| Relink keeps identity/history and leaves original files intact | Passed |
| 100+ papers, pagination and filtering, zero LLM calls | 120-paper backend fixture and frontend API assertions passed |
| DOI aliases, arXiv aliases, conflicting identities, source versions | Passed; ambiguous identities are retained as conflicts rather than silently merged |
| Shared paper/file, separate curation and approvals | Passed; PDF content deduplicated and per-Topic attestation isolated |
| PDF signature, redirect, public-address and size boundary | Existing literature regressions passed after fix; no live publisher acceptance claimed |
| Parse/index/reprocess/checksum + exact version/page evidence | Passed with generated local PDF; parse failures preserve metadata/file |
| OA-only behavior and Unpaywall/Crossref contracts | Offline response fixtures passed; restricted metadata never triggers PDF download |
| Durable queued/interrupted/cancel/retry states | Passed; no automatic replay of interrupted discovery |
| L4 and findings require human review; bibliography separate | Passed; no automatic writes to trusted project memory or legacy library |
| Selected IDs reach explicit AI intent, no click-time inference | Frontend passed; actual scientific model response acceptance pending |
| Legacy chat/provider/plugin/UI contracts | 94 frontend passed; focused backend integration passed; broad browser-export environment error retained above |

## Milestone disposition

- **v5.1:** reuse plugin manager and existing three discovery clients; add Crossref/Unpaywall, read-only Zotero interchange, optional Docling adapter and bounded Optuna helper. Catalog-wide source/tool installation is deferred, not claimed complete.
- **v5.2:** Topic policy/inbox/corpus, OA jobs, PDF object dedup, FTS page retrieval, curation, scoped chat, UTC schedules and recovery are implemented. Vector/reranker, citation graph, live Zotero sync and live Docling benchmarks remain pending.
- **v5.3:** project/Topic/workspace identity, independent native navigation contracts, offline file reconciliation, provenance snapshots, approval-linked findings and contextual drawer are implemented. External session fidelity is explicitly partial; no unsupported private APIs are used. Native interactive engine acceptance remains pending due setup/observability gates.

All migrations are additive and lazy. Existing application data was not migrated during development; tests use throw-away projects. The demo server uses labelled synthetic fixtures and is available for manual verification with `.venv/Scripts/python -B tools/research_workspace_demo.py 8877`.
