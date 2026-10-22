# v5.3.0-preview.1: operation, recovery and extension

This is an additive implementation of the v5.1–v5.3 core, with optional catalog items still gated. The v5.1 plugin/source documents are catalogs, not a requirement to install every listed tool. No user configuration, credentials, native engine database, existing library or project memory is rewritten by this upgrade.

## Use the workspace

1. Start with `run.bat` (or `.venv/Scripts/python -B start.py`). Open **Topics · SKB** and create a Topic. Configure keywords, synonyms, exclusions, source IDs, year, quotas and cadence.
2. **Open Topic** creates a separate topic-bound conversation. The header shows its Topic; opening an older project conversation returns to project scope. Switching Topic clears selected sources and pending attachments. Existing project chats remain available.
3. **Discover now** queues deterministic metadata discovery, using the existing OpenAlex/arXiv/Semantic Scholar clients plus Crossref. **Dry run** makes no network calls. A provider failure leaves other results available and is recorded in the job. Per-run metadata count is enforced across sources, not independently per provider.
4. Search/filter/sort/page through the local corpus. Select candidates to accept, defer or dismiss, associate with another Topic, or queue OA PDFs. Dismissal is recoverable through the Dismissed filter. Selecting a paper makes no model call.
5. **OA PDF** resolves provider-declared OA locations; Unpaywall additionally uses `search.mailto` when configured. Crossref publisher links alone never authorize a PDF download. Restricted/HTML/oversized/private-network downloads fail with metadata preserved.
6. **Versions & evidence** shows source versions, document/checksum/parser state and stored PDFs. Search page evidence to inspect exact version/page references. Some records remain abstract-only. Scanned/formula/table extraction may be incomplete.
7. **Accept** opts a record into this Topic's BibTeX export. **L4 attest** requires your review note and means user review, not scientific validity. The attestation records the reviewed versions and metadata hash. A new source version resets L3/L4 processing status with an audit event and retains prior review evidence; it requires another review. Downloading/indexing never adds a record to `library.json` or trusted memory. L3 is explicitly a metadata/extraction rule screen, not a methodology verdict.
8. **Compare/Review with AI** fills the existing composer with selected source IDs; **Send** executes the actual registered skill instructions through the normal provider. Topic review/comparison/literature skills run as scoped chat synthesis. Project-changing/code/compute run skills require a project conversation until the existing run engine supports Topic scope. MCP tools and automatic memory extraction remain disabled inside Topic chat because their current contracts are project-scoped.

`/find`, `/topic`, `/project`, `/workspace`, `/sync`, `/artifacts`, `/jobs`, `/downloads`, `/library` and `/settings` are whitelisted deterministic UI contributions. In terminal chat they produce local navigation guidance and never fall through to an LLM. Existing AI skills stay registered separately. UI feature flags live in `/api/config` → `ui`: `paper_explorer_v2`, `discovery_inbox`, `contextual_actions`, `topic_scheduler_ui`.

## Native workspaces and offline synchronization

In the Workspaces drawer, create a managed folder or link an **existing absolute folder**. Managed paths are `<existing-project>/topics/<topic-uuid>/<engine>_prj`. The bridge does not initialize undocumented engine internals. Both engines are siblings; either may be absent.

OpenScience 2.0.152 documents `openscience web [project]`. **Open OpenScience** uses that native command with exact cwd and no inherited PhD Lab API keys. Windows opens a separate visible PowerShell terminal, retaining native authentication/startup diagnostics; other platforms retain a local launch log. `started` acknowledges process/window creation, not a validated model connection. On Windows the wrapper remains open for diagnostics even if its child engine exits. Duplicate detection covers processes launched by this backend instance. It cannot identify every independently launched process after a backend restart.

Feynman 0.5.51 documents `--cwd`. **Open Feynman** now opens a separate interactive terminal on Windows with the registered workspace cwd. Other platforms return a safely quoted command to run in your own terminal. Native authentication stays with Feynman. The backend does not claim private session access. Use the **OpenScience · Feynman** sidebar entry; **Open in VS Code** opens the same registered folder in a separate editor window. These windows open on the server computer. See the [current workflow guide](../FRONTEND_WORKFLOW_REVIEW.md) and [model/MCP configuration](../MODEL_RESOURCES.md).

