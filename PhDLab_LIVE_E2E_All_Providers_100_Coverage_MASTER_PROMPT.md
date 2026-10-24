# PhD RESEARCH LAB — LIVE END-TO-END / MULTI-PROVIDER / 100% REGRESSION COVERAGE MASTER PROMPT

**Audience:** Google Antigravity, acting as Principal Software Test Architect + Staff Python/FastAPI Engineer + AI Agent Reliability Engineer + Security Engineer + Research Reproducibility Auditor.  
**Target:** CURRENT checkout of `Duy-Huan/PhD-Research-Lab`, not documentation screenshots, and not another reconstructed project.  
**Language:** Implementation, identifiers, test reports and evidence in English; brief executive summary to the owner in Vietnamese.  
**Mission:** Engineer, execute, investigate and improve a comprehensive **LIVE, real-inference, end-to-end** validation program for PhD Research Lab, including standalone PhD Lab operations, mission/team/workstream paths, local Phi-4, real CLI agents, cloud API agents, MCP integration in both directions, Feynman/OpenScience when actually installed, external integrations, UI-to-backend parity, restart/recovery, scientific correctness, full regression, and an explicitly enforced 100% line + branch coverage release goal.

> **Non-negotiable honesty:** Never say “100% verified”, “production ready”, “all providers work”, or “no bugs” merely because a simulation/unit/mock test passed. Never fabricate a live response, screenshot, subprocess launch, provider authentication, benchmark, token/cost, or coverage. If something cannot run on this machine, report **BLOCKED** with its exact missing prerequisite. `BLOCKED` is not `PASS`. A model inference on Ollama/LM Studio is REAL local inference, but it does NOT prove an external provider has authenticated or that its wire protocol is correct. A full code coverage result does NOT prove research correctness or bug absence.

---

## 0. Essential safety, execution authorization and definitions

1. **Do not alter real user projects, research files, financial/provider settings, saved sessions or papers.** Work on a fresh Git branch and completely isolated temp project/database/config/cache/workspace. `PHDLAB_DATA_DIR` exists in `backend/core/config.py` and must point to an absolute test-only folder **before importing the backend**. Assert the resolved path is *not* the original `data/` or a registered user project. Snapshot affected files before any migration. Clean up **only files created by the tests** and keep evidence artifacts.
2. Default **LIVE_LOCAL** mode may call Phi-4 only on loopback, may use local CPU/limited GPU and local test sandbox, and must have **zero cloud API spend**. Set `fallback_to_cloud=False`; disable implicit auto paid routing; require `allow_api_billing=False` in every local MissionControl. Any paid endpoint, account side effect, external network or subscription-consuming CLI requires an explicit opt-in test profile and a user-approved spending/quota cap. Never silently use a CLI subscription as a free equivalent of API access.
3. `REAL` means actual executable/server/SQLite/disk/network transport/stream response is exercised. Define: **UNIT** (in-process), **CONTRACT** (request/response protocol), **LIVE_LOCAL** (real Phi-4 inference over Ollama or LM Studio), **LIVE_CLI** (real CLI binary authenticated through its intended mechanism), **LIVE_MCP** (actual MCP endpoint or subprocess), **LIVE_CLOUD** (real authenticated provider endpoint), **LIVE_FULL_STACK** (browser → API → orchestrator → inference → tool → evidence → review), **FAULT_INJECTION**, **SOAK**. HTTP MockTransport, monkeypatches, fake CLI binaries, canned LLM text, emulated provider servers must never be labeled LIVE_CLOUD/LIVE_CLI/LIVE_LOCAL.
4. Tests must not run high-risk unrestricted shell commands or automatically approve actions on users' real files. Docker/Python tool tests use a sandbox-only workspace, tight CPU/RAM/time limits and no unapproved outbound network. Malicious prompts are treated as untrusted content.
5. Preserve current, verified backend behavior; do not rewrite the Mission subsystem or change permission defaults for easier tests. Add observability/test seams only where needed and ensure production mode remains unchanged. Honor existing execution policies, CLI terms and authentication mechanisms.
6. Implement a preflight with exact `READY / NOT_INSTALLED / NOT_AUTHENTICATED / NOT_CONFIGURED / NOT_SUPPORTED / BLOCKED_POLICY / ERROR` per provider and an explicit authorization matrix. Do not ask the user to paste secrets into a chat/log. Perform non-paid mode immediately using local resources when available; isolate optional paid-provider profiles.

**Release decision definitions:** `PASS` = all in-scope mandatory gates, including actually executed live integration gates, passed; `FAIL` = reproducible violations; `BLOCKED` = prerequisite/permission unavailable; `CONDITIONAL` = some mandated provider scopes unverified. Individual cases include `PASS/FAIL/BLOCKED/SKIPPED_NOT_APPLICABLE`; never count skipped tests as passing.

---

## 1. Source-specific facts that MUST be reconciled with the CURRENT checkout

These findings are grounded in the supplied v6.3 ZIP, not an assertion about future commits. At start, inspect code and update if it has changed:

| Surface | Source entry point(s) | Source-grounded warning / requirement |
|---|---|---|
| Mission/workstream control plane | `backend/agent/missions.py`, `research_os.py`, `teams.py`, `collaboration.py`, `mission_contracts.py`, `capabilities.py` | Model cannot change permission/digest; workstream supports max 4 teams and `TeamPlan.max_parallel_tasks: Literal[1]`; don't claim parallel process execution if single worker |
| Existing offline benchmark | `tools/research_harness.py`, `tools/verify_v6_harness.py`, `docs/v6_HARNESS_VERIFICATION.md` | Offline benchmark sets `max_reasoning_calls=0`, so **not** the live model inference acceptance suite |
| App LLM / local model | `backend/providers/models.py`, `local.py`, `router.py` | Distinguish `ollama` native API vs `local` OpenAI-compatible LM Studio; detect actual loaded model, context length and stream path |
| Fixed inference inside governed missions | `backend/agent/research_os.py:fixed_reasoning()` | Supports `control.app_backend="ollama"`/`"local"`, `control.app_model`, `allow_api_billing=False`, no fallback; use at least one `paper.compare` real reasoning task |
| Provider registry | `backend/providers/registry.py`, `cli.py`, `gateway.py`, `lifecycle.py`, `events.py` | App providers `app:auto`, `app:local`, `app:ollama`, configured cloud providers and CLI connectors `cli:codex`, `cli:claude_code`, `cli:gemini_cli`, `cli:antigravity` |
| MCP inference **client** | `backend/providers/mcp_agent.py` | Separate protocol from OpenAI-compatible HTTP; `initialize` / `notifications/initialized` / `tools/list` / `tools/call`; named schema-compatible inference tool; no auto-discovery execution |
| MCP **server** exposing research tools | `backend/providers/mcp_server.py`, `backend/api/mcp.py`, `mcp_stdio_bridge.py`, `backend/agent/mcp_policy.py` | Test session grants, tool listing/denial, stdio and actual localhost HTTP POST, not just fake JSON-RPC function calls |
| Research adapters | `backend/providers/research.py`, `backend/research_engines/{feynman,openscience,registry}.py` | Feynman and OpenScience have separate health/capabilities; do NOT equate their research workflow with general CLI chat |
| Existing selective live tests | `tests/test_live_integrations.py` | Currently opt-in ClearML and Codex read-only smoke; extend actual coverage across supported adapters |
| Data isolation | `backend/core/config.py` | `PHDLAB_DATA_DIR` should redirect test data; validate isolation before any backend import |
| Existing coverage | `.coveragerc` | Already enables `branch=True`; existing `omit` and `exclude_also` require line-by-line review before any 100% statement |
| Frontend integration | `frontend/`, `backend/api/`, `backend/app.py` | Discover actual frontend stack in working tree (React may be partly migrated); browser tests must navigate real routes and exercise real controls |

