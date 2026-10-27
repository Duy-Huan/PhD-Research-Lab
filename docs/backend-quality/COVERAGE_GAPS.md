# Coverage gaps — 2026-10-24

The user's required release target is 100% across the whole declared production scope. It has not been achieved.

- Full backend source/branch measurements: [full run](../../artifacts/autonomy-qa/final-backend/coverage.json) and [same-source full + supplemental case](../../artifacts/autonomy-qa/release-combined-coverage.json).
- Missing lines/branches per module: [sorted gap inventory](../../artifacts/autonomy-qa/coverage-gaps.json).
- Whole React TS/TSX source, including untested startup: [frontend coverage summary](../../artifacts/autonomy-qa/frontend-coverage-summary.json).
- New policy/scheduler and new UI/plan builder coverage are reported separately in [audit-summary](../../artifacts/autonomy-qa/audit-summary.json); their 100% result is not a global percentage.
- All OpenAPI operations are inventoried in [api-journey-inventory.csv](../../artifacts/autonomy-qa/api-journey-inventory.csv). An operation's existence is not proof of a fully tested production journey.

The pre-existing omission of `backend/execution/clearml_worker.py` was removed. Standard main-guard exclusions remain visible in the coverage JSON. Subprocess instrumentation, browser WebGL behavior, CSS visual checks, live external providers and Windows/Linux execution are distinct qualification dimensions; code coverage cannot replace them.

See the [honest release assessment](../testing/autonomy-report.md) for skipped tests, historical failure evidence and scientific limitations.
