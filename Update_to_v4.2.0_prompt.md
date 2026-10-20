# PhD Research Lab v4.1.0
## Unified Workflow Orchestrator — Agent Harness + Model Intelligence + Optuna + Ray Tune

**Version:** 3.6.0  
**Codename:** Unified Research Workflow Orchestrator  
**Primary objective:** Build a flexible, extensible, research-oriented workflow engine that combines agent planning, model analysis, hyperparameter optimization, experiment execution, evaluation, and human supervision.

---

# 1. ROLE AND MISSION

You are the lead software architect and implementation engineer for the existing PhD Research Lab repository.

Upgrade the actual repository from v3.5 to v3.6.

The system already has, or is intended to have, the following architectural components:

- Research State and Context Memory
- Evidence and Provenance
- Context Gateway
- Provider Gateway
- MCP Gateway
- Pydantic AI Harness integration
- Agent planning and execution loops
- Python Sandbox
- Docker execution
- Deep Learning Lab
- Dataset and experiment management
- Model analysis and evaluation
- ClearML/MLflow integration, if implemented
- Streaming and workflow observability

Do not assume every feature from earlier plans has been implemented. Inspect the repository first.

The v3.6 objective is to connect these components into a single **Workflow Orchestrator** while supporting multiple workflow templates and different autonomy levels.

The researcher must be able to choose:

1. Fully manual execution.
2. AI-assisted execution with approval gates.
3. Bounded automation.
4. Custom workflows mixing manual and automatic steps.
5. Reusable workflows that can invoke other workflows.

Do not build one rigid end-to-end pipeline.

## Core architectural principle

- **PhD Research Lab:** owns research state, memory, evidence, provenance, and durable experiment records.
- **Pydantic AI Harness:** owns agent planning, delegation, tool orchestration, and replanning.
- **Model Intelligence Engine:** inspects models, estimates complexity, validates search spaces, and assesses resource requirements.
- **Optuna:** owns hyperparameter search and study logic.
- **Ray Tune:** optionally manages trial scheduling and parallel/distributed execution.
- **Sandbox/Docker:** isolates code and experiment execution.
- **Evaluation Engine:** calculates and validates experiment metrics.
- **Researcher:** retains authority over research hypotheses, important decisions, and publication-facing claims.

The models and frameworks must remain replaceable.

---

# 2. FIRST STEP: AUDIT THE REAL REPOSITORY

Before modifying code, inspect the existing codebase.

Audit:

- Project structure and versioning.
- Existing Harness adapter and agent loops.
- Context Gateway and MCP interfaces.
- Research State and persistence.
- Existing workflow/task abstractions.
- Deep Learning Lab implementation status.
- Model import and parsing capabilities.
- Complexity profilers.
- Python Sandbox and Docker execution.
- Experiment lifecycle and artifact storage.
- Evaluation metrics.
- ClearML/MLflow integration, if present.
- Existing frontend and backend APIs.
- Streaming, logging, permissions, and approval gates.
- Current dependency manager, lockfiles, and test framework.

Identify which functionality already exists and which functionality is only planned.

Create:

`docs/architecture/workflow-orchestrator-v3.6-audit.md`

Include:

- Current architecture diagram.
- Existing reusable components.
- Missing components.
- Duplicate functionality that should not be reimplemented.
- Compatibility and migration risks.
- Proposed implementation sequence.
- Dependencies and version compatibility.

Do not modify the application during the initial audit.

After the audit, implement incrementally and run tests at every milestone.

---

# 3. TARGET ARCHITECTURE

Implement the following logical architecture, adapting names and paths to the actual repository.

```text
                    RESEARCHER
                        |
                        v
               PhD Research Lab UI
                        |
                        v
              WORKFLOW ORCHESTRATOR
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
     Workflow       Workflow       Human
     Registry       State          Approval
          |
          v
              WORKFLOW STEP ROUTER
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
  Agent Harness   Model Intelligence   Manual Step
       |                |
       |                +-- Model Adapters
       |                +-- Complexity Analysis
       |                +-- Resource Estimation
       |                +-- Search Space Validation
       |                +-- Optuna Study Manager
       |                +-- Ray Tune Adapter
       |
       v
              Approved Tool Gateway
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
 Context/MCP       Sandbox/Docker    Evaluation
       |                |                |
       +----------------+----------------+
                        |
                        v
               Results and Artifacts
                        |
                        v
               Evidence / Provenance
                        |
                        v
                Researcher Review
                        |
                        v
               Research State Update
```

