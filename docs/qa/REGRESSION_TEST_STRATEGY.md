# Regression test strategy

Reuse unittest for backend, Vitest for components and Playwright for real browser regression. Tests use disposable data, deterministic fixtures and explicitly labeled provider doubles offline. A separate optional Browser Use adapter supplies selected exploration; it does not decide the deterministic suite's truth or replace its assertions. See [REGRESSION_POLICY.md](REGRESSION_POLICY.md) and [FEATURE_TEST_STANDARD.md](FEATURE_TEST_STANDARD.md).

Mandatory dimensions include input validity, persistence, API/CLI/2D/3D parity, cancellation, stale events, project/context isolation, concurrent work, provider failure and recovery, language, responsive/keyboard/accessibility behavior and evidence provenance. The inventory and exact measured denominators live in the latest acceptance reports; a schema-generated graph inventory is not scientific workflow coverage.

Order real qualification 2D -> actual WebGL 3D -> CLI -> provider/research outputs. Keep original failing attempts when rerunning; a flaky rerun does not erase the initial failure. Check source stability and dependencies before reusing any evidence. No cached passing test result is currently substituted for required regression.
