# Actual complete software verification6.5.11

Candidate6.5.11 on existing `dev`, parent `3f60a77c54ada9f1197c901019a119ad5d4ddebf`, source `dd01c60ac488bd91da7dd0cfaf880893d88232e6c1444cebca1b8d265571886c`. Actual stable local complete software gate PASS. Fresh exact-head GitHub CI is still required; no future PASS is presumed.

Owner explicitly confirmed on2026-10-26: complete software regression is mandatory across dev -> qa -> main; live-provider/research/AI-UAT qualification runs separately, and coverage is informational. Optional qualification never becomes live/scientific PASS merely because software CI passes.

Canonical `python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/native-consolidation/software-6.5.11` exited0: **1269/1269PASS,0FAIL/ERROR/SKIP/NOT_RUN**, stable source. Backend1017,frontend217,boundaries6,real2D28thenrealWebGL3D1. Separate Node policy48/48PASS. All15 contracts, static/types/build, dynamic discovery, workflow and browser gates passed.

Independent local non-root Linux/Python3.11.17 diagnostic with the same hash-locked Python dependencies: preflight36/36 then full backend1017/1017PASS, no skip; actual contained Chromium PDF and executable Git hooks. This is a real Debian container test, not a claim of an identical GitHub Ubuntu VM or remote CI PASS. Original failed/noexec/missing-browser diagnostics remain preserved.

Canonical source-bound proof: evidence/local-verification/report.json. Raw logs/screenshots/traces: output/playwright/native-consolidation/software-6.5.11/. Actual RED/GREEN and Linux/Windows backend reports: evidence/ci-recovery-6.5.11/. Live/research/AI-UAT outcomes are separate; no model execution or scientific result is inferred from these software checks.
