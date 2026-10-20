# PhD Research Lab — Unified AI Workspace, Secure CLI Gateway, Context Firewall & Hybrid Control

> **Purpose:** Use this prompt in Claude Code / VS Code to upgrade the existing PhD Research Lab repository. This is an incremental architecture upgrade, not a greenfield rewrite.
>
> **Working principle:** automate repetitive work, but never remove the user's ability to inspect, override, or perform the same workflow manually. AI is an assistant operating inside the research environment—not the owner of the environment.

---

## 0. Your role

Act as the lead software architect, security-minded application engineer, and implementation agent for the **existing** PhD Research Lab repository.

Before changing code, inspect the actual repository, current branch, working tree, technology stack, app entry points, persistence layer, provider integrations, MCP infrastructure, context-memory implementation, and test setup. Adapt this specification to the existing code; do not assume that paths, frameworks, providers, or features named here already exist.

Your goals are to:

1. Preserve currently working capabilities and the existing user data format wherever practical.
2. Add a unified AI interaction layer that can be used from all relevant modules, not just one global chatbot.
3. Put all local CLI providers behind a managed gateway, dedicated per-session workspaces, and enforceable isolation/permission policies.
4. Make module-specific context explicit, inspectable, and testable.
5. Extend context memory with source provenance, selective extraction, deduplication, conflict handling, and manual/automatic control.
6. Redesign the frontend toward a modern, chat-centered research workspace without deleting existing non-chat workflows.
7. Maintain two first-class operating styles: **Automation** and **Manual / Hard Control**. Neither may be a decorative toggle; both must change real backend behavior.
8. Deliver working code, tests, migration handling, and documentation—not merely an architectural proposal.

Do not perform a blind rewrite. Do not claim that a feature works unless it is implemented and verified.

---

## 1. Product vision and architectural decision

Evolve the application into a:

**Research IDE + Universal AI Interaction Layer + Context & Memory Engine + Secure Agent Runtime.**

Use a **Chat-Centered, Context-Aware, Module-Driven** interface:

- Chat is a shared interaction capability available throughout the app.
- Research modules remain real workspaces with their own data, forms, tables, visualizations, state transitions, and direct/manual workflows.
- Every AI session is bound to a module, a specific entity when applicable, a provider, a permission profile, MCP policy, context snapshot, and output/memory policy.
- One reusable chat frontend and one backend session contract serve many modules. Modules provide adapters and allowed actions instead of implementing separate chat stacks.
- Provider-specific functionality is represented through a capability registry. Do not pretend all providers expose the same models, reasoning controls, tool events, multimodal features, session-resume behavior, or usage metadata.

Target mental model:

```text
PhD Research Lab App Shell
├── Research modules: Lit2Plan, Papers, Dataset, Experiment, DL Lab, Evaluation, Memory, ...
├── Universal AI Workspace / Chat Surface
├── Context Orchestrator + Module Context Adapters
├── AI Gateway + Provider Capability Registry
├── CLI Process/Session Manager + Sandbox/Permission Policy
├── MCP Registry/Router + Approval Policy
├── Output/Artifact Collector
└── Memory Candidate Pipeline + Long-Term Context Memory
```

This prompt does **not** authorize copying proprietary provider UI pixel-for-pixel or using provider logos/assets without checking applicable rights. Reuse familiar interaction patterns, while building a coherent PhD Research Lab design system.

---

## 2. Non-negotiable safety and engineering rules

### 2.1 Repository and data safety

- Inspect `git status`, current branch, uncommitted changes, current tests, and relevant project documentation before editing.
- Never overwrite, delete, reset, or reformat unrelated user changes.
- Do not run destructive migrations or clean directories without an explicit, reviewable plan and a backup/rollback path.
- Prefer additive, reversible migrations. Preserve compatibility with existing sessions, memory records, projects, and saved configurations.
- Do not log API keys, cookies, authorization headers, raw secrets, or sensitive environment variables.
- Do not add secrets to source control, context bundles, prompt logs, crash reports, memory, or artifacts.
- Do not add new dependencies or change package lockfiles without explaining why and confirming compatibility with the existing stack.

### 2.2 Security claims must be real

- A separate directory is useful, but **a directory alone is not a security sandbox**.
- Use OS-level/container isolation and least-privilege filesystem/network/process policies where available.
- If a requested security profile cannot be enforced on the current platform, fail closed for that profile or clearly downgrade to a visibly weaker profile requiring explicit user consent. Never silently call an unisolated launch “sandboxed.”
- Do not expose the host Docker socket to an AI-controlled sandbox. If container management needs privileged access, keep it in a separate trusted host-side service with a narrow API.
- Resolve and validate all paths after canonicalization. Reject path traversal, forbidden roots, escaping symlinks, and unexpected mounts.
- Prefer argument-array process spawning (`execFile`/equivalent) over concatenating user/model text into a shell command.
- Treat provider output, MCP output, papers, PDFs, webpages, datasets, and repository text as **untrusted content**, not as trusted instructions. Prompt-injection text inside references must not be able to modify permissions or override system policy.
- User approval is required for security-profile expansion, writes to the real project, sensitive MCP tools, external network access when disabled, destructive commands, and memory operations that exceed the configured auto-policy.

### 2.3 Keep provider capabilities truthful

