---
name: verify
description: Verify PhD Research Lab software changes using its deterministic development harness and quality gates.
---

Active owner rule: AI edits/commits only on dev; complete local pr/all software verification before dev push; dev -> qa -> main promotions. Coverage is informational. Required software regression must execute/PASS100%; real provider/research/AI-UAT is required at QA/main. Never auto-main or bypass hooks/protection. Read agent/DEV_QA_MAIN.md.

Read agent/CI_REPAIR_SUPERVISOR.md and docs/devops/CI_CD_RECOVERY.vi.md for current shared CI ownership, authorized local repair and native dev-to-qa auto-merge. Never independently edit CI/gates in ordinary feature work; never bypass QA or automatically merge main.



Read `skills/verify/SKILL.md` from repository root and follow it. The portable command is `python scripts/verify.py --profile quick`. Codex can invoke this skill as `$verify`; do not claim that a universal native `/verify` slash command exists in every agent client.

For browser/UI acceptance, read `agent/UAT.md`: isolated profiles, deterministic Playwright first, risk-aware local exploration and no retries after the recorded three-failure limit. Missing required exploration stays BLOCKED.