The Workflow Orchestrator coordinates components but must not duplicate their responsibilities.

---

# 4. FLEXIBLE WORKFLOW EXECUTION MODES

Support four execution modes.

## Mode A — Manual

The researcher controls every important transition.

The system may provide:

- Context retrieval.
- Model analysis.
- Complexity calculations.
- Search-space recommendations.
- Trial-result visualization.
- Experiment comparisons.
- Report generation.

However, it does not automatically proceed through consequential steps.

Example:

```text
Import Model
    |
    v
Analyze Complexity
    |
    v
Researcher Reviews
    |
    v
Generate Search Space
    |
    v
Researcher Edits Parameters
    |
    v
Researcher Starts Study
    |
    v
Review Results
    |
    v
Researcher Selects Next Experiment
```

Use for novel methods, sensitive data, early research exploration, or experiments whose methodology has not been validated.

## Mode B — Assisted

This should be the recommended default for a new research project.

The Harness proposes the plan and performs approved low-risk tasks. The researcher approves important transitions.

Example:

```text
Research Objective
    |
    v
Harness Creates Plan
    |
    v
Model Intelligence Analyzes Model
    |
    v
Harness Proposes Search Space
    |
    v
Human Approval
    |
    v
Optuna Runs Bounded Study
    |
    v
Evaluation Validates Results
    |
    v
Harness Interprets Findings
    |
    v
Human Reviews Conclusion
```

## Mode C — Bounded Automation

The system executes a predefined workflow within strict limits.

Requirements:

- Maximum trial count.
- Maximum workflow cycles.
- Maximum runtime.
- Maximum concurrency.
- Resource limits.
- Allowed tool list.
- Defined evaluation protocol.
- Explicit stop conditions.
- Approval gates for sensitive or consequential actions.

Example:

```text
Retrieve Context
    |
    v
Validate Dataset
    |
    v
Inspect Model
    |
    v
Generate Search Space
    |
    v
Validate Constraints
    |
    v
Run Optuna Study
    |
    v
Evaluate Candidates
    |
    v
Verify Artifacts
    |
    v
Generate Report
    |
    v
Pause for Researcher Review
```

Automation must stop when a budget is exhausted, required evidence is missing, validation fails, or an approval is needed.

## Mode D — Custom Workflow

Allow researchers to combine and reorder approved steps.

Example:

```text
Manual: Select Hypothesis
        |
Automatic: Retrieve Evidence
        |
Automatic: Analyze Model
        |
Manual: Approve Architecture
        |
Automatic: Search Hyperparameters
        |
Manual: Select Candidate
        |
Automatic: Run Confirmation Experiment
        |
Manual: Approve Conclusion
```

A workflow may contain manual, assisted, and automatic steps simultaneously.

Changing a workflow's execution mode must not require rewriting the workflow implementation.

---

# 5. WORKFLOW REGISTRY AND COMPOSITION

Create a versioned workflow registry.

Each workflow definition should include:

- `workflow_id`
- `name`
- `version`
- `description`
- `execution_mode`
- `input_schema`
- `output_schema`
- `steps`
- `dependencies`
- `conditions`
- `approval_policy`
- `retry_policy`
- `resource_budget`
- `timeout`
- `allowed_tools`
- `failure_policy`
- `provenance_policy`

Support:

- Sequential steps.
- Conditional branches.
- Parallel steps where safe.
- Retryable steps.
- Human approval steps.
- Checkpoints.
- Pause/resume.
- Cancellation.
- Nested workflows.
- Reusable workflow components.
- Versioned templates.

A workflow must declare its input and output contracts.

A nested workflow must receive explicit inputs and return structured outputs. Do not allow hidden state mutation between workflows.

## Example workflow composition

```text
Research Planning Workflow
          |
          v
Model Feasibility Workflow
          |
          v
Search-Space Design Workflow
          |
          v
HPO Workflow
          |
          v
Candidate Verification Workflow
          |
          v
Research Review Workflow
```

The researcher must be able to run any workflow independently or compose several into a larger workflow.

---

# 6. INITIAL WORKFLOW TEMPLATES

Implement the following reusable templates.

## Template 1 — Research Planning

Purpose: turn a research request into a structured, reviewable plan.

Steps:

1. Retrieve current research state.
2. Retrieve relevant evidence and prior experiments.
3. Identify objective, hypothesis, constraints, and missing information.
4. Have the Harness generate a proposed plan.
5. Identify which steps require tools, model analysis, experiments, or human decisions.
6. Estimate resources and identify risks where possible.
7. Present the plan for approval.
8. Save the approved plan and provenance.

