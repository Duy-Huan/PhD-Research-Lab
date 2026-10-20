# PhD Research Lab v3.2 → v3.3
# Backend & Context Memory Intelligence / Performance Upgrade

## Mission

Upgrade the existing PhD Research Lab v3.2 backend into a research-grade backend optimized for:

1. Context Memory quality
2. Research-state-aware retrieval
3. Evidence and provenance
4. Long-horizon agent continuity
5. Backend performance
6. Reliability and observability

Target:

> **9/10 relative to publicly documented Claude Science / Anthropic context-engineering patterns.**

Do not attempt to clone proprietary Anthropic internals. Benchmark only against publicly described concepts.

---

# 1. NON-NEGOTIABLE PRINCIPLES

- Treat v3.2 as an existing production research tool, not a greenfield project.
- Do not blindly rewrite the backend.
- Preserve backward compatibility and existing research data.
- Measure before optimizing.
- Preserve correctness and research integrity before performance.
- Do not add infrastructure merely for architectural complexity.
- Do not make this milestone primarily a UI project.
- Every new subsystem must have tests and measurable justification.

Priority:

```text
Correctness
↓
Research integrity
↓
Context quality
↓
Retrieval quality
↓
Provenance
↓
Reliability
↓
Performance
↓
Maintainability
```

---

# 2. FIRST STEP — COMPLETE BACKEND AUDIT

Before implementing changes:

- inspect the complete backend;
- map memory, retrieval, context compilation, agents, storage, APIs and workers;
- inspect database/file persistence;
- inspect caching;
- inspect asynchronous/background processing;
- inspect ClearML/Git/experiment provenance;
- run the complete existing test suite;
- record baseline performance.

Create:

```text
docs/architecture/backend-v3.3-audit.md
```

Document:

```text
Current architecture
Memory lifecycle
Memory write path
Memory read path
Retrieval pipeline
Context compilation pipeline
Agent interaction
Storage model
Dependency graph
Performance bottlenecks
Concurrency risks
Technical debt
Recommended upgrade order
```

Do not begin a major rewrite until this audit is complete.

---

# 3. TARGET BACKEND ARCHITECTURE

Evolve toward:

```text
                    USER / AGENT
                         │
                         ▼
                ┌─────────────────┐
                │ Research State  │
                │ Objective       │
                │ Hypothesis      │
                │ Experiment      │
                │ Constraints     │
                │ Decisions       │
                └────────┬────────┘
                         ▼
                ┌─────────────────┐
                │ Context Policy  │
                │ / Planner       │
                └────────┬────────┘
                         ▼
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   Working Memory   Research Memory   Knowledge Memory
        └────────────────┼────────────────┘
                         ▼
                ┌─────────────────┐
                │ Hybrid Retrieval│
                │ lexical         │
                │ semantic        │
                │ graph           │
                │ metadata        │
                │ temporal        │
                └────────┬────────┘
                         ▼
                ┌─────────────────┐
                │ Fusion/Rerank   │
                └────────┬────────┘
                         ▼
                ┌─────────────────┐
                │ Evidence Layer  │
                │ claims          │
                │ sources         │
                │ experiments     │
                │ artifacts       │
                │ metrics         │
                │ provenance      │
                └────────┬────────┘
                         ▼
                ┌─────────────────┐
                │ Context Compiler│
                │ role-aware      │
                │ budget-aware    │
                │ priority-aware  │
                │ deduplicated    │
                └────────┬────────┘
                         ▼
                       LLM
                         │
                         ▼
                Memory / Evidence
                  update pipeline
```

Prefer a modular local-first architecture. Do not introduce microservices, Kafka, Kubernetes, distributed databases, etc. unless profiling proves they are necessary.

---

# 4. CONTEXT MEMORY — PRIMARY FOCUS

The goal is to move from:

```text
query → relevant memories
```

to:

```text
current research state
+
current task
+
agent role
+
evidence
+
history
+
constraints
↓
optimal research context
```

Context Memory must understand the research situation, not merely semantic similarity.

---

# 5. RESEARCH-STATE-AWARE RETRIEVAL

