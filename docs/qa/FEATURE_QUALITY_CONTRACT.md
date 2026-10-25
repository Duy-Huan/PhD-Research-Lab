# Feature Quality Contract

The authoritative machine format is the reviewed JSON in [contracts/](contracts/); the validator is `devtools/verification/contracts.py`. The authoring template is [templates/FEATURE_CONTRACT.md](templates/FEATURE_CONTRACT.md) and execution policy is [FEATURE_TEST_STANDARD.md](FEATURE_TEST_STANDARD.md). Do not create a separate competing gate framework.

The current examples are FQC-DEV-001 (selection, fingerprints, fail-closed gates and repair budget) and FQC-UAT-001 (isolated browser policy and evidence truth). These examples establish only their executed scope. Unimplemented scenarios, incomplete source coverage, unavailable providers and missing independent acceptance remain blockers.

Every new feature must search/select/install relevant pinned GitHub skills before implementation, review acceptance criteria, execute behavioral RED/GREEN and update requirement-to-test-to-evidence links. A PR body references `Contract: FQC-<ID>`. Subjective AI UX scores do not replace deterministic acceptance or human release authorization.