No training starts in this workflow.

## Template 2 — Model Feasibility Audit

Purpose: assess whether a model is feasible before expensive training.

Steps:

1. Validate model format and adapter availability.
2. Validate input/output shapes.
3. Count parameters and trainable parameters where supported.
4. Calculate FLOPs/MACs where supported.
5. Estimate activation and optimizer memory when possible.
6. Measure actual memory usage with a safe dry run when feasible.
7. Measure latency and throughput using warm-up and repeated runs.
8. Compare requirements against available hardware.
9. Generate a report with measured, estimated, and unavailable values.
10. Save the report as an artifact.

Do not launch full training by default.

## Template 3 — Search-Space Design

Purpose: create a bounded and technically valid hyperparameter search space.

Steps:

1. Retrieve the hypothesis, baseline, previous trials, and known failures.
2. Inspect the model and training configuration.
3. Have the Harness propose tunable parameters.
4. Explain why each parameter is relevant.
5. Validate types, ranges, conditional parameters, and dependencies.
6. Estimate trial cost and resource requirements.
7. Remove invalid or redundant configurations.
8. Show the proposed search space to the researcher.
9. Allow manual edits.
10. Save an approved, versioned search-space artifact.

Do not execute arbitrary Python generated by an LLM.

## Template 4 — Hyperparameter Optimization

Purpose: search for strong configurations using Optuna.

Steps:

1. Validate the dataset split and evaluation protocol.
2. Validate baseline metrics and objective directions.
3. Validate the search space.
4. Select a suitable sampler.
5. Create a persistent Optuna study.
6. Execute trials through the local runner or optional Ray Tune adapter.
7. Collect intermediate and final metrics.
8. Prune trials only when intermediate metrics are valid and comparable.
9. Record configurations, seeds, failures, resource use, and artifact references.
10. Rank candidates.
11. Run confirmation experiments where appropriate.
12. Generate a reproducibility report.

Do not assume the best trial is globally optimal or publication-ready.

## Template 5 — Multi-Objective Optimization

Purpose: compare model quality and computational cost.

Potential objectives:

- Maximize PSNR.
- Maximize SSIM.
- Maximize F1 or accuracy.
- Minimize parameter count.
- Minimize FLOPs/MACs.
- Minimize measured inference latency.
- Minimize measured peak VRAM.

The objective set must be task-specific.

Return a Pareto frontier when supported. Explain trade-offs rather than inventing a universally best model.

Keep measured and estimated metrics distinct.

## Template 6 — Failure Diagnosis

Purpose: recover safely from failed experiments.

Steps:

1. Collect structured error logs and trial metadata.
2. Classify the failure.
3. Retrieve similar historical failures.
4. Have the Harness propose a diagnosis.
5. Present evidence and confidence.
6. Apply only approved, safe recovery actions.
7. Retry within the remaining budget.
8. Record the failure and resolution with provenance.

Potential failure categories:

- Out of memory.
- Invalid data or configuration.
- Numerical instability.
- Timeout.
- Provider/tool failure.
- Infrastructure failure.
- Poor validation performance.

Changes to dataset semantics, evaluation protocols, or the research hypothesis require approval.

## Template 7 — Researcher-Led Experiment

Purpose: automate execution without automating the researcher's scientific judgment.

Steps:

1. Researcher specifies hypothesis and experiment configuration.
2. System validates the configuration.
3. Harness proposes an execution plan.
4. Researcher approves the plan.
5. Sandbox/Docker executes the experiment.
6. Evaluation calculates metrics.
7. Harness summarizes findings against the hypothesis.
8. Researcher accepts, rejects, or revises the interpretation.
9. Approved observations are recorded.

## Template 8 — Full Bounded Research Loop

Purpose: coordinate planning, analysis, HPO, execution, and verification.

Steps:

1. Retrieve current research state.
2. Harness proposes a research plan.
3. Researcher approves objective and budget.
4. Model Intelligence inspects model, dataset, and hardware compatibility.
5. Harness proposes the search space.
6. Deterministic validation checks feasibility.
7. Researcher approves the study configuration.
8. Optuna proposes trials.
9. Local execution or Ray Tune runs trials.
10. Evaluation validates metrics and artifacts.
11. Harness analyzes results against the hypothesis.
12. Verification checks reproducibility and protocol compliance.
13. Workflow pauses at configured approval gates.
14. Researcher chooses the next action.
15. The system records approved experiment results.

