# v6 harness verification

Current stages and exact historical release code, run in isolated processes with the currently installed Python/dependencies. This does not recreate historical dependency locks or certify real scientific autonomy.

| Code | Stage | Application version | Missions | CPU trials | Raw samples recomputed | Role envelopes | Cross-team receipts | Result |
|---|---|---|---:|---:|---:|---:|---:|---|
| current | 6.0 | 6.3.0-preview.1 | 4 | 10 | 240 | 0 | 0 | PASS |
| current | 6.2 | 6.3.0-preview.1 | 12 | 30 | 720 | 27 | 0 | PASS |
| current | 6.3 | 6.3.0-preview.1 | 8 | 20 | 480 | 22 | 10 | PASS |
| historical · 312e9b0 | 6.0 | 6.0.0-preview.1 | 4 | 10 | 240 | 0 | 0 | PASS with export limits |
| historical · 40e1173 | 6.2 | 6.2.0-preview.1 | 12 | 30 | 720 | 0 | 0 | PASS with export limits |
| historical · 459fc13 | 6.3 | 6.3.0-preview.1 | 8 | 20 | 480 | 0 | 10 | PASS with export limits |

Governance/resource/recovery/verifier contracts: 69 tests; failures 0, errors 0. Exact case outcomes, real process-exit evidence and each original-format limitation are in [summary.json](summary.json).

v6.1 is a tested compatibility layer, not a separately released version. GPU/Docker containment, live inference/billing and a real scientific pilot remain outside this offline qualification.
