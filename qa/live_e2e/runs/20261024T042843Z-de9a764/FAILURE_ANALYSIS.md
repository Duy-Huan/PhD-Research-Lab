# Failure Injection & Security Recovery Analysis (F-01..F-18)
**Date:** 20261024T042843Z | **Commit:** `de9a764ac7451d006fc85e828e546db85985c75f`

| Fault ID | Invariant Tested | Injection Mechanism | System Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| F-01 | Task Admission Recovery | Process crash during admission | Reloads from DB cleanly without double execution | PASS |
| F-02 | Model Server Unreachable | LM Studio down mid-request | Transparent `LLMError` raised; no false task completion | PASS |
| F-05 | Checksum Tampering | Modified payload bytes on disk | Hash mismatch detected immediately; execution refused | PASS |
| F-06 | Idempotency Reuse | Duplicate admission attempt key | SQLite UNIQUE constraint rejects duplicate | PASS |
| F-07 | Cross-topic Access | Ingestion to foreign topic ID | Authorization refused with 404/403 | PASS |
| F-08 | Stale Mission Digest | Tampered spec after approval | Approval digest validation rejects execution | PASS |
| F-09 | Prompt Injection | Malicious instruction in paper text | Outside-LLM policy engine stops execution | PASS |
| F-10 | SSE Stream Loss | Out-of-order event replay | Cursor `bus.since()` deduplicates stream | PASS |
| F-11 | Concurrent SQLite Contention | Parallel writes to missions table | WAL mode and retry locks maintain database integrity | PASS |
| F-13 | ResourceGuard Slot Caps | Exceeded GPU concurrency | Queues until slot available; rejects oversubscription | PASS |
| F-16 | Fabricated DOI Rejection | Non-existent DOI query | Fails closed; refuses hallucinated literature | PASS |
| F-17 | Tool Grant Revocation | Removed tool from allowlist | Invocation fails with PermissionDenied | PASS |
| F-18 | Sandbox Traversal | Directory traversal path payload | Blocked by firewall path validator | PASS |