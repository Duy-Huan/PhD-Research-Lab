---
name: verify
description: Verify PhD Research Lab software changes using its deterministic development harness and quality gates.
---

ACTIVE OWNER POLICY (2026-10-25): All source edits, repairs and testcase additions ONLY on the existing dev branch; creating any other development/backup branch is forbidden. Native automatic dev -> qa -> main is explicitly authorized ONLY after every mandatory local/GitHub/software/live/research/AI-UAT gate actually passes. Desired production line/branch coverage100%; >95% was an estimate, coverage stays informational/nonblocking. Every mandatory regression must execute/PASS100%. Original UAT three-failure ledger stays intact; exactly ONE separately authorized Spark X2.5 4B local attempt may run, maximum600seconds/six steps. Do not bypass protection or invent evidence.


Active owner rule: AI edits/commits only on dev; complete local pr/all software verification before dev push; dev -> qa -> main promotions. Coverage is informational. Required software regression must execute/PASS100%; real provider/research/AI-UAT is required at QA/main. Native auto-main is owner-authorized only after all mandatory gates pass; never bypass hooks/protection. Read agent/DEV_QA_MAIN.md.

Read agent/CI_REPAIR_SUPERVISOR.md and docs/devops/CI_CD_RECOVERY.vi.md for current shared CI ownership, authorized local repair and native dev-to-qa auto-merge. Never independently edit CI/gates in ordinary feature work; never bypass QA; native automatic main promotion requires every mandatory current-source gate to pass.



Read `skills/verify/SKILL.md` from repository root and follow it. The portable command is `python scripts/verify.py --profile quick`. Codex can invoke this skill as `$verify`; do not claim that a universal native `/verify` slash command exists in every agent client.

For browser/UI acceptance, read `agent/UAT.md`: isolated profiles, deterministic Playwright first, risk-aware local exploration and no retries after the recorded three-failure limit. Missing required exploration stays BLOCKED.
