# v5.6.0-preview.1 — scientific verification and decision governance

This release implements supervised v5.4 Missions, the v5.5 fixed CPU experiment capability and v5.6 scientific review. It is a qualified preview of these bounded workflows. General autonomous science, automatic publication and arbitrary model-generated code execution through Missions remain disabled.

## Audit and implementation

The repository audit, gap decisions and initial threat model are in [the ADR](adr/2026-10-22-supervised-missions.md). Prior milestones have separate [v5.4](release-v5.4.md) and [v5.5](release-v5.5.md) release guides. Existing central chat, `/skills`, native workspace adapters, custom Python/Docker experiments, provider paths, SKB, ClearML and memory routes are preserved.

| Gap at v5.5 | v5.6 implementation | Limit |
|---|---|---|
| Agent prose could be mistaken for evidence | Strict claim/evidence inputs; source claims, measurements and interpretations have distinct kinds | Natural language entailment requires scientific review |
| Page citation lacked an independent review record | Scoped chunk/version/page, exact quote span, document/chunk hashes, extraction method and provenance snapshot | Source parser accuracy is not independently certified; scanned PDFs need OCR |
| Local DOI metadata could be invented | Explicit Crossref resolution, DOI/title/ordered-author matching and persisted response digest | Crossref registration is not proof of the underlying claim; unsupported registries remain unverifiable |
| Metrics were reported by the worker | Separate deterministic metric/method/split/sample/artifact checks | Only the registered generated denoising fixture is qualified |
| Reproduction could be inferred from text | New approved run, distinct nonce, matching trial artifacts; both runs revalidated | Same machine and generator; not an independent laboratory replication |
| Human decisions could overwrite history | Immutable claim/evidence revisions and hash-linked decision events | Local trusted researcher identity, not multiuser authentication or OS-admin-proof storage |
| Manuscript export could hide pending claims | Verification-status appendix across manuscript formats; approved claims rechecked | It covers registered claims; arbitrary unregistered manuscript sentences are not automatically extracted |

Key files: `backend/knowledge/governance.py`, `verification.py`, `research_store.py`, `research_context.py`; `backend/api/research.py`; `backend/agent/decision_ledger.py`, `policy.py`; `backend/paper/export.py`, `backend/api/plugins.py`; `frontend/assets/research.js`, `tools.js`; adversarial tests and `tools/acceptance_v56.py`. No new dependency or daemon was added.

Additional hardening: discovery returns all scoped matched paper IDs including duplicates; a Mission discovery never starts implicit Topic auto-download; a requested PDF prevented by quota cannot be reported as a completed download. Child missions charge reasoning calls and elapsed execution to all ancestors; aggregate hop reservations remain bounded. Missing Docker qualification is recorded as a failed trial instead of leaving it running. SQLite metadata is updated alongside the authoritative `user_version`.

## Evidence and lifecycle

`ClaimInput` accepts `text`, `kind`, and up to 20 strict `EvidenceInput` entries. Each evidence entry has `source_id`, an optional exact `quote`, expected DOI/title/authors/version/page and an optional structured `paired_psnr_gain_db` assertion with finite `value`. The service, not the caller, adds provenance and hashes. A claim cannot substitute another claim for primary evidence.

Evidence snapshots are immutable. Page evidence additionally captures the original document/chunk SHA256, version, page, section, extraction method, observed time, source download/license record and untrusted status. Measured evidence captures protocol digest and artifact manifests. New claim text creates a new ID with `parent_id`; it never erases the prior claim. Original corpus document metadata remains accessible through scoped source/version IDs.

Lifecycle: `proposed` (no evidence) → `sourced` → `independently_checked` → explicit `human_approved`. Failed checks produce `contested`; unverifiable checks keep the claim sourced. Human reject/contest/retract/reopen append decisions. Rejected/retracted claims must be reopened or amended before checking. Approval reevaluates evidence, requires no critical/unverifiable gaps, and binds the current check digest. Retraction, evidence drift or metric discrepancies invalidate prior approval on recheck/export/context use. Checks do not execute instructions embedded in papers.