- Verify currently supported CLI flags, structured output modes, sandbox controls, approval controls, resumption, and usage reporting against the installed provider version and its current official documentation.
- Do not invent a common `think` capability. Build a canonical UI option and map it only when the chosen provider genuinely supports it. Disable or explain unsupported controls.
- Do not rely on terminal color/text scraping if the provider offers a stable machine-readable event/JSON mode. If only text output is available, isolate that parser behind the adapter and test it.
- Do not scrape or imitate a private web UI as if it were a supported API. Preserve the existing ChatGPT Web integration as its own adapter if that is how the current application implements it; document its real limitations and use approved/supported interaction methods. Keep browser-backed integrations separate from CLI process control.

---

## 3. Phase 0 — mandatory repository audit before implementation

First, investigate the codebase and create an audit report, for example `docs/architecture/unified-ai-upgrade-audit.md` (adapt the path to the repository conventions).

The report must identify:

1. Frontend framework, routing, layout system, state management, design components, and existing chat-related components.
2. Backend/runtime architecture, API routes, IPC/WebSocket/SSE mechanisms, persistence, jobs/queues, and process-spawning code.
3. Every existing AI integration and the actual transport used: CLI, API, browser session, MCP, or other mechanism. Preserve current integrations rather than renaming or replacing them casually.
4. Existing MCP registry, permission logic, tools, and server lifecycle.
5. Existing context/memory subsystems, including short-term conversation context, long-term memory, summarization, memory candidate handling, retrieval, and provenance.
6. Existing `reference`/paper management, PDF parsing, indexes, datasets, experiment records, sandbox/Docker execution, and artifact storage.
7. All current module entry points and their business state/contracts, particularly Lit2Plan, Experiment, and Deep Learning Lab.
8. Current tests, lint/typecheck/build commands, known bugs, and current uncommitted changes.
9. Threats caused by current CLI launching behavior, especially whether a provider can run from the PhD Research Lab project root or read/write the wider filesystem.
10. A mapping table: existing component → keep / adapt / replace / add, with reasons and dependencies.

Then write a short implementation plan with milestones, migration risks, and acceptance tests. Do not stop at the report: continue into implementation in the same working session unless an actual blocker prevents safe progress. When time or context is limited, finish the most safety-critical vertical slice and leave precise remaining tasks in the report.

---

## 4. Target architecture

Keep boundaries explicit and use the repository's existing language/framework where possible. Prefer clear contracts over adding needless abstraction layers.

```text
Frontend: App Shell + Module Workspace + Universal Chat
                         │
                   Chat Session API
                         │
                 Context Orchestrator
         ┌───────────────┼────────────────┐
         │               │                │
  Module Adapter    Reference/Memory   Context Policy
         │               │                │
         └───────────────┼────────────────┘
                         │
                     AI Gateway
         ┌───────────────┼────────────────┐
         │               │                │
  Provider Registry   MCP Router   Permission/Approval Gate
         │               │                │
  Provider Adapters   Approved Tools      │
  ├─ existing Claude CLI integration      │
  ├─ existing ChatGPT Web integration     │
  ├─ existing Gemini/other CLI adapters   │
  ├─ existing Codex/other MCP adapters     │
  └─ future adapters                       │
         │                                  │
    CLI Session Manager ── OS/Container Sandbox
         │
  Normalized Event Stream
         ├── Frontend streaming renderer
         ├── Persistent session/message store
         ├── Artifact collector
         ├── audit/security log
         └── Output & Memory Candidate Pipeline
```

Suggested logical service boundaries (adapt to existing architecture):

- `AIProviderRegistry`: provider identity, models, transport, status, capabilities, adapter factory.
- `AIProviderAdapter`: create/send/stream/cancel/resume/terminate where supported; report actual capabilities and errors.
- `SessionManager`: lifecycle, persistence, ownership, provider session IDs, working directory, context snapshot, permissions, and status.
- `CLIWorkspaceManager`: create and clean up isolated per-provider/per-session workspaces and read-only context mounts.
- `ContextOrchestrator`: resolve module state and selected references/memories into a versioned manifest and bounded context package.
- `ModuleContextAdapter`: compile domain-specific context and expose allowed domain actions for a module.
- `MCPRegistry` / `MCPPolicyRouter`: tool discovery, per-session allowlists, arguments, approvals, execution, and audit events.
- `ApprovalPolicyEngine`: enforce user-configured execution modes and explicit approval boundaries.
- `NormalizedEventBus`: translate provider-native output into a shared event schema.
- `ArtifactCollector`: capture files/patches/reports/plots/checkpoints/logs and register provenance.
- `MemoryCandidatePipeline`: extract, score/validate, deduplicate, conflict-check, and persist only allowed memory candidates.

Do not force all these into separate deployable services. Within a desktop app, these may be modules/classes/processes in one application. The critical requirement is separation of responsibilities and enforceable boundaries, not microservices.

---

## 5. Secure CLI Gateway and per-session CLI Space

### 5.1 Dedicated storage layout

Create a configurable data root. `/data/cli-space/` is the proposed conceptual layout, **not a hard-coded absolute path**. The application must choose a platform-appropriate writable data directory and store the resolved root in configuration. Allow an explicit override.

Recommended layout:

```text
<data_root>/
├── cli-space/
│   ├── <provider-id>/
│   │   ├── sessions/
│   │   │   └── <session-id>/
│   │   │       ├── workspace/       # the only normal writable workspace
│   │   │       ├── context/         # generated context bundle; read-only to agent
│   │   │       ├── input/           # staged attachments
│   │   │       ├── output/          # collected raw/normalized output
│   │   │       ├── artifacts/       # extracted deliverables
│   │   │       ├── logs/            # redacted operational logs
│   │   │       └── session.json     # metadata/policy snapshot, no secrets
│   │   ├── cache/
│   │   └── provider-config/         # non-secret, generated configuration only
│   ├── shared/
│   │   ├── context-cache/
│   │   ├── staging/
│   │   └── exports/
│   └── quarantine/                  # suspicious/rejected output if useful
├── references/                      # existing reference repository; canonical source
├── memory/                          # existing durable memory; canonical source
└── projects/                         # existing projects; canonical source
```