Inventory **every** user-facing feature, backend subsystem, endpoint, route, command and handler dynamically from code/OpenAPI. Do not assume the table is exhaustive. Pin base commit, Python/Node versions, OS, model digest and app version in all results. Register new features discovered after this prompt as explicit matrix rows, not implicit untested scope.

---

## 2. Test/QA standards and evidence hierarchy

Use these sources as **guides adapted into measurable assertions**, not as claims of certification or mandatory one-size-fits-all requirements:

- **ISO/IEC 25010:2023** — software product quality model: functionality, performance, compatibility, reliability, security, maintainability, portability and safety qualities: https://www.iso.org/standard/78176.html
- **ISO/IEC/IEEE 29119-1/2/3/4** — test concepts/process/documentation/design techniques, including decision tables, state-transition, boundary values and branch/condition tests: https://committee.iso.org/sites/jtc1sc7/home/projects/flagship-standards/isoiecieee-29119-series.html
- **ISO/IEC TS 42119-2:2025** — AI-system testing and how to adapt the 29119 series to AI systems: https://www.iso.org/obp/ui/#iso:std:iso-iec:ts:42119:-2:ed-1:v1:en
- **NIST AI Risk Management Framework (AI RMF)** — risk identification/measurement/management for AI systems: https://www.nist.gov/itl/ai-risk-management-framework
- **OWASP ASVS** plus **OWASP Top 10 for Agentic Applications 2026** — API, approval, privilege escalation, tool misuse, sensitive data, agent interactions, prompt injection: https://owasp.org/www-project-application-security-verification-standard/ and https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- **Model Context Protocol specification / official conformance** — client/server initialization, transport, capability and tool-call behavior: https://modelcontextprotocol.io/specification and https://github.com/modelcontextprotocol/conformance
- **MCP Inspector** — debugging actual MCP stdio/HTTP connections, CLI scripting: https://github.com/modelcontextprotocol/inspector
- **OpenTelemetry GenAI semantic conventions** — per-call tracing, model, latency, token usage and tool events **where actually observable**: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- **OpenAPI** and schema-driven API/property testing (Schemathesis/Hypothesis where appropriate); **Playwright** real-browser E2E; **coverage.py** statement/branch measurement and mutation testing. See https://spec.openapis.org/oas/latest.html, https://schemathesis.readthedocs.io/, https://playwright.dev/, https://coverage.readthedocs.io/.

Testing method: risk-based tiering + state-transition and graph coverage + metamorphic/property-based tests + contract conformance + adversarial/failure testing + *real* integration + reproducibility verification. Record the source URL and applicable requirement IDs for each quality gate. No ISO conformance/certification claim unless a proper independent assessment is performed.

---

## 3. Deliver architecture: automated test framework (not a one-off prompt-run)

Create or evolve a maintainable hierarchy without breaking the existing `unittest` modules:

```text
tests/
  live_e2e/
    conftest_or_setup.py             # real service preflight and safe isolated data
    test_local_phi4.py              # real inference, no LLM-text mocking
    test_phdlab_only.py            # standalone workflows via HTTP + UI
    test_real_mission_modes.py      # single/fixed/adaptive/multi workstreams
    test_provider_cli.py           # installed logged-in real CLIs
    test_provider_cloud.py         # opt-in authenticated API smoke
    test_mcp_server.py             # real HTTP and stdio server
    test_mcp_inference.py          # real MCP inference client/agent
    test_coding_research_engines.py
    test_live_failure_recovery.py
    test_full_stack_browser.py
  conformance/
  security/
  resiliency/
  load/
  property/
  scientific/
tools/
  live_quality_gate.py             # --profile/--provider/--report-dir; safe default
  live_test_preflight.py
  live_test_environment.py
  live_test_coverage_gate.py
qa/live_e2e/
  PROVIDER_INVENTORY.csv
  FEATURE_TO_JOURNEY_MATRIX.csv
  TEST_PLAN.md
  BUG_LEDGER.md
  COVERAGE_EXCLUSIONS.md
  FAILURE_ANALYSIS.md
  RELEASE_DECISION.md
  runs/<UTC-TIMESTAMP>-<GIT-SHA>/  # report, junit, trace, screenshots, audit, checksums
```

This layout is a design proposal. Adapt to existing project conventions; names must be real implementation files if reported as delivered. Preserve existing test runner and pytest/unittest interoperability. Create one cross-platform entrypoint with `--profile=unit|contract|live-local|live-cli|live-mcp|live-cloud|live-full|fault|soak|all`, and optionally `--provider`, `--budget-usd`, `--max-provider-calls`, `--time-limit`, `--model`, `--report-dir`, `--allow-paid` (default false). All gates must print clear PASS/FAIL/BLOCKED and nonzero process exit on failure or required blocked prerequisites.

All smoke and deep tests need machine-readable JUnit/XML/JSON reports. Never swallow test failures with `|| true`, `except: pass`, fake approvals or success-only assertions. Use test IDs stable across releases and record a test-to-code/feature mapping.

---

## 4. PRE-FLIGHT — real machine, auth, hardware and isolation

Start with a read-only report:

- OS, cwd, Git HEAD/diff (mask secrets), Python/Node, dependencies, CLI versions, Docker/WSL status, port availability, current server health.
- Run `ollama list`, `ollama ps`, `GET http://127.0.0.1:11434/api/tags`, `GET /api/ps` **if Ollama is installed**, and/or LM Studio REST/OpenAI model list **if configured**. Detect exact installed Phi-4 tag; no hard-coded assumption beyond a configurable default `phi4`. Record model digest, quantization, context limit when reported, GPU/CPU placement and actual response latency. Do not run `ollama pull` without explicit approval for disk/network downloads.
- Use one real benign Phi-4 inference that returns a recognizable structured response; then test non-stream and stream over **the exact app adapter code**, not only by direct curl. Assert response nonempty, valid message role, coherent bounded output, correct cancel/timeout semantics, no hidden cloud call.
- Discover configured CLI binaries `codex`, `claude`, `gemini`, Antigravity connector; test version and sign-in status non-destructively. Credential check does **not** equal inference success. Each real auth/inference must be logged separately.
- Enumerate MCP tool server URLs/stdio commands from configuration; ensure only loopback test-only endpoints by default. Test denied remote/unsafe URLs. Detect actual protocol version rather than assuming newest works.
- Discover configured cloud providers from `backend/core/config.py` and provider registry; report those with keys in the test-only config **without printing keys**; do not infer API entitlements from CLI subscriptions. Prepare `LIVE_CLOUD` matrix only if explicitly enabled.
- Disable API fallback in live-local profile, verify its actual persisted settings, and verify request logs contain only loopback target endpoints. Do not rely only on the configuration flag; assert observed transport destinations.
- Set `PHDLAB_DATA_DIR=<absolute isolated test folder>` before importing `backend.*`, start fresh app instance and unique test port. Confirm no write activity under actual production paths using before/after tree hashes (read-only baseline snapshots); do not report isolation pass until checked. Isolate Redis/SQL/cache/browser local-storage/providers' workspace if relevant.
- Limit local inference concurrency and cap context/response tokens to fit hardware. Phi-4 Ollama distribution commonly has a 14B model and a 16K context window, but actual install/quant and effective context length must be queried. For constrained GPUs start with `num_ctx=2048` or `4096` and a short `num_predict` (e.g. 128–512) and tune based on observed VRAM, latency and correctness, **not** pretend all independent agents can run simultaneously.