Build retrieval context from:

```text
current_query
research_objective
active_hypothesis
current_experiment
current_project
agent_role
recent_decisions
known_failures
active_constraints
dataset/model information
temporal state
```

Example:

```text
Query:
"Should we use Swin Transformer?"

Objective:
hyperspectral image denoising

Hypothesis:
HYPE-007

Dataset:
CAVE

GPU:
RTX 3060 12GB

Previous experiments:
EXP-011
EXP-013
EXP-017

Known failure:
OOM with large attention window
```

Retrieval should therefore prioritize:

- relevant papers;
- previous experiments;
- previous failures;
- resource constraints;
- current baseline;
- relevant decisions.

Create a structured retrieval-context object rather than passing only a raw query string.

---

# 6. ROLE-AWARE CONTEXT COMPILER

Do not use one static memory ratio for all agents.

Support role-specific policies.

### Literature Agent

```text
Knowledge: high
Evidence: high
Research: medium
Working: low
```

### Experiment Designer

```text
Research: very high
Evidence: high
Knowledge: medium
Working: medium
```

### Coding Agent

```text
Working: high
Research: high
Artifacts: high
Knowledge: medium
```

### Paper Reviewer

```text
Evidence: very high
Research: high
Knowledge: high
Working: medium
```

The compiler should optimize:

```text
relevance
+
evidence strength
+
research centrality
+
recency
+
task fit
+
coverage
-
redundancy
-
low confidence
```

---

# 7. EXPLICIT CONTEXT BUDGETING

Every context compilation should track:

```text
max_tokens
reserved_tokens
system_tokens
task_tokens
memory_budget
evidence_budget
artifact_budget
safety_margin
```

When the context exceeds its budget:

1. remove redundant low-value information;
2. compress low-priority memories;
3. preserve active research state;
4. preserve relevant evidence;
5. preserve recent decisions;
6. preserve relevant failures;
7. preserve critical provenance;
8. never blindly truncate.

Context selection must be deterministic and explainable.

---

# 8. MEMORY QUALITY SCORING

Create an explainable memory score based on appropriate dimensions such as:

```text
relevance
importance
recency
confidence
evidence_strength
research_centrality
novelty
dependency_count
failure_prevention_value
redundancy_penalty
```

The exact formula should be determined after inspecting the current implementation.

For every retrieved memory, the system should be able to explain:

> Why was this memory retrieved?

---

# 9. FIRST-CLASS EVIDENCE LAYER

Introduce or strengthen explicit entities:

```text
Evidence
Claim
Source
Experiment
Artifact
Metric
Decision
Hypothesis
```

Relationships:

```text
Hypothesis
   ↓ tested_by
Experiment
   ↓ produces
Evidence
   ↓ supports/refutes
Claim
   ↓ informs
Decision
```

Evidence must preserve provenance.

Example conceptual record:

```json
{
  "evidence_id": "EVID-001",
  "claim": "Model A improves PSNR over baseline B",
  "source_type": "experiment",
  "experiment_id": "EXP-021",
  "dataset_version": "CAVE-v2",
  "git_sha": "abc123",
  "clearml_task_id": "task_xyz",
  "metric": {
    "name": "PSNR",
    "value": 31.42
  },
  "status": "validated"
}
```

Adapt this to existing repository conventions rather than blindly adding a parallel database model.

---

# 10. PROVENANCE

Strengthen the chain:

```text
Paper
 ↓
Claim
 ↓
Hypothesis
 ↓
Experiment
 ↓
Code
 ↓
Git commit
 ↓
Environment
 ↓
Dataset version
 ↓
Run
 ↓
Metrics
 ↓
Artifact
 ↓
Decision
```

The backend should be able to answer:

- Where did this conclusion come from?
- Which experiment produced this metric?
- Which code commit produced the artifact?
- Which dataset/version was used?
- Which decision was based on this evidence?

---

# 11. MEMORY LIFECYCLE

Do not permanently save every conversation turn.

Maintain clear states such as:

```text
ephemeral
working
episodic
research
knowledge
evidence
```

