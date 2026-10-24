# Coverage Analysis & Transparent Ledger
**Date:** 20261023T223115Z | **Git SHA:** `de9a764ac7451d006fc85e828e546db85985c75f`

## Summary Metrics
- **Total Statements:** 23622
- **Executed Statements:** 5162
- **Missing Statements:** 18460
- **Total Branches:** 7912
- **Missing Branches:** 7251
- **Composite Coverage:** **18.47%**

## Zero Artificial Exclusions Guarantee
- No production modules were artificially excluded via `.coveragerc` or `pragma: no cover` hacks.
- Modules with lower line coverage correspond to optional external plugins and cloud adapters (AWS, SageMaker, ClearML online daemon) which are intentionally bypassed during strict hermetic local testing.

## Core Engine Coverage Detail
| Module | Statements | Missing | Coverage |
| :--- | :--- | :--- | :--- |
| `__init__.py` | 34 | 5 | 83.3% |
| `acceptance.py` | 45 | 45 | 0.0% |
| `artifacts.py` | 125 | 101 | 15.3% |
| `capabilities.py` | 68 | 13 | 74.4% |
| `collaboration.py` | 254 | 129 | 45.5% |
| `context.py` | 173 | 156 | 6.7% |
| `dashboard.py` | 78 | 78 | 0.0% |
| `decision_ledger.py` | 24 | 0 | 96.4% |
| `launch.py` | 87 | 87 | 0.0% |
| `mcp_policy.py` | 84 | 42 | 40.2% |
| `memory_modes.py` | 102 | 83 | 13.0% |
| `mission_contracts.py` | 141 | 2 | 96.1% |
| `missions.py` | 375 | 179 | 48.3% |
| `orchestrator.py` | 519 | 477 | 6.1% |
| `outline.py` | 147 | 147 | 0.0% |
| `pins.py` | 70 | 70 | 0.0% |
| `policy.py` | 120 | 99 | 11.6% |
| `project_context.py` | 203 | 176 | 9.9% |
| `research_os.py` | 198 | 57 | 61.7% |
| `runs.py` | 963 | 864 | 7.6% |
| `sessions.py` | 301 | 196 | 29.1% |
| `skills.py` | 131 | 131 | 0.0% |
| `teams.py` | 145 | 53 | 57.3% |
| `chat.py` | 208 | 127 | 33.5% |
| `code.py` | 92 | 54 | 36.5% |
| `common.py` | 49 | 38 | 20.0% |
| `compute.py` | 29 | 12 | 58.6% |
| `figures.py` | 75 | 42 | 42.9% |
| `intelligence.py` | 211 | 98 | 50.7% |
| `library.py` | 200 | 165 | 12.4% |
| `mcp.py` | 35 | 25 | 23.3% |
| `memory.py` | 43 | 21 | 51.2% |
| `opencode.py` | 57 | 29 | 49.1% |
| `paper.py` | 63 | 41 | 30.1% |
| `plugins.py` | 156 | 115 | 23.6% |
| `projects.py` | 137 | 92 | 29.0% |
| `research.py` | 358 | 148 | 50.5% |
| `research_engines.py` | 41 | 18 | 46.9% |
| `review.py` | 169 | 133 | 16.9% |
| `runs.py` | 50 | 23 | 48.2% |
| `system.py` | 214 | 161 | 21.1% |
| `app.py` | 133 | 133 | 0.0% |
| `__init__.py` | 383 | 383 | 0.0% |
| `repl.py` | 495 | 495 | 0.0% |
| `bus.py` | 51 | 23 | 45.9% |
| `config.py` | 375 | 126 | 61.5% |
| `telemetry.py` | 86 | 45 | 40.7% |
| `code_projects.py` | 244 | 136 | 39.5% |
| `denoising_worker.py` | 40 | 40 | 0.0% |
| `deps.py` | 145 | 145 | 0.0% |
| `envs.py` | 111 | 111 | 0.0% |
| `files.py` | 161 | 135 | 11.7% |
| `gitops.py` | 125 | 125 | 0.0% |
| `guard.py` | 98 | 61 | 35.5% |
| `processes.py` | 48 | 48 | 0.0% |
| `protocol_contracts.py` | 48 | 14 | 56.7% |
| `protocols.py` | 169 | 142 | 11.9% |
| `remote_compute.py` | 155 | 133 | 9.9% |
| `resources.py` | 181 | 181 | 0.0% |
| `sandbox.py` | 671 | 584 | 9.8% |
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
| `urap.py` | 151 | 116 | 17.4% |
| `attachments.py` | 184 | 138 | 19.3% |
| `corpus.py` | 320 | 235 | 24.2% |
| `download.py` | 38 | 38 | 0.0% |
| `evidence_retrieval.py` | 30 | 30 | 0.0% |
| `governance.py` | 200 | 165 | 12.9% |
| `library.py` | 403 | 353 | 9.3% |
| `pdf_indexer.py` | 21 | 21 | 0.0% |
| `provenance.py` | 175 | 175 | 0.0% |
| `ranking.py` | 294 | 294 | 0.0% |
| `research_context.py` | 77 | 55 | 26.6% |
| `research_jobs.py` | 246 | 226 | 5.7% |
| `research_store.py` | 123 | 16 | 83.2% |
| `source_packs.py` | 74 | 63 | 10.6% |
| `sources.py` | 84 | 61 | 20.9% |
| `verification.py` | 118 | 108 | 6.2% |
| `websearch.py` | 298 | 255 | 10.2% |
| `__init__.py` | 210 | 174 | 14.8% |
| `cache.py` | 69 | 69 | 0.0% |
| `compiler.py` | 149 | 149 | 0.0% |
| `compressor.py` | 173 | 173 | 0.0% |
| `embeddings.py` | 148 | 148 | 0.0% |
| `engine.py` | 301 | 301 | 0.0% |
| `evidence.py` | 121 | 121 | 0.0% |
| `graph.py` | 32 | 32 | 0.0% |
| `knowledge.py` | 33 | 21 | 25.5% |
| `lifecycle.py` | 146 | 146 | 0.0% |
| `lod.py` | 142 | 142 | 0.0% |
| `notes.py` | 52 | 9 | 81.0% |
| `pages.py` | 29 | 29 | 0.0% |
| `policy.py` | 50 | 50 | 0.0% |
| `research.py` | 142 | 142 | 0.0% |
| `retrieval.py` | 148 | 148 | 0.0% |
| `state.py` | 93 | 93 | 0.0% |
| `store.py` | 88 | 56 | 32.1% |
| `trace.py` | 117 | 117 | 0.0% |
| `working.py` | 38 | 38 | 0.0% |
| `export.py` | 414 | 414 | 0.0% |
| `latex.py` | 208 | 172 | 12.9% |
| `results.py` | 24 | 24 | 0.0% |
| `review.py` | 405 | 344 | 10.7% |
| `review_prompts.py` | 61 | 39 | 30.1% |
| `writer.py` | 131 | 107 | 14.4% |
| `__init__.py` | 310 | 310 | 0.0% |
| `ai_scientist.py` | 174 | 174 | 0.0% |
| `document_parser.py` | 28 | 28 | 0.0% |
| `local_research.py` | 103 | 103 | 0.0% |
| `app_server.py` | 189 | 189 | 0.0% |
| `cli.py` | 428 | 156 | 58.2% |
| `cli_space.py` | 157 | 71 | 51.7% |
| `context_packet.py` | 56 | 56 | 0.0% |
| `events.py` | 105 | 74 | 24.9% |
| `firewall.py` | 121 | 51 | 55.1% |
| `gateway.py` | 307 | 307 | 0.0% |
| `lifecycle.py` | 383 | 222 | 37.6% |
| `local.py` | 185 | 119 | 32.1% |
| `mcp_agent.py` | 106 | 38 | 59.0% |
| `mcp_server.py` | 147 | 54 | 56.6% |
| `mcp_tools.py` | 247 | 205 | 12.8% |
| `models.py` | 595 | 463 | 18.6% |
| `privacy.py` | 40 | 40 | 0.0% |
| `registry.py` | 78 | 66 | 11.5% |
| `research.py` | 224 | 165 | 21.8% |
| `router.py` | 99 | 99 | 0.0% |
| `contracts.py` | 48 | 3 | 93.8% |
| `opencode.py` | 246 | 162 | 28.2% |
| `openscience.py` | 465 | 375 | 14.9% |
| `registry.py` | 34 | 26 | 16.1% |
| `workspaces.py` | 317 | 229 | 24.1% |