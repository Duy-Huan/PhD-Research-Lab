# CLI and tool connectivity repair — 2026-10-24

Passing the earlier local-model harness did not establish CLI connectivity: its authenticated CLI execution test was skipped. This investigation used installed vendor binaries and the running HTTP application. Mocked regression tests are separate from real-provider evidence.

## Reproduced failures and changes

| Failure | Evidence and resulting change |
|---|---|
| `/openscience` was unknown | The UI advertised `/openscience`; the built-in command was `/science`. Added the alias and verified exact prompt routing with approval retained. |
| `/feynman` and `/opencode` were unknown | Registered bounded commands preserving the explicitly selected engine. Unavailable explicit engines cannot silently become another provider. `/search` maps to the paper explorer action. |
| Codex authenticated but could not answer | All four agent overrides were `gpt-5`. A real request returned `model_not_found` for this ChatGPT account. A separate request without an override returned `OK`. Cleared those four overrides and obtained the catalog from the installed CLI. Removed the API-model list from CLI defaults. Catalog discovery is not entitlement verification. |
| Antigravity exited before inference | Installed `agy 1.4.6` consumed `--output-format` as the value of `-p`. Changed to an attached `--print=` flag with stream input. A real request then returned `OK`. |
| CLI completion could appear empty | Result-only output now becomes visible text once; a successful exit without answer text becomes an error. |
| Streaming and failed chat turns were invisible | Backend SSE content is nested in `data.text`. The UI now reads it, renders persisted turn errors, handles immediate completion, and clears the old spinner on New chat. SSE waits for the matching session snapshot. |
| CLI Studio silently stopped waiting | Replaced 40 × 700 ms polling with the configured turn deadline and explicit failed/cancelled/waiting outcomes. It uses the assigned assistant provider and backend command catalog. |
| Old session model override remained active | Composer and CLI Studio explicitly send an empty model for vendor default, overriding an old session's `gpt-5` without rewriting chat history. |
| Background run had no approval UI | Added a run status card with backend status, reason, approve and cancel actions. Manual chat launch also has a visible action. |
| OpenCode server would not launch | Installed OpenCode requires `--hostname`, not `--host`. Starts in its own workspace with minimal environment; verifies authenticated OpenAPI JSON. HTML SPA fallback is not API readiness. |
| OpenCode falsely claimed native completion | The previous engine adapter only wrote a manifest, then reported completion with invented native IDs. Removed this result path. Automatic prompt dispatch is explicitly unavailable. Tracking sessions start paused with no native session ID. The panel distinguishes workspace preparation, native runtime launch and artifact sync. |
| Provider launch reported success after failure | OpenCode launch requires verified startup. OpenScience reports disabled/unconfigured runtime rather than opening an unrelated public website. |

## Real-provider observations

| Provider | Observed result | Limit |
|---|---|---|
| Codex | Real connector and HTTP → gateway → SSE → saved answer returned `OK` | Only this account/default model and small exercised requests are qualified. |
| Antigravity | Real connector and HTTP → gateway → SSE → saved answer returned `OK` | Only this account/default model and small exercised requests are qualified. |
| Claude Code | Sign-in exists; actual inference returned a weekly usage limit | No quota bypass or API-billing fallback was enabled. |
| Gemini CLI | No configured sign-in method; the real command refuses inference | Requires vendor sign-in by the user. No credentials were copied. |
| OpenScience | Integration disabled in current configuration | Parsing and planning are verified; scientific runtime execution is not verified. |
| OpenCode | Actual local server launched; authenticated OpenAPI readiness passed | Bridge prompt dispatch remains unavailable; a manifest is not inference evidence. |
| Feynman | Installed status reports its configured model | No successful Feynman inference or scientific workflow is claimed here. |

## Evidence and reproduction

