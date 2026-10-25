# Open-Ended Capability Learning

Owner principle: **Don't build an AI Scientist. Build an environment where an AI Scientist can learn to become more capable.**

This is an environment-level learning mechanism, not a mandatory six-step research template or a new Research Engine. An agent chooses the scientific strategy for the actual question. The environment provides persistent knowledge/memory, typed tools, computation, isolated experiments, collaboration, permissions and verifiable evidence. L2/L3/L4 use the same environment with different scoped authority and verification obligations.

Current status: DESIGN_RECORDED, runtime learning qualification NOT_RUN. Do not claim that this complete mechanism has been implemented or that the system reached L3.

## Learning cycle and reuse

| Stage | Agent authority inside its grant | Reuse and required record |
|---|---|---|
| Explore | Inspect discoverable tools, resource limits, accessible datasets, previous outcomes and current capabilities | Existing tool/provider catalogs, resource governor, context and research stores. Record actual availability and limits; authentication/model listing is not successful inference. |
| Attempt | Select a relevant challenge or small diagnostic and design its method | Existing mission/task/experiment services and paper project's code/experiment folders. Record objective, assumptions, tool/data versions, budget, expected observable outcome and stopping conditions. No prescribed number of hypotheses or domain workflow. |
| Evaluate | Use appropriate tests, actual experiments, evidence and researcher feedback | Existing verifiers, evidence/artifact graph and regression harness. Keep expected rejection, failed method, verifier error and unavailable infrastructure distinct. Self-generated sanity tests are not independent qualification. Freeze held-out/oracle cases before promotion evaluation. |
| Learn | Propose a reusable skill/method, failure lesson or applicability condition | Extend existing skill and memory candidate/review mechanisms. Retain evidence IDs, successful/failed cases, scope, preconditions, revisions and rollback. Unverified model text is a proposal, not trusted experience. |
| Propose | Explain a demonstrated capability gap and an upgrade that may address it | Existing proposals/admission policy. Name missing tool/data/permission, evidence, expected benefit, resource/cost impact and verification plan. A gap never grants its own permission. |
| Evolve | Test an authorized candidate upgrade in a private sandbox | Existing isolated execution and experiment records. Compare candidate against current environment on the same frozen cases. Only verified candidates may be proposed for the main environment; keep failed candidates and reasons. |

Use stored events/artifacts for phase outcomes rather than creating six new services or workflow engines. The cycle may revisit/reject stages as evidence changes. It must not force a conversational answer into six headings or turn every ordinary question into a research job.

Evaluate resource cleanup as well as task output. A successful model reply or passing smoke assertion does not prove that owned processes, proxy containers, model allocations or temporary execution resources were released. Retain ownership records and failures; cleanup must not affect another concurrent request or destroy research evidence.

## Trust, activation and source boundaries

- Runtime skills belong to the scoped paper project and its existing data stores. Repository skills/ contains reviewed development guidance and must not be overwritten/deleted by learning agents. Keep source evidence and candidate instructions separate from trusted system instructions.
- A skill candidate records purpose, inputs/outputs, preconditions, known failures, applicable tool/model/data versions, permissions needed, evidence, evaluation results, superseded version and rollback. Claims about broader applicability require transfer/held-out evidence.
- Activation follows explicit owner policy. An approved project may delegate ordinary low-risk decisions within its existing grant; new permissions, external destinations, cost commitments, global tool installation or main-environment source changes require the applicable authorization. A successful sandbox run does not expand its own grant.
- The main application source, authorization controls and quality gates are not self-modification targets. An environment upgrade requiring code becomes a reviewed development task on the single dev branch, followed by complete local verification and protected CI/CD. A private experiment sandbox is not a new Git development branch.
- Retain raw outcomes and prior versions; reject skill/source injection, credential memorization, cross-project leakage and unsupported conclusions. Do not convert a model's confidence or fluent explanation into a verified capability.
- The three-cycle development CI repair limit and the separately bounded AI-UAT allowance are not a universal limit of three research experiments. Research exploration uses its authorized time/compute/token/data budgets and stopping policy; those controls bound actions without prescribing a method.
- Procedural learning does not imply foundation-model training or improved model weights. If training is later proposed, it needs a separately specified dataset, rights, evaluation, compute and deployment decision.

## Evidence before activation or autonomy claims

Record every attempt with source/model/tool/data identity, actual action/observation, budget/resource use, result classification, feedback, human intervention and evidence references. Include failed and inconclusive cases. Demonstrate useful reuse, conflict handling, scope restriction, interrupted-run recovery, rejection of poisoned skills and rollback. Compare the environment with and without the learned procedure on held-out cases; repeated success on the teaching example is insufficient.

Assess research quality and autonomy separately under RESEARCH_QUALITY_OBJECTIVES.md. New tools or skill count are not intelligence scores. Usefulness, method fidelity, trustworthy conclusions, recoverable failures and reduced routine human rescue are the relevant outcomes. Update STATE/PLAN and research-quality-objectives.json honestly; unexecuted mechanisms remain NOT_RUN.