The installed OpenScience default CLI currently fails with `EEXIST` at its user config directory. A temporary isolated environment successfully returned version/help, but this upgrade does not repair engine settings. Native interactive/browser launch must be accepted on the user's configured environment before calling the integration production-ready.

Work in either native engine with PhD Lab closed. On return, choose **Sync Now** or configure a per-workspace interval. Sync is deterministic Python, never an AI agent:

- Inventory allowlisted persisted files; skip hidden/temp/build/venv/cache directories and links/junctions. Check stable timestamps, open-file identity and pre/post-write signatures before registration.
- At most 10,000 directory entries, 2,000 files, 20 seconds inventory, 32 MB per content hash and 64 MB hashed per scan. These are implementation bounds, not a complete native event capture guarantee.
- Larger/checkpoint files retain path/size/source timestamp and `hash_status=not_computed`; bytes are not copied or embedded. Their metadata signature is not presented as a SHA-256.
- Register content hashes and versioned artifact records. Small plaintext files retain a bounded observed excerpt for FTS retrieval; the excerpt is untrusted source data, not a research finding. Binary/PDF artifact reading is explicit; no discovered program is executed.
- Append tombstones when a complete scan establishes absence. Partial, denied or unstable inventories never tombstone unseen files. No scientific history or native file is deleted.
- Inspect the transparency report: complete/partial/failed, changed/deleted/observed counts, skipped/error/unstable files, last success, hashing budget and observation limits.

An excerpt preserves the historical observation after a native file changes. Other historical binary versions are hash/path references; the bridge does not retain a full copy of every binary. A changed current file must be synced before direct reading/citing. Native sessions, hidden internal DBs, private reasoning, unsaved activity, intent and hypothesis changes are **unknown**. No experiment metric is inferred from a filename.

**Relink / schedule** validates another existing folder and retains workspace identity/history; it never moves or deletes files. Old snapshots/source pointers remain auditable. A subsequent sync reconciles the new folder. Overlapping workspaces, project/application roots, cross-project ownership and link escapes are rejected.

## Storage, migration and recovery

| Path within existing project | Ownership |
|---|---|
| `workspace/research/research.sqlite3` | Schema-versioned SQLite metadata, aliases/versions, Topic associations, FTS evidence, jobs, findings, artifact history, checkpoints, ledger |
| `workspace/research/objects/<sha256>.pdf` | Shared within project; one verified PDF object for identical bytes |
| `workspace/research/launch-<workspace-id>.log` | Local native launcher diagnostics |
| `workspace/research/hpo/` | Explicitly approved Optuna study storage and manifests |
| `workspace/research/models/docling/` | Optional operator-provisioned local parser artifacts |
| `topics/<topic-id>/<engine>_prj/` | Engine-owned native workspace; PhD Lab does not mutate internals |

Each existing project receives an opaque identity in its new store only when the research workspace is used. No old folder, metadata ID, chat session or memory record is moved. **Import existing library** adds idempotent metadata records, without inferring L4 or copying/moving legacy PDFs. Existing library PDFs can still be opened using the old Library UI.

The FastAPI lifespan owns one deterministic research I/O worker across registered projects. Queued jobs persist; jobs left running at restart become **interrupted**, and **Retry** is explicit. Unknown network admissions are not silently repeated. Source requests/downloads have timeouts; default parsing runs in a disposable 45-second subprocess with at most 120 pages / 2 million retained text characters. Docling has a separate 180-second subprocess limit. These are process/time/output bounds, not an OS memory sandbox. Cancellation is checked between stages/files; an active network operation or parser can finish its bounded operation before settlement.

Schedules are UTC, opt-in, daily or weekly; the UI shows actual last status and next eligible run. Pausing stops future scheduled discovery; use **Cancel** for a currently running job. One active job per Topic/kind prevents duplicate submissions. Sync schedules are independently configured. Errors/partial jobs retain metadata and may be retried. Jobs publish status through the existing application event bus; Refresh also reads persisted state.

