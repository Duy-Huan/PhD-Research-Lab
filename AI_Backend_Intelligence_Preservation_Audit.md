# CODEX MISSION — AI Backend Intelligence Preservation Audit

Act as a Principal LLM Systems Engineer, AI Agent Evaluation Researcher, Provider Integration Architect, and Senior Python Backend Engineer.

## Objective

Audit and improve PhD Research Lab's actual AI intelligence preservation across provider gateways, prompt serialization, JSON contracts, context memory, tools, and L2/L3/L4 agent orchestration.

The objective is NOT simply to confirm that providers connect and return valid JSON.

Determine whether PhD Research Lab preserves the actual capabilities and task performance of its underlying AI providers.

## 1. Full Backend Inspection

Inspect all implemented:

- Provider adapters and gateways.
- CLI and API execution paths.
- Prompt templates and prompt assembly.
- System/developer/user message handling.
- JSON schemas and response parsers.
- Structured-output enforcement.
- Streaming and tool-call handling.
- Token and context budgets.
- Memory retrieval and summarization.
- Agent handoffs.
- Harness L2/L3/L4 orchestration.
- Research engine integrations.

Do not assume a feature works solely because its implementation exists.

## 2. Provider Capability Audit

For each supported provider, compare its native documented capabilities with those exposed through PhD Lab.

Check:
- Native CLI session support.
- Multi-turn interactions.
- Tool and function calling.
- MCP integration.
- Skills.
- Filesystem and sandbox tools.
- Streaming.
- Structured outputs.
- Session continuation.
- Cancellation.
- Context limits.
- Model configuration.
- Authentication.
- Error reporting.

Create a provider capability matrix.

Identify unsupported, silently dropped, emulated and degraded capabilities.

Preserve provider-specific features rather than forcing every provider into an oversimplified common interface.

## 3. Prompt Fidelity Audit

Trace the complete request construction process.

Verify:
- Instruction hierarchy.
- Research context inclusion.
- Memory relevance.
- Evidence inclusion.
- Tool definitions.
- Prompt versioning.
- Token budget.
- Context truncation behavior.
- Escaping and serialization.
- Unicode integrity.
- Separation of trusted instructions from untrusted research content.

Detect duplicate, contradictory, missing and excessively restrictive instructions.

Do not claim access to hidden provider reasoning.

## 4. Structured JSON Contract Audit

Inspect every JSON-based agent response contract.

Identify:
- Overly restrictive schemas.
- Silent field loss.
- Response truncation.
- Unsupported nested structures.
- Parser failure.
- Lost tool calls.
- Invalid status transitions.
- Improper retry behavior.
- JSON repair that modifies scientific content.
- Output size restrictions that discard important findings.

Separate control metadata from large scientific artifacts.

Use typed, versioned schemas and explicit validation.

Do not fabricate missing fields or silently coerce scientific results.

## 5. Native vs Wrapped Provider Benchmark

Build a permanent benchmark that compares:

A. Native provider execution.

B. Execution through PhD Research Lab.

Use the same:
- Model/version.
- Research task.
- Input evidence.
- Tools and permissions.
- Data availability.
- Comparable generation settings.

Clearly document unavoidable differences.

Run repeated evaluations using reproducible datasets.

Benchmark:
- Research planning.
- Literature synthesis.
- Context recall.
- Mathematical reasoning.
- Coding and debugging.
- Tool selection.
- Multi-step execution.
- Evidence-based analysis.
- Scientific writing.
- Workflow coordination.

Include a plain native-provider baseline.

## 6. Objective Intelligence Evaluation

Use existing evaluation infrastructure where possible.

Evaluate:

- Task completion.
- Tool correctness.
- Argument correctness.
- Plan quality.
- Execution efficiency.
- Factual grounding.
- Evidence consistency.
- Output completeness.
- Reproducibility.
- Cost.
- Latency.

Use deterministic oracles for checkable tasks.

Use independent evaluators for subjective scientific quality, with blinded scoring and human review of disagreements.

Report variability and confidence intervals where sample sizes permit.

Do not invent a single universal intelligence score.

## 7. Context Memory Integrity

Test:
- Multi-session research continuity.
- Decision recall.
- Experimental result recall.
- Preservation of numerical values.
- Retrieval relevance.
- Source attribution.
- Memory conflict resolution.
- Long-horizon research tasks.
- Summarization quality.
- Recovery after application restart.

Compare raw research evidence with the context actually delivered to the model.

Identify information loss and unsupported memory claims.

## 8. L2/L3/L4 Agent Intelligence

Test the actual Harness behaviors.

L2:
Does the assistant correctly support user-directed research?

L3:
Does the dynamically formed team collaborate effectively, share evidence and respect approval boundaries?

L4:
Can the system plan, delegate, execute, evaluate, replan and terminate within authorized limits?

Verify that adding agents improves task performance rather than merely increasing token usage or producing redundant outputs.

## 9. Intelligent Improvement

For every confirmed degradation:

1. Capture a reproducible failing task.
2. Identify the failing layer.
3. Establish a native-provider baseline.
4. Apply a targeted fix.
5. Rerun the same evaluation dataset.
6. Compare task quality, cost and latency.
7. Confirm no regression in other providers.

Possible corrections include:
- Prompt simplification.
- Better capability negotiation.
- Tool schema improvements.
- Context selection.
- Memory retrieval improvements.
- Artifact-based outputs.
- Streaming fixes.
- Correct structured-output handling.
- Agent-role and delegation improvements.

Do not remove safety or permission boundaries to improve benchmark scores.

Do not optimize exclusively for one benchmark.

## 10. Observability and Permanent Regression

Reuse or integrate suitable open-source tools such as Promptfoo, Langfuse and DeepEval.

Instrument model calls, tool calls, handoffs, context selection and outcomes.

Redact secrets and sensitive research data.

Persist an evaluation suite inside the repository.

Create CI-compatible deterministic tests and separately authorized real-provider evaluations.

## 11. Reports

Generate:

- PROVIDER_CAPABILITY_MATRIX.md
- PROMPT_FIDELITY_AUDIT.md
- JSON_CONTRACT_AUDIT.md
- MEMORY_INTEGRITY_REPORT.md
- NATIVE_VS_WRAPPED_BENCHMARK.md
- AGENT_INTELLIGENCE_EVALUATION.md
- BACKEND_INTELLIGENCE_RELEASE_GATE.md

For every provider, report:

- Actual connectivity.
- Verified native capabilities.
- Preserved capabilities.
- Unsupported capabilities.
- Task success rate.
- Quality difference from native execution.
- Token usage.
- Cost and latency.
- Known limitations.

## 12. Implementation and Git Delivery

Build actual executable benchmark and regression tests.

Repair confirmed defects.

Commit test infrastructure, improvements and documentation on a dedicated branch.

Do not push or merge without approval.

Never report provider intelligence parity without real comparative evidence.

Do not stop after producing a plan.

Audit, benchmark, fix, retest and document measurable results.