# Test case matrix

| TestCaseID | Requirement | Preconditions | Steps | Input | ExpectedResult | Priority | TestLevel | Automation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|

Generate populated CSV from a reviewed contract using `scripts/generate_test_matrix.py`. The generator links actual test IDs and matching-source execution reports. Without execution it emits UNVERIFIED, never PASS. Preserve negative/boundary/failure cases and evidence of initial failures; a completed table is not a completeness proof.
