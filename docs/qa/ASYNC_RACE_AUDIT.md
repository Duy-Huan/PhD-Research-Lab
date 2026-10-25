# Async and cancellation audit

Confirmed defects repaired in `backend/agent/orchestrator.py`:

- Gateway completion could reconcile a still-running application worker before artifact/memory/retention writes finished. Active worker ownership is now respected and terminal state follows postprocessing.
- Failed gateway requests carrying partial text could become completed. Their failure/cancellation provenance is preserved.
- Removing a cancellation flag before worker exit could allow later output to persist as success. The flag lives through worker termination; pending approvals are cancelled.
- A stale running turn without a live worker could block subsequent input. It is reconciled explicitly.
- Optional overrides could be `None` in buffered MCP cancellation. Callers now handle this case.

Behavior oracles are in `test_intelligence_preservation`, `test_orchestrator` and the existing MCP/gateway suites. The local full gate covers offline races; selected browser/CLI runs validate final saved turns. Exhaustive stress, shutdown/restart and every remote transport race remain open.

Two frontend waits timed out under unconstrained worker load. The bounded two-worker full run passed all assertions. Both outcomes remain recorded; this does not establish that no future timing issue exists.
