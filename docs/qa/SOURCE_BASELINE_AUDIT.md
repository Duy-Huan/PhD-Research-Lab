# Source stabilization baseline — 2026-10-25

Status: IN PROGRESS; this is a measured baseline, not release certification. Governance candidate 6.5.0 is on `feature/development-governance`, head `25d0a6478e517bcc252569b774d05925a67d8f8e`. Current audit source digest `d911501d99f67b32e66cd3cb9574e85edef2b9b4b7e767eac0a867aa77db807d` includes the two newly installed pinned skills. The earlier passing feature report has its own source digest and does not certify later edits.

## Architecture inventory

Application boundaries: backend/api receives requests; providers handles routing/lifecycle/native CLI/MCP; memory stores/retrieves evidence and context; agent orchestrates research runs; execution owns workflows/tools/sandbox; research_engines integrates research systems; knowledge handles library/search; paper exports artifacts. React features and shell render the 2D interface and 3D workspace; backend/cli is the terminal surface. devtools/verification and GitHub workflows are development infrastructure, distinct from runtime research execution.

`source-inventory.json` records the complete statically surveyed file lists for these categories, 181 test files and 318 API declarations. Commands: `git ls-files -z` plus Python AST inspection of route decorators, with raw results captured in `source-inventory.json`; declarations are not a live OpenAPI conformance result. Dynamically registered routes may differ.

| Category | Source files surveyed |
|---|---:|
| backend/api | 21 |
| backend/providers | 19 |
| backend/memory | 20 |
| backend/agent | 27 |
| backend/execution | 24 |
| backend/research_engines | 16 |
| backend/knowledge | 18 |
| backend/paper | 7 |
| backend/intelligence | 7 |
| backend/cli | 3 |
| frontend/src/features | 34 |
| frontend/src/shell | 4 |
| devtools/verification | 13 |

The heuristic `python skills/test-gap-audit/scripts/coverage_map.py --format json --top 50` found 278 source candidates, 186 tests and 128 unmatched leads. These include vendor/skill code and indirectly tested paths; they are NOT confirmed missing coverage. Runtime coverage and inspection determine confirmed gaps.

## Actual executions and preservation

Existing unit expectations were retained for the baseline. The prior immutable `feature-attestation-final` report executed 1,043 PASS and 8 SKIP, with stable source. New strict backend and frontend results are in FULL_VERIFICATION_REPORT. Browser reconnaissance covered Workspace and Settings at 375,768,1280,1920px, with eight axe scans, screenshots, traces and Tab samples. This is not every route or a screen-reader certification.

The original workspace remains on feature/full-harness-20261024 with uncommitted application changes preserved. These cloud-preconnect, contained-CLI and context-preservation changes are not integrated/certified by this governance baseline. A separate fix/ui-source-baseline worktree was created from origin/dev and explicitly merged the pending governance dependency; PR7 remains independently gated.

Surveyed but not deeply inspected this pass: all provider transports, all memory concurrency branches, every orchestration transition, scientific correctness, all 3D controls and CLI menu/locale parity. Next: controlled UI fixes, then high-risk context/containment/integration defects and live evidence producer. Never mark these as PASS based on unit results.