Every loop must have a hard maximum number of cycles and trials.

## Template 9 — Ablation Study

Purpose: evaluate the contribution of model components.

Steps:

1. Identify baseline and proposed components.
2. Generate candidate ablation variants.
3. Validate that only intended factors change.
4. Execute bounded experiments.
5. Evaluate all candidates using a consistent protocol.
6. Compare results and uncertainty where feasible.
7. Generate an ablation table.
8. Ask the researcher to approve the interpretation.

## Template 10 — Candidate Confirmation

Purpose: validate the best HPO candidates before accepting conclusions.

Steps:

1. Select top candidates using declared ranking rules.
2. Define confirmation seeds or repeat runs.
3. Keep the evaluation protocol consistent.
4. Execute confirmation experiments.
5. Aggregate results with suitable statistics.
6. Compare against the baseline.
7. Report variance and limitations.
8. Ask the researcher to approve any research conclusion.

---

# 7. PYDANTIC AI HARNESS INTEGRATION

Reuse the existing v3.5 Harness adapter.

The Harness is responsible for:

- Planning.
- Agent loops.
- Tool selection.
- Subagent delegation.
- Replanning.
- Verification coordination.
- Interpretation of validated observations.

Suggested agent roles:

- Research Director.
- Research Planner.
- Literature Researcher.
- Model Analyst.
- Experiment Designer.
- HPO Strategist.
- Experiment Executor.
- Evaluation Agent.
- Research Critic.
- Paper Reviewer.

Do not activate every agent for every task.

The Harness should decide whether delegation is useful based on workflow policy and budget.

All tool calls must go through approved interfaces such as MCP and the existing tool gateway.

The Harness must not directly access the research database or unrestricted filesystem.

---

# 8. MODEL INTELLIGENCE ENGINE

Create an extensible model adapter registry.

Potential adapters include:

- PyTorch `nn.Module`.
- TensorFlow/Keras.
- ONNX.
- TorchScript.
- Hugging Face model wrappers, where applicable.
- User-defined Python model adapters.

Support must be based on tested adapters, not assumptions that all formats are interchangeable.

Each adapter should declare:

- Supported format and version.
- Input/output requirements.
- Supported analysis operations.
- Whether loading requires trusted custom code.
- Limitations.
- Confidence and provenance of outputs.

Expected analysis outputs:

- Parameter count.
- Trainable parameter count.
- Input/output shapes.
- FLOPs/MACs.
- Checkpoint size.
- Estimated training memory.
- Measured peak memory where available.
- Inference latency.
- Throughput.
- Unsupported operations.

Label each result as:

- `MEASURED`
- `ESTIMATED`
- `UNAVAILABLE`

Record units, hardware, software versions, batch size, input shape, precision, warm-up, and measurement repetitions.

Document FLOPs/MACs conventions, including whether a multiply-add counts as one MAC or two FLOPs.

Keep profiling tools behind adapters. Verify the maintenance status, licensing, and compatibility of each optional dependency before adopting it.

---

# 9. OPTUNA INTEGRATION

Optuna is the primary HPO engine.

Support as appropriate:

- Random search.
- Grid search for baselines.
- TPE.
- CMA-ES where suitable.
- Pruning.
- Conditional search spaces.
- Persistent studies.
- Resumable studies.
- Multi-objective studies.
- Trial metadata.
- Artifact references.

Sampler selection should depend on search-space characteristics, objective count, trial budget, and the problem.

Every trial must record:

- Study ID and trial ID.
- Resolved hyperparameters.
- Random seed.
- Git revision where available.
- Dataset and split fingerprint.
- Model and configuration version.
- Environment metadata.
- Intermediate and final metrics.
- Duration and resource use.
- Exit status and structured error.
- Artifact references.
- Provenance.

Do not assume repeated evaluation on the same validation set creates independent evidence.

Support confirmation experiments using a declared protocol when appropriate.

---

# 10. RAY TUNE INTEGRATION

Ray Tune is optional.

Use it where appropriate for:

- Trial scheduling.
- Resource-aware execution.
- Concurrent trials.
- Distributed workers.
- Supported schedulers and search integrations.
- Early stopping at scale.

Provide a local sequential trial runner so the application works without Ray.

Use Optuna and Ray Tune together only through a supported, tested integration path for the pinned versions.

Explicitly define which system owns:

