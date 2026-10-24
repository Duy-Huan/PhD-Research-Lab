# Backend Quality Assurance — Live Bug Ledger

| Bug ID | Subsystem | Severity | Symptom | Root Cause | Reproducing Test | Resolution / Remediation | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 | `backend.agent.orchestrator` | P2 | `AssertionError: 'assistant' != 'research'` when skills throw `AIWSError` | In `_agent(t)` commit `ec550cac`, fallback on `AIWSError` was changed to `'assistant'`, breaking fallback to `'research'` when a specific skill failed to load. | `test_agent.Skills.test_chat_skill_instructions_and_agent` | Restored `'research'` fallback for failed skill lookups while preserving `'assistant'` as default when no skill is requested. | VERIFIED |
