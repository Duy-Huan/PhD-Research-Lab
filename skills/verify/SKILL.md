---
name: verify
description: Run this repository's development verification profiles, inspect compact failure fingerprints, and enforce its feature/CI/full gates. Use while implementing or reviewing PhD Research Lab software changes; application research workflow execution remains separate.
---

Read `agent/DEVELOPMENT_WORKFLOW.md` and the current feature contract. From repository root run `python scripts/verify.py --profile quick --base origin/dev` while editing, `feature` before pushing, `pr` in independent CI, and `full` before QA/release. For diagnosis only, use `targeted --target test_<module>`.

Read the emitted summary/JSON first; inspect only relevant raw logs. Preserve failing evidence. After a failed automatic correction record `--repair-result failure --repair-key <stable-task-or-PR>`; stop after three. Never reset the ledger, narrow mandatory tests or weaken coverage. Missing/skipped live evidence remains unqualified.

For browser acceptance read `agent/UAT.md` and the versioned `devtools/verification/uat_config.json`. `uat` runs an isolated, bounded local Browser Use journey; check the repair ledger before any call. `release` includes full acceptance and remains blocked pending protected GitHub human approval. Playwright remains the regression authority. HIGH/CRITICAL missing exploration blocks acceptance; unsupported personas stay NOT_IMPLEMENTED, observations without reproduction stay UNCONFIRMED. Never attach personal Chrome, leak cookies or invoke paid cloud browsing.

Report the exact profile, component, commit/source digest and result. A quick/feature pass does not authorize merging: required GitHub checks on the current PR head must pass. Only eligible dev PRs may auto-merge; main needs human release authorization. Never delete anything under skills/ or agent/.