- Search suggestions.
- Trial state.
- Scheduling.
- Resource allocation.
- Metrics.
- Artifact references.

Avoid two competing sources of truth for the same study.

On a single constrained GPU, default to one trial at a time unless safe concurrency has been demonstrated.

If Ray integration cannot be validated, implement Optuna with the local runner first and leave Ray behind a feature flag.

---

# 11. SEARCH-SPACE VALIDATION

The Harness may propose a search space, but a deterministic validator must approve its structure before execution.

Validate:

- Parameter names and types.
- Numeric bounds.
- Log-scale validity.
- Categorical options.
- Conditional dependencies.
- Incompatible combinations.
- Model-specific constraints.
- Hardware and resource limits.
- Estimated runtime.
- Trial budget.
- Objective directions.
- Data leakage risks.
- Duplicate or unidentifiable parameters.

Use typed schemas and strict validation.

Never use `eval()` to execute an LLM-generated search space.

Custom code must be an explicitly trusted plugin executed inside the approved sandbox.

Save the approved search space as a versioned artifact.

---

# 12. RESOURCE-AWARE EXECUTION

The execution planner must consider:

- GPU model and available VRAM.
- System RAM.
- Free disk space.
- Model parameters and activations.
- Optimizer state.
- Batch size.
- Input/patch size.
- Precision.
- Checkpoint size.
- Trial concurrency.
- User-defined limits.

Estimates are screening tools, not guarantees.

Use a short dry run when practical.

If an OOM or resource failure occurs:

1. Stop the failed trial cleanly.
2. Record the error and environment.
3. Ask the Harness to diagnose the failure.
4. Suggest possible adjustments.
5. Retry only within the approved retry and budget policy.
6. Do not silently change the research protocol or evaluation metrics.

Cancellation must propagate to child processes and training jobs.

Never kill unrelated user processes.

---

# 13. FLEXIBLE WORKFLOW SCHEMA

Create a typed, versioned workflow definition using the repository's established configuration conventions.

Support:

- Workflow ID and version.
- Execution mode.
- Typed steps.
- Dependencies.
- Conditions.
- Manual/assisted/automatic execution per step.
- Approval requirements.
- Retry limits.
- Timeouts.
- Resource budgets.
- Tool allowlists.
- Failure policy.
- Checkpoints.
- Input/output contracts.

Illustrative configuration:

```yaml
workflow:
  id: image_restoration_hpo
  version: 1
  execution_mode: assisted

  budgets:
    max_trials: 30
    max_workflow_cycles: 3
    max_parallel_trials: 1
    max_runtime_minutes: 240
    max_gpu_memory_gb: 10.5

  approvals:
    before_training: required
    before_parallel_gpu_trials: required
    before_research_state_writeback: required

  steps:
    - id: retrieve_context
      type: research.context
      mode: automatic

    - id: inspect_model
      type: model.inspect
      depends_on: [retrieve_context]
      mode: automatic

    - id: propose_search_space
      type: hpo.propose_search_space
      depends_on: [inspect_model]
      mode: assisted

    - id: approve_study
      type: human.approval
      depends_on: [propose_search_space]

    - id: run_study
      type: hpo.run
      depends_on: [approve_study]
      mode: automatic

    - id: evaluate
      type: evaluation.compare_trials
      depends_on: [run_study]
      mode: automatic

    - id: approve_conclusion
      type: human.approval
      depends_on: [evaluate]
```

This example illustrates the intended design; implement and validate the real schema rather than hard-coding this YAML.

---

# 14. WORKFLOW STATE AND RECOVERY

Persist workflow runs and step states.

Workflow states:

- `CREATED`
- `VALIDATING`
- `READY`
- `RUNNING`
- `WAITING_FOR_APPROVAL`
- `PAUSED`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`
- `BUDGET_EXCEEDED`

Step states:

- `PENDING`
- `READY`
- `RUNNING`
- `WAITING_FOR_APPROVAL`
- `SUCCEEDED`
- `FAILED`
- `SKIPPED`
- `CANCELLED`

Support:

- Pause and resume.
- Recovery after application restart.
- Checkpointing.
- Idempotency for costly actions.
- Explicit retry policies.
- Cancellation propagation.
- Auditable approval history.

Do not rerun a completed expensive step after resume unless the user explicitly requests it or the step is proven safe to repeat.

---

# 15. HUMAN APPROVAL POLICY

Approval requirements should be configurable by workflow and project.

Require approval by default before:

- Expensive training.
- Concurrent GPU trials.
- Destructive actions.
- Changing dataset splits.
- Changing evaluation methodology.
- External transfer of sensitive context.
- Major hypothesis changes.
- Publication-facing conclusions.
- Committing candidate memory updates as durable research state.

The user must be able to review:

- Planned action.
- Reason for action.
- Inputs and context.
- Expected resource use.
- Budget remaining.
- Evidence used.
- Potential risks.
- Output expected.

Provide `Approve`, `Edit`, and `Reject` actions where applicable.

---

# 16. CONTEXT AND MEMORY INTEGRATION

Every workflow step requiring research context must use the existing Context Gateway/MCP Gateway.

Do not duplicate Research State or create a separate source of truth inside the Harness, Optuna, or Ray.

Persist references to:

- Workflow plans and changes.
- Approved search-space versions.
- Study and trial IDs.
- Experiment configurations.
- Metrics and artifacts.
- Model complexity reports.
- Failures and recovery actions.
- Git revision.
- User approvals.
- Final recommendations.

Memory write-back must follow:

```text
Agent Output
    |
    v
Candidate Extraction
    |
    v
Sensitivity Classification
    |
    v
Evidence / Provenance Validation
    |
    v
Approval Policy
    |
    v