Adapt this layout to existing path conventions; do not move existing data just to match the example. Each session must have a unique workspace. Provider-level directories must not be used as a shared writable working directory by multiple sessions.

### 5.2 Required launch sequence

For every CLI session:

1. Resolve provider ID, session ID, module/entity binding, model, capability selection, context manifest, and security profile.
2. Validate the profile against detected OS, container runtime, provider version, and application settings.
3. Create or safely resume that session's dedicated workspace.
4. Generate a context snapshot from the canonical references/memory/project state. Mount or stage only the approved files.
5. Validate all paths/mounts after resolving symbolic links and platform-specific path syntax.
6. Construct a minimal environment from an allowlist. Exclude inherited credentials, `.env` files, browser cookies, SSH keys, cloud credentials, and unrelated environment variables unless explicitly required and approved.
7. Launch the provider with an argument array and the session workspace as its working directory. Never default to the PhD Research Lab repository root.
8. Start structured event collection, timeout/cancellation handling, process-tree termination, and redacted audit logging.
9. Return the normalized stream to the correct frontend chat session.
10. Collect permitted artifacts and output; do not automatically merge workspace changes into the real project.

If launch fails at any security step, explain the reason and do not silently fall back to an unrestricted terminal process.

### 5.3 Filesystem and execution profiles

Implement profiles using clear names and user-visible descriptions. Suggested baseline:

**A. Read-only / Review**
- Reads only the workspace snapshot and explicitly mounted references.
- No file writes, shell execution, network access, or MCP mutations unless individually enabled.
- Suitable for paper analysis, code review, literature synthesis, and planning.

**B. Assisted (recommended default)**
- Writable session workspace only.
- Approved tool execution permitted; risky commands require approval.
- Real project, canonical references, and long-term memory remain read-only.
- Network is denied by default and can be explicitly enabled per task/profile.

**C. Experiment Sandbox**
- Session workspace writable, with a designated sandbox/runtime for code execution.
- Mount datasets and references read-only; output/artifact directory writable.
- GPU/Docker capability must be explicitly configured and shown to the user.
- No broad host filesystem access.

**D. Controlled Project Apply**
- The agent produces patches or staged file changes first.
- Applying to the real project requires a visible diff and user approval.
- Git-aware backup/checkpoint where available.
- No automatic destructive operation.

**E. Manual / Developer Control**
- User can inspect the exact command/arguments, working directory, environment allowlist, mounts, network rules, context manifest, and all proposed tool calls.
- User can edit permitted configuration, invoke approved commands manually, and apply/reject generated patches.
- This is not an automatic bypass of security. Unrestricted host execution must never be silently enabled; any elevated profile has to be explicit, scoped, logged, and reversible.

Implement risk-tiered approval gates: filesystem writes outside the session workspace, network expansion, secret access, package installation, process control, MCP mutation, and destructive commands must be handled explicitly.

### 5.4 Cross-platform requirement

The app is used on Windows. Prefer a portable workspace abstraction that supports Windows paths and, where installed, WSL/Docker/Podman isolation. Keep OS-specific sandbox adapters separate. Detect whether a chosen isolation mechanism is actually available. Do not assume Linux bind-mount semantics or shell syntax on Windows.

### 5.5 Reference access without copying the entire corpus into every prompt

All approved references should be **discoverable and retrievable** by the AI through the context/retrieval layer, but do not inject the full contents of every PDF into every request by default.

Use a combination of:
- a searchable reference index and paper metadata;
- selected full papers explicitly attached by the user;
- bounded excerpts/chunks relevant to the current question;
- read-only reference-search/read tools exposed through approved MCP or internal retrieval APIs;
- a per-session context manifest listing exactly which sources were made available.

The UI must make it possible to choose `None`, `Selected`, `Relevant`, or `Expanded/Full selected sources` context modes. Clarify that “Full” means full access to the chosen scope, not indiscriminate access to all host files. Provide token/context-budget estimates when the provider supports useful estimates.

Reference and memory files must never become writable merely because they have been included as context. If files are copied or staged, create a source/hash manifest and treat them as read-only snapshots. Avoid symlink-based mounts unless the resolved target is verified and enforced by the sandbox.

---

## 6. Universal AI Chat: shared frontend, module-aware backend

### 6.1 UX decision

Redesign toward a **chat-centered research workspace**, not a full chat-only application.

Recommended shell:

```text
┌────────────────────────────────────────────────────────────────────┐
│ Project / Breadcrumb / Current Module / Session Controls            │
├───────────────┬────────────────────────────────────────────────────┤
│ Navigation    │ Module Workspace                                   │
│               │ tables / papers / graphs / configs / experiment     │
│ Lit2Plan      │ state / plots / artifacts / existing manual actions │
│ Papers        │                                                     │
│ Experiment    ├────────────────────────────────────────────────────┤
│ DL Lab        │ Context bar + persistent Chat Composer              │
│ Dataset       │ conversation / streamed events / tool approvals      │
│ Evaluation    │                                                     │
└───────────────┴────────────────────────────────────────────────────┘
```

Support three entry styles with the **same shared chat implementation**:

1. **Global AI Workspace**: full conversation-oriented screen for broad research tasks.
2. **Module chat**: a contextual chat view tied to the current module/entity (e.g., a Lit2Plan topic, paper, dataset, or `EXP-042`).
3. **Inline/docked assistant**: optional side panel or composer in the current module, without losing the user's current table/form/plot.

The app must not force users into chat for operations they already prefer to perform manually. Existing direct controls remain available, and AI actions should call the same domain services/actions as manual UI controls.

### 6.2 Shared components

Implement/reuse a coherent set of components matching the current frontend stack. Suggested responsibilities:

- `ChatShell`: session layout and responsive workspace integration.
- `SessionList`: create, rename, search, archive, delete (with confirmation), filter, and switch sessions.
- `MessageList` / `MessageRenderer`: user/assistant/system status messages and provider-neutral event rendering.
- `ChatComposer`: text, attachments, submit, stop/cancel, retry, and edit/resend.
- `ProviderPicker`: provider/model selection based on actual registry state.
- `ReasoningPicker`: `Auto/Off/Low/Medium/High` or provider-supported options only; display unsupported states rather than pretending a setting was applied.
- `ContextPicker` and `ContextChips`: module context, selected references, memories, experiments, files, and context mode.
- `MCPPicker`: allowed servers/tools, per-session toggles, auto-selection option, and descriptions of side effects.
- `ApprovalPanel`: show proposed command/tool, permissions, paths, network effect, and Approve/Reject/Inspect actions.
- `ToolCallTimeline`: running/succeeded/failed/cancelled tool events with logs where available.
- `ArtifactPanel`: generated/modified files, reports, images, plots, code, diffs, and export/apply actions.
- `MemoryReviewPanel`: pending memory candidates with source links and Approve/Edit/Reject/Ignore controls.
- `SessionSettings`: security mode, output-capture mode, memory mode, and session metadata.

Do not implement fake buttons. If a function is not yet supported by the provider, disable it with an explanation or omit it.

### 6.3 Context-aware composer

Every module-specific chat must display an understandable context bar, for example:

`Lit2Plan · HSI Denoising · 12 selected papers · 3 candidate gaps · Memory: Relevant`

Clicking a context chip must show exactly which records/documents are included. Users can add/remove sources and disable auto-context for a turn. The UI should distinguish:

- current module context;
- attached/selected sources;
- retrieved sources added for this turn;
- longer-term memory entries;
- untrusted external material;
- context omitted due to limits.

Show when the context was last compiled and whether it is a frozen snapshot or live/refreshable context. Never silently expand permissions or context scope because a model asks for it.

### 6.4 Provider and MCP selection

Provider, model, reasoning, MCP tools, context selection, sandbox profile, output capture mode, and memory mode are session properties, with a clearly defined inheritance policy:

- global defaults;
- module defaults;
- per-session override;
- per-turn temporary override where appropriate.

Show the effective value and its source (global/module/session/turn). Switching provider must not silently broaden tool, filesystem, or network permissions. On provider change, re-evaluate its capabilities and explain any unsupported settings. Preserve conversation history and context where possible, but do not claim native provider session continuity if it is not supported.

`MCPPicker` must support both:
- **Auto-select**: the orchestrator proposes tools based on intent/context, then applies the active allowlist and approval policy;
- **Manual selection**: user chooses allowed tools/servers and can disable automatic tool selection.

The model must never be allowed to enable a disabled MCP server, expand the allowlist, or approve its own high-risk call.

---

## 7. Module context contracts and domain actions

Every module with a chat option must provide a context adapter and an action registry. Do not build separate chat implementations for each module.

A context adapter should support, using types and patterns that fit the current codebase:

```text
getModuleIdentity()
resolveCurrentEntity()
buildContext(request, contextPolicy)
listAvailableSources()
validateContextReferences()
getAllowedActions(user, session, policy)
executeApprovedAction(action, validatedArgs)
```

The adapter must return a typed, versioned context bundle including provenance and a budget/selection report. Avoid placing giant unstructured JSON blobs into a prompt.

### 7.1 Lit2Plan / Literature planning context

Include only relevant and authorized state, such as:
- research objective, research questions, topic and stage;
- candidate/selected papers with stable IDs and citation metadata;
- extracted relevant sections, claims, methods, datasets, limitations and results when available;
- known literature gaps, hypotheses, novelty claims, decisions and open questions;
- citations/DOIs/source links and evidence quality;
- the user's current selection and workflow status.

AI should be able to propose structured updates, but it must not overwrite the approved research objective, confirmed gap, or literature records without review. For evidence-based claims, return source references and mark unsupported hypotheses as hypotheses.

Allowed actions may include `propose_gap`, `draft_literature_matrix`, `add_candidate_paper`, `create_hypothesis`, or `update_plan_draft`. State-changing actions require schema validation and appropriate user approval.

### 7.2 Paper / reference context

Include paper identity and metadata, extracted passages/page numbers where supported, local PDF availability, citation details, user annotations, and explicit source-selection state. Keep attribution attached to claims. Do not represent generated citations as verified unless the underlying source was checked.

### 7.3 Experiment context

Include:
- experiment/run ID and status;
- research objective and hypothesis;
- dataset version/split and preprocessing;
- model/code version or commit;
- configuration/hyperparameters and random seeds;
- metrics, logs, errors, runtime, hardware, artifacts and prior/failing runs;
- links to source records and reproducibility metadata.

The assistant may analyze, propose a run, generate a config, or draft code. Launching expensive or destructive compute, changing canonical configs, modifying datasets, or overwriting results needs the corresponding permission/approval gate. Do not invent missing metrics.

### 7.4 Deep Learning Lab context

