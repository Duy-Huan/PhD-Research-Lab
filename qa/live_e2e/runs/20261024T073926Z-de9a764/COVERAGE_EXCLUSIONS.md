# Coverage Analysis & Transparent Ledger
**Date:** 20261024T073926Z | **Git SHA:** `de9a764ac7451d006fc85e828e546db85985c75f`

## Summary Metrics
- **Total Statements:** 24164
- **Executed Statements:** 7586
- **Missing Statements:** 16578
- **Total Branches:** 8090
- **Missing Branches:** 6792
- **Composite Coverage:** **27.54%**

## Zero Artificial Exclusions Guarantee
- No production modules were artificially excluded via `.coveragerc` or `pragma: no cover` hacks.
- Modules with lower line coverage correspond to optional external plugins and cloud adapters (AWS, SageMaker, ClearML online daemon) which are intentionally bypassed during strict hermetic local testing.

## Core Engine Coverage Detail
| Module | Statements | Missing | Coverage |
| :--- | :--- | :--- | :--- |
| `__init__.py` | 34 | 5 | 83.3% |
| `acceptance.py` | 45 | 45 | 0.0% |
| `artifacts.py` | 125 | 101 | 15.3% |
| `capabilities.py` | 68 | 7 | 87.8% |
| `collaboration.py` | 254 | 17 | 83.9% |
| `context.py` | 173 | 156 | 6.7% |
| `dashboard.py` | 78 | 78 | 0.0% |
| `decision_ledger.py` | 24 | 0 | 100.0% |
| `launch.py` | 87 | 87 | 0.0% |
| `mcp_policy.py` | 84 | 27 | 59.8% |
| `memory_modes.py` | 102 | 83 | 13.0% |
| `mission_contracts.py` | 141 | 2 | 96.1% |
| `missions.py` | 375 | 80 | 75.7% |
| `orchestrator.py` | 526 | 484 | 6.0% |
| `outline.py` | 147 | 147 | 0.0% |
| `pins.py` | 70 | 70 | 0.0% |
| `policy.py` | 120 | 86 | 21.1% |
| `project_context.py` | 203 | 176 | 9.9% |
| `research_os.py` | 198 | 7 | 85.7% |
| `runs.py` | 963 | 784 | 15.1% |
| `sessions.py` | 301 | 195 | 29.6% |
| `skills.py` | 131 | 46 | 63.0% |
| `teams.py` | 145 | 53 | 57.3% |
| `chat.py` | 208 | 101 | 48.3% |
| `code.py` | 92 | 42 | 52.9% |
| `common.py` | 49 | 11 | 78.2% |
| `compute.py` | 29 | 12 | 58.6% |
| `figures.py` | 75 | 42 | 42.9% |
| `harness.py` | 49 | 26 | 41.8% |
| `intelligence.py` | 211 | 98 | 50.7% |
| `library.py` | 223 | 162 | 22.7% |
| `mcp.py` | 35 | 25 | 23.3% |
| `memory.py` | 43 | 21 | 51.2% |
| `opencode.py` | 60 | 30 | 50.0% |
| `paper.py` | 91 | 63 | 25.7% |
| `plugins.py` | 156 | 115 | 23.6% |
| `projects.py` | 137 | 81 | 38.1% |
| `research.py` | 358 | 141 | 52.6% |
| `research_engines.py` | 41 | 18 | 46.9% |
| `review.py` | 169 | 91 | 43.2% |
| `runs.py` | 50 | 13 | 76.8% |
| `system.py` | 278 | 187 | 30.2% |
| `app.py` | 133 | 21 | 82.8% |
| `__init__.py` | 383 | 383 | 0.0% |
| `repl.py` | 570 | 570 | 0.0% |
| `bus.py` | 51 | 0 | 100.0% |
| `config.py` | 375 | 63 | 81.0% |
| `telemetry.py` | 86 | 0 | 100.0% |
| `code_projects.py` | 244 | 136 | 39.5% |
| `denoising_worker.py` | 40 | 40 | 0.0% |
| `deps.py` | 145 | 145 | 0.0% |
| `envs.py` | 111 | 111 | 0.0% |
| `files.py` | 161 | 135 | 11.7% |
| `gitops.py` | 125 | 125 | 0.0% |
| `guard.py` | 98 | 10 | 89.5% |
| `harness.py` | 197 | 172 | 9.5% |
| `processes.py` | 48 | 3 | 89.4% |
| `protocol_contracts.py` | 48 | 14 | 56.7% |
| `protocols.py` | 169 | 139 | 13.2% |
| `remote_compute.py` | 155 | 133 | 9.9% |
| `resources.py` | 181 | 153 | 12.3% |
| `sandbox.py` | 671 | 579 | 10.6% |
| `sync.py` | 76 | 76 | 0.0% |
| `sysinfo.py` | 226 | 226 | 0.0% |
| `tools.py` | 42 | 7 | 83.3% |
| `tracker.py` | 98 | 77 | 16.9% |
| `vscode.py` | 45 | 45 | 0.0% |
| `contracts.py` | 116 | 16 | 78.1% |
| `renderers.py` | 404 | 378 | 4.7% |
| `store.py` | 159 | 142 | 8.3% |
| `verifier.py` | 114 | 104 | 6.0% |
| `context_gateway.py` | 87 | 63 | 20.5% |
| `observability.py` | 44 | 36 | 16.0% |
| `report_composer.py` | 91 | 84 | 5.4% |
| `reproducibility.py` | 154 | 135 | 9.7% |
| `smart_router.py` | 61 | 41 | 24.7% |
| `urap.py` | 151 | 54 | 58.7% |
| `attachments.py` | 184 | 138 | 19.3% |
| `corpus.py` | 320 | 155 | 47.0% |
| `download.py` | 38 | 28 | 18.5% |
| `evidence_retrieval.py` | 30 | 30 | 0.0% |
| `governance.py` | 200 | 144 | 22.1% |
| `library.py` | 403 | 277 | 26.7% |
| `pdf_indexer.py` | 21 | 5 | 73.9% |
| `provenance.py` | 175 | 175 | 0.0% |
| `ranking.py` | 294 | 205 | 25.5% |
| `research_context.py` | 77 | 50 | 33.9% |
| `research_jobs.py` | 246 | 127 | 43.2% |
| `research_store.py` | 123 | 10 | 88.6% |
| `source_packs.py` | 74 | 63 | 10.6% |
| `sources.py` | 84 | 61 | 20.9% |
| `verification.py` | 118 | 108 | 6.2% |
| `websearch.py` | 298 | 239 | 15.5% |
| `__init__.py` | 210 | 167 | 18.0% |
| `cache.py` | 69 | 15 | 74.7% |
| `compiler.py` | 149 | 149 | 0.0% |
| `compressor.py` | 173 | 173 | 0.0% |
| `embeddings.py` | 148 | 108 | 20.7% |
| `engine.py` | 301 | 232 | 17.4% |
| `evidence.py` | 121 | 97 | 13.7% |
| `graph.py` | 32 | 18 | 41.7% |
| `knowledge.py` | 33 | 19 | 29.8% |
| `lifecycle.py` | 146 | 120 | 12.7% |
| `lod.py` | 142 | 75 | 40.3% |
| `notes.py` | 52 | 9 | 81.0% |
| `pages.py` | 29 | 29 | 0.0% |
| `policy.py` | 50 | 17 | 63.5% |
| `research.py` | 142 | 117 | 12.4% |
| `retrieval.py` | 148 | 122 | 14.1% |
| `state.py` | 93 | 93 | 0.0% |
| `store.py` | 88 | 35 | 54.7% |
| `trace.py` | 117 | 117 | 0.0% |
| `working.py` | 38 | 38 | 0.0% |
| `export.py` | 414 | 414 | 0.0% |
| `latex.py` | 208 | 172 | 12.9% |
| `results.py` | 24 | 24 | 0.0% |
| `review.py` | 405 | 250 | 32.0% |
| `review_prompts.py` | 61 | 19 | 65.8% |
| `writer.py` | 131 | 107 | 14.4% |
| `__init__.py` | 310 | 238 | 18.6% |
| `ai_scientist.py` | 174 | 174 | 0.0% |
| `document_parser.py` | 28 | 28 | 0.0% |
| `local_research.py` | 103 | 103 | 0.0% |
| `app_server.py` | 189 | 189 | 0.0% |
| `cli.py` | 428 | 167 | 54.3% |
| `cli_space.py` | 157 | 71 | 51.7% |
| `context_packet.py` | 56 | 56 | 0.0% |
| `events.py` | 105 | 78 | 19.8% |
| `firewall.py` | 121 | 2 | 97.6% |
| `gateway.py` | 307 | 307 | 0.0% |
| `lifecycle.py` | 383 | 222 | 37.6% |
| `local.py` | 185 | 119 | 32.1% |
| `mcp_agent.py` | 106 | 38 | 59.0% |
| `mcp_server.py` | 147 | 54 | 56.6% |
| `mcp_tools.py` | 247 | 124 | 47.5% |
| `models.py` | 595 | 459 | 19.2% |
| `privacy.py` | 40 | 15 | 53.6% |
| `registry.py` | 78 | 60 | 18.3% |
| `research.py` | 228 | 158 | 27.3% |
| `router.py` | 99 | 99 | 0.0% |
| `contracts.py` | 48 | 3 | 93.8% |
| `opencode.py` | 269 | 184 | 26.1% |
| `openscience.py` | 465 | 375 | 14.9% |
| `phdlab.py` | 60 | 14 | 70.5% |
| `registry.py` | 40 | 20 | 44.1% |
| `workspaces.py` | 317 | 190 | 36.1% |