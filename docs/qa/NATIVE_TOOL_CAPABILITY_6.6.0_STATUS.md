# P0 Native Tool Capability System — item status (v6.6.0)

Owner checklist of 2026-10-27 (P0 — Native Tool Capability System). Status values follow
`agent/NATIVE_AI_RESEARCH_ENVIRONMENT.md`: PASS, PARTIAL, NOT IMPLEMENTED, NOT VERIFIED. "Software" evidence is
`tests/test_tool_capability_system.py` and `tests/test_google_mcp_isolation.py` (FQC-NATIVE-TOOLS-660, 47 scenarios,
RED 47 ERROR → GREEN 47 PASS); agent-loop cases there use a MOCKED scripted model. "Live" evidence is a real model run
of `tools/tool_agent_acceptance.py` and is reported separately. Software PASS is not live or scientific qualification.

## Tool Registry

| Item | Status | Evidence / gap |
|---|---|---|
| Central capability registry | PARTIAL | `backend/tools/registry.py` unifies builtin research/sandbox MCP tools, manifests, external MCP and optional Google tools. Mission capabilities in `backend/agent/capabilities.py` are not yet registry entries (6.6.1). |
| Dynamic tool discovery | PASS (software) | Registry rebuilt per query; tool installed mid-task found (`RegistryDiscovery…runtime…`, `AgentLoop…previously_unknown…`). |
| Tool metadata and schema validation | PASS (software) | `ToolSpec` + bounded JSON Schema; unsupported keywords rejected; input and output validated. |
| Capability-based tool search | PASS (software) | BM25-style ranking with capability/kind/permission filters. Lexical, not semantic embedding search. |
| Runtime tool availability detection | PASS (software) | Cached adapter probes; unavailable tools listed with reason. |
| Lazy loading of tool specifications | PASS (software) | Listing returns summaries; full schemas only via `describe`. Manifests are still read on each listing (small files). |
| Tool versioning and compatibility | PASS (software) | Semver, constraints, active pointer, `requires_app`. |

## Agent Tool Autonomy

| Item | Status | Evidence / gap |
|---|---|---|
| Model-driven tool selection | PASS (software); live PARTIAL | Loop has no tool-specific logic. Live spark-x2.5-4b diagnostics selected and called the right tool; official run pending. |
| Model-driven tool chaining | PASS (software); live PARTIAL | Live diagnostic chained three measurements and cited them. |
| Dynamic multi-tool composition | PASS (software); live NOT VERIFIED | `AgentLoop…composes…`. |
| Model-driven error recovery | PASS (software); live NOT VERIFIED | Structured errors with hints fed back; truncated/empty replies become protocol observations. |
| Agent-initiated tool discovery | PASS (software); live PARTIAL | A live diagnostic searched the registry; the latest one used the starting catalog instead. |
| No hardcoded scientific tool sequences | PARTIAL | New loop and `tool_mode=agent` contain none. Legacy workflow templates/missions remain available. |
| No keyword-based tool forcing | PARTIAL | Removed for `tool_mode=agent` (verified: keyword `propose` never called). Default chat mode is still `legacy`; flipping the default is planned for 6.6.1 after test review. |

## Tool Runtime

| Item | Status | Evidence / gap |
|---|---|---|
| Unified tool execution interface | PASS (software) | `RUNTIME.submit/run/wait/events/cancel/replay` for all kinds. |
| Native tools and external adapters | PASS (software) | native, python, cli, mcp (HTTP + stdio), container. |
| Async execution and job tracking | PASS (software) | Thread-pool jobs, persisted job records. |
| Streaming execution observations | PASS (software) | stderr/status observations; `/api/tools/jobs/{id}/stream` SSE. |
| Execution timeout and cancellation | PASS (software) | Whole-process-tree kill; native handlers abandoned and reported. |
| Per-tool permissions | PASS (software) | Grant tool patterns, permissions, mutation flag, expiry. |
| Resource budget enforcement | PARTIAL | Calls, wall time and output bytes per grant/tool. Memory/CPU limits only for container tools. |
| Sandbox isolation | PARTIAL | Allowlisted env, `python -I`, no shell, private workdir; containers read-only/no-network. Defense in depth, not a certified OS sandbox; real container execution NOT VERIFIED (process boundary mocked in tests). |
| Structured errors and retry support | PASS (software) | `ToolError` codes; retry only retryable + idempotent. |
| Complete execution provenance | PASS (software) | Hash-chained provenance for every attempt incl. denials; tamper detection; replay with result digest. |

