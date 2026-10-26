# Regression execution and measured coverage6.5.10

Candidate6.5.10, branch `dev`, parent HEAD `10c3d018134204fb778206c825b28f1846998304`, measured source `d1caebdc1c8f6156ea8aedb905ccd9608c5cb5480fd3f3ddc9156bd0f74c1930`. Local source was stable. GitHub result for a future commit is not presumed.


Mandatory selected software1266/1266PASS, no skipped or unexecuted selected case. Coverage remains informational; desired100% line/branch is not achieved.

| Scope | Covered / total | Actual |
|---|---:|---:|
| Python production lines | 23688/26672 | 88.81% |
| Python production branches | 7117/8956 | 79.47% |
| Frontend lines | 2523/3818 | 66.08% |
| Frontend branches | 2754/4218 | 65.29% |

Python scope now includes backend and first-party Hermes service code under tools/hermes_runtime; the earlier backend-only denominator differs. Node proxy coverage is not included in these Python/React denominators and remains separately UNAVAILABLE. Do not add vendor package internals or exclude ordinary recovery paths to inflate results.

Uncovered Python: 2984 lines and 1839 branches. Frontend: 1295 lines and 1464 branches. Detailed per-file missing lines/branches remain in software-6.5.10/backend/coverage.json and frontend/coverage/. These are untested variants, not necessarily confirmed defects; live dependencies, platform-specific recovery and UI/error paths require further behavior-based coverage.

Dynamic discovery discovers implemented tests; it does not invent complete assertions or prove every feature is covered. Baseline-versus-candidate PASS totals and differing coverage scopes cannot demonstrate a paired quality improvement.
