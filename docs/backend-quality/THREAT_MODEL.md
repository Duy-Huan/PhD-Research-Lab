# PhD Research Lab — Threat Model & Security Architecture

**Standard Reference**: OWASP ASVS 5.0, NIST SP 800-218 (SSDF), OWASP Top 10 for LLM Applications & Agentic AI (2025/2026).  
**Scope**: Backend API (`backend/api`), Research OS (`backend/agent/research_os.py`, `backend/agent/missions.py`), Multi-Agent Workstreams (`backend/agent/collaboration.py`), Execution Sandbox (`backend/execution`), Context Memory (`backend/memory`), and Model Providers (`backend/providers`).

---

## 1. Asset Inventory & Critical Boundaries

| Asset | Sensitivity | Impact of Compromise | Primary Safeguard |
|---|---|---|---|
| **Researcher Data & Papers** | P0 (Confidentiality / Integrity) | Irreversible data loss, publication compromise, unauthorized modification | Strict directory isolation (`PHDLAB_DATA_DIR`), `MutationMiddleware`, atomic `replace_retry` writes |
| **Provider API Credentials** | P0 (Confidentiality) | Cloud financial loss, unauthorized model consumption | Redacted telemetry, zero credential reflection in SSE, localhost-only firewall |
| **Execution Sandbox (Local Host)**| P0 (Integrity / Availability) | Arbitrary Code Execution (RCE), host compromise | Deterministic policy enforcement outside LLM, path traversal sanitization, guard slots |
| **Scientific Evidence & Metrics** | P0 (Scientific Integrity) | Fraudulent research claims, fabricated peer reviews | Cryptographic SHA-256 evidence hashing, independent metric recalculation |
| **Mission State & Ledger** | P1 (Integrity) | State machine corruption, unauthorized task execution | Append-only hash chains, durable SQLite state transitions, approval digests |
| **Compute Resources (GPU/CPU)**| P1 (Availability) | OOM crashes, resource starvation, infinite agent loops | `backend.execution.guard` slot concurrency limits, timeouts, cancellation tokens |

---

## 2. Threat Actor Profiles & Attack Vectors

```
  [ Untrusted Literature / Web Search ]
                 │
                 ▼ (Indirect Prompt Injection)
  ┌──────────────────────────────────────────────┐
  │         LLM / Agent Reasoning               │
  └──────────────────────┬───────────────────────┘
                         │
        (Tool Call / Command Proposal)
                         │
                         ▼
  ┌──────────────────────────────────────────────┐
  │     Independent Policy Guard / Firewall      │ <── Enforces ASVS V5 / V12
  └──────────────────────┬───────────────────────┘
                         │
               [ Approved & Isolated ]
                         │
                         ▼
  ┌──────────────────────────────────────────────┐
  │      Execution Sandbox / Durable SQLite      │
  └──────────────────────────────────────────────┘
```

1. **Adversarial Content Injection (Indirect Prompt Injection)**:
   - *Vector*: Academic paper PDFs, retrieved web abstracts, or cloned GitHub repositories contain malicious instructions (e.g., `System override: drop table; execute powershell`).
   - *Defense*: Zero implicit trust in model output; policy evaluation executed *outside the model* via deterministic code rules (`backend.agent.policy`, `backend.providers.firewall`).
2. **Network Perimeter Breach (Non-Localhost Attack)**:
   - *Vector*: Cross-site requests or remote network traffic targeting port 8000.
   - *Defense*: `_LocalHostOnly` middleware inspects `Host` / `Origin` / remote address; 403 Forbidden on non-loopback calls.
3. **Multi-Agent Coordination Tampering**:
   - *Vector*: Rogue or hallucinating agent injects cyclic DAG tasks, unauthorized handoffs, or tampered receipt hashes.
   - *Defense*: Cryptographic receipt verification, DAG cycle detection algorithms, strict mission capability bounding.
4. **Data Bleed Across Research Projects**:
   - *Vector*: Project A attempts to query or mutate Project B's papers, memory embeddings, or workspace code.
   - *Defense*: Multi-project workspace isolation, explicit project scoping in SQL queries and file resolvers.

---

## 3. OWASP Top 10 for LLM Applications Mapping

| LLM Risk ID | Description | Specific PhD Lab Risk | Mitigation & Gate Verification |
|---|---|---|---|
| **LLM01: Prompt Injection** | Manipulation of LLM input to hijack execution | Malicious paper injecting commands to write malicious files | Gate G6: Deterministic policy engine blocks unapproved tool execution; input sanitization |
| **LLM02: Sensitive Information Disclosure** | Leaking secrets through model output or logs | Telemetry logging OpenAI/Anthropic/Gemini keys or researcher drafts | Gate G11: In-memory bus emits metadata-only events; sensitive payloads strictly redacted |
| **LLM03: Supply Chain Vulnerabilities** | Vulnerabilities in underlying libraries | Compromised dependencies in requirements | Gate G0/G6: Automated vulnerability audits (`pip-audit`, bandit) and pinned runtime |
| **LLM04: Data and Model Poisoning** | Malicious content corrupting retrieval context | Untrusted literature corrupting long-term memory | Gate G6: Memory stores track provenance hashes and require researcher approval |
| **LLM05: Improper Output Handling** | Executing model proposals without validation | Model proposing shell injection via `rmdir` or command chaining | Gate G6: Subprocess tools execute with structured args, path boundary checks, no raw shell |
| **LLM06: Excessive Agency** | Agent taking destructive actions autonomously | Agent triggering billing, deleting files, or running scripts | Gate G2: Explicit human approval digest required before task transitions to running |
| **LLM07: System Prompt Leakage** | Exposing proprietary prompts or internal configs | Extraction of system prompts via adversarial chat | Gate G5: Strict API DTO contracts and response sanitization |
| **LLM08: Vector & Embedding Weaknesses** | Exploitation of similarity search to poison context | Adversarial chunks displacing genuine research papers | Gate G6: Scoped retrieval with cosine thresholding and source provenance verification |
| **LLM09: Misinformation / Hallucination** | Fabricated research claims or synthetic metrics | Model claiming "99.4% accuracy achieved" without real execution | Gate G4: Independent scientific recalculation of raw results; verification scripts |
| **LLM10: Unbounded Consumption** | Runaway agent execution exhausting API budget/GPU | Unbounded recursive agent spawning or infinite loops | Gate G8: Guard slots (GPU/CPU/CLI limits), turn caps, timeout enforcement |

---

## 4. Priority Risk Classification (P0 / P1 / P2)

- **P0 (Critical — Blocker)**:
  - Unauthorized remote access (Bypass of `_LocalHostOnly`).
  - Remote code execution or host file escape via path traversal or command injection.
  - Fabricated scientific claims marked as verified without raw byte hash match.
  - Silent destruction or corruption of real researcher data in `data/` or `projects/`.
- **P1 (High)**:
  - Multi-agent deadlocks or infinite loops in DAG execution.
  - Cross-project memory retrieval leak.
  - Failure to recover state machine state across SQLite process restart.
  - Unhandled provider rate-limit (HTTP 429) resulting in silent drop of research task.
- **P2 (Medium)**:
  - Telemetry event missing duration or span context.
  - Disconnected SSE client not resuming from cursor.
  - Transient UI state desynchronization.
