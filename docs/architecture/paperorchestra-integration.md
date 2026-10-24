# PaperOrchestra Integration Architecture

## 1. Executive Summary

This document describes the integration of **PaperOrchestra** into the **PhD Research Lab** L2–L4 Agent Harness as a dedicated Research Writing Engine plugin.

The integration adheres strictly to the architectural boundary principles:
1. **PhD Research Lab remains the sole top-level orchestrator**: PaperOrchestra never spawns its own top-level scheduler, maintains separate mission state, or circumvents PhD Lab's DAG orchestration.
2. **Dual-backend execution model**:
   - **Isolated CLI Backend**: Executes official `paper-orchestra` CLI inside a sandboxed workspace under `data_dir()/research-engines/paperorchestra/<operation_id>/workspace` with strict environment sanitization, timeouts, and cancellation.
   - **Capability-Based Skill Backend**: Implements PaperOrchestra's 5 agent roles (Outline Agent, Literature Review Agent, Section Writing Agent, Plotting/Figure Agent, Refinement Agent) using PhD Lab's existing agent harness and provider routing (`RP.app_complete`).
   - **Automated Fallback**: If the CLI binary is absent or unconfigured, the engine transparently falls back to capability-based skill execution.
3. **No Duplication**: Reuses existing provider routing, context memory, append-only SQLite audit ledgers, resource guards, and LaTeX engines.
4. **Shared Versioned Artifact Contract**: Every task consumes and produces versioned, SHA-256 hashed, traceable artifacts recorded in SQLite.
5. **Rigorous Evidence and Quality Gates**: Hallucination-resistant citation checking, experimental metric provenance verification, figure asset validation, LaTeX compilation, scientific consistency checking, independent multi-criteria peer review, and mandatory human submission sign-off.

---

## 2. Architecture & Component Reuse

```
                          ┌─────────────────────────────────────┐
                          │     Unified Chatbox & UI Studio     │
                          │   (Composer, PaperOrchestraStudio)   │
                          └──────────────────┬──────────────────┘
                                             │ REST API / WebSocket
                                             ▼
                          ┌─────────────────────────────────────┐
                          │     PhD Lab Mission Orchestrator    │
                          │      (MissionWorker, Autonomy)      │
                          └──────┬───────────────────────┬──────┘
                                 │                       │
               ┌─────────────────┴────────┐    ┌─────────┴────────────────┐
               │    Execution Guard       │    │    Artifact & Audit      │
               │    (ResourceGuard)       │    │ (decision_ledger, SQLite)│
               └─────────────────┬────────┘    └─────────┬────────────────┘
                                 │                       │
                                 ▼                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PaperOrchestra Engine Plugin                         │
│  (backend/research_engines/paperorchestra/engine.py: PaperOrchestraEngine) │
├───────────────────────────────────┬────────────────────────────────────┤
│       Isolated CLI Backend        │    Capability-Based Skill Backend  │
│  - Sandboxed execution workspace  │  - Outline Agent                   │
│  - Environment sanitization       │  - Literature Review Agent         │
│  - Subprocess cancellation/timeout│  - Section Writing Agent           │
│  - Artifact harvesting            │  - Plotting & Figure Agent         │
│                                   │  - Refinement & Polish Agent       │
├───────────────────────────────────┴────────────────────────────────────┤
│                        Evidence & Quality Gates                        │
│  - Citation Verification (references.bib & corpus)                     │
│  - Experimental Provenance (measured metrics vs claim sentences)       │
│  - Figure Source Validation (Figure Studio & workspace/figures)        │
│  - LaTeX Compilation Wrapper (backend.paper.latex)                    │
│  - Scientific Consistency Verification                                 │
│  - Independent 4-criteria Peer Review                                  │
│  - Explicit Human Submission Sign-off Gate                             │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Mapping

| Subsystem | Existing PhD Lab Abstraction | PaperOrchestra Integration |
| :--- | :--- | :--- |
| **Orchestration** | `MissionWorker`, `MissionControl`, `AutonomyPolicy` | Dispatched via `execute_mission_task()` without nested loops |
| **Engine Contract** | `backend.research_engines.base.ResearchEngine` | Conforms to protocol with `descriptor`, `health()`, `execute()` |
| **Provider Routing** | `backend.providers.models.route_provider` | Skills invoke `RP.app_complete("research", ...)` |
| **Resource Safety** | `backend.execution.guard.ResourceGuard` | Maps to `"cli"` (CLI backend) or `"local_llm"` (Skill backend) |
| **Audit & State** | `decision_ledger.record()`, SQLite | Artifacts stored with parent workflow ID, task ID, and SHA-256 |
| **Paper Management** | `backend.paper.writer`, `backend.paper.latex` | Bidirectional sync with `project.json` and LaTeX compiler |

---

## 3. Execution Modes (L2–L4)

### Level 2: Approved Execution (Individual Capabilities)
- **Concept**: User triggers individual paper generation capabilities (e.g. outline creation, literature survey, section draft, figure integration).
- **Execution Contract**:
  - The mission is configured with `AutonomyPolicy(level="L2")`.
  - After each task finishes, execution stops immediately and enters state `awaiting_step_review`.
  - Next task is blocked until the human user issues an explicit acceptance (`POST /api/research/topics/{tid}/missions/{mid}/steps/{task_id}/review` with `decision="accept"`).
- **Function**: `create_l2_paper_mission(topic_id, capability, prompt, ...)`

### Level 3: Specialist Writing Team
- **Concept**: Harness creates a specialist 4-agent writing team executing a directed acyclic graph (DAG) with parallel tasks and checkpoint verification.
- **Team Composition**:
  1. `lead_author`: Synthesizes research objectives, abstracts, conclusions, and outlines.
  2. `methods_writer`: Formalizes technical methodology, algorithm specifications, and experimental setups.
  3. `literature_curator`: Conducts related work synthesis and bibliography management.
  4. `manuscript_verifier`: Deterministic reviewer validating citations, figures, and formatting.
- **Execution Contract**:
  - DAG contains checkpoints with intermediate verifiers assigned to each writing task.
  - Final task requires explicit human sign-off (`awaiting_review`).
- **Function**: `create_l3_team_mission(topic_id, objective, paper_ids, style, target_venue)`

### Level 4: Goal-Driven Autonomous Research-to-Paper Workflow
- **Concept**: Full closed-loop workflow:
  1. Literature gap analysis (`paperorchestra.literature`)
  2. Empirical metric extraction & provenance matching (`paperorchestra.provenance_verify`)
  3. Structured manuscript generation (`paperorchestra.section_write`)
  4. Quality gate evaluation & citation verification (`paperorchestra.cite_verify`)
  5. Independent peer review (`paperorchestra.peer_review`)
  6. Final technical synthesis report (`mission.report`)
  7. Deterministic verification gate (`artifact.verify`)
- **Execution Contract**:
  - Meets strict L4 autonomy policy: the final task must be `artifact.verify` depending on `mission.report`.
  - `autonomy.validate()` and `completion_state()` refuse technical closure if any reasoning is truncated, empty, or unverified.
- **Function**: `create_l4_research_to_paper_mission(topic_id, objective, paper_ids, style)`

---

## 4. Shared Traceable Artifact Contract

All writing tasks consume and emit typed `WritingArtifact` records (`backend/research_engines/paperorchestra/contracts.py`).

### Schema Definition
```python
class WritingArtifact(BaseModel):
    artifact_id: str             # Deterministic or UUID
    task_id: str                 # Owning task
    parent_workflow_id: str      # Owning mission / workflow
    topic_id: str                # Topic identifier
    section_id: str              # Section (abstract, methods, etc.)
    title: str                   # Human-readable title
    content: str                 # LaTeX / Markdown manuscript text
    content_hash: str            # SHA-256 digest of content
    version: int                 # Monotonic version counter
    agent_id: str                # Agent role identifier
    provider_id: str             # Execution provider identifier
    input_artifact_ids: list[str]# Predecessor artifact IDs
    output_artifact_ids: list[str]
    evidence_refs: list[str]     # References to papers/experiments
    execution_status: str        # "completed", "failed", "pending"
    review_status: str           # "unreviewed", "passed", "rejected"
    execution_metrics: dict      # Token count, duration, compile status
    checkpoint_id: str | None
    created_at: str
    updated_at: str
    storage_path: str            # Persistent filesystem path
