---
name: verify
description: Verify PhD Research Lab software changes using its deterministic development harness and quality gates.
---

Read `skills/verify/SKILL.md` from repository root and follow it. The portable command is `python scripts/verify.py --profile quick`. Codex can invoke this skill as `$verify`; do not claim that a universal native `/verify` slash command exists in every agent client.

For browser/UI acceptance, read `agent/UAT.md`: isolated profiles, deterministic Playwright first, risk-aware local exploration and no retries after the recorded three-failure limit. Missing required exploration stays BLOCKED.
