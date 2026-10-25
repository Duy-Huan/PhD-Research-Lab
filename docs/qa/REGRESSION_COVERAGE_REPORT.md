# Regression and coverage ? 6.5.9

Local snapshot before6.5.9 publication. Source `568d68f5c218f4ccdfa941de160621e79e5a6794309ffaaf14b68d179e76b3c3`, stable. Baseline HEADb3080ab0f89715b207c7e2004d84968954eef5e5. Actual publication and independent CI must be matched by exact latest GitHub HEAD; durable remote receipts are in shared.git/ci-observations/6.5.9-dev/. This local report does not presume a future GitHub result.

Mandatory selected software regression1198/1198PASS. Source coverage is informational; desired100% line/branch and intermediate>95% are not achieved.

| Production scope | Covered / total | Measured |
|---|---|---|
| Backend lines |23949/26570 |90.14% |
| Backend branches |7151/8820 |81.08% |
| Backend combined |Measured by coverage.py |87.88% |
| Frontend lines |2521/3821 |65.97% |
| Frontend branches |2679/4126 |64.92% |
| Frontend functions |754/1467 |51.39% |

Missing lines/branches are coverage gaps, not automatically bugs, skipped cases or PASS. Raw per-file missing-line/branch data: output/playwright/hermes-core-audit/runtime-cleanup-659-final/backend/coverage.json and frontend/coverage/. Prioritize behavioral/failure cases in CLI, system APIs, missions/runs, research execution and other uncovered modules; never exclude active code simply to raise the number. Historical failed cases and infrastructure reasons are retained in the checkpoint/defect registry. [Measured execution](AGENT_NATIVE_CORE_CHECKPOINT_6.5.9.md).