Memory promotion:

```text
raw interaction
    ↓
candidate
    ↓
classification
    ↓
deduplication
    ↓
confidence / importance
    ↓
persistent memory
```

Memory consolidation:

```text
raw events
    ↓
episodes
    ↓
research summaries
    ↓
stable decisions
    ↓
knowledge/evidence
```

Never delete raw evidence simply because a summary exists.

Preserve:

```text
raw source
+
derived representation
+
provenance link
```

---

# 12. FAILURE MEMORY

Failures are research knowledge.

Persist:

```text
failure_id
experiment
model
dataset
environment
configuration
error
cause
observation
lesson
avoidance rule
```

Example:

```text
FAIL-003

Model:
SwinIR-large

GPU:
RTX 3060 12GB

Failure:
CUDA OOM

Cause:
attention window too large

Lesson:
avoid configuration X under 12GB VRAM
```

Failure memory must be retrievable during future experiment planning.

---

# 13. HYBRID RETRIEVAL

Preserve and improve the current architecture where applicable:

```text
BM25
+
Vector
+
Graph
+
Metadata
+
Temporal
↓
RRF / Fusion
↓
Reranker
↓
Context Compiler
```

Improve:

### Query construction
Use research state.

### Metadata filtering
Support:

```text
project
experiment
dataset
model
agent
date
source_type
evidence_status
```

### Temporal retrieval
Prefer current state when appropriate while retaining historical failures and decisions.

### Graph traversal
Support:

```text
hypothesis → experiment
experiment → result
result → decision
paper → claim
claim → hypothesis
artifact → experiment
```

### Reranking
Only use expensive reranking when it provides measurable benefit. Cache safely where appropriate.

---

# 14. CACHE AND PERFORMANCE

First profile the system.

Measure:

```text
memory read latency
memory write latency
retrieval latency
embedding latency
reranking latency
context compilation latency
database latency
API latency
cold-cache latency
warm-cache latency
```

Potential caches:

```text
query normalization
embedding
retrieval
reranking
compiled context
research state
metadata
```

Cache keys must include all state that can affect the result.

Implement correct invalidation.

Avoid stale-context bugs.

---

# 15. PERFORMANCE TARGETS

Use these as initial targets, then adjust according to actual hardware and baseline:

```text
simple memory lookup: <100 ms
hybrid retrieval: <500 ms where practical
context compilation: <300 ms excluding external LLM calls
normal memory write: <200 ms
```

Do not sacrifice correctness merely to hit a number.

Expensive operations should use:

```text
async/background processing
```

where appropriate.

---

# 16. CONCURRENCY AND RELIABILITY

Audit:

- SQLite/file concurrency;
- race conditions;
- async/sync boundaries;
- background workers;
- duplicate writes;
- simultaneous agent sessions;
- memory consolidation;
- cache invalidation.

The system must remain consistent when:

```text
user
+
multiple agents
+
background summarizer
```

operate simultaneously.

---

# 17. OBSERVABILITY

Add structured backend telemetry.

Major operations should expose:

```text
request_id
session_id
project_id
agent_id
operation
latency
cache_hit
candidate_count
selected_count
context_tokens
memory_tokens
errors
```

Retrieval trace should expose:

```text
query
retrieval sources
candidate counts
fusion scores
reranker scores
selected memories
```

Context compiler trace should expose:

```text
budget
selected items
discarded items
compression ratio
selection reasons
```

Avoid unnecessarily logging sensitive content.

---

# 18. CONTEXT TRACE / DEBUG MODE

Implement an optional debug mode such as:

```text
CONTEXT TRACE

Task:
Design denoising experiment

Research state:
HYPE-007

Retrieved:
EXP-013     score 0.91
FAIL-003    score 0.87
PAPER-022   score 0.83
DEC-004     score 0.78

Dropped:
CHAT-192    low relevance
PAPER-011   duplicate

Compiled:
Research: 8.2k tokens
Evidence: 3.1k
Knowledge: 2.7k
Working: 1.9k

Total:
15.9k tokens
```

This is critical for debugging context quality.

---

