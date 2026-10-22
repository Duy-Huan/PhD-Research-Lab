# Supervised missions, fixed protocols and scientific governance

Audit baseline: v5.3.0-preview.1 commit cb0ef5b, on feature/v3.2-research-os; upgrade documents were added separately by the user at ecbe70c. The documents are specifications, not evidence of integrations or authority to spend tokens/GPU.

| Area | Existing implementation | Gap / decision |
|---|---|---|
| Procedures | agent/skills.py Markdown catalog, plugins snapshots | Add versioned capability descriptors and validated declarative DAG manifests; never execute supplied hooks/code |
| Runs | agent/runs.py durable linear pipelines, idempotency, approvals | Keep legacy runs; add Topic mission DAG records in the existing SQLite store, driven by the existing research I/O worker |
| Engines | research_engines contracts/registry + native workspace reconciliation | Invoke existing typed engine port only after explicit permission; never infer external transcript completeness |
| Compute | execution/sandbox.py Python/Docker, guard.py, resources.py, ClearML tracker | Preserve custom research execution. New fixed-protocol acceptance uses a trusted CPU denoising runner; arbitrary code generation/GPU remains disabled in the new loop |
| Corpus | knowledge/research_store.py, corpus.py, scoped page evidence | Reuse source IDs and topic checks; mission observations are not trusted memory |
| Decisions | findings human review + events | Add claim lifecycle, deterministic checks, append-only hash-linked decisions with tamper detection |
| UI | Vanilla PL, research drawer, one composer | Extend existing drawer/action registry with Missions, Experiments, Review Room |

Installed CLI probes (2026-10-22): OpenScience 2.0.152 `web [project]`; Feynman 0.5.51 `--cwd`, `--session-dir`. Version/help probes used temporary OpenScience config, changed no user engine settings and submitted no inference. Existing official SDK capability/receipt qualification remains authoritative. Engines remain sibling adapters. Native external private sessions remain unknown.

Minimal architecture: schema migrations with SQLite backup → typed mission/task/capability contracts → explicit permission snapshot and plan digest approval → deterministic worker dispatch → structured evidence/artifacts → immutable experiment protocol → independent verifier → human decision. No new daemon, tracker, vector store or agent framework.

Threats: malicious skill DAG (reject unknown fields/capabilities/cycles), forged approval (approval comes only from API, expires and binds a digest), retrying uncertain effects (pause and require reconciliation), topic spill (all source and entity lookups constrained by Topic/project), protocol drift (hash/approval lock), fabricated metrics (recompute from per-sample artifacts and independent execution), fake citations (local metadata is not authoritative DOI resolution), reviewer self-certification (deterministic checks cannot claim methodology validity), ledger tampering (hash-chain verification; not OS-admin-proof immutability).

Milestones: v5.4 mission core + contract/recovery acceptance; v5.5 immutable CPU protocol + real multi-seed benchmark/reproduction; v5.6 evidence checks + claim decisions + adversarial tests. External-dependent features stay disabled with explicit reasons until qualified. Each version receives its own commit, release guide, rollback/migration notes and test evidence.
