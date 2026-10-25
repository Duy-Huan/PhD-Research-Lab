# Zero fake testing and scientific evidence policy

Every result must identify execution mode, source revision/hash, command, timestamps, asserted behavior and evidence paths. Allowed outcomes are PASSED, FAILED, ERROR, BLOCKED, SKIPPED, UNAVAILABLE, UNSUPPORTED and UNVERIFIED. Simulation and mock execution are separate modes, never live evidence.

PASSED requires evaluated assertions. LIVE_PROVIDER and REAL_E2E additionally require actual execution provenance. Missing credentials, unavailable models, skipped tests and empty reports cannot become PASS. Fallback must be explicitly allowed and preserve the original failure and actual executing provider. Unknown usage/cost remains unknown.

Scientific verification requires `claim → evidence → experiment → execution → data → source revision`. Hashes prove integrity, process exit proves completion, and LLM review is advisory; none independently proves scientific correctness. Reproduction requires fresh execution and comparison to raw outputs, never copying expected metrics. Synthetic datasets and simulations must be labeled.

Regression guards must reject unknown harness success, unavailable benchmark metrics, copied replay measurements, failed-agent workflow completion, skipped-live PASS, missing-citation verification, synthetic-provider real evidence and provenance-free fallback. Inject faults only in isolated tests and preserve the failing case.

Report test counts and production source line/branch denominators separately from workflow, UI, platform, provider and scientific qualification. The owner requires 100% execution/PASS of mandatory regressions; coverage is informational without a percentage gate. The desired production line/branch coverage is100%; >95% was an estimate/intermediate milestone, never a claim of achieved coverage. Dev explicitly defers only declared live-provider cases as NOT_RUN, required at QA/main. Never exclude failing code, silently skip mandatory tests, execute lines without assertions or auto-accept visual snapshots as qualification.

Any unresolved mandatory failure is NO-GO; missing mandatory evidence is BLOCKED. CI configuration alone does not prove a remote CI run passed. Preserve legitimate unit mocking and scientific simulation with accurate classification.