# 19. MEMORY EVALUATION

Create:

```text
tests/memory_eval/
```

Measure:

### Retrieval Recall
Can relevant memories be retrieved?

### Precision
Are irrelevant memories excluded?

### Evidence Fidelity
Does context preserve the actual evidence?

### Temporal Correctness
Does the system retrieve the correct state/version?

### Failure Recall
Can prior failed approaches be recovered?

### Context Efficiency
How much useful information is delivered per token?

### Decision Support
Does retrieved context improve downstream research decisions?

---

# 20. GOLDEN RESEARCH TASKS

Create deterministic benchmark tasks:

```text
Task 001:
Find previous experiments using dataset X.

Task 002:
Why did model Y fail?

Task 003:
What is the current best PSNR?

Task 004:
Which hypothesis is currently active?

Task 005:
Which papers support claim Z?

Task 006:
What configuration caused OOM?

Task 007:
What experiment should be run next?

Task 008:
Which code commit produced result R?
```

Store expected relevant records/answers.

Run before and after changes.

---

# 21. PERFORMANCE REGRESSION

Compare:

```text
v3.2 baseline
vs
v3.3
```

Track:

```text
latency
memory usage
database operations
retrieval quality
context size
cache hit rate
test pass rate
```

A performance optimization is invalid if it silently degrades research retrieval quality.

---

# 22. TESTING

Maintain:

```text
unit tests
integration tests
memory tests
retrieval tests
context compiler tests
concurrency tests
migration tests
performance tests
```

At minimum cover:

```text
CRUD
deduplication
promotion
consolidation
retrieval
RRF
reranking
context budgeting
role-aware policies
provenance
failure memory
cache invalidation
concurrent writes
schema migration
```

Do not accept manual testing as the only validation.

---

# 23. CLAUDE SCIENCE / ANTHROPIC BENCHMARK

Use only publicly documented Anthropic patterns as the benchmark:

```text
long-horizon context management
structured persistent notes
context compaction
multi-agent research
lead-agent orchestration
artifact-first workflows
evidence-oriented research
actor/critic verification
persistent research state
scientific provenance
```

Do NOT claim knowledge of proprietary Claude Science internals.

Document:

```text
What PhD-Lab implements
What Anthropic publicly describes
What is unknown
Where PhD-Lab is stronger
Where PhD-Lab is weaker
```

The goal is not to copy Claude Science.

The goal is:

> Build a research memory architecture that reaches approximately 9/10 against the publicly observable architectural principles.

---

# 24. WHAT NOT TO DO

Do not spend this milestone primarily on:

- UI redesign;
- new dashboards;
- animations;
- superficial features;
- adding databases without profiling;
- adding vector stores merely because they are fashionable;
- rewriting stable code without evidence.

Do not introduce:

```text
Kafka
Kubernetes
microservices
distributed vector DB
graph DB
Redis cluster
```

unless profiling demonstrates a real need.

The application is local-first.

Prefer:

```text
simple
fast
local
deterministic
observable
portable
```

---

# 25. IMPLEMENTATION ORDER

## Phase 1 — Baseline

- audit backend;
- run tests;
- benchmark;
- identify bottlenecks;
- document architecture.

## Phase 2 — Research State

Formalize:

```text
objective
hypothesis
experiment
constraints
recent decisions
known failures
```

## Phase 3 — Retrieval

Implement:

```text
state-aware retrieval
metadata filtering
temporal retrieval
graph-aware retrieval
hybrid fusion
explainable scoring
```

## Phase 4 — Context Compiler

Implement:

```text
role-aware policy
token budgeting
priority scoring
evidence preservation
deduplication
compression
```

## Phase 5 — Evidence / Provenance

Strengthen:

```text
claims
evidence
experiments
artifacts
metrics
Git
ClearML
dataset versions
```

## Phase 6 — Memory Lifecycle

Improve:

```text
promotion
consolidation
deduplication
failure memory
archival
invalidation
```

## Phase 7 — Performance

Optimize only after profiling:

```text
DB queries
serialization
caching
async processing
retrieval
reranking
context compilation
```