Back up the **entire project folder** with PhD Lab stopped, including SQLite and PDF objects. Source files/native workspaces remain intact. To roll back the preview, restore the earlier application and retain the new `workspace/research/` and `topics/` directories as an archive; old features continue using their existing files. Never edit the DB while the worker is active. Newer unsupported SQLite schema versions are refused instead of overwritten.

## Optional v5.1 integrations

- **Zotero:** import CSL JSON or Zotero JSON export (≤5 MB, ≤1,000 records) into a Topic; attachment/note records are ignored. This is read-only interchange. Accepted records export BibTeX for deliberate Zotero import. The later reconciliation adds explicit read-only Local API sync while Zotero is running; authenticated Web API sync and remote writes remain outside the adapter. See [current reconciliation](../upgrade-reconciliation.md). No API key is harvested.
- **Docling:** optional, not installed here. Install it deliberately in the app environment and pre-provision its model artifacts in the cache above. Select Docling in Topic settings. Worker uses CPU, disables OCR, requires local artifacts and sets Hugging Face offline variables. Missing models/dependencies fail explicitly; switch to the default parser or retry. Real Docling formula/table/OCR quality acceptance remains pending.
- **Optuna:** installed 5.0.0 in the observed environment. Trusted experiment code can call `backend.plugins.local_research.run_optuna(objective, name=..., approved=True)` from the existing approved compute executor. Default is refused without approval; one study admits at most 10 total trials, one worker, configured seed, SQLite resume and a provenance manifest. The existing executor must enforce hard objective CPU/GPU/time limits. An objective can outlive Optuna's trial-admission timeout; no extra daemon is started. Trial history resumes; exact sampler RNG continuity is not claimed.
- **phd-skills / research-plugins:** existing Settings → GitHub plugin importer remains the integration path. Install a reviewed public repository explicitly. Nothing in this upgrade silently copies hooks, executes a third-party installer or grants permissions. Existing plugin guard tests cover snapshots/skills; a live repository skill acceptance is still pending.
- **ClearML, providers, Docker, VS Code, memory:** reuse existing contracts. No competing tracker/vector database is installed.

Consult `/api/research/capabilities` or **Local integration status** for actual dependency states. Installed does not mean live-qualified.

## Adapter extension guide and remaining gates

Discovery is in `backend/knowledge/sources.py`; reuse existing websearch clients and return normalized metadata/declared OA locations. Add a reviewed provider ID to the allowlist only with response-contract, credential, rate-limit, legal-download and failure tests. All URLs still pass through the bounded public downloader. Source text never changes agent permissions.

Workspace integration lives beside existing engine task adapters in `backend/research_engines/workspaces.py`. Extend capabilities only with a verified documented native API, preserve explicit fidelity labels, store cursors/checkpoints transactionally and keep file reconciliation available after disconnect. The existing OpenScience admitted-session runtime adapter remains separate and unchanged; its receipt/replay semantics cannot be generalized to all external sessions.

Deferred: live source acceptance and rate-limit tuning; CVF/PMLR/OpenReview/NeurIPS and discipline-specific source packs; local vector retrieval/reranking; citation graph/retraction refresh; live Zotero sync; Docling quality benchmark; full native-session observation where officially supported; Topic-scoped compute/run execution. P1/P2 optional engines/tools require demonstrated research need and separate integration acceptance. This preview does not claim complete implementation of those catalog entries.

References checked during implementation: [Crossref REST](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [Unpaywall API](https://unpaywall.org/products/api), [Zotero API/read-only local access](https://www.zotero.org/support/dev/web_api/v3/basics), [Docling converter](https://docling-project.github.io/docling/reference/document_converter/), [Optuna SQLite resume](https://optuna.readthedocs.io/en/stable/tutorial/20_recipes/001_rdb.html). Engine capabilities were checked against installed CLI help and the prior [OpenScience audit](../openscience-integration.md).
