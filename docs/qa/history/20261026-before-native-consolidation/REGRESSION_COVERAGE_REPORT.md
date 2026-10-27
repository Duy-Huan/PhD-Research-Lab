# Regression and coverage ? 6.5.9 CI repair1

Local pre-publication snapshot for CI fixture repair1/3, source `b2b35a188e3eba19323c7c9eb51bf99b993c8f1018262787f974aff8baa47ac1`, stable. Baseline HEAD2a5ee141a1d06291eb65589045f0c5a35b711526. Actual latest publication/CI must be read from GitHub and shared.git/ci-observations/6.5.9-dev/receipt.json; no future remote result is presumed.

Mandatory selected software1199/1199PASS. Target100% production line/branch is not achieved; coverage remains informational, never a waiver of failing regressions.

| Scope | Covered / total | Actual |
|---|---|---|
| Backend lines |23949/26570 |90.14% |
| Backend branches |7156/8820 |81.13% |
| Backend combined |coverage.py |87.89% |
| Frontend lines |2521/3821 |65.97% |
| Frontend branches |2679/4126 |64.92% |
| Frontend functions |754/1467 |51.39% |

Raw missing-line/branch data: output/playwright/hermes-core-audit/runtime-cleanup-659-ci-repair-1/backend/coverage.json and frontend/coverage/. Gaps are not automatically bugs or passing behavior. Add meaningful behavioral/failure tests; never exclude active code to raise coverage. Exact previous3fixture errors per CI matrix and the new absent-vendor cached-health regression are documented in [checkpoint](AGENT_NATIVE_CORE_CHECKPOINT_6.5.9.md).
