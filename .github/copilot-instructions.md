Read agent/CI_REPAIR_SUPERVISOR.md and docs/devops/CI_CD_RECOVERY.vi.md for current shared CI ownership, authorized local repair and native dev-only auto-merge. Never independently edit CI/gates in ordinary feature work; never automatically modify qa/main.

Read root AGENTS.md and agent/DEVELOPMENT_WORKFLOW.md before editing. Follow the feature quality contract and deterministic verification harness. Only trusted feature -> dev PRs may auto-merge after all independent required checks pass. QA/main require promotion gates and human main authorization. Never delete skills/ or agent/ files, weaken tests/coverage or fabricate provider/scientific evidence.

For browser/UI acceptance, read `agent/UAT.md`: isolated profiles, deterministic Playwright first, risk-aware local exploration and no retries after the recorded three-failure limit. Missing required exploration stays BLOCKED.
