# Reusable UAT personas

Only implemented behavior may be selected. A plan or inventory is NOT_RUN until assertions/real actions execute. Reuse existing Playwright flows before adding tests; exploratory work should seek untested edge behavior rather than repeat every successful assertion.

| Persona | Existing surfaces / relevant tests | Exploration and acceptance |
|---|---|---|
| First-time user | navigation.spec, journeys project creation/settings, ci_smoke, uat_harness language persistence | Startup, empty/error states, project creation, configuration and basic chat; current Browser Use adapter qualifies only a narrow settings-language journey when actually completed |
| PhD researcher | journeys real chat/memory, workflows, harness_ide, Golden Thread script | Topic/idea/plan, actual workflow outputs, evidence/memory and restoration; needs configured real provider and experiment/paper artifacts |
| Advanced operator | harness_ide, tools, mission/worker/backend integration tests | Manual/auto modes, selection, handoff, concurrency, progress, cancel/retry; native CLI work requires hardened project containment |
| Failure/recovery user | deterministic fault/recovery cases and uat_harness network/reload | Provider unavailable, timeout, invalid input, partial workflow, refresh/restart; inject faults explicitly and retain actual errors |
| Frontend quality user | navigation responsive controls, journeys a11y/settings, office3d actual WebGL | Keyboard, layout, overflow, streaming, locale/state synchronization; screenshot review and deterministic assertions remain necessary for visual claims |

The development CLI is shared by Codex, Claude Code and Antigravity. Each concurrent task must get its own server/data/browser lease. The current model adapter uses local Spark DOM observations; it has not automatically certified visual quality or all five personas. Follow [agent/UAT.md](../../agent/UAT.md) and the latest [acceptance checkpoint](UAT_ACCEPTANCE_REPORT.md).

Executable selection configuration: `devtools/verification/uat_config.json`; selector: `devtools/verification/journeys.py`. Each journey declares real suite filenames, affected paths, model requirement and implemented adapter status. Offline CI excludes suites needing provider inference; full/release selection includes them in 2D then 3D order. A selection plan never certifies execution. Native CLI remains a separate live qualification layer.
