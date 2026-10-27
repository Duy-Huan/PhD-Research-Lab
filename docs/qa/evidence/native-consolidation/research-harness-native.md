# Measured local research harness

Synthetic literature/workspace fixtures; actual local code and CPU workers. These serial samples do not establish a productivity or scientific quality advantage.

| Workflow | Mode | Domains | Logical roles | Wall seconds | Task executions | Technical completion |
|---|---|---:|---:|---:|---:|---|
| Literature inspection | single | 1 | 1 | 0.258 | 2 | True |
| Literature inspection | multi | 1 | 1 | 0.283 | 2 | True |
| Federated artifact reconciliation | single | 1 | 1 | 0.400 | 3 | True |
| Federated artifact reconciliation | multi | 3 | 1 | 0.412 | 3 | True |
| CPU reproducibility 1 | single | 1 | 3 | 1.452 | 4 | True |
| CPU reproducibility 2 | single | 1 | 3 | 1.579 | 4 | True |
| CPU reproducibility 1 | multi | 4 | 3 | 1.607 | 4 | True |
| CPU reproducibility 2 | multi | 4 | 3 | 1.592 | 4 | True |

Provider tokens/currency are unknown; GPU time is zero. Simulated review actions and retries are recorded per row in harness.json. Raw artifact hashes, ZIP integrity and the original merged audit chain were checked after packaging.