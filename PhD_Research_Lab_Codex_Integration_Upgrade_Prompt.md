# Upgrade Prompt — Integrate OpenAI Codex into PhD Research Lab

> **Purpose:** Upgrade the existing PhD Research Lab by adding Codex as an optional coding-agent backend. This is an incremental enhancement to the existing repository and previously approved architecture—not a rewrite, not a replacement of Claude, and not a new standalone product.
>
> **Execution rule:** Start with repository inspection and a short implementation plan. Then implement in small, testable phases. Preserve current functionality and user data.

---

## 1. Role

Act as a senior software architect and engineer working inside the existing PhD Research Lab repository.

Before changing code, inspect the actual repository, its current architecture, agent orchestration, Context Memory, workspace handling, frontend, configuration, tests, and any existing migration/architecture documents. Treat repository code and current documentation as the source of truth. Do not assume that the architecture described in this prompt already exists.

## 2. Product context

PhD Research Lab is the research control plane / Research OS. Its unique responsibilities include:

- Research projects, questions, hypotheses, plans, and decisions
- Context Memory and research timeline
- Agent orchestration and task tracking
- Research-oriented Deep Learning workflows
- Linking code, experiments, results, evidence, and conclusions

The product should integrate mature tools rather than recreate their generic functionality.

Target role separation:

- **PhD Research Lab:** research context, orchestration, workflow, permissions, traceability, and memory
- **Claude backend:** retain all currently supported Claude workflows and behavior
- **Codex backend:** optional coding agent for repository analysis, implementation, refactoring, tests, and engineering tasks
- **VS Code:** human coding workspace and review surface; it is not itself the Codex backend
- **Git:** source-control history and change tracking
- **Docker / existing sandbox:** isolated or reproducible execution where already supported
- **ClearML:** experiment tracking when integrated/configured

Codex must be an additional provider behind a stable abstraction. Do not replace Claude or hard-code Codex-specific assumptions throughout the application.

## 3. Primary objective

Add an optional `CodexBackend` to the existing agent architecture, using the official OpenAI Codex integration mechanism that best fits the current application.

Investigate the current official Codex options and their APIs before implementation, including as applicable:

- Codex CLI
- Official TypeScript SDK
- Codex App Server

Prefer the smallest supported integration that meets the actual repository requirements. Do not invent SDK methods, event names, configuration keys, or capabilities. Verify the current official documentation and installed package version. If internet access is unavailable, inspect the repository/package metadata and clearly mark any unverified API assumptions before using them.

Do not implement a generic OpenAI model API call and label it “Codex.” A model API call and a coding-agent runtime are different integrations.

## 4. Non-goals

Do **not**:

- Rewrite the application or change its main framework without a documented necessity
- Replace or remove the existing Claude integration
- Rebuild VS Code, a terminal, Git, Docker, Jupyter, or ClearML
- Build a custom Codex model or clone the Codex UI
- Automatically send all research tasks to Codex
- Run untrusted generated code with unrestricted host access
- Automatically commit, push, publish, deploy, or delete project data without explicit approval
- Make Kubernetes, KServe, or remote compute a requirement for this upgrade
- Refactor unrelated modules merely to make the code look cleaner
- Claim a feature works when only a mock or placeholder exists

## 5. Phase A — Audit and propose the smallest safe change

Inspect and report:

1. Current agent/backend abstractions and agent lifecycle.
2. How Claude is invoked, authenticated, streamed, resumed, cancelled, and monitored.
3. How projects and workspace paths are resolved and validated.
4. How task status, logs, diffs, usage, and errors are persisted.
5. Current Context Memory write/read rules and how agent runs are linked to research entities.
6. Existing UI patterns for choosing providers, viewing run status, approving actions, and inspecting results.
7. Current tests and build commands.
8. Current official Codex SDK/CLI/App Server options relevant to this codebase.

Produce a short `CODEX_INTEGRATION_PLAN.md` containing:
- Findings grounded in actual file paths and symbols
- Chosen integration mechanism and why
- Proposed minimal file/module changes
- Authentication and configuration approach
- Permission/sandbox model
- Event and run lifecycle mapping
- Test plan and acceptance criteria
- Risks, limitations, and items requiring user decisions

Do not make broad code changes during this phase. If the repository already has an appropriate provider abstraction, extend it instead of creating a parallel system.

## 6. Phase B — Add the provider abstraction or extend the existing one