Include task type, dataset schema and validation status, input/output shape, model design, parameter/FLOP or memory estimates when available, training settings, hardware constraints, run queue, current metrics, evaluation/ablation state, and reproducibility metadata. Keep architecture generation, computational analysis, config search, execution, evaluation, and report creation as distinct actions in the workflow.

### 7.5 Dataset, Evaluation, Memory, and future modules

Define lightweight adapters for other modules using the same interface. Avoid passing unrelated module state just because it is available. Dataset access must respect data permissions; Evaluation should distinguish measured metrics from estimates; Memory must provide read/write policy and provenance. A module without an implemented adapter must explicitly run with a generic, limited context profile rather than claiming domain-specific awareness.

### 7.6 Structured actions, not arbitrary prompt-side writes

AI should propose structured domain actions. Route those actions through the same validated services used by manual UI controls. Do not let the model directly mutate database rows or invoke arbitrary internal methods. Use schemas, permissions, audit records, idempotency keys where appropriate, and clear confirmation for irreversible actions.

---

## 8. Context firewall and context compiler

Implement a context pipeline that is deterministic enough to inspect and test:

```text
Current module/entity + user request
              │
              ▼
       Context Policy Check
              │
              ▼
       Source/Permission Resolver
              │
              ▼
  Reference + Memory + Experiment Retrieval
              │
              ▼
      Relevance / Budget Filtering
              │
              ▼
  Versioned Context Manifest + Content Bundle
              │
              ▼
      Provider Adapter / MCP Resources
```

Requirements:

- Explicit allowlist of source roots and resource IDs per session.
- Canonical paths and path-traversal protections.
- Separate data, instructions, and trusted system policy. Papers/webpages/repository comments are untrusted evidence; never concatenate them as privileged instructions.
- Detect and label source boundaries in the rendered prompt/context bundle. Do not promise perfect prompt-injection detection; rely primarily on permissions, isolation, and explicit trust boundaries.
- Record source ID, content hash/version, page/chunk range, retrieval reason, and access mode in the manifest.
- Support context modes such as `None`, `Selected`, `Relevant`, and `Expanded` with explicit definitions.
- Budget-aware retrieval, deduplication, and prioritization. Keep enough provenance to reconstruct which context was used for a response.
- Separate context cache from authoritative source data. Cache invalidation must account for reference or memory version changes.
- Do not leak one project's/session's private context into another session by accidental cache reuse. Key caches by project, permissions, source versions, context policy, and session isolation requirements.
- Provide “preview effective context” and “copy/export manifest” in Manual mode.

The context firewall is not only a prompt sanitizer. Enforce critical controls at the filesystem, tool, process, network, and authorization layers.

---

## 9. Context memory: evidence-backed, selective, and reversible

Keep the existing three-tier/context-memory implementation if present, but audit it and extend it rather than replacing it unnecessarily.

### 9.1 Separate memory layers

Use concepts appropriate to the existing design, for example:

1. **Session memory:** current conversation/event history and a rolling summary.
2. **Project working memory:** current objective, decisions, active hypotheses, task state and recent experiment context.
3. **Long-term research memory:** durable decisions, verified findings, knowledge, open questions, reusable methods, rejected approaches, and lessons from experiments.

Do not simply save every full conversation into long-term memory.

### 9.2 Memory modes

Implement real behavior for:

- **Off:** no automatic memory extraction or writes; normal chat history may still be stored under its separate history policy.
- **Manual:** user explicitly selects a message/response/artifact and chooses a memory type, edits the draft, and approves saving.
- **Suggest / Review queue:** extract candidates and show them for selection, editing, merging, or rejection. Nothing becomes durable until approved.
- **Auto (restricted):** auto-save only explicitly allowlisted low-risk memory categories under a user-enabled policy. High-impact decisions, unverified factual claims, sensitive information, contradictory findings, or ambiguous project changes require review.

Mode can be set globally, per module, and per session, with clear precedence and a visible effective mode. Never change the mode silently.

### 9.3 Memory candidate schema

Use a typed schema suited to the current database, with fields comparable to:

```json
{
  "memory_id": "generated-id",
  "project_id": "project-id",
  "type": "decision | finding | hypothesis | experiment | knowledge | open_question | rejected_approach",
  "title": "Concise statement",
  "content": "Atomic, testable memory",
  "status": "candidate | approved | rejected | superseded",
  "source": {
    "session_id": "...",
    "provider_id": "...",
    "message_ids": ["..."],
    "reference_ids": ["..."],
    "experiment_ids": ["..."],
    "artifact_ids": ["..."]
  },
  "evidence_excerpt_or_pointer": "...",
  "confidence_note": "Qualitative and explainable; do not treat model confidence as truth",
  "created_at": "ISO-8601",
  "created_by": "user | model | system",
  "reviewed_by": null,
  "version": 1
}
```

Treat this as a conceptual schema, not a mandate to duplicate fields already supported by the current persistence layer. Add migrations with rollback and data-preservation checks.

### 9.4 Candidate pipeline

```text
Session messages + tool events + artifacts
                 │
                 ▼
        Candidate extraction
                 │
                 ▼
      Type/schema/evidence validation
                 │
                 ▼
      Deduplicate / near-duplicate check
                 │
                 ▼
       Conflict / supersession check
                 │
                 ▼
     Policy check + user mode decision
            ┌────┴────┐
            │         │
          review     allowed auto-save
            │         │
            └────┬────┘
                 ▼
        Long-term memory + provenance
```