**Windows-first operator checks (examples, adapt to installation):**

```powershell
ollama list
ollama ps
curl.exe http://127.0.0.1:11434/api/tags
curl.exe http://127.0.0.1:11434/api/ps
# Must run in a NEW shell before importing PhDLab backend:
$env:PHDLAB_DATA_DIR = (Join-Path $env:TEMP "phdlab-live-e2e-isolated")
# Example inference only after discovering model tag:
$body = @{model="phi4";stream=$false;messages=@(@{role="user";content="Reply with the word READY"})} | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/chat" -Method Post -ContentType "application/json" -Body $body
```

**Important:** The last direct `/api/chat` request is a *server availability check*, not full application E2E proof. A full E2E test must route through PhDLab's API, orchestrator, state persistence, tool execution and verification.

---

## 5. Local Phi-4: REAL AI agent test harness, with measurable oracles

Use the user's already installed Phi-4 as an actual local backend, never a prerecorded dummy response:

- Configure test-only `ollama_model` to the discovered model ID; set `agent_modes.assistant/research/reviewer/utility` to `ollama` for PhDLab-only tests; set each Mission `control.app_backend="ollama"`, `control.app_model=<discovered-tag>`, `allowed_engines=["deterministic","app"]`, appropriate `permissions`, `max_reasoning_calls>0`, `allow_api_billing=false`, `review_required=true`. Confirm the current schema before constructing objects.
- If using LM Studio instead, set agent engine to `local`, `local_model=<loaded-ID>`, proper base URL, and use `control.app_backend="local"`. Do not conflate Ollama and LM Studio transports. Do not emulate paid-provider proprietary message formats and call this real integration.
- Roles: Assistant chat, Research, Reviewer and Utility/background memory. Where the architecture has logical `TeamPlan.agents`, explicitly map owner/verifier to **roles** and show actual inference calls; do not assert each logical agent represents a separate process/LLM if it does not. Include single-team and 2–4 workstreams, provided schema permits.
- Test real inference: 3 distinct prompts per role (basic, context-dependent, adversarial), real streaming and nonstreaming, multi-turn context, summarization, traceable output, knowledge retrieval, token/context budget, and reload/restart. Assert **role separation via prompts/provenance**, not merely by response text style.
- Deterministic expectations: protocol/JSON schema adherence, nonempty and bounded output, event ordering, persistence, correct artifacts, correct state transitions, explicit uncertainty, prohibition of unauthorized actions, no cross-topic leak. Do **not** assert exact words from Phi-4. Use multiple seeded or temperature-zero trials where useful but treat GPU determinism as limited; record seeds/temperature/request settings.
- For AI judgment tasks, implement a small owner-approved `golden cases` dataset containing evidence-linked facts and known false citations. Score factuality/citation integrity manually or via independent grounded verifier; do not let the same Phi-4 instance approve its own result as a substitute for ground truth.
- For tool calling: FIRST verify if the installed Phi-4 + runtime actually supports native `tool_calls` and structured outputs. Ollama's Phi-4 description advertises text, not guaranteed native function calling. If unsupported, PhDLab must continue working through its actual app-controlled bounded tools, and mark **native tool-calling-specific tests NOT_SUPPORTED**; do not fake tool calls or manipulate output to simulate native support. Separately test with another truly tool-capable model only if already installed and explicitly authorized.
- Force memory pressure/context overflow, slow token generation, malformed/partial JSON, user cancel, server not running, model unloaded, 429/503 from a separate protocol-fault harness, and recovery. For REAL local model failures use real service manipulation only inside a dedicated isolated test instance; never kill another user's active Ollama session indiscriminately.

Minimal live agent acceptance cases:

| ID | Real action | Required assertion |
|---|---|---|
| LOC-01 | Phi-4 through PhDLab chat API, nonstream | actual Ollama request observed; response in same conversation + DB |
| LOC-02 | Phi-4 stream through SSE | valid ordering, no duplicate final response, cancel safe |
| LOC-03 | Research→Reviewer on same evidence | both run; second receives evidence/context; reviewer may disagree |
| LOC-04 | Topic A/B separation | no unauthorized data crossing; context selection correct |
| LOC-05 | Restart app then continue chat | state+context restored, no invented native CLI resume |
| LOC-06 | Memory compaction and retrieval | retrieval references persisted provenance and survives restart |
| LOC-07 | Live `paper.compare` inside approved mission | `reasoning_calls>=1`; engine/model=Phi-4; verifiable output and audit |
| LOC-08 | Bad prompt requests deletion/exfiltration | no tool or write without matching rights and approval |
| LOC-09 | Local offline + paid fallback disabled | 0 paid-provider requests and no hidden network egress |
| LOC-10 | Model stopped/unloaded mid-stream | explicit failure, resumable app state, no false completion |

---

## 6. PhD-Lab-only END-TO-END journeys: real functionality, not orchestration mocks

Run the app using only its built-in backend, bundled skill registry, configured local services and real Phi-4; **disable external research engines, CLI providers, cloud APIs and optional network scholarly search** for the pure offline lane. A paper search requiring network should be tested in a separately flagged **live-network** lane; do not manufacture literature from the model to make the offline lane pass.

For every journey: execute actual API or UI command → inspect DB/process/events → verify artifact/output → reload page/app and verify persisted state → human-reviewed or test-owned expected results. New test data must use explicit synthetic identifiers and disclosure banners.