## Tool Extensibility

| Item | Status | Evidence / gap |
|---|---|---|
| Support Python and CLI tools | PASS (software) | Real subprocess tests; CLI option-injection blocked. |
| Support Docker/container execution | PARTIAL | Adapter implemented and isolation flags verified; no real container run recorded. |
| Support MCP tools | PASS (software) | External HTTP and stdio MCP; registry exposed to external agent clients via `/mcp` meta-tools. Google live compatibility NOT VERIFIED. |
| Support scientific software adapters | PARTIAL | Generic python/cli/container adapters; no dedicated adapters (e.g. MATLAB) yet. |
| Support agent runtime adapters | NOT IMPLEMENTED | CLI agents as callable registry tools are not implemented; agents instead use the registry as MCP clients. |
| Agent can propose new tools | PASS (software) | `propose_tool` action (requires `workspace_write`). |
| Agent can implement tools in sandbox | PASS (software) | Isolated proposal area; agent-written Python validates in a container, host only by owner setting. |
| Validate generated tools before promotion | PASS (software) | Examples executed; report bound to digest and to the proposer's permissions; promotion needs a named human. |
| Tool versioning and rollback | PASS (software) | Immutable versions, active pointer history, rollback. |

## Acceptance Tests

| Item | Status | Evidence / gap |
|---|---|---|
| Agent discovers previously unknown tool | PASS (software); live NOT VERIFIED | |
| Agent selects an appropriate tool without hardcoding | PASS (software); live PARTIAL | spark diagnostic selected `numerics.quadrature_error` unaided. |
| Agent combines tools for a new task | PASS (software); live NOT VERIFIED | |
| Agent recovers from tool failure | PASS (software); live NOT VERIFIED | |
| Agent switches tools when results are inadequate | PASS (software); live NOT VERIFIED | |
| Agent executes a real scientific experiment | NOT VERIFIED (official) | Pre-commit spark diagnostic executed a real convergence experiment (order 2; independent 1.997) but FAILED the pre-registered `searched_registry` check. Codex BLOCKED (quota), Antigravity wrapper BLOCKED (terms). |
| Tool calls retain authorization boundaries | PASS (software) | Grants, session allowlist, MCP bridge permissions, Drive FolderGuard. |
| All actions are traceable and reproducible | PASS (software) | Provenance chain + replay. |

## Optional Google MCP (owner request)

Google Colab (official `googlecolab/colab-mcp`, local stdio) and Google Drive (official remote
`drivemcp.googleapis.com`) are off by default and confined to `<project>/google_mcp/` with FolderGuard for Drive.
Software: 8 scenarios PASS with local fixture servers. Live compatibility with Google's servers: NOT VERIFIED (the
Colab bridge from GitHub was not executed in this session; Drive needs the owner's OAuth client).

## Gemini 3.8 Flash without violating Antigravity terms

Antigravity's FAQ forbids third-party software accessing Antigravity on consumer plans, and recommends a Gemini
Enterprise or Google AI Studio API key for third-party apps. Compliant routes: (1) Google AI Studio API key in
Settings → Providers → Google Gemini (`tool_agent_acceptance.py --provider gemini`); (2) the researcher uses Antigravity
directly as an MCP client of PhD Lab (register the MCP server), and Gemini reaches the registry through the
`phdlab_tools_*` meta-tools under PhD Lab permissions.