A candidate must cite its source messages, documents or experiments. Distinguish model-generated hypotheses from verified experimental observations. Never convert an assistant's speculation into an established finding without evidence. Preserve rejected/superseded records where practical so research history stays auditable.

### 9.5 Output collection controls

Support separate policies for:
- raw conversation/history retention;
- normalized session summaries;
- candidate memory generation;
- artifact collection;
- applying generated file changes;
- writing approved research state.

A user may enable output capture but disable memory writes, or save artifacts but reject the memory candidate. These switches must be independent.

---

## 10. Provider adapters and normalized event stream

Build on current integrations and add adapters only where a provider is actually installed and usable.

Each adapter should declare supported capabilities through a machine-readable descriptor, such as:

```text
provider_id
transport_type: cli | api | browser | mcp | local
available_models
streaming
native_session_resume
reasoning_controls
image_or_file_inputs
structured_tool_events
usage_reporting
cancellation
sandbox_options
approval_options
```

Only advertise capabilities the adapter can verify. The exact schema should follow project language conventions.

Normalize backend events into a provider-neutral stream, e.g.:

```text
session.created / session.resumed / session.failed
message.started / message.delta / message.completed
status.updated
reasoning.started / reasoning.delta / reasoning.completed   # only if provider exposes it
tool.proposed / tool.approval_required / tool.started
tool.stdout / tool.stderr / tool.completed / tool.failed
artifact.discovered / artifact.updated
usage.updated
permission.denied
session.cancelled / session.completed
error
```

Use one canonical naming convention for event IDs and names.

The event stream must carry session ID, turn ID, provider ID, timestamp, event ID/sequence, and safe metadata. Handle duplicate/out-of-order events, stream reconnection, cancellation, and process termination. Keep `stdout` and `stderr` separate internally and redact secrets before persistence or display.

Use the most reliable output protocol supported by the installed provider. Do not assume every provider has token-by-token streaming or exposes hidden reasoning. Do not render private chain-of-thought from provider output; render only user-visible reasoning/status summaries actually provided by the integration, plus transparent tool/activity traces.

---

## 11. Session lifecycle, persistence, and reliability

An AI session must be more than a `messages[]` array. Persist the concepts supported by the current architecture:

- session ID, title, timestamps, status, project/module/entity binding;
- provider, model, transport, actual provider-native session ID where supported;
- context manifest/version/snapshot reference;
- effective security and MCP policies;
- reasoning/model settings and their capability support;
- messages and normalized events;
- tool calls and approval decisions;
- artifacts and their storage locations/hashes;
- memory candidates and review statuses;
- redacted diagnostic/audit events.

Implement create, list, rename, archive, resume where supported, cancel, delete with confirmation, retry, and fork/branch where feasible. Distinguish **resume of a native provider session** from **starting a new provider session with restored conversation/context**. Do not claim they are equivalent.

Support reliable process cancellation, child-process cleanup, timeouts, crash recovery, stale-session detection, and bounded log/artifact retention. Never reuse another session's workspace because a session crashed.

---

## 12. Dual workflow: Automation AND Manual / Hard Control

This is a core product requirement, not a future nice-to-have.

### 12.1 Global operating mode

Provide a visible operating mode with at least:

**Automation**
- infer relevant module context;
- propose/select allowed MCP tools;
- compile a bounded context package;
- stream the provider response;
- collect outputs and produce memory candidates;
- perform only those actions allowed by policy;
- ask for approval when the policy says so.

**Manual / Hard Control**
- user explicitly selects provider/model, context sources, references, memory entries, MCP servers/tools, reasoning mode, sandbox profile, network mode, and output/memory behavior;
- preview the compiled context manifest and approximate budget where possible;
- inspect command/arguments, working directory, mounts, allowed environment variables and permission scope before launch;
- require user decisions for proposed actions;
- inspect normalized events and raw redacted logs;
- edit configuration and generated patches before applying;
- manually select, edit, merge, approve, or reject memory candidates;
- disable automatic memory extraction and auto tool selection independently.

Keep the UI simple by using an `Auto` default and an expandable `Advanced / Manual` area, but all manual controls must be operational and persisted according to defined rules.

### 12.2 Per-turn control

Support per-turn overrides without permanently mutating the session defaults, such as:
- `Use selected references only for this turn`;
- `Do not use long-term memory for this turn`;
- `Disable MCP for this turn`;
- `Use another provider once`;
- `Run as read-only review`;
- `Generate a patch but do not apply it`.

The UI must label temporary overrides and show the effective policy applied to that turn.

### 12.3 Direct/manual workflows must remain first-class

Do not remove existing forms, configuration editors, experiment controls, paper-management actions, dataset validation, scripts, Docker workflows, or other direct research operations. AI should be able to accelerate these workflows while users can still call the same operations manually. Manual operations should continue to update the canonical domain state, and the next context compilation should reflect those changes.

If a change cannot safely be automated, show a structured proposal/diff and let the user perform the final action manually.

---

## 13. Artifact and project-change workflow

Do not automatically copy every CLI output file into the real project. Use a reviewable artifact lifecycle:

```text
Provider workspace
      ↓
Artifact discovery
      ↓
Type / path / size / safety validation
      ↓
Artifact registry + preview
      ↓
User action: inspect / export / compare / apply / reject
      ↓
Optional project apply via staged patch and backup
```

Artifact metadata should include session/provider, creation time, source path, destination/staging path, hash, size, type, related turn/tool call, and apply status. Detect path collisions and never overwrite canonical reference files or experiment outputs silently. Support text diffs for code/config changes; preview images, plots, logs, and reports safely where feasible.

---

