# v5.6 validation — 2026-10-22 (Asia/Saigon)

| Command | Observed result |
|---|---|
| `.venv/Scripts/python -B tools/run_tests.py` | 614 tests in 319.211s: 606 passed, 7 skipped, 1 browser-PDF error inside the execution sandbox. No assertion failures. Raw `backend-tests.log` retains the original PowerShell stderr capture. |
| `.venv/Scripts/python -B tools/run_tests.py test_governance test_protocols test_missions test_research_workspace test_config test_entrypoints test_literature test_context_cache` | Latest focused code: 88 tests in 28.654s, OK (1 Windows symlink privilege skip). Exit 0. See `focused-backend-tests.log`. |
| `.venv/Scripts/python -B tools/run_tests.py test_v51_features.NotesGuideLanguage test_entrypoints` | 13 tests, OK, 0.647s. Includes the updated UI config merge fixture and matching launcher/version checks. |
| `.venv/Scripts/python -B tools/run_tests.py test_v51_features.Export.test_pdf_through_the_local_browser` | Outside process sandbox, temporary app data/profile: **1 test, OK, 0.982s**. Confirms the sandbox-only PDF error without changing browser security flags or the production renderer. |
| `node --test tests/frontend/*.test.js` | **96 passed, 0 failed, 0 skipped**, 8.084s on the final UI code. Includes Review Room decisions, evidence, audit, composer preservation, Mission retry and digest-bound protocol approval. |
| `.venv/Scripts/python -B tools/acceptance_v56.py` | Passed: 6-step Mission, 10 metadata fixtures, 2 PDF links, 2 actual CPU experiment runs, independent verification passed, audit valid. |
| `git diff --check` | Passed; only normal Windows LF/CRLF conversion notices. |

The full discovery began before one additional adversarial test was added (`test_uncertainty_test_summary_and_missing_trial_are_detected`). That test and all final governance/protocol/mission code were included in the passing 88-test focused run. The full sandbox run is explicitly **not reported as a single green run**. Its sole remaining error passed when rerun with permission to start Edge outside the sandbox. Skips cover environment privileges, optional integrations and opt-in live tests; no live model/server acceptance is implied.

The earlier strict UI expectation predated v5.3 feature flags. It now verifies language/font overrides alongside retained UI defaults. A first exploratory full run also overlapped the version bump; the subsequent full run had matching versions and no launcher error.

## Actual acceptance observations

The approved immutable generated-image protocol used seeds `[11,23,37]`, alpha candidates `[0.5,1.0]`, an actual noisy-input baseline, 8 validation and 8 held-out samples per seed. Each run made 5 trial groups (3 validation + baseline/selected held-out). Validation selected alpha 1.0; paired validation PSNR gain was **8.9455077101 dB**, approximate normal interval **[8.7778339012, 9.1131815189]**. These are measurements of this synthetic fixture only; they are not a result on real MRI images or a publication claim.

The independent verifier recorded 50 checks, both runs' observation hashes matched and all retained arrays/logs were checked. There are 44 hash-linked audit events in the recorded acceptance trace. The fixture quote containing an instruction to approve claims never became an instruction to the verifier. A fabricated quote was contested. Harness decisions are explicitly labelled simulated, and automatic memory promotion is disabled.

`acceptance.json` uses `<temporary-data>` for ephemeral absolute path prefixes. `observations.zip` retains the actual request/measurement/log files under their stable run/trial IDs so the raw outputs remain reviewable after temporary application state is removed. `scientific-review.md` demonstrates export status disclosure.

Not executed: live paid/native scientific reasoning, live scholarly network retrieval, live citation service availability, GPU, live pinned Docker containment/cancellation, external datasets, or interactive browser visual inspection. Transport fixtures are never presented as live integrations. Installed native CLI help/version probes are documented in the ADR.
