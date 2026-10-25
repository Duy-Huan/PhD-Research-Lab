Active owner rule: AI edits/commits only on dev; complete local pr/all software verification before dev push; dev -> qa -> main promotions. Coverage is informational. Required software regression must execute/PASS100%; real provider/research/AI-UAT is required at QA/main. Never auto-main or bypass hooks/protection. Read agent/DEV_QA_MAIN.md.

Read `skills/verify/SKILL.md`. Run the requested development verification profile via `python scripts/verify.py`; default to quick. Read compact reports, then only relevant raw evidence. Targeted runs never replace mandatory gates. Follow the persistent three-repair limit in `agent/DEVELOPMENT_WORKFLOW.md`.

For browser/UI acceptance, read `agent/UAT.md`: isolated profiles, deterministic Playwright first, risk-aware local exploration and no retries after the recorded three-failure limit. Missing required exploration stays BLOCKED.