| ID | Standalone full flow | Artifacts and required checks |
|---|---|---|
| ST-01 | Launch, configure, create project, set active project, create Topic A/Topic B | project metadata, isolation, no parent path escape |
| ST-02 | New chat session → Research model → follow-up → Reviewer model → reload | messages, context, provider model ID, durable conversation |
| ST-03 | Test-only text/Markdown document ingestion and reading | chunk/store/index/search/citation; no invented source |
| ST-04 | Test-only sample PDF and BibTeX import/parse/index (if dependencies present) | source hash, page metadata, expected paragraphs, deduplication |
| ST-05 | Research question → grounded retrieval → answer → citation/claim validation | exact evidence refs, unsupported DOI marked unverifiable |
| ST-06 | Long-term memory: several sessions, context compaction, summary, reconstruction, conflicting decision | provenance, temporal consistency, no cross-project leakage |
| ST-07 | Source→hypothesis→research charter→Mission plan→approval→execution→evidence→human review | final status, complete audit, no premature scientific verification |
| ST-08 | Code project → sandbox Python execution → stdout/stderr/files → process cancel/restart | actual subprocess, resource caps, artifact sha256 |
| ST-09 | Experiment protocol approval → CPU workload → raw metrics→independent reproduction | numeric recomputation from raw arrays, reproducible seeds, bounded runtime |
| ST-10 | Model output → draft research note / LaTeX if available → local compile | valid generated files, no fake references, no automatic external dissemination |
| ST-11 | Optional research file workspace sync → manual review → accepted/rejected artifact | project scope, rollback, versioning, audit event |
| ST-12 | Standalone provider-less mode with inference unavailable | readable UI error, blocked state, no ghost success |
| ST-13 | Project switching with actively running mission | old project state unchanged, UI context accurate, no cross-write |
| ST-14 | Browser refresh, navigation, two tabs/clients, SSE reconnect | no duplicate user action, no lost result, coherent monitor |
| ST-15 | Full 30+ minute synthetic research session with >1 mission, >1 topic | memory/DB integrity, bounded logs, no state leakage |
| ST-16 | Workspace cleanup/archival/export/reimport when supported | round-trip matching artifacts and references; destructive operations require test-only confirmation |

All expected output files, citations, metrics and terminal states must have independent, machine-checkable oracles. A nice prose answer or final `status="completed"` alone is insufficient. Verify that mission finalization and research/scientific review are **separate** state transitions.

---

## 7. Real Mission/Team/Workstream branch coverage matrix

Create a **real-inference counterpart** to `tools/research_harness.py`, preserving existing offline verifier. Use one `paper.compare` where possible to invoke actual Phi-4, and combine it with deterministic tasks for interpretable verification. Supply local synthetic papers (clearly labeled untrusted fixtures) to avoid network dependencies in local lane.

**Modes (if existing feature flags and exact schema support them):** legacy single mission, Team `single`, Team `fixed`, Team `adaptive`, multi-workstream (2, 3 and 4 teams), multi-topic parent/child charter, an end-to-end mission requiring real `paper.compare`, and one mission with no model. Because `max_parallel_tasks=1` in the examined v6.3 schema, test **sequential worker execution with multiple logical teams**, not fabricated process parallelism. If latest implementation adds parallelism, add race/locking tests specifically.

**Required branches:**

1. Happy path: Charter→MissionSpec→propose→request approval→approve correct digest→run tasks in DAG order→publish dependency evidence→acknowledge→verify→await human review→review→completed.
2. Reject draft, stale digest, expired approval, permission escalation, missing/forged topic/project identifier, allowed-engine expansion, workstream owner mismatch and wrong dependency digest.
3. DAG fan-out, fan-in, impossible dependency, cyclic dependency, missing dependency, failed upstream task, downstream blocking and optional replan. Exercise same flow with Phi-4 data and deterministic data.
4. Budget edges: exactly at limit and just over limit for wall time, reasoning calls, depth, hops, tasks, artifacts, tokens when obtainable, subscription/provider quota when reported, and CPU/GPU caps. No silent paid fallback.
5. Provider missing/unavailable, timeout, bad auth, malformed LLM output, JSON parse failure, SSE partial response, process crash, cancellation and one retry policy (must not double-charge or duplicate irreversible side effects).
6. Workstream boundaries: owner vs verifier; source→destination handoff; accepted/denied/missing/double ack; duplicate/mismatched source digest; wrong receiver; conflict on canonical output/revision; dispute→human resolution; resulting final evidence chain.
7. Restart from at least **five distinct checkpoint moments:** before approval; after task admitted but before effect known; after external side effect but before acknowledgment; after handoff publish; after final review request. Use separate OS processes and persisted test database. Assert idempotency or explicitly `interrupted` awaiting human intervention when exactly-once cannot be guaranteed.
8. Run an intentionally failed workflow in a sibling workstream; prove other branches are not falsely marked complete. Prove final state cannot be `verified` based only on an LLM claim.
9. Each mission must capture at minimum: mission UUID, topic/project, task and workstream IDs, configured provider vs actual provider, model ID, input/output digests, approved permissions, timing, stdout/trace if applicable, file artifacts and checksums, state transitions, reviewer independence, resource usage and cost status (`unknown` when unverifiable).
10. Re-run reproducibility benchmark with original offline deterministic suite **and** new live model lane. Do not equate stochastic text-identical reproduction to deterministic numerical reproducibility.

Create a machine-readable coverage matrix for `state × mode × provider class × permission × failure type` using **pairwise** to limit combinatorial explosion, but retain all mandatory state transitions and risk-critical combinations. List uncovered combinations explicitly.

---

## 8. Provider-by-provider REAL verification (not provider emulation)

**Transport/contract phase** may use a local test server for controlled faults, but live phase must also use its REAL installed/authenticated implementation. Execute separately by provider; don't use Phi-4 to impersonate a paid provider and claim success.

### 8.1 Local inference adapters

- `app:ollama` → Phi-4 over actual Ollama native API and, where app supports, streaming; assert model ID, `num_ctx`/response limits, lifecycle unload/reload, cancellation, no cloud fallback.
- `app:local` → a genuinely running **LM Studio** OpenAI-compatible endpoint using Phi-4 loaded in LM Studio *if available*; if not installed, BLOCKED, not covered by Ollama. Compare output normalization and role handling across adapters.
- `app:auto` → if permitted, verify local-only routing selects a real local model and paid-provider candidates are excluded; trace target URL to catch hidden fallback.

### 8.2 CLI subscriptions: distinct real binaries

- `cli:codex`, `cli:claude_code`, `cli:gemini_cli`, `cli:antigravity` from `backend/providers/cli.py`; verify each installed binary/version, real sign-in session state, `gateway.prepare`/`gateway.send`/`events`/`cancel`, spawned OS process arguments, actual JSONL/event decoding, output and workspace isolation. Test read-only task with a tiny `hello.py`, then a separately approved sandbox-write task; assert same test file content before/after as expected.
- Test real CLI tool call, streamed output, cancel/timeout kill-tree, `stdin`, session resume when advertised, unsupported resume truthfulness, login expired, quota exceeded, malformed CLI output, clean process teardown, security profiles (`review` vs `assisted`) and provider capability metadata. CLI-specific flags may vary by version; detect/version-pin and adapt, not forcibly set unsupported flags.
- Strictly differentiate *subscription sign-in* from *API key*. Do not bypass authentication or use unofficial token/session extraction. Antigravity connector may offer a different execution capability than Codex/Claude CLI; if no callable CLI exists, mark NOT_SUPPORTED/BLOCKED and do not equate IDE agent runtime with real CLI.

### 8.3 Cloud APIs (opt-in, actual paid endpoints)