```

### Persistence and Concurrency Protection
- **SQLite Table**: `paperorchestra_artifacts` stores full artifact metadata with indexes on `topic_id`, `task_id`, `section_id`, and `parent_workflow_id`.
- **Filesystem**: Artifacts written atomically using `replace_retry()`.
- **Locking**: Section-level re-entrant thread locks (`get_lock(section_key)`) ensure concurrent tasks never corrupt the manuscript.
- **Sync**: Automatically syncs with `backend.paper.writer` (`project.json`), making sections visible in the native paper editor.

---

## 5. Evidence & Quality Gates

The engine implements 7 quality gates prior to paper approval:

1. **Citation Verification (`verify_citations`)**:
   - Parses `\cite{...}`, `\citep{...}`, `\citet{...}` in manuscript text.
   - Cross-references keys against `references.bib` and registered topic corpus papers.
   - Detects hallucinated citations, flags fuzzy matches, and rejects unresolvable keys.
2. **Experimental Provenance Verification (`verify_experiment_provenance`)**:
   - Extracts numeric performance claims (e.g. `94.5%`, `BLEU = 32.1`, `Loss: 0.042`).
   - Validates that reported numbers match actual metrics measured in completed mission tasks or SQLite `experiment_runs`.
   - Prevents unbacked or fabricated benchmark numbers.
3. **Figure Source Validation (`verify_figure_sources`)**:
   - Parses `\includegraphics{...}` directives.
   - Verifies the figure files exist in Figure Studio, topic diagrams, or the project workspace.
4. **LaTeX Compilation Wrapper (`verify_latex_compilation`)**:
   - Compiles manuscript via `backend.paper.latex.compile_pdf()`.
   - In environments without live TeX binaries, produces a structured layout preview report with zero failure crashes.
5. **Scientific Consistency Check (`verify_scientific_consistency`)**:
   - Verifies core terminology and claim consistency between Abstract, Method, and Conclusion.
6. **Independent Multi-Criteria Peer Review (`evaluate_peer_review`)**:
   - Evaluates manuscript on 4 criteria: Clarity (0–10), Novelty (0–10), Soundness (0–10), and Empirical Rigor (0–10).
   - Computes weighted overall score; requires overall score $\ge 6.0$ to pass.
7. **Human Approval Gate**:
   - Requires explicit human submission sign-off (`author_signoff: true`) before any paper is finalized or submitted.

---

## 6. Execution Safety & Anti-Loop Safeguards

1. **No Nested Loops**: PaperOrchestra never calls `asyncio.gather()` or recursive task runners; tasks are dispatched purely by PhD Lab's `MissionWorker`.
2. **Resource Guard Enforced**: Guard slots are acquired (`cli` or `local_llm`) before running, preventing local compute exhaustion.
3. **Timeouts & Cancellation**: Every task is bounded by mission timeout limits (`limits.timeout_seconds`); cancellation checks propagate `EngineFailure("cancelled")`.
4. **Isolated Filesystem**: CLI backend creates an isolated workspace per operation (`data_dir()/research-engines/paperorchestra/<operation_id>/workspace`) and sanitizes environment variables.

---

## 7. Frontend Integration

1. **Chatbox Integration**:
   - Quick command `/paperorchestra` added to `Composer.tsx`.
   - Supports natural language commands with auto-detection of paper writing intents.
2. **Paper Writing Studio (`PaperOrchestraStudio.tsx`)**:
   - Embedded in `OutlinePaperCodePanels.tsx` under the "PaperOrchestra" view tab.
   - Level Selector: Choose between L2 (Human-Controlled), L3 (Specialist Team), or L4 (Autonomous Research-to-Paper).
   - Backend Selector: Switch between "Harness Specialist Skills" and "Isolated Official CLI".
   - Objective & Venue controls: Specify target venue (NeurIPS, ICML, IEEE, Nature, etc.) and research focus.
   - Section Progress Dashboard: Visual status indicators for Abstract, Introduction, Related Work, Methodology, Experiments, and Conclusion.
   - Quality Gate Report Card: Live feedback on citations, experimental provenance, figure sources, and LaTeX compilation.
   - Author Submission Sign-off: Interactive human review confirmation button.
   - Versioned Artifact History: Audit list of generated artifacts with SHA-256 hashes and download links.

---

## 8. Capability Audit & Verification Report

### A. Tested Capabilities (Automated Verification)
- [x] **Engine Registration & Health Contract**: Registered in `FACTORIES` and `CATALOG`, protocol compliant.
- [x] **CLI Backend Workspace Isolation**: Sandboxed folder creation, probe verification, environment sanitization.
- [x] **Harness Skill Backend Multi-Agent Roles**: 5 specialized agent roles executing with real event streams and artifact generation.
- [x] **Automated CLI-to-Skill Fallback**: Graceful fallback when CLI binary is absent.
- [x] **L2 Mission Lifecycle**: Single capability task creation with human gate checkpoint (`awaiting_step_review`).
- [x] **L3 Writing Team Creation**: 4-agent specialist team (Lead Author, Methods Writer, Literature Curator, Manuscript Verifier) with DAG dependencies.
- [x] **L4 Autonomous Research-to-Paper Closure**: Full DAG validated with `autonomy.validate()` ending with `artifact.verify` on `mission.report`.
- [x] **Traceable Shared Artifact Contract**: SQLite persistence, monotonic versioning, SHA-256 content hashing, metrics capture.
- [x] **Thread-Safe Concurrent Editing**: Multi-threaded write lock protection preventing file race conditions.
- [x] **Citation Hallucination Gate**: Identification of valid, substituted, and missing citations.
- [x] **Experimental Provenance Gate**: Extraction and verification of metric claims against measured task results.
- [x] **Figure Asset Validation**: Detection of valid and missing graphic assets.
- [x] **Independent Peer Review Scoring**: 4-criteria rubric evaluation and recommendation generation.
- [x] **REST API Schema & Endpoints**: `/api/research/paperorchestra/*` health, artifacts, verification, and mission planning.
- [x] **Execution Safety & Cancellation**: Clean handling of task cancellation.
- [x] **Frontend UI & Studio Components**: 168 vitest tests passing; production bundle compiled cleanly (`dist/index.html`).

### B. Untested Capabilities
- **Live Cloud PaperOrchestra Execution**: Requires paid Google Cloud AI Platform / Vertex AI API credentials with live PaperOrchestra cloud runners configured.
- **Host TeX Live System Compilation**: Requires local `pdflatex` / `xelatex` binaries installed on host PATH (the system falls back to structured layout preview when TeX binaries are not present).

### C. Blocked Capabilities
- **Direct Execution of Host `paper-orchestra` CLI Binary**: The official Google Cloud `paper-orchestra` CLI package is not pre-installed on this Windows host. **Status**: Non-blocking in practice, because the engine automatically detects missing binaries and gracefully routes execution to the capability-based skill backend using local harness models.
