Read `skills/verify/SKILL.md`. Run the requested development verification profile via `python scripts/verify.py`; default to quick. Read compact reports, then only relevant raw evidence. Targeted runs never replace mandatory gates. Follow the persistent three-repair limit in `agent/DEVELOPMENT_WORKFLOW.md`.

For browser/UI acceptance, read `agent/UAT.md`: isolated profiles, deterministic Playwright first, risk-aware local exploration and no retries after the recorded three-failure limit. Missing required exploration stays BLOCKED.