## 14. Implementation milestones

Work incrementally. At the beginning of each milestone, list its scope and the existing components being adapted. At the end, run relevant tests and update the audit/implementation report.

### M0 — Audit and contracts
- Complete repository map and current-state risk audit.
- Identify canonical data stores and existing integrations.
- Define initial provider capability contract, session contract, context contract, memory policy, and security-profile contract.
- Record non-goals and compatibility requirements.

**Exit criteria:** audit document exists; current test/build status is known; no unrelated changes are lost; migration plan is explicit.

### M1 — CLI Gateway and isolation (highest priority)
- Remove direct launches from the repository root.
- Add configurable data root and per-provider/per-session workspaces.
- Add provider launch abstraction, path validation, minimal environment, logs, cancellation, and process-tree cleanup.
- Add security profiles, policy enforcement, and visible fail-closed behavior.
- Stage approved context read-only and write outputs to per-session directories.

**Exit criteria:** tests prove launched working directory is the session workspace; references are not writable; traversal/symlink escape is blocked; unsupported enforced sandbox does not silently fall back to unsafe execution; processes can be cancelled and cleaned up.

### M2 — Session API and normalized streaming
- Implement or adapt session manager and normalized event bus.
- Stream assistant output/events into the frontend through the existing appropriate transport (WebSocket/SSE/IPC).
- Persist sessions/messages/status and redacted diagnostics.
- Support stop, error state, retry, and resume only where correctly supported.

**Exit criteria:** messages stream to the correct session; separate sessions cannot receive each other's events; cancellation terminates the process; restarting the app does not corrupt persisted history.

### M3 — Universal Chat frontend
- Build/reuse a shared chat renderer and composer.
- Add session navigation and create/rename/archive/search controls as supported.
- Add provider/model selector, real capability-aware reasoning control, context chips, MCP picker, security badge/profile control, and tool approval panels.
- Add global chat plus contextual module chat/inline drawer.
- Keep existing module workflows available.

**Exit criteria:** frontend never needs to display a raw terminal to receive normal assistant conversation; unsupported provider options are not fake-enabled; chat is reachable from multiple modules using the same shared components.

### M4 — Context Orchestrator and module adapters
- Implement `ContextPolicy`, versioned context manifest, source provenance, bounded compilation, and preview.
- Add Lit2Plan, Paper/Reference, Experiment, and DL Lab adapters first; then Dataset/Evaluation/Memory where their current state contracts permit.
- Add selected/relevant/expanded context modes and read-only retrieval.
- Add validated, permissioned domain action proposals.

**Exit criteria:** each supported module supplies the correct domain-specific context; switching module/entity cannot reuse stale context; a user can see which sources went into a turn; context sources cannot mutate canonical files.

### M5 — Memory pipeline and output collection
- Separate raw chat history, summaries, memory candidates, artifacts, and domain state writes.
- Implement Off/Manual/Suggest/Restricted Auto modes.
- Add schemas, source provenance, deduplication, conflict/supersession checks, review UI, and rollback/audit records.
- Ensure manual decisions are reflected in later context.

**Exit criteria:** Manual and Suggest modes never commit durable memory before approval; auto-save honors the strict category allowlist; every saved memory can be traced to source evidence; conflicts are surfaced instead of silently overwritten.

### M6 — MCP policy, hybrid control, and integration hardening
- Ensure MCP tools are governed per session and per action.
- Add auto-select/manual-select behavior and visible approvals.
- Complete Advanced/Manual controls and per-turn overrides.
- Harden retry/cancel/recovery, concurrent sessions, artifact import/apply, and OS-specific behavior.

**Exit criteria:** a model cannot expand MCP permissions itself; Manual mode lets the user inspect effective context and proposed commands/actions; project changes are staged and reviewable; current provider integrations still work.

### M7 — End-to-end validation and documentation
- Run full tests, type checks, lint, build, and basic security integration tests supported by the repository.
- Add developer/user documentation, default settings, troubleshooting and recovery instructions.
- Document real provider limitations and platform-specific isolation levels.
- Produce a completion report with implemented features, tests run/results, known limitations, and follow-up issues.

**Exit criteria:** core workflows are demonstrably functional; docs match actual behavior; known gaps are explicit rather than hidden.

---

## 15. Required tests and acceptance scenarios

Add unit/integration tests in the project's existing test framework. Cover at least:

### CLI isolation and permissions
- Provider launch never defaults to project root.
- Session A and session B use different workspaces and logs.
- Path traversal (`..`), drive-path tricks, escaping symlinks and unapproved mount roots are rejected.
- Reference/memory source content is read-only to the agent runtime.
- Missing/failed sandbox support produces a clear error or an explicitly confirmed weaker mode; no silent unsafe fallback.
- Secrets are not inherited wholesale, included in context, or written to logs.
- Cancel and crash recovery clean up child processes without deleting unrelated user files.
- High-risk command, network expansion, project write and destructive tool requests go through policy/approval.

### Context correctness
- Lit2Plan chat includes only expected objective, literature state, selected/retrieved sources and allowed memory.
- Experiment chat includes the correct experiment/run/config/metric/artifact state.
- DL Lab chat includes the active task/configuration and does not make up missing measurements.
- Switching module/entity/context mode changes the manifest deterministically.
- Stale cached context is invalidated when source versions change.
- Prompt-injection instructions in papers/tool results cannot alter permission policy.