Reuse the existing abstractions if present. Otherwise add only the minimum useful provider contract. Adapt names and types to the project's conventions; the following is conceptual, not a demand to create this exact API:

```ts
interface AgentBackend {
  getCapabilities(): Promise<AgentCapabilities>;
  startRun(input: AgentRunInput): Promise<AgentRunHandle>;
  streamEvents?(runId: string): AsyncIterable<AgentEvent>;
  resumeRun?(input: ResumeRunInput): Promise<AgentRunHandle>;
  cancelRun?(runId: string): Promise<void>;
  getRunStatus(runId: string): Promise<AgentRunStatus>;
}
```

Requirements:
- Keep the current Claude provider working.
- Add `CodexBackend` as an optional implementation.
- Use typed request, response, event, and error models consistent with the repository.
- Support capability discovery so the UI can show only actions that a backend actually supports.
- Represent unsupported operations explicitly; do not silently fake support.
- Avoid coupling research-domain entities directly to vendor-specific SDK objects.
- Keep vendor-specific implementation inside the adapter/provider boundary.

## 7. Phase C — Implement Codex execution

Implement the selected official Codex integration, scoped to a validated project workspace.

Minimum behavior:

1. Check whether Codex runtime and required dependencies are installed/available.
2. Validate configuration and authentication without exposing credentials.
3. Start a coding-agent run for a selected workspace and task.
4. Capture run/thread/session identifiers when available.
5. Stream or poll progress using the mechanism supported by the chosen integration.
6. Persist meaningful lifecycle states such as queued, starting, running, awaiting approval, completed, failed, and cancelled, adapted to existing conventions.
7. Capture final summary, errors, changed-file information, and usage data only when the integration actually provides them.
8. Support cancellation if the chosen runtime supports it reliably.
9. Resume an existing run only if the selected mechanism officially supports it.
10. Recover gracefully from missing runtime, authentication failure, timeout, process crash, and unavailable services.

Do not assume Codex events always provide a complete Git diff. Obtain diffs from Git when safe and available, and label them as Git-derived. Keep agent output and authoritative repository state distinct.

### Authentication and billing

- Prefer the official supported authentication flow for the chosen Codex runtime.
- Do not store raw API keys or session tokens in source code, frontend state, logs, Context Memory, or Git.
- Use the application's existing secure secret/configuration approach.
- Explain whether the selected mode uses ChatGPT-plan authentication or API billing; do not assume they are interchangeable.
- Never print secrets while diagnosing connection errors.

## 8. Phase D — Permissions, safety, and human approval

Codex must operate under explicit workspace and permission boundaries.

Requirements:
- Restrict operations to a validated project workspace by default.
- Use the official Codex sandbox/approval controls supported by the selected runtime.
- Default to the safest practical permission mode compatible with the workflow.
- Require explicit approval before privileged or destructive actions, including broad filesystem access, external network access where restricted, deleting data, committing/pushing, deploying, or running costly experiments.
- Never bypass configured Codex approvals or sandbox policies for convenience.
- Do not accept arbitrary frontend-provided filesystem paths or shell commands without server-side validation.
- Record the effective permission mode in the Agent Run metadata.
- Clearly distinguish an agent proposal from an executed action.
- Provide a stop/cancel control where supported.

If the existing app has a sandbox/execution policy, integrate with it rather than adding a competing policy system.

## 9. Phase E — Link Codex to VS Code and the existing workspace

VS Code remains the editor, not a required part of headless agent execution.

Implement only what fits the existing application:
- Allow the user to select a valid project/workspace.
- Provide an **Open in VS Code** action using the existing workspace integration, if available.
- Provide an **Run with Codex** action for supported coding tasks.
- Show the associated repository path, Git branch, run status, changed files, and result summary.
- Provide **Review changes in VS Code** when the local environment can open the workspace.
- If VS Code cannot be opened from the current deployment architecture, show clear setup guidance rather than claiming success.

Do not require the VS Code extension to be installed for backend-driven Codex execution unless the chosen integration genuinely depends on it. Avoid creating two competing Codex sessions unintentionally (one launched by PhD Lab and another manually in the IDE).

## 10. Phase F — Context Memory and research traceability

Integrate Codex runs into the existing memory model without storing excessive raw logs or duplicating data.

For each run, persist the minimal useful metadata supported by the application, such as:
- Project and research-task IDs
- Provider identifier (`codex`)
- Backend run/thread/session ID, if available
- Task prompt or a safe reference to it
- Workspace and repository identity
- Git commit before/after, when available
- Start/end timestamps and final status
- Files changed and test outcomes, when verified
- Final summary, errors, and artifact references
- Approval/permission mode
- Links to related hypothesis, experiment, dataset, or research decision when explicitly associated