- For each **configured** cloud API provider (Anthropic, OpenAI, Gemini or others from current registry), optionally execute at least one actual minimal authenticated non-stream response, one stream response, and one observed transport-level error, plus proper model enumeration/health where officially supported. A provider without approval or key is BLOCKED, never passed via an emulated HTTP server.
- Record provider endpoint/host, selected exact model, request ID when emitted, HTTP code, latency, supported usage counters, billable cost from authoritative data if available, request count and any real rate/quota error. Never invent subscription remaining tokens. Redact all credentials/prompt-sensitive text from public logs.
- Live-cloud profile must require `--allow-paid`, provider allowlist and hard maximum calls/expense; auto-fallback disabled unless the scenario explicitly tests authorized fallback. Stop when cap reached; treat inability to enforce budget reliably as BLOCKED for unbounded profiles.
- Negative: invalid key, disallowed model, restricted paid fallback, retry on 429 only if policy allows, timeout/cancel, provider unavailable, provider returns unsupported usage fields; ensure no hidden handoff to another vendor.

### 8.4 MCP BOTH DIRECTIONS — absolutely mandatory

**A. PhDLab as MCP server** (`backend/api/mcp.py`, `backend/providers/mcp_server.py`, stdio bridge): spawn real app/bridge → initialize → capability handshake → list tools/resources/prompts actually supported → call a read-only research tool with session grant → call denied unauthorized tool → verify blocked write → accepted review-candidate path (not direct unsafe mutation) → session expiration → malformed JSON-RPC → wrong protocol/session → remote-origin rejection. Use official MCP Inspector/Conformance where its current version supports the transport; pin version/record exact invocation, verify live protocol capability. Include unexpected disconnect and restart.

**B. PhDLab as MCP inference CLIENT** (`backend/providers/mcp_agent.py`): start one actual **test-owned** MCP HTTP server exposing an inference tool which invokes real Phi-4 (Ollama/LM Studio) behind the server; this is **LIVE_LOCAL_MCP** (real model + real MCP transport), not LIVE_EXTERNAL_MCP. The client performs actual initialize→initialized→tools/list→schema check→tools/call. Assert no other tool automatically runs, no credential forwarding, no redirect, correlation IDs/session state correct, 2MiB response cap, timeout, malformed and uncorrelated replies, denied host/url, token handling. If a real external MCP server is configured/authorized, run an additional **LIVE_EXTERNAL_MCP** test against it; distinguish both in report.

**C. Cross-provider:** CLI agent using PhDLab MCP tools → PhDLab project data permission → evidence return → chat/review result → reload session; ensure authority is session-scoped and not preserved beyond revocation.

### 8.5 Research runtime plugins and experiment tracking

- Feynman and OpenScience: if installed and ready, run **real** small, bounded provider-specific research workflows with citations/artifacts, compare output contracts and actual process/workspace handling; if not ready BLOCKED and show actionable setup. Test provider selection without pretending the app model is literally executing a Feynman/OpenScience pipeline.
- Python sandbox: real Python subprocess with bounded execution, stdout and metrics, cancel, reproducibility, disallowed path. Docker: real container only if installed/authorized, no privileged host writes; test exec/kill/cleanup.
- ClearML: local/offline tracker for deterministic events, real server integration only on opt-in with actually configured credentials. Preserve existing selective live test behavior.

**Provider evidence file per test:** `provider_id, transport, observed_binary_or_base_url, runtime_version, configured_model, observed_model, auth_status, actual_call_count, first_byte_time, total_latency, terminal_state, event_count, usage_source, usage_tokens_or_unknown, cost_or_unknown, context_hash, output_hash, artifact_hashes, approval_policy, pass_fail_reason`.

---

## 9. Real FULL APP UI → backend → provider → storage → UI regression

If React migration has happened, test React; if partly migrated, audit whichever routes are actually shipped. Launch **real** frontend and backend using isolated test data; drive a real browser (Antigravity Browser Subagent and/or Playwright). Verify accessibility and design separately in existing frontend QA gate.

Critical end-to-end UI journeys:

1. Configure Phi-4 from Settings → successful connection test → create topic → chat → streaming transcript persisted after refresh.
2. Create mission → view plan/DAG → approval dialog → start → live event updates → task/agent/workstream inspector → evidence artifact → human review → completed status persisted.
3. Run `paper.compare` with actual Phi-4 and show real provider/model and latency; backend inference events should be observable without false “multi-agent parallel” animation.
4. Switch provider to a **different actually available local transport** (Ollama→LM Studio), if ready, and verify a subsequent AI response uses the new provider rather than stale default.
5. Switch to CLI agent/authorized MCP route and verify UI shows real session state, tool grant, live output and final artifact; BLOCKED if missing provider, not a fake green check.
6. Disconnect network/kill only test-owned service during run → honest error, no completed badge, retry after reconnection and no duplicate task.
7. Two tabs/client reconnect + background task + topic switching, browser reload, cancel and process restart. Ensure existing mission ID continues; no double dispatch caused by UI effects.
8. Workstream handoff/ack/dispute/canonical revision conflicts: verify frontend can inspect and operate current backend-supported APIs; record missing controls as a UX/API parity defect, not backend pass.
9. API/GUI state parity assertions based on source of truth; compare events and persisted snapshot, not merely screenshots.
10. Full-session tests include empty, loading, error, reconnect, quota exhaustion, partial data and stale-event race conditions.

Capture screenshot/trace/video when failures occur; redact sensitive content. Use real host ports and process IDs. Separate JS/CSS/Vite coverage from Python backend coverage and instrument the browser bundle where feasible. Avoid reporting only Playwright “tests pass” without server/process and inference evidence.

---

## 10. Failure injection, security and chaos scenarios — real consequences, safe isolation

Construct a reversible, test-owned failure-injection harness and run against true app processes, local provider and data. At minimum:

| ID | Fault | Must prove |
|---|---|---|
| F-01 | Kill test-owned backend after task admission | state interrupted or resumed correctly, no duplicate irreversible effect |
| F-02 | Kill model server/make it unreachable during real Phi-4 inference | transparent error, bounded retry, no false completion |
| F-03 | End real CLI subprocess mid-stream | cancel/kill-tree cleanup, correct request terminal state |
| F-04 | MCP disconnect after initialization | retry or explicit failure, no unbound tool execution |
| F-05 | Corrupt/tamper artifact/checksum after creation | verification fails, scientific claim not auto-certified |
| F-06 | Reuse request ID/idempotency key | no duplicate paid/side-effecting operation; if impossible then flagged for human intervention |
| F-07 | Wrong tenant/topic/project ID | data denied and audit recorded |
| F-08 | Invalid/stale Mission plan digest | approval/execution denied |
| F-09 | Prompt injection in paper/tool output | cannot acquire write, network, secrets or API billing privileges |
| F-10 | Out-of-order, repeated SSE frames and page reload | client state converges without duplicate action |
| F-11 | SQLite busy, concurrent writes, crash during transaction | no partially committed inconsistent state |
| F-12 | Storage full/write denied/artifact too large | no false evidence record, bounded error response |
| F-13 | GPU OOM/long inference/CPU overload within test safety bounds | no catastrophic data loss, resource cleanup or graceful rejection |
| F-14 | Provider 401/403/429/5xx or malformed response | classified error, safe cooldown, no unauthorized fallback |
| F-15 | Canonical output revision race across two clients | one authoritative revision or explicit conflict resolution |
| F-16 | Source evidence claims false DOI or fabricated PSNR | verifier rejects/unverifiable; reports preserve limitations |
| F-17 | User revokes tool grant during session | subsequent tool invocation rejected; no inherited authority |
| F-18 | Sandbox path traversal/zip slip/oversized output | deny access outside test workspace, no leak |

