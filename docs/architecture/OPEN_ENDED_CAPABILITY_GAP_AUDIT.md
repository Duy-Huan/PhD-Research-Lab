# Open-ended capability learning: implementation boundary audit

Audit date: 2026-10-26. Source: the uncommitted 6.5.8 candidate in the existing dev worktree. This is a source audit and design proposal, not a completed autonomous-learning experiment. See agent/OPEN_ENDED_CAPABILITY_LEARNING.md for the owner policy and agent/research-quality-objectives.json for unqualified objectives.

The environment should help an agent learn reusable procedures without choosing the scientific method on its behalf. Explore, Attempt, Evaluate, Learn, Propose and Evolve are capabilities that can be revisited, rather than mandatory stages of every chat or six new workflow services. Ordinary conversation remains ordinary conversation.

## Existing components and missing connections

| Capability | Existing implementation to reuse | Confirmed gap / required evidence |
|---|---|---|
| Explore | Provider registry/connections, MCP tool catalog, project context, resource governor | Listing a tool, successful authentication and successful inference are separate observations. Native Codex synthetic inference is proven separately; complete research tools and every provider are not qualified. |
| Attempt | Agent action proposals, missions, experiment records, native CLI sandbox and code projects | The model can propose existing actions; general open-ended tool strategy, interruption recovery and scoped ordinary decision delegation require end-to-end qualification. Fixed domain pipelines remain optional tools, not the definition of autonomy. |
| Evaluate | Existing software Verification Harness, research verifiers, evidence/artifact/provenance stores | A stored metric or a human-approved candidate alone does not establish fresh execution, reproducibility or scientific validity. Bind evaluations to actual execution, immutable candidate identity and frozen oracle cases. Keep development verification separate from research execution. |
| Learn | backend/memory/lifecycle.py candidates/review, research failure records, backend/agent/memory_modes.py, backend/agent/skills.py | Candidate kinds are observation/decision/experiment_result/failure/claim/note. There is no qualified procedural-skill candidate with revision/evaluation/activation lineage. save_user replaces the active Markdown file directly; it is not a verified learning or rollback protocol. |
| Propose | Existing action schemas/approvals, memory candidates, mission/task records | Capability-gap proposals need explicit evidence, missing resource/permission/data, expected benefit, cost, risk and evaluation plan. No new right can be inferred from a proposed gap. |
| Evolve | Existing isolated execution, experiments and admission policy | Complete baseline-versus-candidate evaluation, held-out transfer, scoped activation, failure recovery and rollback have NOT_RUN status. A successful sandbox process is not authorization to change the main application. |

## Smallest coherent implementation path

Extend the existing candidate lifecycle and skill repository, rather than building another Research Engine. A proposed procedure needs complete source text and immutable digest, a project scope, purpose and applicability, input/output contract, required tool/model/data versions, preconditions, known failure cases, requested permissions, source evidence IDs, predecessor revision and rollback target. Keep proposal text outside active skill lookup until admission succeeds. Do not reuse the current 4000-character general-memory truncation for complete procedure source; reject an explicit declared size limit or preserve the full artifact with a retrievable pointer.

Record actual evaluation attempts against the exact candidate digest and frozen case-set digest. Store raw execution/artifact references, current baseline identity, outcome, budget/resource use and verifier identity. Preserve failed, blocked and inconclusive attempts. The candidate cannot provide an authoritative PASS field or approve its own evaluation. A model may critique results, but deterministic verifiers and appropriate researcher review establish the measured result and its limits.

Admission requires an evaluation appropriate to the claimed capability and the existing authorization policy. Approval authorizes activation; it does not turn an unexecuted method into a verified method. Use atomic project-scoped activation of an immutable revision, retain the prior active revision and support rollback. Never silently shadow a built-in command or a separately reviewed skill with an automatically learned procedure. Recheck that its permissions remain within the current grant when invoked, not just when admitted.

Use existing event, task and experiment records to persist progress across interruption. No six-service orchestration layer is needed. Runtime learning may write scoped project data under its authorization; upgrades to application source, development skills, security controls or quality gates enter the normal single-dev development process.

## Frozen acceptance cases before capability claims

1. A proposed skill is retrievable as a candidate but absent from active command lookup.
2. Failed, unavailable, skipped or unrelated evaluation cannot activate it; changing its text invalidates prior evaluation.
3. A real local experiment retains its actual outputs and a failed method as well as a successful method. Scientific correctness remains a separate judgment.
4. An admitted revision works on held-out tasks, with identical baseline/candidate data and budgets; its teaching example alone cannot establish transfer.
5. Project B cannot read or activate project A's private candidate, raw data or credentials.
6. Embedded instructions in papers, logs and candidate text cannot grant rights or replace system/development policy. Sensitive information cannot be promoted into reusable shared skills.
7. Interrupted evaluation/admission resumes without duplicate activation or loss of earlier failures; concurrent updates cannot silently overwrite the active revision.
8. A later regression can disable the affected revision and restore its exact predecessor with an auditable reason, without deleting evidence or changing protected Git history.

These cases are a proposed acceptance contract, currently NOT_RUN, not invented passing tests. The current measured corrections remove several obstacles to agency (keyword interception, premature native turn completion, delayed streaming and clipped profile instructions). They do not complete this learning mechanism or demonstrate L3/L4.
