# Measured regression and coverage6.5.11

Candidate6.5.11 on existing `dev`, parent `3f60a77c54ada9f1197c901019a119ad5d4ddebf`, source `dd01c60ac488bd91da7dd0cfaf880893d88232e6c1444cebca1b8d265571886c`. Actual stable local complete software gate PASS. Fresh exact-head GitHub CI is still required; no future PASS is presumed.


Owner explicitly confirmed on2026-10-26: complete software regression is mandatory across dev -> qa -> main; live-provider/research/AI-UAT qualification runs separately, and coverage is informational. Optional qualification never becomes live/scientific PASS merely because software CI passes.


| Scope | Covered / total | Actual |
|---|---:|---:|
| Python lines | 23691/26672 | 88.82% |
| Python branches | 7121/8956 | 79.51% |
| React lines | 2523/3818 | 66.08% |
| React branches | 2754/4218 | 65.29% |

Software1269/1269PASS plus48Node policy cases. Desired100% coverage is not achieved and does not block CI; untested lines/branches are not asserted as covered. Python scope includes backend and first-party Hermes service; JavaScript proxy coverage is separately UNAVAILABLE. Full per-file missing lines/branches remain in the canonical raw coverage files.

Uncovered Python lines2981,branches1835; React lines1295,branches1464. New regression IDs are dynamically discovered; discovery does not generate complete behavioral assertions or waive recovery/platform/UI coverage gaps.
