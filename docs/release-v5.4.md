# v5.4.0-preview.1 — supervised capability missions

Audit and threat model: [ADR](adr/2026-10-22-supervised-missions.md). Initial Git snapshot cb0ef5b contains the earlier v5.3 implementation. Installed OpenScience/Feynman help/version were rechecked without inference or modifying native config.

Implemented: typed MissionSpec/Task/ToolCall/ExecutionResult/EvidenceRef/ArtifactManifest; versioned capability descriptors with JSON schemas; legacy Markdown skill descriptor adapter; declarative DAG validation; dependency cycles/unknown hooks/capabilities rejected; deterministic discovery/download/inspect/sync/report; explicit research engine routing and listed fallbacks; per-Topic/project source checks; fixed concurrency 1; digest/expiry approval; bounded attempts/time/reasoning/depth/hops; parent permission restrictions; human-only retry/reconciliation; append-only hash-linked ledger. Existing native adapters and app model transport are reused. No raw shell from model output is accepted.

Use Topics · SKB → Missions or `/mission`. Create a JSON draft, inspect permissions and limits, then approve the exact plan. The existing research worker executes it. Read a failed task result before retry; uncertain admissions must be reconciled first. The service/API requires a fresh approval after retry. Automatic background scientific delegation is disabled.

API under `/api/research`: GET `/mission-capabilities`; GET/POST `/topics/{tid}/missions`; POST `.../missions/plan` (explicit `allow_reasoning: true`; one app-provider call, draft only); POST `.../missions/{mid}/approve` `{plan_digest,note,expires_minutes}`; POST `.../cancel`; POST `.../retry` `{task_id,reconcile_note}`. Sources and child missions must belong to the same Topic. The generated model draft cannot approve itself.

Example deterministic plan:
```json
{"topic_id":"<uuid>","objective":"Inspect and report selected evidence","permissions":["workspace_write"],"tasks":[{"id":"inspect","capability":"paper.inspect","args":{"paper_ids":[],"limit":2}},{"id":"report","capability":"mission.report","depends_on":["inspect"]}]}
```
Discovery adds `paper.discover` (network/workspace_write), then `paper.download` using `args.from_task` and a dependency, then `paper.inspect`. `paper.compare` requires reasoning/network/workspace_write and `preferred_engine: feynman|openscience|app`. Only caller-listed fallbacks are considered. Research engine task workspaces remain isolated admission workspaces; this does not claim all independent native sessions are visible or mutate native project databases.

Migration: existing project `research.sqlite3` advances 1→2 with `research.v1.sqlite3.bak`. Mission/task/admission/ledger tables are additive. Stop the app and retain the whole project backup to roll back to v5.3 (restore the v1 database backup as well as code). Earlier code deliberately refuses newer DB versions.

Validation: `tools/run_tests.py test_missions test_research_workspace test_skills test_orchestrator`: 47 tests, OK with one Windows symlink privilege skip. The focused mission rerun: 8/8 passed. Frontend regression: 94/94 passed. Tests cover no-LLM deterministic work, hashes/reports, scope, malicious manifests/cycles, expiry, uncertainty/retry, missing engines, explicit fallback and delegation caps. Default CPU/GPU experiment capability is disabled until v5.5 acceptance. Live model/native research execution and full scientific end-to-end acceptance remain external gates, not claimed by offline tests. This preview is ready for bounded manual plans; not a claim of production autonomous science.

Sample evidence: successful deterministic missions save SHA-256 manifests at `workspace/research/missions/<uuid>/evidence-report.json`, with scientific review pending. The ledger preserves admissions/decisions. On restart, running admissions become interrupted; completed tasks remain untouched. No new daemon or tracker is installed.
