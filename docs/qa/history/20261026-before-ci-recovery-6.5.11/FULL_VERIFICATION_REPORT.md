# Actual software and integration verification6.5.10

Candidate6.5.10, branch `dev`, parent HEAD `10c3d018134204fb778206c825b28f1846998304`, measured source `d1caebdc1c8f6156ea8aedb905ccd9608c5cb5480fd3f3ddc9156bd0f74c1930`. Local source was stable. GitHub result for a future commit is not presumed.

Canonical command: `python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/native-consolidation/software-6.5.10`.

**1266/1266 software assertions PASS,0FAIL/ERROR/SKIP/NOT_RUN; process exit0.** Backend1014, frontend217, deterministic boundaries6, browser2D28thenWebGL3D1. Separate Node policy48/48PASS. Static validation,15feature contracts, dynamic discovery, workflow policy, types, frontend build and browser gate PASS. Logs/screenshots/traces remain under that output folder. The exact canonical source-bound report is [evidence/local-verification/report.json](evidence/local-verification/report.json). Tests use owned disposable data; unit/controlled vendor boundaries retain their MOCKED classification.

On the same final source, actual free Nous/Hermes gateway nonce and fresh-backend/runtime restart history checks passed. One direct-name native MCP attempt failed; a protocol-aware attempt passed with an independently observed native read call. Both are source-scoped live observations, not a general reliability certification. Raw receipts are under evidence/native-consolidation.

The native local research harness completed8workflows and fresh CPU reproduction with measured artifacts/audit-chain/ZIP checks. Its literature and review fixtures are synthetic; this is neither deep-learning GPU validation nor scientific endorsement. It ran on the preceding source snapshot, which is retained in its own report. Current-source scientific paper qualification and AI-UAT remain BLOCKED/NOT_RUN. No GitHub CI result is inferred from local success.
