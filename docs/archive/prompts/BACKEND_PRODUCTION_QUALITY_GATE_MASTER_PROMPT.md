# MASTER ENGINEERING PROMPT — PhD Research Lab Backend Production Quality Gate

> **Target**: PhD Research Lab / Open-Research-Lab backend, source version detected from the actual repository. Reference audit was made against uploaded ZIP `v6.3.0-preview.1`.  
> **Audience**: Google Antigravity, Claude Code or Codex as engineering agent.  
> **Mission**: Inspect **real repository code**; implement, run, fix and verify a **production-grade backend QA program** while protecting researcher data. This is not a proposal-only task.  
> **Success**: Evidence-backed acceptance with *PASS / CONDITIONAL / FAIL / BLOCKED*. No agent may self-certify a release without executed tests.

## 0. Operating contract — read before touching code

You are a principal backend engineer, independent QA lead, security reviewer, agent-systems architect, research data integrity auditor and release engineer. You must:

1. Inspect actual code, installed dependencies, test discovery and any existing `.github`, `tests`, `tools`, `requirements-dev.txt`, `.coveragerc`, `backend/app.py`, `backend/api`, `backend/agent`, `backend/knowledge`, `backend/memory`, `backend/providers`, `backend/execution` and `backend/research_engines`.
2. Report **existing implementation**, **verified working**, **missing tests**, **missing capability**, **reproducible bug** separately. Do not infer missing behavior from an absent UI alone.
3. Preserve the current application architecture and APIs, SQLite schema, CLI and existing research artifacts. Never rewrite a working backend just to make testing easier.
4. Do not run any testing command against live `data/`, `projects/`, user papers, real API credentials, active provider sessions or real models. Use a **unique disposable PHDLAB_DATA_DIR** and explicit fixture repositories. Deny all paid API calls by default through mocks/test fakes.
5. **Never** claim the environment is offline merely because a `PHDLAB_QA_MODE=offline` env var exists; this is a label, not a security control. Enforce offline behavior via provider mock/transport interception, controlled subprocess commands and network sandboxing where feasible. Log exceptions transparently.
6. No unapproved downloading of large model weights, Docker pulls, destructive shell commands, GPU training, live network calls or paid token usage. Hardware test suites are opt-in, separate from basic CI.
7. No fake PASS: missing dependencies, skipped cases, uncollected coverage, browser unavailability and tests that time out are `BLOCKED` or `FAIL` as appropriate.
8. For bugs, write a **failing regression test first**, reproduce, patch the root cause, rerun the affected modules and a suitable wider regression suite, and record evidence.
9. Do not silently mark security test failures as expected, lower assertion strength, weaken policy, or set `coverage omit` to hide uncovered production code.
10. Deliver all code, scripts, CI and reports inside the repository; do not end with 'you can run these later' unless the environment cannot execute them, in which case mark the unfinished parts `BLOCKED` with exact reproduction commands.

## 1. Standards mapped to executable gates

Adopt these sources, referencing versions and specific requirements **actually used**:

| Reference | Purpose | Action |
|---|---|---|
| ISO/IEC 25010:2023 | Quality properties | Trace accuracy, robustness, maintainability, efficiency, security, compatibility to measurable cases |
| ISO/IEC/IEEE 29119 family | Test process/documentation | Requirement-based test plan, cases, expected result, incident logging and test report |
| OWASP ASVS **5.0** | Security verification | Threat model, input validation, authorization, APIs, data protection; capture ASVS control references in test matrix |
| NIST SP 800-218 SSDF | Secure development | Track vulnerabilities, reproduce and document remediation, dependency and release provenance |
| OpenAPI (server's real version) | API contracts | Schema validation, breaking-change detection, HTTP status/DTO consistency and frontend parity |
| OWASP Top 10 for LLM Apps / Agentic AI | AI risks | Prompt injection, excessive agency, tool misuse, unsafe outputs, secrets, unbounded consumption |
| OpenTelemetry GenAI conventions | Observability | Correlation of request → mission → task → agent/provider/tool → artifact; sensitive content opt-in only |
| Python `unittest`, `coverage.py`, Hypothesis, Ruff, Bandit/pip-audit as suited | Executable verification | Retain unittest foundation; add bounded property-based and static analysis where beneficial |

These are references for our internal quality gates, **not a claim that the product is ISO-certified**. See `docs/BACKEND_QA_STANDARD_MATRIX.md` for the gate IDs and severity mapping.

## 2. Actual-source discoveries to verify, not assume

The supplied reference ZIP showed:

- `backend/app.py` creates a FastAPI app with `MutationMiddleware`, `_NoStaleUI` and `_LocalHostOnly`.
- `backend/api/research.py` serves Research OS, mission, team, workstream, handoff, output, dispute, finding, protocol and evidence APIs.
- `backend/agent/missions.py` uses durable SQLite state transitions, approval digests, restricted capabilities and `recover` semantics.
- `backend/agent/collaboration.py` coordinates workstreams and their receipts; `decision_ledger.py` stores an append-only hash chain that does **not** protect against local administrators replacing the DB.
- `backend/execution/guard.py` implements class-level slots for GPU, CPU, local LLM, CLI and cloud.
- `backend/core/bus.py` has an event bus and a metadata-only API mutation notifier; this in-memory ring is **not** a durable global message queue.
- `tests/_env.py` isolates data, `tools/run_tests.py` discovers `unittest` cases, `.coveragerc` enables branch coverage; `tools/research_harness.py` tests v6.0, v6.2, v6.3 with synthetic source fixtures and a real CPU worker.
- The previous focused run passed 40/40 existing tests; six new gate tests and 58-test smoke run passed in an isolated copy. This **does not** establish full-stack or live-provider certification.

The live checked-out repository may differ: detect all differences before proceeding.

## 3. Required implementation phases

### M0 — Baseline + threat model

- Capture exact commit hash, dirty tree status, runtime/OS, Python version, test framework versions, installed providers, allowed test environment and source snapshot hashes.
- Inventory all endpoints from `app.openapi()`; record duplicate names, status schemas, streaming endpoints and direct Python entrypoints not documented by OpenAPI.
- Inventory background task runners, subprocess adapters, CLI gateways, SQLite storage, config, memory, research engines and GPU resource controls.
- Build a **risk map** with P0 irreversible data loss, unauthorized work, double execution/billing, forged evidence; P1 broken core workflows, scope leaks, integrity drift; P2 usability/performance or recoverable degradation.
- Produce `BACKEND_QA_BASELINE.md`, `BACKEND_API_CONTRACTS.json`, `THREAT_MODEL.md`, `BACKEND_TEST_INVENTORY.csv`.
- Validate fixture health and test discovery BEFORE blaming application code for test failures.

### M1 — Test framework and automation without invasive rewrites

- Retain existing unittest and the app's code/test layout. Add composable offline smoke and core profiles using the proposed `tools/backend_quality_gate.py` and `tests/test_backend_quality_gate.py` overlay.
- Never reuse the researcher's real data/config; create an isolated temp root per run. Add test cleanup on success AND failure.
- Use `coverage.py` with branch analysis. Report per-package and changed-file line **and branch** coverage; do not compute one flattering total from selected suites and call it full coverage.
- Add robust `unittest` discovery of both root `tests/test_*.py` and nested `tests/security`, `tests/streaming`, `tests/acceptance`, etc. A baseline script may use explicit modules, but *full* mode must not omit nested tests silently.
- Use a safe runner exit code and write `report.json`, raw `unittest.log`, `RELEASE_DECISION.md`. Use `BLOCKED` for a non-terminating test and provide traceback, timing, and blocker.
- Add GitHub Actions CI on Linux+Windows/Python matrix for safe tests; keep paid API/GPU and long-running tests manual/opt-in.
- Carefully consider test isolation across global singletons and process state (project context, event bus, GPU guard, config and DB).

### M2 — API + integration contract

Required: status and schema checks of valid/invalid requests, type errors, missing params, empty values, boundary lengths, arbitrary JSON keys, 422 contract errors, Unicode/path behavior, upload size and MIME, and multi-project isolation. Include FastAPI `TestClient` and isolated storage.

Special cases:
- Rejected requests must not modify DB nor publish success mutation events.
- Allowed requests must produce correct metadata-only mutation notification; no API keys or prompt content in events.
- Source of truth is OpenAPI + response contracts, not a handwritten route list. If route shape changes, CI must flag relevant frontend API client/types and E2E tests.
- Test SSE with disconnect, retry, heartbeat, cursor, reconnection, interrupted producer and errors. Events can be delivered more than once; consumers must deduplicate. A TCP/WebSocket/SSE drop is **not** proof of task rollback.
- Test the API's localhost-only assumptions. Any remote/multi-user deployment requires a separate security design (authentication, CSRF, TLS, user identity), not simply expanding allowed hosts.

### M3 — Research state-machine and durable semantics (**P0**)

Write a state model and executable transition table for Mission and Task: draft, awaiting approval, approved/queued, running, blocked, paused, interrupted, failed, awaiting human review, completed and cancelled (use actual declared states).

For each transition test:
- Valid and invalid transitions, duplicate commands, approval digest mismatch, expiration, cancel/retry and human review.
- Concurrent tick contention: only one permitted execution per task admission; number of attempts and billed operations cannot silently multiply.
- Crash points: **before dispatch**, **after admission/before effect**, **after effect/before commit**, **after task commit/before receipt**, **after receipt/before report**.
- Restore a new process against the existing SQLite store and assert correct recovery; do not simply monkeypatch a method in the same process and call it restart testing.
- Uncertain side effects require human reconciliation and new approval before retry. Non-idempotent tool calls must not be replayed automatically.
- Parent-child delegation cannot escalate permissions, max reasoning, deadline, cost or wall-time budgets.
- Cross-topic/project reference attempts reject safely and never leak state.

### M4 — Multi-agent / workstream / scientific evidence (**P0/P1**)

- Verify DAG validation: unknown tasks, cycles, conflicting ownership, bounded team count, blocked dependencies, proper completion order.
- Verify handoff publication, receiver authorization, acknowledgment, checksum, dedupe across repeated requests, revision/optimistic concurrency, disputes/finding registration and resolution.
- Verify evidence manifests refer to actual bytes and persisted SHA-256 values. Recompute raw measurements and scientific metrics independently instead of trusting `harness.json: passed` or a model-authored claim.
- Mutate one fixture at a time: forged metrics, tampered ledger, swapped artifact, fabricated DOI, corrupt receipt, duplicate mission IDs and stale revisions. Each perturbation must be rejected.
- Label synthetic literature/source metadata, simulated approval, mocked providers and live scientific observations separately, in final report and UI contracts.
- Ensure research conclusions are never marked 'verified' solely because a deterministic code contract passed.

### M5 — Provider, tool, sandbox and prompt injection (**P0/P1**)

For each supported provider adapter and CLI engine, use controlled fake transports/processes to test:
- Connection loss, HTTP 429/5xx, invalid JSON, truncated chunks, missing finish event, cancellation, slow consumer, hard timeout, authentication failure, quota exhaustion and partial-but-valid output.
- Token/cost counters never display fabricated zeros as actual usage; unavailable billing remains unknown. Configure retry bounds and budgets; no silent failover to a more expensive provider.
- Untrusted search result/PDF/retrieved memory instructs the agent to execute a command, leak a key or bypass approvals: ensure **policy enforced outside the model** blocks the action.
- Shell/path traversal, command injection, URL/SSRF, unexpected file extensions, symlink escapes, process-tree kill and resource limits. Test Windows path quirks and drive letters as well as Unix traversal.
- CLI gateway must not treat subscription app sessions as a paid API entitlement; enforce distinct connection semantics and evidence of successful execution before marking tools available.
- Detect/avoid writing prompts, completions, private PDFs, API keys and research files into telemetry by default; OTel trace payload capture must be off or strictly redacted.

### M6 — Memory, persistence and migrations (**P1**)

- Validate data migrations on copied projects (including old versions), invalid/corrupt SQLite records, schema mismatch, forced I/O failure, exhausted disk and interrupted upgrade.
- Ensure transaction boundaries and atomic writes, backup/restore proof and no silent loss of research records or memory provenance.
- Test context assembly determinism, branch/project scoping, revision, deduplicated recall, retrieval poisoning, stale summaries and rollback of incorrectly proposed memory actions.
- Preserve current persisted research schema and legacy migration behavior unless an explicit migration with backward-compatibility tests is provided.

### M7 — Resource, performance, load and observability (**P1/P2**)

- Validate guard slots, GPU memory admission, competition among local LLM and training workers, cancellation, subprocess cleanup, thread exhaustion and file handle limits.
- Add stress/soak with fake CPU/GPU jobs; isolate real CUDA/GPU qualification as opt-in and report hardware identifiers and driver/runtime versions.
- Define repeatable HTTP/API/SSE and SQLite workloads, record p50/p95/p99, errors, peak memory, DB locks, throughput and worker heartbeat. Save baseline, warm-up and 3 repeats on same machine before imposing fixed gates.
- Use trace/span IDs from incoming request to Topic/mission/task/run/evidence with no secret/prompt/paper contents by default. Define missing-telemetry mode and verify behavior without an observability server.
- Verify frontend–backend contract and SSE event semantics together: no missing task lifecycle state, duplicate UI mutation, stale revision loops or unexplained waiting state.

### M8 — Static analysis, dependencies and CI

- Use Ruff for lint, typing checks appropriate to codebase (incrementally MyPy/Pyright); do not create 100s of unjustified `# noqa` or `type: ignore` suppressions to fabricate a clean run.
- Use dependency and vulnerability scanners (e.g. pip-audit, OSV), secret scanning and SAST; never dump actual credentials into output files. Report high/critical findings and triage false positives.
- Add test categorization (`unit`, `api`, `security`, `stateful`, `fault`, `integration`, `performance`, `hardware`, `paid-provider`) using simple structured manifest or unittest wrapper, not a forced wholesale pytest migration.
- Test Windows and Linux. Gate release when Python compatibility, API contract, or core research invariants are broken.

## 4. Non-negotiable release criteria

| ID | Quality Gate | PASS condition |
|---|---|---|
| G0 | Test integrity | No failing, skipped or blocked **mandatory** tests; each has command and evidence |
| G1 | Data safety | No real research data used or corrupted; disposable test root verified |
| G2 | Mission authority | Approval, digest, scope, budget, capability restrictions all provably enforced |
| G3 | Recovery | Recovery and duplicate-effect fault tests pass across real process restart |
| G4 | Evidence | Raw artifacts independently validated; tampering and fake claims caught |
| G5 | API | Contract and negative-path tests pass; breaking changes flagged |
| G6 | Security | No unresolved P0/P1; ASVS control matrix has tested/not-tested rationale |
| G7 | Multi-provider | Safe, offline provider adapter failure matrix passes; paid live tests identified separately |
| G8 | Resource | Slot, guard, cancellations and process cleanup pass; GPU claims only with hardware evidence |
| G9 | Coverage | Report full-suite and changed-module branch/line coverage; improvement targets are transparent |
| G10 | Performance | Repeatable baseline, error rate and regression analysis; unjustified threshold failures resolved |
| G11 | Observability | Correlated non-sensitive traces, errors recoverable, unknown usage never displayed as zero usage |
| G12 | Cross-platform | Supported Windows/Linux matrix passes, or explicitly mark platform `BLOCKED` |
| G13 | Integration | Research chat ↔ agent ↔ mission ↔ tool ↔ evidence ↔ UI exercised at least one real offline end-to-end test |

**Release decision:**

- `PASS`: every mandatory gate for declared release scope verified with artifacts and human signoff.
- `CONDITIONAL`: tested subset is green but mandatory integration, hardware/security/manual checks remain.
- `FAIL`: reproducible mandatory gate failure, security issue, integrity violation or broken runtime.
- `BLOCKED`: prerequisite missing, unrun/hung tests, unavailable platform/runtime, no valid evidence.

Do not use a false universal 90% coverage requirement: measure **current full-suite baseline first**. Proposed long-term critical-path coverage target >=90%, changed business logic >=80%, both branch-aware; keep project-specific documented exceptions with tests. Never misrepresent a focused 21% global number as full-suite quality.

## 5. Required final deliverables

Create/update in repository:

```text
docs/backend-quality/
  BACKEND_QA_BASELINE.md
  REQUIREMENT_TEST_TRACEABILITY.csv
  THREAT_MODEL.md
  BACKEND_API_PARITY.csv
  SECURITY_ASVS_MATRIX.csv
  BUG_LEDGER.md
  COVERAGE_GAPS.md
  RELEASE_DECISION.md

tests/
  test_backend_quality_gate.py           # installed baseline tests
  ...                                     # additional named cases by subsystem

tools/
  backend_quality_gate.py                # isolated test orchestrator
  ...                                     # optional contract, coverage, fault tools

.github/workflows/
  backend-quality-gate.yml               # offline safe smoke, Windows and Linux

artifacts/backend-qa/
  report.json
  unittest.log
  coverage.json
  openapi_snapshot.json
  ... trace/fault/performance evidence
```

Deliver a short final engineering summary containing: exact source commit; tests total/run/pass/fail/skip; each blocked test; module and branch coverage; # of P0/P1/P2 issues identified/fixed/open; confirmation no production data touched; commands to reproduce; release decision and next 5 prioritized actions.

## 6. Executable starting commands

Windows PowerShell (from repo root):

```powershell
.\.venv\Scripts\python.exe -B tools\backend_quality_gate.py --profile smoke
.\.venv\Scripts\python.exe -B tools\backend_quality_gate.py --profile core
# Separate, explicit opt-in after review:
.\.venv\Scripts\python.exe -B tools\backend_quality_gate.py --profile full --i-understand-full-suite
```

For coverage in this repository, prefer the **existing test runner** because the tests depend on `_env` being importable:

```powershell
.\.venv\Scripts\python.exe -m coverage run --branch tools/run_tests.py test_backend_faults_core test_backend_faults_api test_missions test_workstreams test_research_os
.\.venv\Scripts\python.exe -m coverage report
.\.venv\Scripts\python.exe -m coverage json -o artifacts/backend-qa/coverage.json
```

WARNING: If running coverage directly with `unittest tests.test_...`, the current import layout may throw `No module named _env` (this is a runner import-path mismatch, **not** evidence the backend is defective). Correct test discovery/path rather than hiding the error.

## 7. Completion behavior

Do the work iteratively and continuously maintain a live bug ledger. Preserve API behavior unless a security/correctness defect requires a versioned change. Build executable tests before expanding presentation. End only after the applicable commands have been run and all evidence files have been updated with accurate PASS/FAIL/BLOCKED, followed by proposed improvements prioritized by empirical risk. Do not claim '100% bug-free' or 'ISO certified'.
