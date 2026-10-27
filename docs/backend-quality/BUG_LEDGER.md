# Backend Quality Assurance — Live Bug Ledger

| Bug ID | Subsystem | Severity | Symptom | Root Cause | Reproducing Test | Resolution / Remediation | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 | `backend.agent.orchestrator` | P2 | `AssertionError: 'assistant' != 'research'` when skills throw `AIWSError` | In `_agent(t)` commit `ec550cac`, fallback on `AIWSError` was changed to `'assistant'`, breaking fallback to `'research'` when a specific skill failed to load. | `test_agent.Skills.test_chat_skill_instructions_and_agent` | Restored `'research'` fallback for failed skill lookups while preserving `'assistant'` as default when no skill is requested. | VERIFIED |

## L1–L4 audit incidents (2026-10-24)

| ID | Severity | Finding | Evidence / disposition |
|---|---|---|---|
| AUTO-01 | P1 | A slow mission blocked independent workflows | Four-slot scheduler; dispatch overlap, six-workflow fairness, cancellation and scope tests pass |
| AUTO-02 | P1 | Qwen 3.5 reasoning-only response could become a false successful warning | Real reproduction; protocol regressions; hard thinking switch and empty-answer rejection verified |
| AUTO-03 | P1 | CPU contention could consume a task admission before a slot was available | Guard admission regression; competing slot leaves attempts zero |
| AUTO-04 | P1 | New L4 closure originally nested write transactions and locked SQLite | Failed live evidence retained; snapshot artifact checks remove nested DB lookup; repeated live runs pass |
| AUTO-05 | P1 | Historical quality scripts reported coverage/platform/fault PASS without sufficient evidence | Conservative assessments and per-case evidence; previous blanket certification withdrawn |
| AUTO-06 | P2 | Legacy research harness referenced a removed frontend HTML path | Source manifest points to actual React entrypoint; v6.0/6.2/6.3 exports executed and verified |
| AUTO-07 | P2 | Mobile inspector was clipped despite zero document overflow | Screenshot review; full-width inspector and stronger geometry oracle verified in Edge |
| AUTO-08 | P1 | Installed pypdf/certifi versions had four dependency advisories | Patched floors/install; pip-audit and npm audit pass afterwards |
| AUTO-09 | P1 | arXiv XML parser expanded declared entities | Failing adversarial test first; defusedxml rejects entities; regression rerun |
| AUTO-10 | P1 | Three intermittent failures in first legacy live run | Team fixed/adaptive failures plus MCP timeout; isolated and complete repeat pass; **root cause OPEN**, no universal stability claim |
| AUTO-11 | P1 | Legacy Mission form submitted reasoning cap 4 although the real API permits at most 3 | New assertion first failed with 4; default form changed to 3; frontend regression verifies the backend limit |

These are engineering severity assignments for this audit, not external certification. The complete raw history and remaining qualification gaps are in [the audit report](../testing/autonomy-report.md).

## Real CLI and tool feedback (2026-10-24)

- CLI-01: UI-advertised `/openscience`, `/feynman`, `/opencode` commands did not match the registry. Commands registered; explicit engines and approvals retained.
- CLI-02: ChatGPT Codex rejected stored `gpt-5` agent overrides. Vendor-default requests succeeded; invalid overrides cleared, catalog discovered from installed CLI.
- CLI-03: Antigravity `-p` consumed the next flag. Attached print flag verified by a real reply.
- CLI-04: Nested SSE content, persisted turn errors, immediate completion and New chat reset were mishandled. Regression and browser checks added.
- CLI-05: CLI Studio abandoned turns after 28 seconds and hid failures. Uses configured deadline and explicit outcomes.
- CLI-06: OpenCode server used an unsupported host flag; npm v2 native executable and authenticated JSON readiness now used.
- CLI-07: OpenCode adapter fabricated completion/native IDs from a manifest, and prompt keywords fabricated quota. Removed false observations; automatic native prompt dispatch remains unavailable.
- CLI-08: Claude real request hit a weekly limit; Gemini lacks configured sign-in; OpenScience integration disabled. External qualification remains blocked for these cases.

Raw failures, corrected runs and scope limits are in [the repair report](../testing/cli-connectivity-report.md).