Evidence is in `artifacts/cli-connectivity/`. `before/` preserves original failures, including the rejected Codex model. `after-connectors/` records separate default-model diagnostics. `http-codex/` and `http-antigravity/` contain actual SSE events and persisted answers. HTTP harness test conversations are archived. Browser tests use the built frontend and real backend, with no substituted model responses.

```powershell
.venv\Scripts\python.exe tools\cli_connectivity_harness.py --out artifacts/cli-connectivity/recheck
.venv\Scripts\python.exe tools\cli_http_harness.py --provider codex --out artifacts/cli-connectivity/http-recheck
node tools\cli_browser_harness.mjs http://127.0.0.1:8765 artifacts/cli-connectivity/browser-recheck
```

Settings → research providers exposes **Test real CLI chat**, calling the actual connector with a harmless fixed ping. Binary detection and sign-in inspection alone do not prove inference success.

Validation results are recorded in the final evidence summary. The first broad regression run found two failures because Gemini auth inspection leaked into fake-provider tests. Moving auth-file inspection into the real probe fixed the affected gateway and orchestrator suites. Failed initial browser attempts are retained: selector/timing issues and the New chat spinner bug were corrected before the final run.

Release remains **NO-GO for all-provider commercial certification or 100% coverage**. CLI smoke tests do not establish sustained-load stability, access to every catalog model, OpenScience execution or every native tool workflow. The earlier [autonomy report](autonomy-report.md) covers the separate local-model and L1–L4 scope.

Codex invocation was cross-checked against [official non-interactive mode documentation](https://learn.chatgpt.com/docs/non-interactive-mode). The account-specific model rejection and success come from saved real request traces.

## Final verification

- Backend full regression: **752 cases; 745 passed, 7 skipped, 0 failures, 0 errors**. The quality gate returns BLOCKED for release qualification because skips/coverage prevent universal acceptance. Evidence: `backend-verified/report.json`, `unittest.log`, `coverage.json`.
- Backend measured coverage: **90.43% lines**, **81.72% branches**, **88.24% combined**; no claim of 100%. Earlier failed broad runs are retained in `backend-full/` and `backend-final/`.
- Frontend: **168/168 passed**, typecheck and production build passed. Evidence: `frontend-release.json`, `frontend-build-release.log`. Build warns about bundle size and unresolved legacy font fallbacks; bundled WOFF2 files are present. Whole-frontend coverage was not remeasured for this repair.
- Built-browser test: **PASS**, zero page errors, no mocked model responses. It sent a real Codex chat, displayed the exact `/openscience` prompt as an approval-pending run, and cancelled that run in the UI. Desktop/mobile screenshots: `browser-release/`.
- Final real HTTP rechecks: Codex **14.326 s**, Antigravity **15.925 s**, both persisted `OK` and delivered it through nested SSE. Evidence: `http-codex-verified/`, `http-antigravity-verified/`.
- Direct provider recheck: Codex and Antigravity passed; Claude **RATE_LIMITED**, Gemini **AUTH_EXPIRED**. Expected blocked providers make the complete CLI diagnostic exit nonzero; they are not counted as successful integrations.
- Real OpenCode local HTTP server/API readiness passed. OpenScience launch correctly returned HTTP 503 with a disabled-runtime reason. Neither result proves scientific task execution.
- Twelve dedicated connectivity regressions were rerun after import-only test cleanup and passed (`regressions-verified.log`). New repair harnesses and the dedicated regression module pass their scoped Ruff check; repository-wide lint is still not clean.

The removed OpenCode keyword-quota simulation required updating a legacy acceptance expectation. The replacement asserts a paused tracking session with no invented native ID or quota observation. Local ledger approval also does not claim a native prompt started. The native npm v2 executable and positional workspace argument now match installed CLI help.

Machine-readable summary: [summary.json](../../artifacts/cli-connectivity/summary.json). Source hashes: [source-fingerprint.json](../../artifacts/cli-connectivity/source-fingerprint.json). Test fixtures that intentionally corrupt files run in isolated temporary data; their log warnings are fault injection evidence, not observations of production data corruption.
