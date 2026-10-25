# CODEX MISSION — Autonomous Workflow QA & Full Harness Regression

You are a Principal QA Automation Architect, Workflow Engine Verification Engineer, and AI Agent Systems Reliability Engineer.

## OBJECTIVE

Build a permanent, autonomous, workflow-aware quality assurance system for PhD Research Lab.

The application already contains:
- L2/L3/L4 research execution.
- Dynamic multi-agent Harness.
- Visual Workflow Builder.
- Workflow presets.
- User-created workflows.
- AI-generated workflows.
- Multiple AI and research providers.
- Shared research memory and artifacts.

The number of workflows is growing rapidly.

Your mission is to make the complete Harness ecosystem systematically testable WITHOUT writing a separate manually maintained test suite for every workflow.

Implement real executable automation, not just documentation.

## PHASE 1 — Full Workflow Discovery

Inspect the actual repository and running application.

Discover:
- Workflow registry.
- Preset definitions.
- User-created workflow storage.
- AI-generated workflow definitions.
- Node type registry.
- Edge and port schemas.
- Execution states.
- Agent roles.
- Provider adapters.
- Human approval contracts.
- L2/L3/L4 mode contracts.
- Workflow persistence and versioning.

Create a machine-readable workflow inventory.

Each workflow must have:
- Stable workflow ID.
- Version or content hash.
- Node and edge inventory.
- Execution mode.
- Provider dependencies.
- Required permissions.
- Expected output contracts.
- Known execution constraints.

Do not assume every workflow can safely execute.

## PHASE 2 — Install and Configure Playwright

Check for existing Playwright installations and compatible skills.

Install missing dependencies, Chromium and Playwright Test where authorized.

Start the real PhD Research Lab frontend and backend.

Use a separate test profile and isolated application data.

Verify that Chromium can open the real localhost application.

## PHASE 3 — Universal Workflow Test Engine

Implement reusable tests based on workflow graph contracts.

Test every supported node type:
- Start / End.
- Agent Task.
- Multi-Agent Team.
- Tool and Research Engine.
- MCP Tool.
- Conditions.
- Parallel Branch / Join.
- Bounded Loop.
- Human Approval.
- Evaluation Gate.
- Artifact Transformation.
- Memory Read / Write.
- Retry / Error Handler.
- Checkpoint.

For every node type, cover:
- Valid execution.
- Invalid input.
- Missing dependency.
- Timeout.
- Cancellation.
- Retry.
- Output validation.
- State persistence.

Validate graph invariants including reachability, port compatibility, dependency resolution, valid joins, bounded cycles and permitted transitions.

Build reusable node and edge contract tests.

Do not duplicate the same testing logic across all workflows.

## PHASE 4 — Model-Based Workflow Generation

Use property-based and model-based testing techniques.

Evaluate fast-check or an equivalent compatible framework.

Generate reproducible test workflow graphs covering:
- Sequential tasks.
- Branching.
- Parallel execution.
- Nested subworkflows.
- Agent delegation.
- Provider failure.
- Retry and fallback.
- Human approval.
- Checkpoint recovery.
- Bounded research loops.

Generate both valid and intentionally invalid graphs.

Use deterministic random seeds and preserve failing seeds.

For invalid graphs, verify that validation rejects them safely.

For valid graphs, execute against isolated test services where feasible.

Verify correctness using state transitions, invariants and output contracts, not merely successful HTTP responses.

## PHASE 5 — Full Playwright Browser Testing

Launch real Chromium.

Inspect every implemented Harness Studio page and relevant UI state.

Test:

1. Create workflow from scratch.
2. Load an existing preset.
3. Add and remove nodes.
4. Drag and reposition nodes.
5. Connect and disconnect edges.
6. Configure node properties.
7. Assign agents and providers.
8. Create dynamic teams.
9. Configure L2/L3/L4.
10. Configure conditional branches.
11. Configure loops and parallel stages.
12. Save and reload workflow.
13. Clone and version workflow.
14. Import and export workflow.
15. Validate workflow graph.
16. Start execution.
17. Observe live node status.
18. Pause, cancel, retry and resume.
19. Inspect task results and research artifacts.
20. Restore execution after application restart.

Only test operations actually supported by the application; record missing requirements separately.

Verify UI state AND actual backend state.

Use reliable locators and web-first assertions.

Capture screenshots, browser console failures, network failures and Playwright traces.

Test responsive layouts and accessibility using axe-core where appropriate.

## PHASE 6 — Existing Workflow Inventory Regression

