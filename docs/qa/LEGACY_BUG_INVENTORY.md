# Legacy defects and recovery accounting

Canonical machine inventory: [KNOWN_ISSUES_BASELINE.json](KNOWN_ISSUES_BASELINE.json). Existing UI defects and uncertain latency observation remain in [defects.json](defects.json). Baseline entries are accounting, not exceptions; all original mandatory checks still enforce their failures.

| ID | Priority | Established state | Next owner action |
| --- | --- | --- | --- |
| LEGACY-PY311-001 | P1 | Clean dev6725975 SyntaxError; repair present only in unmerged dependency | Maintainer: retain syntax repair through required dev CI |
| CI-REPORT-001 | P2 | Governance-introduced classification error; local functional fix verified | Recovery SDET: fresh independent PR checks |
| CI-COVERAGE-BE-001 | P1 qualification | Coverage below100%, no assertion failures in observed hosted run | Test owners: meaningful uncovered-module tests |
| CI-COVERAGE-FE-001 | P1 qualification |174 passing assertions, whole-source thresholds unmet | Frontend owners: component/state/error-path coverage |
| CI-UAT-001 | P1 infrastructure | Missing matching-source execution; existing3-attempt model budget exhausted | Maintainer: reviewed adapter/producer work without budget reset |
| CI-LIVE-001 | P1 infrastructure | Five exact SDK/live cases skipped on all inspected hosted matrix jobs | Maintainer: audited SDKs and isolated authorized services |
| CI-POLICY-IDENTITY-001 | P2 infrastructure | Initial local policy input omission caught before publication; fixed | Recovery SDET: retain permanent identity regression |

Each machine record includes evidence hashes, exact observed baseline, reproduction, expected/actual, owner, remediation and review date2026-11-01. That date is a remediation review target, not a waiver deadline or permission to merge. No security/data-loss/research-integrity exception exists. No pre-existing application assertion failure has been bisected beyond the explicitly proven Python3.11 compatibility failure. Broad coverage deficits do not prove particular application behavior is broken.

New regressions always fail the unchanged mandatory suites. No baseline allowlist is passed to test selection or result aggregation. The baseline validator rejects any nonempty exception collection, including self-asserted approval. Any future owner-approved noncritical exception requires a separate narrow design and exact test/SHA/evidence/expiry enforcement; it is not implemented implicitly here.