Use real negative cases when safe; protocol fault proxies and local test servers may inject deterministic HTTP errors and must be labeled `FAULT_INJECTION`, not provider-live success. Never intentionally DOS external cloud vendors or stress personal subscription quotas.

Run OWASP Agentic risk cases covering prompt injection, privilege escalation, tool misuse, memory poisoning, insecure inter-agent messages, insecure approval delegation, secrets, denial-of-wallet and unverified external content. Human approval remains required for high-impact actions.

---

## 11. Scientific verification, reproducibility and long-horizon memory

A successful mission is not automatically a valid scientific finding. Enforce independently checked invariants:

- Denoising CPU benchmark with generated small arrays and fixed seeds: recompute MSE/PSNR/statistics independently from raw artifacts, verify training/test separation, file SHA, protocol version, executable source SHA and rerun consistency. No use of Phi-4 prose to validate numeric truth.
- Fabricated literature metadata test: make the model see a plausible but fake DOI/reference, assert it stays unverified. Compare a known valid synthetic fixture metadata row to its source payload; avoid claiming real scholarship when tests are synthetic.
- Research project across multiple sessions: Topic A evidence should not appear in Topic B without an explicit retrieval grant; log context packet digests and lineage. Test memory compaction fidelity and the “uncertain” status if data is insufficient.
- Agent Research proposes a hypothesis; Reviewer disputes one invalid claim; mission must surface dispute for human decision and produce corrected final report only after review.
- Evidence handoff to Workstream B must preserve provenance, original trust label and receiving scope. Publishing handoff does not upgrade untrusted AI text into verified evidence.
- 3 independent runs for stochastic real Phi-4 narrative quality cases; score structural compliance and evidence consistency with explicit thresholds, confidence notes and logged parameters. No exact-string golden tests for generative prose.
- Full-day/overnight long-horizon soak is **optional opt-in**; choose reasonable cap on cost/VRAM/CPU, never run indefinitely. Verify recovery between sessions and memory growth trends.

---

## 12. 100% COVERAGE POLICY — STRICT, ANTI-GAMING, WITH TRACKED EXCEPTIONS

**Owner's target:** **100.00% executable statement/line coverage + 100.00% branch coverage** for the declared project-owned backend under the full combined regression suite; also **100% coverage of the mandatory live E2E journeys and supported/authorized provider paths**. Treat this as the **release aspiration and enforced target**, not an assertion it has already been achieved. The run must report current actual percentages and missed lines/arcs honestly. Separately compute frontend statement/branch/function/line coverage once the migrated React test tooling supports it; report frontend browser journey coverage independently.

Mandatory actions:

1. Inventory all in-scope backend packages from source (`backend/**`, app entrypoints, local orchestration tools if project-owned). Distinguish dynamic imports/plugins/processes. Keep generated files, third-party dependencies and vendor directories outside measured first-party source by documented scope rules. **Do not exclude project-owned modules merely because their tests are hard.**
2. Audit `.coveragerc` existing `omit = backend/execution/clearml_worker.py`; investigate whether this is project-owned testable code. Explicitly justify or remove such omit before any global “100% backend coverage” claim. Source-level `# pragma: no cover`, `exclude_also`, and coverage `omit` must have an inventory, rationale, reviewer approval and counts. Reject unjustified exclusion changes and denominator reductions in CI.
3. Combine unit, contract, integration, live-local, live-MCP, CLI/cloud opt-in, fault-injection, subprocess and browser-driven backend execution in a reproducible coverage dataset. If subprocess tracing is unavailable, implement correct `coverage.py` subprocess startup/parallel aggregation; do not mistake an uninstrumented child as covered. Keep production behavior unchanged when coverage is off.
4. Enable and validate branch tracing (`branch=True`) and use `coverage json` to parse **actual** `missing_lines` and `missing_branches` per file; fail if any remain in the approved scope. Do not rely on rounded `100%` display: zero missing lines and zero missing arcs are required. Also run `coverage report --fail-under=100` on the combined measured scope.
5. Add tests for every missing decision branch, negative outcome and recoverable failure. Where an apparently unreachable code path is discovered, **investigate and correct dead code** rather than adding random mocks solely to execute a line. Flag truly platform-impossible branches as `UNREACHABLE_PENDING_REVIEW` with source location, proof, ownership and explicit sign-off; until resolved, **do not claim universal 100%**.
6. Coverage alone is not enough: mutation test (`mutmut` or equivalent where compatible) at least risk-critical modules (missions, policy, grants, data persistence, provider gateway). Target **≥95% mutation score on P0 modules**, investigate survivors with behavior tests; thresholds are project-defined QA gates, not ISO requirements.
7. Add static scan and dependency security checks (ruff/mypy/pyright if adopted, pip-audit/bandit/Semgrep when appropriate) plus OpenAPI schema fuzz/property tests. Scan results must be triaged, not hidden.
8. Introduce **risk-first increments**: 100% for new or modified P0 security/control-plane modules in each PR, then increase legacy whole-backend coverage module-by-module while the FULL 100% target remains visible and failing until honestly attained. No automatic waiver because a model ran out of context or quota.
9. Require diff coverage 100% on every new change to business logic; line-only or branch-only success is insufficient. Provide per-file, per-package, per-profile numbers plus combined suite. Differentiation: full-suite coverage may benefit from mocks for inaccessible branches, but **LIVE_E2E certification requires real transports/provider invocations regardless of code coverage**.
10. Never game test counts by splitting assertions, duplicating nearly identical tests or deleting implementations. Every named critical journey must pass end to end with independent evidence even if 100% of statements were executed.

**Illustrative commands** (adapt to installed Python/Windows and existing runner, do not execute simultaneously with active user data):

```powershell
# Set isolation before running; activate repository venv as needed.
$env:PHDLAB_DATA_DIR = (Join-Path $env:TEMP "phdlab-live-e2e-isolated")
.\.venv\Scripts\python.exe -m coverage erase
.\.venv\Scripts\python.exe -m coverage run --branch --parallel-mode --source=backend -m unittest discover -s tests -p "test_*.py"
# Run LIVE profiles under coverage as separate collected processes as implemented by live_quality_gate.py.
# No commands in this sample imply the live test runner already exists!
.\.venv\Scripts\python.exe -m coverage combine
.\.venv\Scripts\python.exe -m coverage json -o qa\live_e2e\coverage.json
.\.venv\Scripts\python.exe -m coverage report -m --fail-under=100
```

Do not simply add `--fail-under=100` on a partial suite and declare this request satisfied. Explicit test runner must combine **full** backend scope, subprocess coverage and coverage scope inventory. If tests/coverage runner exits nonzero, record `FAIL` with full logs and fix root causes.

---

## 13. Release Quality Gates: non-negotiable PASS conditions

