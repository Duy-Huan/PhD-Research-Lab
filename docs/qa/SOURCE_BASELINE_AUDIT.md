# Source baseline6.5.11

Candidate6.5.11 on existing `dev`, parent `3f60a77c54ada9f1197c901019a119ad5d4ddebf`, source `dd01c60ac488bd91da7dd0cfaf880893d88232e6c1444cebca1b8d265571886c`. Actual stable local complete software gate PASS. Fresh exact-head GitHub CI is still required; no future PASS is presumed.

Owner explicitly confirmed on2026-10-26: complete software regression is mandatory across dev -> qa -> main; live-provider/research/AI-UAT qualification runs separately, and coverage is informational. Optional qualification never becomes live/scientific PASS merely because software CI passes.

Previous source baseline and native migration remain retained under history/20261026-before-ci-recovery-6.5.11 and evidence/native-consolidation. The actual failed6.5.10 CI is the recovery baseline; parent local1266PASS did not qualify its remote environment. New controlled absent-runtime RED reproduces that environment coupling. Same-suite main-versus-candidate comparison remains NOT_RUN; changing suite/coverage scopes cannot be ranked by absolute PASS counts. No baseline exception was added. Integrated PaperOrchestra remains preserved, standalone software retirement and native replacements are retained.

[Actual root causes and evidence](CI_ROOT_CAUSE_REPORT.md).