Automatically load all discovered workflow definitions.

For every workflow:

1. Validate its schema and references.
2. Verify all required node types are registered.
3. Verify configured provider capabilities exist.
4. Verify graph structure and permissions.
5. Determine if execution is safe in the test environment.
6. Execute eligible workflows using isolated inputs.
7. Verify state transitions and output contracts.
8. Record PASS, FAIL, SKIPPED or BLOCKED.

Never report structural validation as full end-to-end coverage.

For workflows requiring expensive cloud providers, GPU training, destructive commands, or human intervention, require appropriate isolated environments and authorization.

## PHASE 7 — L2/L3/L4 Harness Validation

Test each implemented autonomy mode separately.

L2:
- Explicit user-controlled execution.
- Correct manual checkpoints.
- No unauthorized automatic progression.

L3:
- Dynamic agent assignment.
- Parallel task execution.
- Correct coordination.
- Human approval boundaries.

L4:
- Goal decomposition.
- Dynamic agent-team formation.
- Bounded replanning.
- Research evaluation.
- Iterative refinement.
- Budget enforcement.
- Recovery from intermediate failure.
- Correct termination behavior.

Verify that mode changes do not corrupt workflow state.

## PHASE 8 — Research Workflow E2E

Execute small, reproducible real research scenarios covering:

- Idea → Hypothesis.
- Literature → Evidence.
- Hypothesis → Code.
- Code → Experiment.
- Experiment → Evaluation.
- Research → Paper, when implemented.
- Full research orchestration.

Exercise Feynman, OpenScience, OpenCode and PaperOrchestra through their actual registered adapters where available.

Use local Phi-4 for compatible low-cost real-model tests.

Separate real provider tests from simulated-provider contract tests.

Verify artifact provenance, memory persistence and output integrity.

## PHASE 9 — Autonomous Defect Repair

When a reproducible failure is detected:

1. Preserve the failing graph and seed.
2. Capture traces, screenshots and logs.
3. Determine root cause.
4. Create a permanent regression test.
5. Fix the actual defect.
6. Rerun the failing case.
7. Run related node and workflow tests.
8. Check for new regressions.

Never modify expected outcomes merely to make tests pass.

Limit repeated repair attempts and report unresolved problems.

## PHASE 10 — Workflow Coverage Dashboard

Implement a repository-native, machine-readable QA report.

Show:
- Total discovered workflows.
- Tested workflow IDs and versions.
- Untested workflows.
- Schema validation coverage.
- Node type coverage.
- Edge and transition coverage.
- Branch coverage.
- L2/L3/L4 scenario coverage.
- Real-browser E2E coverage.
- Provider compatibility coverage.
- Actual execution pass/fail results.
- Known defects.
- Flaky tests.
- Blocked tests and reasons.

Add a visible QA Coverage section to Harness Studio if compatible with the existing UI.

Do not confuse code coverage with workflow coverage.

## PHASE 11 — Continuous Regression

Implement separate suites:

- Fast: schema, node contracts and selected unit tests.
- Standard: affected workflows and real-browser regression.
- Full: complete eligible workflow inventory, model-based tests and research E2E.
- Release: mandatory gates, recovery, security and compatibility.

Automatically detect changed nodes, providers, runtime contracts and workflow definitions.

Run affected tests first, then periodically execute the full suite.

Store test evidence and allow comparison across workflow versions.

## PHASE 12 — Git Delivery

Create or extend the test infrastructure in the existing repository.

Deliver:
- Workflow discovery implementation.
- Graph validators and test generators.
- Playwright test suite.
- Model-based testing suite.
- Research E2E suite.
- Coverage reports.
- CI configuration.
- QA documentation.
- Reusable QA skill or AGENTS.md instructions.

Preserve all existing user data and uncommitted changes.

Commit implementation on a dedicated Git branch.

Do not push or merge without approval.

Provide actual commands, commit hashes and evidence of executed tests.

## ACCEPTANCE CRITERIA

The system must demonstrate:

- Discovery of all accessible registered workflows.
- Automated validation of every discovered workflow definition.
- Real-browser verification of the visual workflow builder.
- Executable tests for every implemented node type.
- Branch and transition coverage reporting.
- End-to-end execution evidence for eligible critical workflows.
- Repeatable failing cases and permanent regression tests.
- Honest reporting of blocked or unverified scenarios.

Do not claim the application is bug-free.

Do not stop after generating a plan.

Implement, execute, diagnose, repair, retest and commit.