No raw paper, experiment measurement, model statement or reviewed claim is automatically copied into trusted project memory. Explicitly selected claims may enter Topic chat as untrusted context with their status and source IDs. Human approvals are available only through researcher controls/API, outside agent write-tool grants. The app is a local trusted-user application: someone with direct API/OS access acts as that researcher, so this is not a security boundary against an administrator or malicious code already running under the user account.

## Verification matrix

| Check | Evidence and failure behavior |
|---|---|
| DOI identity | Explicit network receipt; no receipt/unsupported registry → unverifiable; DOI/title/authors mismatch → failed |
| Quote trace | Exact page/chunk span, version/page assertions, persistent file/chunk hashes; unavailable source → unverifiable, wrong quote/hash → failed |
| Source risk | Retraction, expression of concern or uncertain-rights flag → failed; local sources without DOI explicitly assert only local identity |
| Dataset and leakage | Fixed recipe/license/code digest, regenerated sample arrays, disjoint registered train/validation/test IDs |
| Fair baseline/method | Actual noisy-input baseline, identical seeds/samples, independent smoothing conformity, registered validation trial sequence and stopping rule |
| Numerical integrity | Raw arrays finite/shape/sample checks, independently recomputed MSE/PSNR/per-seed summaries/gain/approximate interval/recommendation |
| Held-out discipline | Validation alone selects; selected method and baseline have held-out measurements; test never drives selection |
| Artifact integrity | Local owned path, SHA/bytes and retained logs; missing/corrupt output/logs fail |
| Reproduction | Separately admitted run/nonce and identical hashes; peer artifacts also pass independent checks; no second run → unverifiable for experiment claim approval |
| Statistical uncertainty | At least three distinct seeds, all paired gains positive and pre-registered threshold for a candidate recommendation; small-n intervals explicitly approximate |
| Novelty | Bounded local Topic retrieval and contested-term overlap with coverage disclaimer; never a binary originality certificate |

An `independently_checked` label means these bounded deterministic checks passed, not that a model or software performed peer review. Semantic contradiction detection, causal validity, confounders, external dataset/model lineage, publication-ready statistics and broad prior art coverage require human/domain review. Optional LLM reviewing is not used as the approval oracle.

## Operations and API

Use **Topics · SKB → Review Room** or `/claims`. Propose a JSON claim using exact source IDs and quotes or an experiment run/metric/value. Read evidence beside its checks. Resolve DOI metadata only through **Resolve DOI · network** (explicit network action), then **Check evidence**. A decision requires a human note. Source page links, measured verification links, claim status export and audit inspection are available. **Use in chat** selects the claim without starting an AI turn. The existing composer is preserved.

All routes below are scoped under `/api/research/topics/{tid}`:

- GET/POST `/claims`; POST may include `?parent_id=<prior-claim-id>` for amendment.
- POST `/claims/{cid}/check`; POST `/claims/{cid}/decision` with `{action: approve|reject|contest|retract|reopen, note}`. A caller-supplied actor/status is rejected.
- POST `/citations/resolve` with `{doi, allow_network: true}`; no hidden lookup on checks.
- GET `/experiments/{rid}/verification`, `/prior-art?q=...`, `/audit`, `/claims/export`.