Research State
```

Distinguish:

- AI suggestion.
- AI claim.
- Measured result.
- Verified observation.
- Experiment result.
- Human decision.
- Validated evidence.

Never automatically convert an AI-generated interpretation into a verified research fact.

---

# 17. EVALUATION AND VERIFICATION

Keep metric computation separate from agent interpretation.

Verify:

- Expected artifacts exist.
- Metrics are finite and generated by the declared evaluator.
- Train/validation/test separation is respected.
- Checkpoint selection follows the declared rule.
- Configurations and seeds are recorded.
- Candidate comparisons use a consistent protocol.
- Failed or incomplete trials are not treated as valid.
- Inference can be reproduced where applicable.

Support task-specific evaluator plugins.

For image restoration, support metrics such as PSNR and SSIM where implemented. Other tasks may need accuracy, F1, mAP, or domain-specific metrics.

The Harness may interpret validated results but cannot fabricate metrics.

---

# 18. UI REQUIREMENTS

Add or extend a Workflow Builder and Workflow Run view.

Users should be able to:

- Select a workflow template.
- Choose manual, assisted, bounded automation, or custom mode.
- Configure the execution mode of individual steps.
- Edit workflow parameters.
- Set trial, time, memory, and concurrency budgets.
- Inspect and edit search spaces.
- Choose Optuna settings.
- Enable Ray Tune when available.
- Approve/reject steps.
- Pause, resume, and cancel runs.
- Inspect agent plans and replanning.
- Inspect tool calls and subagents.
- View trial metrics, failures, logs, and artifacts.
- Compare models and inspect Pareto results.
- Export workflow configuration and reports.

Show the workflow as a timeline or graph.

Each step should display:

- Status.
- Duration.
- Inputs.
- Outputs.
- Warnings.
- Approval state.
- Provenance.

Do not expose raw framework-specific objects to the frontend.

---

# 19. EVENT AND API INTEGRATION

Reuse the existing backend API and streaming conventions.

Provide logical operations for:

- Listing workflow templates.
- Validating a workflow.
- Creating and starting a run.
- Inspecting run status and timeline.
- Approving or rejecting a step.
- Pausing, resuming, and cancelling.
- Inspecting Optuna studies and trials.
- Comparing candidates.
- Retrieving reports and artifacts.

Normalize events into an internal contract:

- `workflow_created`
- `workflow_started`
- `step_started`
- `step_progress`
- `approval_required`
- `approval_resolved`
- `plan_updated`
- `study_created`
- `trial_started`
- `trial_pruned`
- `trial_completed`
- `trial_failed`
- `evaluation_completed`
- `verification_completed`
- `workflow_paused`
- `workflow_completed`
- `workflow_failed`
- `workflow_cancelled`

Reuse existing SSE/WebSocket infrastructure where possible.

Never leak secrets or sensitive raw context into events.

---

# 20. SECURITY

All execution must respect:

- Sandbox/Docker isolation.
- Tool allowlists.
- Filesystem path validation.
- Secret redaction.
- Context sensitivity classification.
- Provider authorization.
- Approval gates.
- Resource and time limits.
- Safe subprocess management.
- Audit logging.

LLM-generated workflows must not be able to enable arbitrary shell commands, bypass approvals, or access secrets.

Validate all workflow definitions against a server-side allowlist of step types and tools.

Do not silently activate paid API billing or send sensitive research context to external providers.

---

# 21. FEATURE FLAGS

Integrate feature flags with the existing configuration system.

Suggested flags:

```text
ENABLE_WORKFLOW_ORCHESTRATOR
ENABLE_MODEL_INTELLIGENCE
ENABLE_OPTUNA_HPO
ENABLE_RAY_TUNE
ENABLE_MULTI_OBJECTIVE_HPO
ENABLE_AUTOMATED_REPLANNING
ENABLE_EXPERIMENT_EXECUTION
ENABLE_MEMORY_WRITEBACK
```

Each optional feature must be independently disableable.

The application must still start if Ray Tune is not installed.

---

# 22. BACKWARD COMPATIBILITY

Keep v3.5 operational.

Do not:

- Replace the Harness adapter.
- Replace Context Gateway.
- Replace Research State.
- Replace MCP Gateway.
- Duplicate experiment storage.
- Require Ray Tune for local use.
- Break existing Python/Docker workflows.
- Perform destructive migrations.
- Couple the entire application to Optuna or Ray-specific classes.

Implement v3.6 behind feature flags.

If the orchestrator is disabled, the existing v3.5 behavior must remain available.

---

# 23. TESTING

Add tests using the repository's existing testing conventions.

Cover:

- Workflow schema validation.
- Workflow template registry and versioning.
- Manual, assisted, and automation modes.
- Step dependencies and conditional branches.
- Approval gates.
- Pause/resume/cancel.
- Recovery and idempotency.
- Harness adapter contract.
- Optuna study lifecycle.
- Local sequential trial runner.
- Optional Ray integration.
- Search-space validation.
- Multi-objective results.
- Model adapter capability detection.
- Measured versus estimated metrics.
- Resource budget enforcement.
- OOM and timeout recovery.
- Artifact and metric verification.
- Memory write-back approvals.
- Sensitive-context protection.
- End-to-end workflows using deterministic mock tools.

GPU tests must be optional. The basic test suite must run without a GPU.

---

# 24. BENCHMARKING

Compare:

1. Manual workflow.
2. Assisted workflow.
3. Bounded automation.
4. Optuna with the local sequential runner.
5. Ray Tune where supported.

Measure:

- Workflow completion rate.
- Valid versus invalid trial ratio.
- Time to first useful result.
- Total wall-clock time.
- Trial throughput.
- Peak GPU memory.
- Objective quality under equal trial budgets.
- Tool failure and recovery rates.
- Number of required approvals.
- Token usage and cost where available.
- Reproducibility across reruns.

Do not claim globally optimal hyperparameters.

Document the specific tasks, budgets, hardware, seeds, and limitations.

Create:

`docs/benchmarks/workflow-hpo-v3.6-benchmark.md`

---

# 25. ACCEPTANCE SCENARIOS

## Scenario A — Manual Model Audit

The user imports a supported model, runs a feasibility audit, inspects parameters/FLOPs/memory/latency, and exports the report.

No training starts automatically.

## Scenario B — Assisted HPO

The Harness proposes a plan. Model Intelligence inspects the model. The Harness proposes a search space. The user approves it. Optuna runs a small study through the local runner. Results appear in the UI and the researcher approves the interpretation.

## Scenario C — Bounded Automation

The user approves a fixed resource budget and workflow policy. The system runs a capped study, evaluates candidates, verifies artifacts, and produces a report. It stops at its configured limits.

No unapproved durable research conclusion is created.

## Scenario D — Optional Ray Tune

When Ray Tune is installed and compatible, the workflow uses the tested adapter. When unavailable, the application remains healthy and offers the local runner.

## Scenario E — Failure Recovery

A simulated OOM occurs. The system records the failure, proposes an adjustment, respects the approval policy, and continues only if the remaining budget permits.

## Scenario F — Multi-Objective Comparison

The system optimizes a quality metric and a resource metric, returns a valid Pareto set, and explains the trade-offs.

## Scenario G — Mixed Manual/Automated Workflow

The researcher manually defines a hypothesis, automatically retrieves evidence, manually approves the model configuration, automatically runs HPO, manually selects a candidate, and automatically executes a confirmation experiment.

The workflow must support this combination without custom source-code modifications.

## Scenario H — Nested Workflow

The Research Planning workflow invokes Model Feasibility Audit, which returns a structured result to the parent workflow. The parent workflow uses that result to decide whether to proceed to Search-Space Design.

The nested workflow must preserve run IDs, provenance, budgets, and approval policies.

---

# 26. DOCUMENTATION

Create or update:

```text
docs/architecture/workflow-orchestrator-v3.6.md
docs/architecture/model-intelligence-v3.6.md
docs/architecture/hpo-execution-v3.6.md

