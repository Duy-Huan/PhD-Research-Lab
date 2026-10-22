# Measured local research harness

Synthetic literature/workspace fixtures; actual local code and CPU workers. These serial samples do not establish a productivity or scientific quality advantage.

| Workflow | Mode | Domains | Logical roles | Wall seconds | Task executions | Technical completion |
|---|---|---:|---:|---:|---:|---|
| Literature inspection | single | 1 | 1 | 0.216 | 2 | True |
| Literature inspection | fixed | 1 | 2 | 0.195 | 2 | True |
| Literature inspection | adaptive | 1 | 1 | 0.199 | 2 | True |
| Federated artifact reconciliation | single | 1 | 1 | 0.311 | 3 | True |
| Federated artifact reconciliation | fixed | 1 | 2 | 0.295 | 3 | True |
| Federated artifact reconciliation | adaptive | 1 | 1 | 0.316 | 3 | True |
| CPU reproducibility 1 | single | 1 | 2 | 1.169 | 3 | True |
| CPU reproducibility 2 | single | 1 | 2 | 1.228 | 3 | True |
| CPU reproducibility 1 | fixed | 1 | 3 | 1.211 | 3 | True |
| CPU reproducibility 2 | fixed | 1 | 3 | 1.163 | 3 | True |
| CPU reproducibility 1 | adaptive | 1 | 2 | 1.229 | 3 | True |
| CPU reproducibility 2 | adaptive | 1 | 2 | 1.076 | 3 | True |

Provider tokens/currency are unknown; GPU time is zero. Simulated review actions and retries are recorded per row in harness.json. Raw artifact hashes, ZIP integrity and the original merged audit chain were checked after packaging.