Crossref uses its documented [`/works/{doi}` singleton endpoint](https://www.crossref.org/documentation/retrieve-metadata/rest-api/). Metadata resolution has no inference calls. Failure stays visible and never fabricates a receipt. The receipt stores response digest and source URL, not a claim of scientific verification.

Existing `/api/export` accepts optional `topic_id`. Topic chat exports include that Topic's registered claims. Project-level exports without a Topic include registered claims in the current project. Pending/rejected/retracted statuses are explicit in Markdown, LaTeX, HTML, Word and the HTML sent to the PDF renderer. Browser PDF production remains separately environment-dependent. No submit/publication endpoint is enabled.

## Acceptance evidence and executed validation

Run `.venv/Scripts/python -B tools/acceptance_v56.py`. It uses a temporary application data directory and preserves compact output in [`artifacts/v56`](../artifacts/v56/). It never changes user projects, native engine configuration or provider credentials.

The recorded six-step Mission discovers **10 fixture metadata records**, downloads/links **2 fixture PDFs**, inspects and compares them, runs **real CPU denoising subprocesses**, then writes its report. Scholarly transports and the single comparison response are explicitly mocked. Both PDF links deliberately share bytes to exercise content deduplication. The same fixed protocol then runs a second time with a new approval nonce and fresh processes. Independent verification passes; fabricated quote evidence becomes contested; audit chain validates. Human approval in this harness is explicitly simulated, not a real scientific endorsement.

Evidence files: `acceptance.json` has mission/task admissions, approvals, run/protocol digests, measurements, verification and audit events; `observations.zip` retains requests, raw observations and stdout/stderr for both runs; `scientific-review.md` demonstrates statuses/provenance. CPU measurements are real; source publications and reasoning transport are fixtures. The script is reproducible and overwrites only these generated acceptance files.

Tests cover fake/unresolved DOI, wrong title/authors/page/quote, retracted source, prompt instructions embedded in PDF text, invented numerical prose, corrupt original/reproduction artifacts, missing logs, falsified reported metrics, worker drift, invalid splits/GPU/limits, duplicate compute approvals, immutable revisions, forged actor/status, audit tampering, Topic isolation, ancestor quota accounting, restart/reconciliation, schema backup and existing UI/export/provider behavior. Final focused regression: **88 tests OK (1 privilege skip)**; frontend: **96/96 passed**. Full sandbox discovery: **614 tests, 606 passed, 7 skipped, 1 browser-PDF error**; that exact PDF test passed independently outside the process sandbox. Detailed commands, counts, coverage limits and observations are recorded in [validation.md](../artifacts/v56/validation.md).

## Migration, rollback and external gates

SQLite schema 3→4 adds scientific claims, immutable evidence, checks and citation receipts plus mutation guards. Before migration, `research.v3.sqlite3.bak` retains the old database; older schemas similarly retain their own versioned backup. Topic/corpus/workspace/run data is preserved. Existing protocol payloads become immutable while their human approval field can still change. The migration test verifies Topic retention, v3 backup contents, schema4 metadata and new tables.

Rollback: stop the application and retain the whole project directory, including research artifacts and current DB. Check out the chosen prior version, then restore that version's matching `workspace/research/research.vN.sqlite3.bak` as `research.sqlite3`. A v5.3 rollback needs schema1, v5.4 schema2, v5.5 schema3. Do not open a newer DB with older code; the runtime rejects it. Decisions created after the backup must remain archived rather than silently merged into the old schema.

Unqualified/disabled paths: arbitrary model-generated scientific code in Missions, autonomous agent delegation, GPU trials, external datasets/weights, live Docker resource/cancellation acceptance, live paid/native reasoning, live scholarly retrieval/citation service availability and manual browser visual QA. Native CLI version/help probes alone do not establish scientific acceptance. Local Python fixture execution is trusted finite code, not an OS network/memory sandbox. Hash-linked audit detects ordinary edits but an OS administrator can replace the whole database; retain separate backups. Existing custom workflows remain available under their prior controls.

Next handoff: qualify live scholarly sources and native CLI receipts with explicitly chosen providers/budgets; qualify pinned Docker containment/cancellation and a licensed external dataset; add independent semantic reviewers and domain-specific methodology checks. Expand automation only after these gates have evidence. There is no general autonomous research or peer-review guarantee in this preview.