| Gate | Definition of PASS | On missing prerequisite |
|---|---|---|
| G00 source/isolation | Git SHA, test-only data root, no production file mutation verified | FAIL/BLOCKED |
| G01 deterministic regression | all existing tests including v6 historical/current verifiers pass; no hidden skip | FAIL |
| G02 real Phi-4 | 10/10 LOC cases pass through real local server/app adapter and DB | BLOCKED if Phi-4/server unavailable |
| G03 standalone app | all applicable ST critical journeys pass across HTTP+persisted data, not only model direct calls | FAIL/BLOCKED |
| G04 real mission paths | single/fixed/adaptive/multi modes + real reasoning, DAG, approvals, human review, evidence | FAIL/BLOCKED |
| G05 provider registry | every configured/advertised adapter has health/contract/error truthfulness; no fake READY | FAIL |
| G06 live CLI | every explicitly required available subscribed CLI has actual authenticated invocation and process evidence | BLOCKED if no installed/authenticated CLI |
| G07 MCP two-way | actual server + actual client/tool transport, grants, failures, bounded inference through Phi-4 | FAIL/BLOCKED |
| G08 live cloud | every user-authorized target API has authenticated response; spend limits honored | BLOCKED (not optional PASS) when unapproved/unavailable |
| G09 research engines | actual Feynman/OpenScience runtime calls if required and installed; honest capability/state | BLOCKED for missing provider |
| G10 failure/recovery | all P0 fault cases pass without duplicate side effects or scientific promotion | FAIL |
| G11 scientific integrity | independent raw-archive recomputation and claim/evidence verifier pass | FAIL |
| G12 UI-full-stack | critical browser→backend→real Phi-4/MCP/CLI→artifact journeys pass with traces | FAIL/BLOCKED |
| G13 resource/soak | no leaked subprocess/temporary resources; bounded performance and recovery | FAIL |
| G14 full-backend coverage | 100.00% **statement/line and branch**, zero missing executable lines and arcs on approved honest scope | FAIL unless genuinely achieved |
| G15 frontend coverage | 100% declared frontend automated coverage target (lines/branches/functions/statements) + 100% critical browser journeys; report unavailable instrumentation as BLOCKED | FAIL/BLOCKED |
| G16 security | no unresolved critical/high exploitable issues, no unauthorized paid fallback or secret leakage | FAIL |
| G17 mutation tests | ≥95% score in P0 modules + no surviving critical authorization/idempotency mutation | FAIL |
| G18 evidence and CI | complete machine-readable logs/screenshots/call provenance; regression wired into local/CI appropriate lanes | FAIL |

**Separate release policies:**
- `LOCAL_OFFLINE_RELEASE`: G00–G05, G07 (local MCP), G10–G18 where applicable; cloud/CLI/external integrations are correctly reported **NOT_TESTED/BLOCKED**, not claimed verified.
- `FULL_PROVIDER_RELEASE`: all G00–G18 and ALL explicitly required connected providers live-tested. Missing API key/login/service gives **BLOCKED**; no fabricated bypass.
- Distinguish **local release pass** from **full coverage goal pass** if overall 100% is still pending. A `CONDITIONAL` recommendation may be made for internal development only; no blanket `production-ready` claim.

---

## 14. Regression automation, test data and CI

- Build a **small/fast** local non-paid gate (`unit+contract+focused replay`, PR), a **medium** real Phi-4/nightly or developer-triggered lane (`local`), **manual authorized** live CLI/cloud gates (never automatic spending), and **pre-release** full gate including two-way MCP, chaos/recovery, Playwright, coverage aggregation and scientific verifier.
- Avoid scheduled automatic local inference if Ollama isn't running or the user has an active workload; record BLOCKED and do not wake/pull GPU models silently. No tests auto-login to paid CLI/cloud.
- Freeze tiny datasets/artifacts to test repo only if licensed and privacy-safe; store large binary/regression outputs as build artifacts. Generated fixtures are clearly marked and verified by SHA.
- Track all reported defects with `P0/P1/P2`, reproduction command, baseline commit, observed vs expected, root cause, fix commit, new regression ID, risk/owner/status. Write a regression test that fails before and passes after each fix where feasible.
- Pin tool versions and maintain OS-specific runs (at least Windows 11 dev environment, Linux CI for pure Python). If an OS lacks a required binary, show blocked evidence rather than turning off the relevant test silently.
- Work incrementally: new test framework must not destabilize the original app or use unbounded model tokens. Employ bounded live local inference budgets per test, profile budgets and cleanup guarantees.

---

## 15. REQUIRED DELIVERABLES AND MINIMUM EVIDENCE

Produce real artifacts in `qa/live_e2e/runs/<timestamp>-<commit>/`:

1. `ENVIRONMENT_AND_PREFLIGHT.json` — git SHA, machine/OS, versions, model digest, real service health, resource caps, authorization.
2. `FEATURE_TO_JOURNEY_MATRIX.csv` — complete app features vs UI/API/provider/harness coverage IDs and unresolved holes.
3. `PROVIDER_INVENTORY.csv` — actual registered provider IDs, transport, health, capabilities, auth and live status; no secrets.
4. `MATRIX_RESULTS.json` — every case ID with `PASS/FAIL/BLOCKED`, execution start/end, mode, actual calls, evidence paths, no skip-count inflation.
5. `LLM_CALLS_REDACTED.jsonl` — hashed prompt/response IDs, role, model, provider, endpoint hostname, outcome, latency, tokens if known; never log secret contents.
6. `HARNESS_STATES.jsonl` — real mission IDs, event sequence, task ownership/workstream handoffs, crash/recovery checkpoints and approvals.
7. `MCP_CONFORMANCE.md` / `CLI_PROVIDER_RESULTS.md` / `CLOUD_PROVIDER_RESULTS.md` — actual handshake/request metadata and independent tool output.
8. `BROWSER_E2E/` — Playwright tests plus screenshots/trace and relevant console/network failures.
9. `SCIENTIFIC_REPRODUCIBILITY/` — raw arrays, hashes, scripts, independent numerical rechecks, failure-case output.
10. `coverage.xml`, `coverage.json`, `coverage.html/`, `MISSING_LINES_AND_BRANCHES.csv` and `COVERAGE_EXCLUSIONS.md`. Coverage scope and exclusions must be inspectable.
11. `MUTATION_REPORT.md`, `SECURITY_FINDINGS.md`, `BUG_LEDGER.md`, `FAILURE_ANALYSIS.md`.
12. `RELEASE_DECISION.md`: gate-by-gate signed-off summary with actual numbers, 100% target progress, exact blockers, NOT TESTED declarations, recommended next steps.
13. `tools/live_quality_gate.py` and runnable tests committed on a clean feature branch, alongside documented usage and optional CI workflows. Preserve original historical harness tests.

For **every** claimed PASS, append a verifiable `evidence_id`: command used + exit code + process ID/HTTP request or CLI event identifier + stored persisted effect + trace/log path + source SHA + independent assertion. Provider health/online alone is **never** a full live test pass.

---

## 16. EXECUTION ORDER — complete the job, not only a design report

**Phase 0 — Inventory and protect data.** Read current tree; enumerate all providers, API routes, agent roles, feature flags, saved tests; create branch, test-only data root and backup hashes. Build matrix and baseline report.

**Phase 1 — Deterministic baseline.** Run existing unit/regression/historical harness accurately and capture failed tests/environment blockers. Repair root defects only after reproduction. Do not silently lower coverage scope.

