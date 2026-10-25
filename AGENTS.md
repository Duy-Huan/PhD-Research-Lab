Read agent/CI_REPAIR_SUPERVISOR.md and docs/devops/CI_CD_RECOVERY.vi.md for current shared CI ownership, authorized local repair and native dev-only auto-merge. Never independently edit CI/gates in ordinary feature work; never automatically modify qa/main.

Current emergency override: read [agent/CI_RECOVERY.md](agent/CI_RECOVERY.md) before older automation plans. Never automatically merge main; dev auto-merge remains quarantined until trustworthy independent CI.

# Repository agent instructions

Before any code change, read [agent/AGENT.md](agent/AGENT.md), [agent/STATE.md](agent/STATE.md) and [agent/DEVELOPMENT_WORKFLOW.md](agent/DEVELOPMENT_WORKFLOW.md). Resume the first unfinished task; preserve all existing work.

Read [docs/quality/ZERO_FAKE_TESTING_POLICY.md](docs/quality/ZERO_FAKE_TESTING_POLICY.md). Never promote a mocked, simulated, skipped, unavailable or unexecuted check into live or scientific validation. Report measured scope and denominators; the requested release target is 100% production line/branch coverage and complete mandatory workflow qualification.

For every new feature: search GitHub for relevant skills, inspect them, install selected skills under `skills/` with pinned revision/license/provenance, then write a reviewed Feature Quality Contract and behavioral tests before implementation. See [skills/SOURCES.json](skills/SOURCES.json).

Use `python scripts/verify.py --profile quick` during development and `--profile feature` before pushing. Read its compact report, then only relevant raw evidence. Never skip required tests to save tokens. Automatic repair stops after three failed cycles per stable task/PR; persist its ledger.

For browser/UI or acceptance changes, read [agent/UAT.md](agent/UAT.md). Playwright is authoritative; `uat` adds risk-selected local Browser Use exploration with disposable app/browser profiles. Use the versioned persona/selector configuration and report unsupported/unexecuted journeys explicitly. Required HIGH/CRITICAL exploration and independent review must be evidenced before merge. Never use personal browser profiles, unrelated domains or subjective AI scores as acceptance. No model retry after the task's three-failure budget is exhausted.

The branch flow is `feature/* -> dev -> qa -> main`. Independent required GitHub checks must pass on the current head before merging. Only eligible trusted dev PRs may use native squash auto-merge. Never auto-merge qa/main, bypass protections, force-push or weaken tests/coverage. Main requires human release authorization. Verify the actual merged SHA before cleanup.

Preserve API/SSE contracts and research data. Use disposable `PHDLAB_DATA_DIR`. Development verification lives in `devtools/verification/`; it must not become an application Research Agent Harness dependency.

Never delete files from `skills/` or `agent/`, including during cleanup. Extend/update in place. The user authorized staged version updates, commits, feature pushes after local gates and eligible dev auto-merge after independent CI. Preserve unrelated dirty changes. Existing release blockers remain blockers.

Provider forward/launch actions target locally installed CLI applications (including npm executables). Do not replace a native launch with a vendor website. Missing native apps must return an explicit unavailable result.
