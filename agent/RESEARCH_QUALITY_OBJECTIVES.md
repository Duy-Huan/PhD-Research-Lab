# Persistent objective: credible L3 research, progressing toward L4

Owner requirement,2026-10-25: optimize PhD Research Lab for research quality rather than feature count. Aim to demonstrate L3 research autonomy in a declared computational domain and develop evidence toward L4. This is an unfinished objective for every future AI session. **Current level is UNASSESSED; L3/L4 are NOT demonstrated.** Do not change that status without actual qualification evidence.

Read this file and research-quality-objectives.json before architecture, agent, memory, provider, project or workflow changes. Read AGENT_CORE_UPGRADE.md for the current migration/implementation task. Work only on dev; preserve all user data, worktrees and agent/skills files.

## Owner's authoritative product definition

> PhD Research Lab is an agent-native scientific research environment that provides persistent knowledge, memory, computation, experimentation, collaboration, and verifiable evidence infrastructure, while allowing advanced AI agents to autonomously develop and execute their own research strategies.

Build one environment, not separate L2/L3/L4 research engines. Autonomy varies through authority, action scope, approval conditions and verifiability: L2 retains human approval for consequential research decisions; L3 delegates ordinary decisions within an authorized charter and escalates exceptions; L4 additionally requires demonstrated credible and accountable closure. The first implementation action is to audit existing backend interference with reasoning and remove unnecessary constraints. Infrastructure supplies knowledge, memory, tools, computation, collaboration and evidence; it must not prescribe a scientific strategy merely because a workflow template exists. Security boundaries, resource bounds and truthful evidence validation remain enforced.

## Definitions and source boundaries

