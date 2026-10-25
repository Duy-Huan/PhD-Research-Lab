# QA bug register

| ID | Status | Finding / remaining requirement |
|---|---|---|
| QA-001 | FIXED | Fabricated harness/visual-runtime measurements and default success |
| QA-002 | FIXED | Expected metrics copied into replay; integrity incorrectly treated as execution |
| QA-003 | FIXED | Invented library bibliographic/ranking metadata |
| QA-004 | FIXED | Deterministic workflow falsely labeled AI-generated |
| QA-005 | FIXED | Native CLI forwarding opened websites / unknown readiness default |
| QA-006 | FIXED | Completion, partial failure, stale turn and cancellation races |
| QA-007 | FIXED | Unrelated conversation injected into multi-turn context; empirical-only prompt suppressed ordinary reasoning |
| QA-008 | FIXED | Placeholder PNG/PDF exports independent of scientific data; legacy versions could be approved |
| QA-009 | FIXED | Per-record clock sampling destabilized equal-timestamp temporal retrieval |
| QA-010 | OPEN | Backend/frontend production coverage below 100%; seven backend skips |
| QA-011 | BLOCKED | Missing auth/API keys/services and exhausted Claude quota |
| QA-012 | OPEN | Complete workflow adapters, viewport/control inventory and native window qualification |
| QA-013 | OPEN | Full context/memory/router/policy consolidation and complete EN/VI parity |
| QA-014 | UNVERIFIED | Cause of two model-unloaded live requests; sustained provider reliability |
| QA-015 | OPEN | Remote Windows/Linux CI and independent scientific review |

Exact per-attempt assertions and failures are in the [case CSV](evidence/2026-10-25/all-case-results.csv). FIXED means a specific mechanism was repaired and its regression executed; it does not imply complete qualification of the surrounding subsystem.