docs/workflows/workflow-modes.md
docs/workflows/workflow-template-authoring.md
docs/workflows/workflow-composition.md

docs/integrations/optuna.md
docs/integrations/ray-tune.md
docs/integrations/model-profiler-adapters.md

docs/security/workflow-execution-security.md
docs/benchmarks/workflow-hpo-v3.6-benchmark.md
docs/migration/v3.5-to-v3.6.md
```

Also create a final implementation report describing:

- Actual files changed.
- Architecture decisions.
- Dependencies and licenses.
- Implemented versus deferred features.
- Tests and results.
- Known limitations.
- Performance measurements.
- Security review.
- Migration and rollback instructions.

---

# 27. IMPLEMENTATION MILESTONES

Implement incrementally. Do not attempt one giant rewrite.

### M0 — Audit

Inspect v3.5 and document current architecture and gaps.

### M1 — Workflow Contracts

Define typed workflow, run, step, event, budget, and approval schemas.

### M2 — Workflow Orchestrator

Implement registry, state machine, manual mode, approvals, pause/resume, and cancellation.

### M3 — Harness Integration

Connect planning, tool calls, and replanning through the existing Harness adapter.

### M4 — Model Intelligence

Implement model adapter registry, complexity analysis, resource estimation, and provenance labels.

### M5 — Optuna

Implement search-space validation, persistent studies, local sequential execution, and trial tracking.

### M6 — Ray Tune

Add an optional Ray adapter after confirming version compatibility and end-to-end behavior.

### M7 — Evaluation

Implement validated metrics, candidate comparison, confirmation experiments, and Pareto analysis.

### M8 — Deep Learning Lab Integration

Connect dataset validation, Sandbox/Docker training, evaluation, and artifact tracking.

### M9 — Workflow UI

Expose templates, custom composition, execution modes, approvals, traces, trial results, and reports.

### M10 — Verification and Release

Run tests, benchmark workflows, audit security, document limitations, and prepare the migration guide.

At the end of each milestone:

1. Run targeted tests.
2. Fix regressions.
3. Update documentation.
4. Report files changed and remaining issues.
5. Do not claim completion without evidence.

---

# 28. DEFINITION OF DONE

v3.6 is complete when:

- [ ] Existing v3.5 functionality remains operational.
- [ ] Workflow Orchestrator is implemented behind feature flags.
- [ ] Manual, assisted, bounded automation, and custom workflows work.
- [ ] Individual steps support different autonomy levels.
- [ ] Workflow templates are reusable and versioned.
- [ ] Nested workflows work with explicit contracts.
- [ ] Harness integration reuses the existing adapter.
- [ ] Model Intelligence reports supported capabilities and measurement provenance.
- [ ] Optuna study lifecycle works end-to-end.
- [ ] Local sequential trial execution works without Ray.
- [ ] Ray Tune is optional and tested when enabled.
- [ ] Search spaces are validated before execution.
- [ ] Resource and trial budgets are enforced.
- [ ] Training and evaluation use sandboxed execution.
- [ ] Failure recovery and cancellation are auditable.
- [ ] Multi-objective results are handled correctly.
- [ ] Metrics and artifacts are verified before interpretation.
- [ ] Memory write-back follows the approval policy.
- [ ] UI displays plans, workflow steps, approvals, trials, and results.
- [ ] Acceptance tests pass.
- [ ] Benchmark and security audit are documented.
- [ ] Migration and rollback instructions are documented.

---

# 29. FINAL ARCHITECTURAL PRINCIPLE

The completed system should support many workflows, not one rigid pipeline.

The researcher controls the autonomy level.

The Harness plans and coordinates.

Model Intelligence analyzes models and proposes feasible search spaces.

Optuna searches hyperparameters.

The local runner or Ray Tune executes trials.

The Evaluation Engine verifies measurements.

The researcher reviews important conclusions.

PhD Research Lab records approved outcomes with provenance.

**Final principle: automate repetitive execution, not scientific responsibility.**

Inspect the real repository first, reuse existing code wherever possible, and clearly distinguish implemented features from proposed or unsupported capabilities.
