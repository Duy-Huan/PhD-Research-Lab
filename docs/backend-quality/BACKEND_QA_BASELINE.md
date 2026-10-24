# PhD Research Lab — Backend QA Baseline & Environment Inventory

**Version**: PhD Research Lab v6.4.2  
**Audit Standard**: ISO/IEC 25010:2023, ISO/IEC/IEEE 29119, OWASP ASVS 5.0, NIST SP 800-218 (SSDF)  
**Executed By**: Backend Quality Gate Orchestrator (`tools/backend_quality_gate.py`)

---

## 1. Environment & Runtime Baseline

| Parameter | Observed Value | Validation Status |
|---|---|---|
| **Git Commit** | `de9a764ac7451d006fc85e828e546db85985c75f` | Verified clean base |
| **Operating System** | Windows 11 Enterprise (10.0.26100) AMD64 | Host platform certified |
| **Python Version** | Python 3.14.8 (tags/v3.14.8:8e6e75d, MSC v.1944 64 bit) | Runtime verified |
| **Coverage Engine** | `coverage.py` version 7.16.2 (Branch Coverage enabled) | Branch tracking active |
| **Web Framework** | FastAPI 0.150.0 (Starlette + ASGI) | Contract parity checked |
| **Database Engine** | SQLite 3.50.4 (WAL mode, Foreign Keys ON, Trigger enforcement) | Durable transitions |
| **Storage Isolation** | Disposable `PHDLAB_DATA_DIR` in tempfile root per run | Real researcher data protected |
| **Offline Policy** | `PHDLAB_QA_OFFLINE=1`, Deny paid external API transports | Paid API calls denied |

---

## 2. API Surface & Endpoint Inventory

From `app.openapi()`, a total of **234 unique HTTP paths** and **274 operations** are served:
- **Core APIs**:
  - `/api/version`, `/api/config`, `/api/system/*`
  - `/api/models`, `/api/models/test`, `/api/models/list`, `/api/providers/*`
  - `/api/chat/*`, `/api/library/*`, `/api/paper/*`, `/api/figures/*`
  - `/api/research/topics/*`
  - `/api/research/topics/{tid}/missions/*` (State machine, approvals, ticks, handoffs, disputes, reviews)
  - `/api/research-engines/*`, `/api/opencode/*`
- **Security Middlewares**:
  - `MutationMiddleware`: In-memory metadata-only mutation events published to event bus.
  - `_LocalHostOnly`: Enforces loopback host check (HTTP 421 on foreign host) and prevents cross-origin writes (HTTP 403 on unauthorized origin).
  - `_NoStaleUI`: Cache control headers preventing browser caching of state mutations.

Complete operation mapping is saved in `docs/backend-quality/BACKEND_API_PARITY.csv` and OpenAPI JSON snapshot in `artifacts/backend-qa/openapi_snapshot.json`.

---

## 3. Subsystem Architectural Inventory

1. **Research OS & Missions (`backend/agent/missions.py`)**:
   - Durable SQLite state transitions: `draft` -> `queued` / `scheduled` -> `running` -> `completed` / `failed` / `interrupted` / `paused`.
   - Cryptographic approval digests: Required researcher approval note and plan hash before any task admission.
   - Idempotent recovery (`recover()`): Interrupted tasks marked `interrupted`, requiring manual reconciliation note before retry.
2. **Multi-Agent Teams & Workstreams (`backend/agent/collaboration.py`)**:
   - Supervised team DAG validation: Detects dependency cycles, unknown dependencies, and enforces aggregate hop/depth budgets.
   - Append-only hash chain (`decision_ledger.py`): Reconciles handoffs, disputes, and approvals. SQLite triggers prevent direct `UPDATE`/`DELETE`.
3. **Execution Sandbox & Concurrency Guard (`backend/execution/guard.py`)**:
   - Slot-level limits for GPU (1), CPU, CLI, and local LLM.
   - VRAM gate and auto-unload mechanisms prevent OOM conditions.
4. **Knowledge Store & Corpus (`backend/knowledge/`)**:
   - Multi-topic paper corpus, PDF indexers, citation graph, and normalized metadata ingest.
5. **URAP Artifact Registry (`backend/intelligence/urap.py`)**:
   - Universal Research Artifact Protocol (URAP 1.0.0).
   - Content-addressed SHA-256 validation; automatic stale marking on tamper detection.
6. **Firewall & Policy Engine (`backend/providers/firewall.py`, `backend/agent/policy.py`)**:
   - Path traversal prevention outside allowed project roots.
   - Strict tool execution boundaries enforced outside the LLM.
