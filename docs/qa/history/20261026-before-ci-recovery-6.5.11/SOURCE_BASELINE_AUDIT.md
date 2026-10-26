# Source baseline and native consolidation audit

Candidate6.5.10, branch `dev`, parent HEAD `10c3d018134204fb778206c825b28f1846998304`, measured source `d1caebdc1c8f6156ea8aedb905ccd9608c5cb5480fd3f3ddc9156bd0f74c1930`. Local source was stable. GitHub result for a future commit is not presumed.

The owner explicitly retains integrated engines, especially PaperOrchestra. Its engine/API/Studio source is unchanged. Standalone Feynman/OpenScience/OpenCode/ClearML dispatch, setup and mutable controls are retired; historical producer IDs, opaque settings and files remain identifiable. Native coding, tracking, portable compute, VS Code and model CLI/subscriptions remain. Hermes is an independent pinned Docker runtime with unrestricted Internet and scoped host tools/filesystem.

The initial full software backend diagnostic executed1010 cases:893PASS,19FAIL,98ERROR,0SKIP. Findings include obsolete standalone-provider fixtures, legacy multi-topic setup and real UI/materialization/integrity defects. Their original logs/results remain under output/playwright/native-consolidation/backend-full; the exact backend report is retained in evidence/native-consolidation/baseline-backend.json.

The final suite has changed after explicit feature retirement and added regression coverage. It cannot be compared to main or the initial diagnostic by absolute PASS counts. A same-suite/same-environment paired main-versus-candidate comparison is NOT_RUN. No baseline exception or production defect waiver was added. Full current software results and residual qualification gaps are documented separately.
