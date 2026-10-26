---
name: verify
description: Run this repository's development verification profiles, inspect compact failure fingerprints, and enforce its feature/CI/full gates. Use while implementing or reviewing PhD Research Lab software changes; application research workflow execution remains separate.
---

Read `agent/DEVELOPMENT_WORKFLOW.md` and the current feature contract. From repository root run `python scripts/verify.py --profile quick --base origin/dev` while editing, `pr --component all` before dev push, `pr` in independent CI, and `full` before QA/release. For diagnosis only, use `targeted --target test_<module>`.

Read the emitted summary/JSON first; inspect only relevant raw logs. Preserve failing evidence. After a failed automatic correction record `--repair-result failure --repair-key <stable-task-or-PR>`; stop after three. Never reset the ledger, narrow mandatory tests or weaken coverage. Missing/skipped live evidence remains unqualified.

For browser acceptance read `agent/UAT.md` and the versioned `devtools/verification/uat_config.json`. `uat` runs an isolated, bounded local Browser Use journey; check the repair ledger before any call. `release` includes full acceptance and remains blocked pending protected GitHub human approval. Playwright remains the regression authority. HIGH/CRITICAL missing exploration blocks acceptance; unsupported personas stay NOT_IMPLEMENTED, observations without reproduction stay UNCONFIRMED. Never attach personal Chrome, leak cookies or invoke paid cloud browsing.

Report the exact profile, component, commit/source digest and result. A quick/feature pass does not authorize merging: required GitHub checks on the current PR head must pass. Develop only on dev; only eligible dev-to-qa PRs may auto-merge; main needs human release authorization. Never delete anything under skills/ or agent/.

Owner policy2026-10-25: source edits and testcase additions ONLY on the single existing dev branch; creating any other development branch is forbidden. Current authority is agent/DEV_QA_MAIN.md. Desired coverage100%, >95% was an estimate, no percentage CI gate. Preserve original three UAT failures; exactly ONE owner-granted Spark local attempt may run with external one-use grant, maximum600seconds/six steps.

## Owner completion rule (2026-10-26)

Owner design constraints (2026-10-27): read the complete [Native AI Research Environment checklist](../../agent/NATIVE_AI_RESEARCH_ENVIRONMENT.md) before core, prompt, orchestration, context, memory, tool, provider or runtime design/changes. Maintain item-level status, source and actual evidence, including the seven required reports. CI/CD is first; the native core campaign targets 6.6.xx. Requirements or software PASS do not certify real scientific execution or L3/L4.

For every coding task, the AI agent must inspect the actual repository on GitHub **in a browser**: the exact commit, relevant Actions run and forward promotion PRs. A CLI/API receipt supplements this browser inspection. Local PASS, a push, an open PR or an auto-merge request is not completion. Continue the authorized protected automatic `dev -> qa -> main` flow; verify both PRs are actually merged, record their URLs and merge SHAs, and prove the task commit is contained in current `main`. Where delivery is in scope, also verify the exact main release SHA. Never report the coding task complete before this evidence exists. If mandatory gates fail or a repair budget is exhausted, retain an explicit incomplete/blocker handoff with actual evidence; do not bypass protection or manufacture success. This rule does not turn software CI into live-provider or scientific L3/L4 qualification.
