# v6 upgrade handoff

Delivered as separate opt-in preview milestones: v6.0 supervised charters/lifecycle, v6.2 logical team harness and bounded reassignment, v6.3 durable workstream collaboration. The missing v6.1 assumption was implemented through compatibility models on existing tasks rather than a second orchestrator. Readiness audits, release guides and architecture/API/operator docs are under `docs/audits`, `docs/release-v6.*`, and `docs/architecture`.

Restart PhD Lab to load the new backend/frontend, then open `/monitor`, `/team`, `/workstreams` inside the chat UI. All three Research OS flags default false; enable only the desired features, create an editable draft, review exact permissions/providers/billing/resources and approve it. A final technical review and separate scientific claim approval remain distinct. Existing legacy runs, chat, `/skills`, Paper Explorer, SKB, memory, independent native workspaces and custom Python/Docker routes are retained.

The repeatable entry point is `.venv/Scripts/python -B tools/research_harness.py --stage 6.3`; `--stage 6.2` compares single/fixed/adaptive logical roles; `--stage 6.0 --probe-engines` adds isolated help/version probes. Running a prior stage under newer code records the current application version; committed earlier artifacts retain the original milestone measurements. Harness state is isolated and generated artifacts under the selected version folder are overwritten intentionally. No live model call is needed.

Current single-machine policy: one task at a time, existing global hardware slots, finite generated CPU protocol, per-Mission/charter/workstream limits, conservative PDF/observation preflight and observed artifact bytes. Storage counters cover declared artifacts/observations and newly stored PDFs, not an OS filesystem quota for SQLite/index/log overhead. External workspace scans observe files without claiming ownership of external storage. Do not treat these controls as a general OS sandbox for arbitrary code.

Next qualification: manually review a real bounded Topic using explicitly selected native providers/billing budgets; verify lawful source access and current adapter receipts; qualify pinned Docker cancellation/containment and a licensed dataset; evaluate multi-team benefit on real model tasks before adding parallel execution. Remote team identity and multi-Topic execution within a single Mission need a new authenticated contract. Preserve the current default-deny behavior and scientific verification gates.

Schema advances: 4→5→6→7 with versioned SQLite backups. Stop the app and archive complete data/artifacts before restoring the matching older DB/code. Never discard new scientific decisions or open a new schema with older code. Original audit files/raw arrays are retained in harness ZIPs; portable JSON redacts temporary paths.

Direct upgrades retain the actual prior schema backup (for v5.6, `research.v4.sqlite3.bak`) and jump directly to schema7. They do not create hypothetical intermediate backups for versions never run against that project.

Final measured tests and limitations: [validation](../artifacts/v63/validation.md). The stable scientific-autonomy release gate remains open; this is not a claim of guaranteed discovery, peer review or 24/7 cloud operation.