## Phase 8 — Evaluation

Add:

```text
golden research tasks
retrieval benchmarks
context benchmarks
performance benchmarks
regression tests
```

## Phase 9 — Hardening

Test:

```text
migration
recovery
corruption handling
concurrency
restart
long-running sessions
```

---

# 26. DEFINITION OF DONE

## Architecture

- [ ] Backend architecture documented.
- [ ] Memory lifecycle documented.
- [ ] Retrieval lifecycle documented.
- [ ] Context compiler documented.

## Context Memory

- [ ] Research-state-aware retrieval.
- [ ] Role-aware context compilation.
- [ ] Explicit token budgeting.
- [ ] Explainable memory scoring.
- [ ] Deduplication.
- [ ] Consolidation.
- [ ] Failure memory.
- [ ] Evidence layer.
- [ ] Provenance.

## Retrieval

- [ ] BM25/lexical retrieval preserved/improved.
- [ ] Vector retrieval preserved/improved.
- [ ] Graph retrieval preserved/improved.
- [ ] Fusion/RRF tested.
- [ ] Reranking tested.
- [ ] Retrieval explanation available.

## Performance

- [ ] Baseline benchmark recorded.
- [ ] Post-upgrade benchmark recorded.
- [ ] No major regression.
- [ ] Caching justified by measurements.
- [ ] Expensive processing moved async where appropriate.

## Reliability

- [ ] Concurrent operations tested.
- [ ] Migration tested.
- [ ] Recovery tested.
- [ ] Corruption handling tested.

## Evaluation

- [ ] Golden tasks created.
- [ ] Retrieval quality measured.
- [ ] Context quality measured.
- [ ] Performance measured.
- [ ] Regression suite passes.

---

# 27. REQUIRED DOCUMENTATION

Create/update:

```text
docs/architecture/backend-v3.3-audit.md
docs/architecture/backend-v3.3-final.md
docs/architecture/context-memory-v3.3.md
docs/benchmarks/backend-v3.3-benchmark.md
docs/benchmarks/context-memory-v3.3-evaluation.md
```

Final report must contain:

```text
1. What changed
2. Why it changed
3. Before/after architecture
4. Context Memory before/after
5. Retrieval before/after
6. Context Compiler before/after
7. Evidence/provenance changes
8. Performance before/after
9. Test results
10. Memory evaluation results
11. Known limitations
12. Remaining gap vs public Claude Science patterns
13. Recommended v3.4/v4 roadmap
```

---

# 28. CORE ENGINEERING QUESTION

Do not optimize for:

> How many memory components can we add?

Optimize for:

> Can the AI research agent recover the correct research state, evidence, decisions, failures and artifacts at the exact moment they are needed, using the minimum necessary context?

The target loop is:

```text
Research Question
       ↓
Research State
       ↓
Context Policy
       ↓
State-Aware Retrieval
       ↓
Evidence + Provenance
       ↓
Role-Aware Context Compiler
       ↓
LLM / Agent
       ↓
Experiment / Action
       ↓
Observation / Result
       ↓
Evidence Update
       ↓
Research Memory Update
       ↓
Next Decision
```

---

# 29. FINAL INSTRUCTION TO CLAUDE

You are upgrading the **backend intelligence substrate** of a local-first AI research environment.

Do not merely add features.

For every major change:

```text
inspect
→ measure
→ design
→ implement
→ test
→ benchmark
→ document
```

The final backend must allow a research session to continue naturally after:

- context-window reset;
- agent restart;
- application restart;
- model/provider change;
- failed experiment;
- weeks of inactivity.

The system must remember:

```text
research state
+
evidence
+
decisions
+
failures
+
provenance
+
artifacts
```

not merely conversation history.

## Milestone Target

**PhD Research Lab v3.3 — Backend & Context Memory Intelligence / Performance Upgrade**

Primary success criterion:

> **A fast, reliable, research-state-aware Context Memory backend that approaches 9/10 against publicly documented Claude Science / Anthropic context-engineering principles, while remaining local-first, maintainable, measurable, and backward compatible.**