The owner selected [AutoResearch AI,2605.23204v1](https://arxiv.org/html/2605.23204v1), especially Introduction/Figures1-2, Sections3-4 and6, and [AI-Researcher,2505.18705v1](https://arxiv.org/html/2505.18705v1), especially Sections2-4 and6. Use these exact versions for the design baseline; later versions require a documented comparison. They are research proposals/results, not a certification standard.

- L3 in the survey means AI leads ordinary research coordination and scientifically credible progress; humans supervise, assist and handle exceptions rather than verify each routine transition.
- L4 is an aspirational regime of end-to-end ordinary workflow closure with retained institutional accountability. Do not advertise universal autonomy or infer it from a narrow demonstration.
- Existing Research Harness L1-L4 names are implementation layers. Scientist-Bench Level1/Level2 are guided/open-ended task settings. Neither is the survey's autonomy scale. Always state which scale is being used.

Preserve useful L1-L4 harness behavior and data while retiring active Feynman/OpenScience integrations. A native engine, several role names, fluent chat, passing CI, many tools, a long run or an exported paper cannot by themselves establish research autonomy or scientific correctness.

## Architecture decisions for PhD Lab

Apply the owner's [Open-Ended Capability Learning](OPEN_ENDED_CAPABILITY_LEARNING.md) principle at environment level. Agent-designed strategies, diagnostics, skills and sandbox upgrades must be evaluated through observable evidence and scoped permissions, not proliferating fixed domain workflows. The complete learning cycle remains unqualified until actual evaluation demonstrates it.

1. **One project = one topic/paper.** A persistent research charter holds the question, scope, prior-art boundary, success/falsification criteria, budget and authorized tools. Multiple experiments remain under code/. Keep each experiment's distinct hypothesis, implementation revision, dataset/configuration, execution and analysis. Do not create a second planning/database framework when an existing mission/topic/artifact store can represent this.
2. **Model-led reasoning, code-enforced constraints.** Reuse the orchestrator, task/mission envelopes, model gateway and tool registry. Open questions and follow-ups reach the model with the user's actual context; keyword matches must not silently turn questions into runs. The model proposes plans/actions; schemas, permissions, project boundary, budgets and evidence validators decide which actions execute and what is verified. Record concise decisions and observable reasons, not private chain-of-thought.
3. **Research is a feedback loop.** Failed or contradictory results can invalidate the hypothesis or method, revise the research charter within authorized scope, select an alternative, or stop with a justified negative/inconclusive outcome. Do not merely tune code until a metric improves or convert every completed pipeline into a successful scientific finding. Preserve rejected paths and reasons.
4. **Maintain scientific commitments.** Represent method components and their mathematical definitions, required code components, tests and experiment assertions explicitly. Implementation completion requires these commitments to be checked. An executable simplified substitute must not pass for the requested method; missing components remain visible after many turns/restarts.
5. **Preserve precise long-term context.** Reuse existing session/memory/retrieval/context stores. Keep source passages, equations, assumptions, constraints, unresolved contradictions, failed attempts, evidence IDs, and code/configuration references. Summaries are indexes with raw pointers, not replacements for originals. Make omission and token-budget pressure visible; retrieve the exact source on demand rather than silently truncate decisive scientific detail. Current scoped user statements override stale recall.
6. **Learn procedures with evidence.** Extend existing skill/memory mechanisms with versioned candidate procedures, source/outcome links, evaluated held-out use, review/activation and rollback. Store failures and scope restrictions as well as success. Retrieved or generated skills cannot grant permissions or edit core code themselves. Do not activate skill instructions merely because an LLM says they work. Procedural learning is not training foundation-model weights.
7. **Challenge conclusions independently.** Reuse verifier/critic roles and deterministic evidence tools. Separate generation from validation: replay, baseline checks, statistical/design checks and theory-to-code oracles must constrain claims. LLM reviewers provide advisory critique; shared models/prompts/memory can correlate errors. Do not let polished writing or consensus compensate for missing controls or falsified evidence.
8. **Unified providers remain replaceable.** API, local and supported native CLI adapters share contracts for model selection, context, tools, cancellation, failure/fallback and actual usage. Official ChatGPT subscription uses Codex CLI sign-in, never token scraping/API-key substitution. Preserve provider identity and unknown usage. More providers/models/roles are not evidence of more intelligence. Native isolation cannot be disabled to obtain a passing connection.

## Evidence required before claiming L3

The JSON companion defines individually tracked criteria. All critical criteria must be qualified in the declared domain; an average score cannot compensate for invalidity, unsafe access, missing provenance or fabricated claims.

- Frozen, representative guided and open-ended cases with held-out questions, fixed data availability, model/provider versions, budgets and stopping rules. Baseline/candidate use the same suite/environment/policy. A paper used as answer material must not also serve as an unseen novelty target.
- Source-grounded hypotheses with explicit alternatives, feasibility and prior-art limits; baseline/control/ablation plans and appropriate uncertainty methods chosen before looking at final metrics. Any post-hoc changes are disclosed and rerun, not rewritten as preregistered success.
- Actual implementations and executions, raw measurements, fresh replay and output/claim consistency. Unit fixtures, synthetic demonstrations, scientific simulations and real-domain experiments are labeled distinctly. Missing infrastructure is BLOCKED, not a safe rejection or PASS.
- Held-out faults: omitted method component, wrong metric, leakage, stale/contradictory memory, poisoned source/skill, provider failure, interrupted run and unsupported conclusion. The system must detect/reject/escalate correctly and preserve the evidence.
- Long-work continuity through many turns and process/session restarts, without lost requirements, duplicate experiments, cross-project memory leakage or invented recovery. Choose the concrete turn/restart/case counts and budgets before running the qualification campaign; report denominators and every attempt.
- Track who controlled hypotheses, branch/research-direction selection, rejection, replanning and stopping. Record initial authorization, routine human verification, scientific rescue, exception handling and final publication review separately. If humans still verify ordinary consequential steps, do not claim L3 merely because the pipeline is automated.
- A paper/report assembled from verified artifacts, with traceable claims/tables/figures/citations, null results, failed experiments, uncertainty and limits. An inconclusive or negative scientific result may be a correctly completed investigation; a plausible-looking unsupported positive claim may not.

Report novelty, validity, impact, reliability and provenance separately, with their evidence and unknowns. Novelty is scoped to the searched prior art and time; impact requires actual research usefulness/follow-up, not an invented universal score. Stochastic benchmark success is a measured sample, not a guarantee of100% reliability.

Software regression still requires100% execution/PASS of mandatory cases. Desired production line/branch coverage is100%, currently informational/nonblocking. Those software metrics do not replace scientific qualification. QA/main retain real provider/research/UAT requirements and protected native promotion.

## Progress toward L4

Only after credible scoped L3 qualification: evaluate autonomous continuation across linked investigations, reliable rejection/stopping under changed assumptions, scientific correction/retraction, useful outcomes over time, and robust closed-loop recovery without routine human rescue. Expand domains only when their actual validation mechanisms are available. No clinical, embodied or wet-lab autonomy claim may be borrowed from computational test success. Keep oversight, authorization and accountable publication controls.

## Mandatory continuation record

For every relevant task, update STATE/PLAN with: affected research-quality criterion; source/contract/model/environment identity; actual case results and human interventions; code/experiment/report evidence links; residual scientific and infrastructure uncertainty; next highest-priority unqualified criterion. Keep criterion status NOT_RUN/BLOCKED/PARTIAL until measured evidence justifies qualification. Never silently mark this objective complete or replace it with a feature checklist.
