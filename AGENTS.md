# Repository agent instructions

Read [agent/AGENT.md](agent/AGENT.md) before changing this repository. It contains the active execution plan, safe test commands and continuation protocol.

Read [docs/quality/ZERO_FAKE_TESTING_POLICY.md](docs/quality/ZERO_FAKE_TESTING_POLICY.md). Never promote a mocked, simulated, skipped, unavailable or unexecuted check into live or scientific validation. Report measured scope and denominators; the requested release target is 100% production line/branch coverage and complete mandatory workflow qualification.

Preserve uncommitted user work, API/SSE contracts and research data. Use disposable `PHDLAB_DATA_DIR` for tests. Do not push or merge without user authorization.

Never delete files from `skills/` or `agent/`, including during cleanup, generated-file pruning or refactoring. Extend and update these folders in place. The user authorized staged version updates, commits and pushes to the task branch; do not merge it without authorization.

Provider forward/launch actions target locally installed CLI applications (including npm executables). Do not replace a native launch with a vendor website. Missing native apps must return an explicit unavailable result.