**Phase 2 — Live-local real Phi-4.** Discover Ollama/LM Studio and installed model, configure isolated test instance, verify direct inference, then *real* PhDLab APIs, chat, memory and actual mission `paper.compare`; prove observed real inference and zero cloud egress.

**Phase 3 — Full PhD-Lab-only workflows.** Run ST-01..ST-16 and verify files/DB/source/claims with independently checked oracles.

**Phase 4 — Full mission multi-branch.** Run single/fixed/adaptive/multi workstreams, governance, evidence handoffs, disputes, revision conflicts and restart through separate OS processes. Include at least one real model call in each supported branch class that can use `app`.

**Phase 5 — MCP in two directions.** Test real PhDLab MCP server (HTTP/stdio), and real Phi-4-backed MCP inference server as test target; run official MCP conformance/inspector where applicable.

**Phase 6 — CLI/cloud/external opt-in.** Detect installed & logged-in services first. Execute approved live provider contracts within caps; if absent, mark BLOCKED with exact actions needed. Do not delay the local program indefinitely waiting for a cloud credential.

**Phase 7 — Browser full stack and concurrency.** Test actual shipped frontend route→backend→model→artifact→review; inspect browser and API parity, duplicate actions/races and SSE.

**Phase 8 — Chaos/security/science.** Run test-owned process crash/recovery, OWASP agent risks, checksum tampering and raw-metric independent verifier.

**Phase 9 — Coverage closure.** Merge run coverage; identify every missing line/branch, implement behavior tests and production fixes where justified. Track the **100% line and branch target** honestly; full exit gate remains failing until achieved. Add mutation/security checks.

**Phase 10 — Final independent rerun.** Clean room isolated test directory, execute complete authorized regression set from clean checkout/branch, record environment, hash evidence, compare to baseline, generate deliverables. Only mark PASS with actual artifacts.

**DO NOT STOP at writing code or test specs.** Execute every non-paid test feasible on this machine now. When an integration requires outside services, annotate with exact missing binary/version/login/key/permission. Continue other tests; report PARTIAL+BLOCKED honestly. Never claim background autonomous execution after the active task ends.

---

## 17. Example real acceptance scenario: evidence-rich 2-workstream mission with Phi-4

Create a test-owned Topic called `E2E-Gaussian-Denoising-Phi4`. Supply (1) synthetic source records with deterministic claims and one fabricated DOI, (2) small grayscale arrays with fixed noise seeds, (3) a safe Python denoising baseline and approved protocol, (4) a research objective that requires discussing a real measured metric. Build a `MissionSpec` consistent with the *actual current Pydantic contracts* (do not paste invalid schema blindly).

- **Workstream A — evidence/analysis:** `paper.inspect` / `paper.compare` with `preferred_engine="app"` and mission `control.app_backend="ollama"`, Phi-4 real inference, citations constrained to synthetic source IDs; unsupported DOI must be rejected. Agent owner and independent verifier separate where supported.
- **Workstream B — reproducibility:** run the exact approved deterministic CPU experiment; output raw arrays, metrics, source SHA; independent verifier re-computes MSE/PSNR. Phi-4 narrative cannot change numerical evidence.
- **Join / final report:** evidence handoff digest/receiver, ack, final `mission.report` pending human review. Reviewer agent critiques claims; one deliberately invalid scientific assertion yields a dispute; only approved human resolution allows final reviewed state.
- **Fault variant:** kill the test app after A handoff but before B completes; restart from same test DB and prove A handoff not duplicated and B not ghost-complete.
- **Provider variant:** for a permitted CLI test, ask a real signed-in coding agent to *read* the test-only baseline program and return a review artifact; the core experiment remains controlled by PhDLab. For MCP, invoke one read-only PhDLab research tool with scoped grant and capture result. Do not auto-promote model-generated assertions.

**Required PASS evidence**: actual Phi-4 HTTP request and model ID, durable project/mission/task IDs, approved plan digest, one real model-generated text output with bounded length, deterministic experiment's real OS process and raw arrays, independent numeric recomputation, handoff/receipt hashes, reviewer status/limitations, all UI/API state alignment, and a verified no-paid-egress audit.

---

## 18. FINAL RESPONSE TEMPLATE (Vietnamese)

At the end, provide a factual table with **executed vs required**:

| Category | Passed | Failed | Blocked | Not run | Evidence |
|---|---:|---:|---:|---:|---|
| Existing regression |  |  |  |  |  |
| Real Phi-4 app calls |  |  |  |  |  |
| Standalone PhDLab E2E |  |  |  |  |  |
| Mission/team/workstream live |  |  |  |  |  |
| CLI providers actual |  |  |  |  |  |
| Cloud APIs actual |  |  |  |  |  |
| MCP server + client actual |  |  |  |  |  |
| Browser full-stack |  |  |  |  |  |
| Chaos + scientific verification |  |  |  |  |  |
| Total backend **line / branch** | measured %, missing line count | missing branch count | scope/exclusion notes |  |  |
| Frontend statement / branch / functions | measured %, actual scope |  |  |  |  |
| P0 mutation score | measured % |  |  |  |  |

Then list (i) the 10 most serious reproduced bugs, (ii) actual provider connectivity matrix, (iii) code/branch changes and test files created, (iv) commands to rerun locally, (v) exact reasons gates did not meet 100% if applicable, and (vi) an explicit `LOCAL_OFFLINE_RELEASE` and `FULL_PROVIDER_RELEASE` decision with the relevant gate statuses.

**Definition of complete:** A comprehensive, repeatable, independently evidenced live E2E and regression program exists and has actually run wherever machine capabilities/approvals permit; uncovered areas and 100% coverage gaps are transparent; no model, mock, skipped test or optimistic narrative is used to substitute for true verification.

---

## 19. References / version-aware notes

The standards and tools mentioned are current references to **consult**, and their exact features or CLI flags may evolve. Pin compatible versions rather than relying on old copied commands. In particular, official MCP conformance coverage is changing; do not treat passing Inspector as comprehensive security validation. Phi-4 on Ollama is a text model; native structured tool-call compliance must be demonstrated on the installed runtime before claiming it. `coverage.py` combines measured execution paths but does not independently certify functional correctness. Source reference files:

- https://www.iso.org/standard/78176.html
- https://www.iso.org/standard/79430.html
- https://www.iso.org/obp/ui/#iso:std:iso-iec:ts:42119:-2:ed-1:v1:en
- https://www.nist.gov/itl/ai-risk-management-framework
- https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- https://github.com/modelcontextprotocol/conformance
- https://github.com/modelcontextprotocol/inspector
- https://ollama.com/library/phi4
- https://lmstudio.ai/docs/developer/openai-compat/tools
- https://opentelemetry.io/docs/specs/semconv/gen-ai/
- https://coverage.readthedocs.io/
- https://playwright.dev/

**START NOW. Read this entire file, audit the current source, create an isolated feature branch and execute Phases 0–5 immediately where available. Advance through remaining phases with explicit user authorization for paid/external providers. Only declare 100% coverage when an independently inspectable complete measured scope has zero missing executable lines and branches, all mandated E2E tests have truly passed, and there are no unreported blockers.**
