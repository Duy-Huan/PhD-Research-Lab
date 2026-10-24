# Feature contract authoring template

Create `docs/qa/contracts/FQC-<ID>.json`; use the current examples for machine shape. Fill expected behavior before implementation; a DRAFT or empty field must not pass the validator.

| Field | Required content |
|---|---|
| id, title, user_story | Stable feature ID, concrete actor, trigger and resulting behavior |
| requirements | Unique FR IDs and descriptions; every ID traced to executable tests |
| nonfunctional | Measurable quality expectations, resource/security/accessibility constraints |
| inputs / outputs | Valid/invalid classes, schemas and persisted artifacts |
| preconditions / postconditions | Required state and guaranteed state after success/failure |
| dependencies / affected_modules | Actual services, code paths, public contracts and impact boundaries |
| risk / mode | LOW/MEDIUM/HIGH/CRITICAL and MOCKED/REAL_LOCAL/REAL_INTEGRATION/LIVE_PROVIDER |
| acceptance_criteria | Observable outcomes, error/recovery behavior and pass/fail oracle |
| scenarios | ID, requirement ID, positive/negative/boundary/failure; HIGH/CRITICAL also security/performance; executable `tests/file.py::Class.method` |
| recovery | Cancellation, retry, partial completion, rollback and three-repair stopping rule |
| test_environment | Disposable app/browser/database, fixtures, provider authorization and platform |
| skill_sources | GitHub search/selection decision, pinned installed skill paths, license/provenance |
| review | REVIEWED only after an actual review; identify same-agent versus independent/human |
| tdd | Actual RED/GREEN report paths, SHA-256 digests, process exit codes and precise scope |
| browser acceptance | Affected routes, persona/journey IDs, deterministic tests, exploratory requirement by risk, evidence and independent-review needs |

For test design consider equivalence classes, boundaries, decision tables, state transitions, properties, fault injection, API contracts, persistence, concurrency and real E2E. Select techniques that can expose a specific wrong behavior. Do not generate a passing test stub or claim 100% feature coverage from a row inventory.

After execution export the matrix with `python scripts/generate_test_matrix.py --contract docs/qa/contracts/FQC-<ID>.json --report output/playwright/<run>/report.json`. Missing or source-stale evidence stays UNVERIFIED.

Use the machine field `browser_acceptance` for browser requirements, for example:

```json
{"browser_acceptance":{"required":true,"journeys":["settings-language"],"independent_review":true,"applies_to":["frontend/src/features/settings/**"]}}
```

The five-persona catalog and actual adapter support are in `devtools/verification/uat_config.json`. Unchanged contracts still apply to changes in their `affected_modules`. `applies_to` limits exploration to actual browser-impacting paths, so a docs-only edit does not blindly call an LLM. Add unknown/missing journeys before claiming acceptance. Never set `required:false` to bypass high-risk inferred requirements.
