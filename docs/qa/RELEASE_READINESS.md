# Software release readiness6.5.11

**LOCAL SOFTWARE PASS; WAITING FOR FRESH EXACT-HEAD GITHUB CI.**

Candidate6.5.11 on existing `dev`, parent `3f60a77c54ada9f1197c901019a119ad5d4ddebf`, source `dd01c60ac488bd91da7dd0cfaf880893d88232e6c1444cebca1b8d265571886c`. Actual stable local complete software gate PASS. Fresh exact-head GitHub CI is still required; no future PASS is presumed.

Owner explicitly confirmed on2026-10-26: complete software regression is mandatory across dev -> qa -> main; live-provider/research/AI-UAT qualification runs separately, and coverage is informational. Optional qualification never becomes live/scientific PASS merely because software CI passes.

No promotion until every required software CI job and protected QA gate actually passes. GitHub must perform native dev->qa->main merges with source/tree/run provenance; no force/admin bypass. Actual remote run/PR/merge SHAs will be recorded after observation, not anticipated.

Separate qualification: prior real Hermes free inference/history/native-tool observations include one deferred-tool discovery failure and a later protocol-aware success. Full current scientific/research/paper/replay and independently reviewed AI-UAT are unqualified unless separately executed. These do not block software promotion under the new explicit owner policy; they also do not establish scientific correctness orL3/L4. Original3failed UAT and one unused600s/sixstepSpark allowance remain unchanged. Historical SIGSEGV remains of unknown original cause pending fresh CI observation. No blanket zero-bug/100%coverage claim.