### Frontend and session behavior
- Global chat and at least Lit2Plan, Experiment and DL Lab use the shared chat components.
- A stream is associated with the correct session and message order is stable.
- Stop/cancel, provider switch, retry and errors are communicated accurately.
- Unsupported capabilities are disabled or explained, not falsely applied.
- Manual controls actually affect the outgoing context, policy, or execution behavior.
- Existing direct module workflows still operate.

### Memory and output
- Off mode performs no memory extraction/write.
- Manual/Suggest modes require explicit approval before durable memory writes.
- Restricted Auto mode writes only allowed memory types and refuses unsafe/ambiguous candidates.
- Candidate/source links survive persistence and are visible in the UI.
- Duplicate and conflicting candidate records are detected and reviewed.
- Saving an artifact does not automatically grant permission to apply it to the project.

### Regression
- All existing automated tests still pass, except failures that are demonstrably pre-existing and documented.
- Run existing lint/typecheck/build commands.
- Provide manual smoke-test steps for anything that cannot be automated.

---

## 16. Observability and diagnostics

The user needs to understand what the system actually did without exposing secrets.

Provide a session activity timeline containing:
- context compilation and source IDs (not sensitive raw contents by default);
- provider launch/model/capability selection;
- security profile and effective permissions;
- MCP tool proposals, approvals, denials, and outcomes;
- tool/process status and duration where measured;
- artifacts collected and changes staged/applied;
- memory candidates generated, saved, rejected or superseded;
- errors and retries.

Provide diagnostics/export suitable for bug reports, with secrets and sensitive paths redacted. Keep a clear difference between model-generated text, actual tool output, measured experiment results, inferred suggestions, and user-approved decisions.

---

## 17. Documentation to update

Update or create docs that match the repository's conventions:

- architecture overview and component responsibilities;
- provider adapter contract and capability registry;
- CLI workspace and security profiles;
- context manifest and module adapter contract;
- universal chat UX and session lifecycle;
- MCP permissions/approval model;
- memory schema, modes, provenance and retention;
- how to configure data root/providers/sandbox/container dependencies on Windows and other supported platforms;
- threat model, limitations and safe troubleshooting;
- milestone/acceptance report with actual tests executed.

Include diagrams where useful, but keep the prose actionable for a future developer.

---

## 18. Implementation rules for the coding agent

- Reuse existing code and patterns when they are sound. Do not create duplicate gateways, registries, session stores, memory engines, or chat systems just to match the names in this prompt.
- Prefer small vertical slices that compile and can be tested over a large batch of unverified changes.
- Before editing a core subsystem, identify callers and compatibility impact.
- Create a test before or with every security-critical change.
- Use typed validation at boundaries: provider events, context manifests, MCP arguments, action payloads, persisted metadata and file paths.
- Do not expose arbitrary shell execution through a generic public API. Keep process spawning behind a narrow backend boundary and policy engine.
- Keep UI state separate from authoritative domain state. Use domain services for both AI-proposed actions and manual UI actions.
- Do not hard-code one provider's assumptions into the universal chat model.
- Do not claim hidden reasoning/chain-of-thought access. Provide only supported, user-visible reasoning/status data and traceable tool activity.
- If a feature cannot be implemented with existing provider capabilities, implement a graceful fallback or mark it unsupported with a visible reason; do not fabricate functionality.
- When an action might destroy data, modify canonical project files, incur substantial compute/API cost, upload data externally, or alter security permissions, show the impact and require the appropriate approval.
- Do not stop after producing a plan. Implement and test the safest coherent increments possible in the current task.
- If blocked, state the precise blocker, preserve a working state, and document the smallest next action. Do not conceal unimplemented work behind mock data or a fake success state.

---

## 19. Definition of done

The upgrade is not complete merely because a chat UI renders. It is complete when:

1. Existing CLI integrations run through the managed gateway rather than opening in the PhD Research Lab project root.
2. Every supported chat entry point binds to the correct module/entity context through a context adapter.
3. Provider and MCP choices are available flexibly, but only within real provider capabilities and enforced permission policies.
4. Global chat, module chat, and optional inline chat share the same session/event/component architecture.
5. User can inspect/override context, MCP tools, security profile, output capture, and memory mode through Manual/Advanced controls.
6. Existing non-chat/manual research workflows remain available.
7. Long-term memory stores selectively reviewed/allowed research knowledge with provenance instead of blindly storing raw conversations.
8. Artifacts and code changes are staged/reviewed before entering canonical project state.
9. Tests cover the security boundaries and module context routing, and build/test status is reported truthfully.
10. Documentation describes the actual implementation and remaining limitations.

At completion, provide:

- a concise architecture change summary;
- files/components added or changed;
- milestones completed and deferred;
- commands/tests run with exact results;
- security limitations by provider/OS;
- migration/rollback notes;
- manual smoke-test instructions;
- known bugs and next recommended milestone.

**Start now with Phase 0 repository audit, then implement the highest-value safe vertical slice. Do not ask the user to repeat repository details that are already present in the codebase; inspect them.**

---

## 20. Official documentation to re-check during implementation

Provider options and flags evolve. Check docs matching the installed versions instead of treating this list as a permanent API contract:

- OpenAI Codex CLI overview/approval modes: https://help.openai.com/en/articles/11096431
- Gemini CLI sandboxing: https://geminicli.com/docs/cli/sandbox/
- Anthropic engineering overview of Claude Code sandboxing: https://www.anthropic.com/engineering/claude-code-sandboxing
- MCP TypeScript SDK documentation: https://ts.sdk.modelcontextprotocol.io/

The purpose of these links is to guide verification of provider-specific controls. The PhD Research Lab gateway must keep its own version-aware capability and permission model rather than assuming the three providers behave identically.
