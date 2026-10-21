# Full validation — 2026-10-21

Regression: **PASS**. Bounded stress: **PASS**. The 100% coverage gate is **NOT MET**. Ordinary uncovered code is not waived or renamed as an environment skip.

| Measurement | Result |
|---|---|
| Backend regression | 563 tests; 0 failures; 0 errors; 5 skips in the main run |
| Frontend regression | 88 tests, all passed |
| Python statement coverage | 93.81% (16599/17695) |
| Python branch coverage | 88.70% (5258/5928) |
| Python combined statement/branch score | 92.52% |
| Frontend line / branch / function coverage | 100.00% / 95.99% / 95.03% |
| Bounded application stress | 15 phases, 16 concurrent workers, 3 repetitions; PASS |
| Real Codex read-only smoke | PASS, one model task |
| Real LM Studio GPU load/unload | PASS |
| Real OpenScience protocol | PASS, isolated runtime 2.0.152, no model work |

Python scope includes all backend modules, the standalone ClearML worker, `start.py` and `mcp_stdio_bridge.py`. The strict report has **zero excluded lines**: existing pragma/main exclusions are removed when analyzing the recorded traces. The regular harness report also remains available with the repository's original exclusions, so its numbers differ. Development tools/tests and third-party dependencies are outside application coverage. Frontend coverage measures first-party JavaScript from the actual page; it does not claim CSS/layout or third-party vendor coverage.

## Stress evidence and limits

Recorded stress results cover 9,600 gateway events with three concurrent subscribers and cold durable replay; 1,440 real loopback HTTP requests; and 2,400 real SSE deliveries, including disconnect/reconnect. See individual PASS/FAIL phases for assertions: concurrent session identity/content, CPU admission, and exit settlement of 48 scripted CLI subprocesses (18 forced timeouts) plus their owned Windows termination helpers. Initial fixture failures and the immediate-vs-settled helper observation are retained as separate diagnostic reports; the final report is `stress-sse.json`.

Model output is scripted in load tests. This is a short application concurrency test, not a 24-hour soak, a GPU burn-in, a provider quota benchmark or scientific model evaluation. The HTTP load phase disables application lifespan to isolate request admission; startup/recovery has separate regression coverage. RSS before/after includes cold module imports and caches and is not proof of absence of memory leaks.

## Failures found and repaired

* ClearML worker kept `.partial` artifact bytes after checksum failure. Failed copies now remove temporary bytes and preserve completion semantics.
* Malformed worker JSON escaped the structured result/error protocol. Parsing now occurs inside its error boundary.
* Legacy research/CLI acceptance fixtures could dispatch real Feynman work. They explicitly select the mocked application engine; native Feynman has separate contract tests. Initial live leakage produced quota/auth failures and is preserved in the baseline log.
* Old lifecycle tests configured removed agent names and fell through to real cloud routing. They now use current utility/research roles and restore configuration after each test.
* The SSE disconnect fixture lacked current Request headers/event identities. It now supplies the real contract fields.
* The regression harness could fail to print Unicode tracebacks on Windows. Its console output is explicitly UTF-8.

## Skips with evidence

The main run recorded five skips. Separate successful live runs are credited in the machine-readable summary, leaving 3 unexecuted cases:

* `test_cli_workspace.Paths.test_inner_symlink_is_allowed` — Windows user token cannot create symlinks (Developer Mode/admin privilege required); no OS privilege settings changed. Scripted path-containment tests still run.
* `test_cli_workspace.Paths.test_symlink_escape_is_refused` — Windows user token cannot create symlinks (Developer Mode/admin privilege required); no OS privilege settings changed. Scripted path-containment tests still run.
* `test_live_integrations.ClearMLLive.test_create_log_read` — Validation environment has no online ClearML host/access-key/secret-key settings. Real offline SDK ZIP recording and worker/API contracts are tested.

Windows symlink creation was independently probed and returned WinError 1314. ClearML offline ZIP recording passed; an online experiment server was not exercised.

LM Studio live evidence: {"passed": true, "returncode": 0, "model": "nvidia/nemotron-3-nano-4b", "context_length": 4096, "elapsed_s": 11.295, "user_authorized_load_unload": true, "vram_before_mb": 4413.0, "vram_after_mb": 1349.0, "unload_wait_s": 1.6}. This separate test uses the installed model, checks the VRAM busy gate while loaded, unloads local models, then checks empty LM Studio state and a free gate. Its execution is separate from the recorded coverage run; coverage percentages above are unchanged.

## Coverage still open

**1096 executable Python statements and 670 Python branch destinations remain uncovered.** The frontend also has untested branch/function variants despite 100% line coverage. Those gaps include ordinary recovery, routing, legacy memory and tool behavior as well as environment-dependent paths. They are not all unavoidable, and the external-service skips do not explain or waive them. The quality gate continues to fail with exit code 2.

The complete file/function/line inventory is in [coverage-gaps.json](../artifacts/full-validation/coverage-gaps.json). Prioritize workflow recovery/cancellation, native-engine decisions/artifact faults, model routing, sandbox failure cleanup and memory migration. The remaining work needs behavior-based tests, not execution-only calls, blanket mocks or exclusions added to raise the number.

## Reports and reproduction

* [Machine-readable summary](../artifacts/full-validation/summary.json)
* [Strict Python JSON](../artifacts/full-validation/coverage-strict.json), [HTML](../artifacts/full-validation/coverage-strict-html/index.html), [text](../artifacts/full-validation/coverage-strict.txt)
* [Regression log](../artifacts/full-validation/backend-final/tests.log), [frontend log](../artifacts/full-validation/frontend-final.log), [frontend coverage](../artifacts/full-validation/frontend-coverage.json)
* [Stress](../artifacts/full-validation/stress-sse.json), [Codex live log](../artifacts/full-validation/codex-live.log), [OpenScience protocol](../artifacts/full-validation/openscience-live-protocol.json)
* [LM Studio live result](../artifacts/full-validation/lmstudio-live.json), [log](../artifacts/full-validation/lmstudio-live.log)

```powershell
# Install the optional SDK or put its pinned audited source on PYTHONPATH for its socket integration test.
.venv/Scripts/python.exe tools/backend_regression.py --include-workers --include-entrypoints --out artifacts/full-validation/backend-final
node --test --experimental-test-coverage --test-coverage-include='frontend/assets/*.js' --test-reporter=spec --test-reporter-destination=artifacts/full-validation/frontend-final.log tests/frontend/*.test.js
.venv/Scripts/python.exe tools/stress_runtime.py --workers 16 --rounds 3 --out artifacts/full-validation/stress-sse.json
.venv/Scripts/python.exe tools/validation_report.py --backend backend-final
```

Live Codex and OpenScience evidence must be regenerated separately when validating another installation. The aggregator consumes these evidence files; it does not run live services. No production user data is used by the regression/stress harnesses. No source changed during the measured regression run.
