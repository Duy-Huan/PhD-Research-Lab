# v6.2.0-preview.1

See [architecture/API/operator guide](architecture/v6.2_team_composition.md), [readiness audit](audits/v6.2_readiness.md) and `artifacts/v62/harness.json` for measured evidence. Missing v6.1 prerequisites were implemented as a compatibility layer rather than assumed complete. This is an experimental, opt-in serial team harness; external pilot, live reasoning and parallel execution gates remain open. It is not a claim of general autonomous research.

Validation: 52 backend tests OK (team/OS/mission/protocol/governance/launcher), 98 frontend tests passed, 12 measured harness Mission executions passed across three workflow families and three composition modes. One CPU run per mode was repeated with a distinct approval and actual fresh processes. Full measurements and original audit records are retained in `artifacts/v62/measurements.zip`.

Observed wall seconds (single / fixed / adaptive): literature 0.222 / 0.217 / 0.217; workspace reconciliation 0.331 / 0.317 / 0.328; first CPU run 1.190 / 1.259 / 1.256. These tiny sequential samples do not support a productivity ranking. All modes performed the same 2/3/3 technical tasks for these workflows; fixed roles added ownership partitions, not parallel compute. Provider tokens/currency remain unknown; no paid calls or GPU work occurred. Final resource-inheritance hardening was separately retested before commit.