Rules:
- Separate raw agent output from validated research knowledge.
- Do not automatically convert an agent's claim into a scientific fact.
- Only save a research conclusion to durable Context Memory when it passes existing policies or a user explicitly approves it.
- Preserve provenance so the user can trace a conclusion back to the run, code, tests, and experiment evidence.
- Follow existing retention and summarization policies.

## 11. Phase G — UI integration

Extend the current UI using its existing design system. Do not redesign the entire frontend in this upgrade.

Add or adapt:
- Provider selection: existing providers plus Codex when configured
- Codex availability/authentication status without revealing secrets
- Task/run creation
- Live progress or honest polling status
- Cancel action when supported
- Run history and final summary
- Changed files and Git diff/review links when available
- Test results clearly labelled as passed, failed, not run, or unknown
- Error messages and recovery guidance
- Open in VS Code action when supported

The UI must distinguish:
- Codex unavailable
- Codex installed but not configured
- Authentication required/failed
- Run in progress
- Awaiting user approval
- Completed successfully
- Completed with test failures
- Failed or cancelled

Avoid placeholder metrics, fabricated events, or fake “success” indicators.

## 12. Phase H — Testing and verification

Add tests using the project's established testing framework.

### Unit tests
- Provider registration and selection
- Valid/invalid configuration
- Workspace path validation
- Event/state mapping
- Missing Codex runtime
- Authentication errors without secret leakage
- Timeout, cancellation, and process failure handling
- Context Memory metadata and provenance
- Unsupported capabilities

### Integration tests
- Test the adapter with a controlled fake/stub where appropriate.
- Add an opt-in real Codex smoke test that runs only when explicitly configured.
- Do not require paid credentials in ordinary CI.
- Use a tiny, safe test workspace for real execution.
- Verify that a run's actual status, output and file changes are reflected correctly.
- Verify existing Claude workflows still work.

Run the available lint, type-check, build, and tests. Report the actual commands and results. Do not mark skipped tests as passed.

## 13. Documentation

Create or update the smallest relevant set of documents, including:
- `CODEX_INTEGRATION_PLAN.md`
- `CODEX_INTEGRATION.md`
- `INTEGRATION_STATUS.md`
- `DEVELOPMENT.md` or the existing setup documentation

Document:
- Prerequisites and supported runtime/version
- Authentication and billing-mode caveats
- Configuration keys with sanitized examples
- How to enable/disable Codex
- How to run a safe smoke test
- Workspace and permission boundaries
- Troubleshooting
- Known limitations
- How the Codex provider coexists with Claude and VS Code

Never include actual secrets, personal tokens, or sensitive local paths.

## 14. Acceptance criteria

This upgrade is complete only when all applicable criteria are verified:

1. Existing PhD Research Lab functionality remains operational.
2. Existing Claude integration continues to work.
3. Codex can be configured as an optional provider using the selected official integration.
4. A user can launch a real Codex run for a validated workspace.
5. Run status and final output are accurately reported.
6. Changed files/diffs are shown only when actually obtained.
7. Workspace boundaries and approval controls are enforced.
8. Run metadata is linked to the correct project and stored in accordance with current Context Memory policies.
9. The user can open/review the workspace in VS Code when supported by the deployment environment.
10. Tests, setup instructions, and known limitations are documented.
11. Disabling or uninstalling Codex does not break Claude or the core Research Lab.
12. No unrelated large refactor has been introduced.

## 15. Working protocol

Follow this order:

1. Inspect repository and current architecture.
2. Write `CODEX_INTEGRATION_PLAN.md`.
3. Summarize the plan, affected files, dependencies, and risks.
4. Implement the smallest vertical slice: availability check → start one safe run → capture status/result.
5. Add lifecycle persistence and Context Memory linkage.
6. Add UI actions and VS Code handoff.
7. Add tests and documentation.
8. Run validation and report exact results.
9. Stop and ask for approval before any broad refactor or destructive migration.

After each phase, summarize:
- Files changed
- Behavior added
- Tests run and exact outcomes
- Known limitations
- Recommended next step

**Final instruction:** Treat this as a backward-compatible feature upgrade to the existing PhD Research Lab. Preserve the existing architecture and user data. Do not start by rebuilding the product. First inspect the repository and adapt this plan to the actual codebase.
