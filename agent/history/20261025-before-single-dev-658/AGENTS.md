ACTIVE OWNER UPDATE (2026-10-25): AI must edit source, repairs and testcases only on the single existing dev branch. Creating any other development/backup branch is forbidden; Git reference-transaction hook enforces local writes only to dev. Latest owner explicitly authorizes native automatic dev-to-qa then qa-to-main promotion ONLY after every mandatory local/GitHub/software/live-provider/research/AI-UAT gate truly passes; this supersedes older never-auto-main wording. Coverage >95% is an improvement target, explicitly informational/nonblocking. Do not weaken regressions, reset exhausted UAT counters or bypass branch protection.

# Repository agent instructions

ACTIVE OWNER RULE (2026-10-25): All AI source development and repair commits MUST use branch `dev`. Run the local verification harness before pushing `dev`. Promotion is `dev -> qa` (CI/CD, mandatory live-provider and AI-UAT) -> `main` (qualified release). Never develop on main, qa or feature/fix branches. Coverage is informational; every required software regression must execute and PASS. Missing/skipped checks are not PASS. Preserve historical worktrees and all skills/agent files during migration/cleanup.

Before any code change, read [agent/AGENT.md](agent/AGENT.md), [agent/STATE.md](agent/STATE.md) and [agent/DEVELOPMENT_WORKFLOW.md](agent/DEVELOPMENT_WORKFLOW.md). Resume the first unfinished task; preserve all existing work.

Read [docs/quality/ZERO_FAKE_TESTING_POLICY.md](docs/quality/ZERO_FAKE_TESTING_POLICY.md). Never promote a mocked, simulated, skipped, unavailable or unexecuted check into live or scientific validation. Report measured scope and denominators. Coverage is informational; required software regressions must all execute and PASS. Actual provider/research/AI-UAT qualification is mandatory at QA/main.

For every new feature: search GitHub for relevant skills, inspect them, install selected skills under `skills/` with pinned revision/license/provenance, then write a reviewed Feature Quality Contract and behavioral tests before implementation. See [skills/SOURCES.json](skills/SOURCES.json).

Use `python scripts/verify.py --profile quick` during development and `--profile pr --component all` before dev push. Install `scripts/development_guard.py` hooks; do not disable or bypass them. Read compact reports, then only relevant raw evidence. Never skip required tests to save tokens. Automatic repair stops after three invocations per stable task/PR; persist its ledger.

For browser/UI or acceptance changes, read [agent/UAT.md](agent/UAT.md). Playwright is authoritative; `uat` adds risk-selected local Browser Use exploration with disposable app/browser profiles. Use the versioned persona/selector configuration and report unsupported/unexecuted journeys explicitly. Required HIGH/CRITICAL exploration and independent review must be evidenced before merge. Never use personal browser profiles, unrelated domains or subjective AI scores as acceptance. No model retry after the task's three-failure budget is exhausted.

The branch flow is `dev -> qa -> main`. All AI development/repair commits are on dev, one writer at a time. Independent required GitHub checks must pass on the current head before promotion. Only eligible trusted dev-to-qa PRs may use native merge auto-merge after complete QA qualification. Never automatically merge main, bypass protection, force-push or weaken assertions. Main is owner-controlled. Verify actual source containment and preserve a verified Git bundle before obsolete remote branch cleanup; never delete worktrees.

Preserve API/SSE contracts and research data. Use disposable `PHDLAB_DATA_DIR`. Development verification lives in `devtools/verification/`; it must not become an application Research Agent Harness dependency.

Never delete files from `skills/` or `agent/`, including during cleanup. Extend/update in place. The user authorized staged version updates, dev commits/pushes after local gates and eligible dev-to-qa promotion after independent QA. Preserve unrelated dirty changes. Existing release blockers remain blockers. Read [agent/DEV_QA_MAIN.md](agent/DEV_QA_MAIN.md) and [agent/CI_REPAIR_SUPERVISOR.md](agent/CI_REPAIR_SUPERVISOR.md) for exact operator commands and trust prerequisites.

Provider forward/launch actions target locally installed CLI applications (including npm executables). Do not replace a native launch with a vendor website. Missing native apps must return an explicit unavailable result.
