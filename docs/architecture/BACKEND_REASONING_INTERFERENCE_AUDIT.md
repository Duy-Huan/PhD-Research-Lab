# Backend reasoning-interference audit

Owner definition: one agent-native scientific research environment, not separate L2/L3/L4 engines. This audit distinguishes scientific choices that belong to the agent from infrastructure controls that remain necessary. It does not establish L3/L4 or certify every backend path.

## Scope and evidence

Inspected chat orchestration, plain-language routing, history/context compilation, native CLI event handling, model-to-CLI streaming, workflow generation, native research adapter, memory candidate handling and isolated execution. Source baseline includes the ongoing uncommitted dev changes. Raw RED/GREEN and actual synthetic subscription receipts are in output/playwright/hermes-core-audit/. Scientific workflow qualification is still pending.

| ID | Concrete behavior and source | Decision | Evidence/status |
|---|---|---|---|
| RI-01 | orchestrator._route called launch.route on ordinary text; regex could start a literature run or create a fixed experiment proposal before any model response | Remove default interception; explicit slash commands remain available | FIXED targeted. English/Vietnamese questions, hypothetical actions and a long request fail on old behavior and pass after correction. |
| RI-02 | Keyword-matched chat skills assigned a role/instruction block to a normal conversation | Do not impose a skill or role on plain text; allow explicit commands and model-proposed actions | FIXED targeted. Agent authority tests and updated explicit-skill tests; affected full regression pending. |
| RI-03 | CodexConnector/CLIConnector treated item.completed agent_message as whole-turn completion | Wait for terminal protocol event; preserve later reasoning output, failures and usage | FIXED targeted. Controlled real Python protocol fixture reproduced loss of later text and hidden failure; corrected provider/fault suite23PASS. Actual Codex request before correction lacked usage; after correction its durable event stream contains real token usage. |
| RI-04 | models._stream_cli accumulated the entire CLI response in a worker, then yielded chunks | Stream observations incrementally through existing provider interface, with cancellation/error propagation | FIXED targeted. Five async boundary tests PASS, including early delivery, late errors, startup failure, owned cancellation and normal completion. Bounded32event queue; protocol granularity remains provider-dependent, not invented token streaming. |
| RI-05 | _history_packet limits configured history to32000tokens and may keep only ends of an oversized recent message | Review provider-aware/context-budget policy; preserve exact commitments/raw references and expose omissions | PENDING. Current manifest already records omissions/truncation. Do not remove all bounds or claim it silently loses every conversation. |
| RI-06 | Context compiler ranks and clips sources to configured budgets; sibling context uses recent excerpts | Keep permission/relevance isolation; validate whether decisive equations, assumptions and failed attempts remain recoverable | PENDING long-work and adversarial retrieval evaluation. Existing source manifests and raw stores should be reused. |
| RI-07 | _tools uses deterministic read-prefetch rules before model dispatch | Treat as optional context enrichment under the stored MCP policy, not authority to choose a research strategy | KEEP permissions/no-tools enforcement. Evaluate redundancy and relevance, especially when native agents can select MCP tools themselves. |
| RI-08 | workflow_architect emits deterministic templates, keyword-selected teams and L-level-dependent defaults | Optional explicit templates must not become the mandatory reasoning path or autonomy qualification | PENDING policy/UI reconciliation. Retain useful capabilities while separating autonomy policy from template shape. |
| RI-09 | phdlab adapter selects a role and makes one model call while describing a broad multi-agent engine | Correct unsupported claims and use existing mission/harness tools; do not build another engine to simulate intelligence | PENDING. One role label/report is not independent collaboration or validation. |
| RI-10 | Fixed research-run pipelines organize explicit run skills | Keep as optional executable tools; allow strategy revision/rejection through the shared environment | PENDING reflexive research-control qualification. Pipeline completion is not scientific success. |
| RI-11 | Default token/time/retry/resource limits constrain execution | Retain explicit scoped budgets; make limits and resulting incompleteness visible | KEEP safety/resource controls. They are not blanket permission to truncate scientific requirements or pretend completion. |
| RI-12 | Schema validation, action approval, project isolation, sanitized context and actual evidence checks | Retain deterministic enforcement; evolve scoped authorization for ordinary L3 decisions separately | KEEP. Removing them would weaken trust rather than improve reasoning. |
| RI-13 | Memory uses candidates/review, fixed extraction patterns and summaries | Extend exact retrieval and evaluated procedural learning within existing stores; never self-promote generated instructions | PENDING long-term qualification. Do not replace reviewed evidence by a growing collection of untrusted skills. |
| RI-14 | workflow_architect.save_agent_profile silently clipped purpose to500characters and system_prompt to2000 | Preserve complete scientific instructions on durable save; retain normal permission controls | FIXED targeted. Actual RED/GREEN checks full long purpose/prompt and disk reload; related profile/harness suite12PASS. Previously discarded text is not magically recoverable from the clipped record. |

## What the first correction actually changes

Plain language now reaches the agent with the complete current request and conversation instead of being converted into a keyword-selected run. The agent may explain, compare, ask a useful clarification or propose a research action. Existing action schemas, permissions and researcher approval remain enforced. Explicit /commands still provide a direct interface when the user intentionally chooses a tool.

The native protocol correction prevents an intermediate assistant observation from terminating the process and being mistaken for a completed result. It also preserves subsequent provider errors and actual usage. The actual subscription probe returned the requested random nonce and arithmetic result in an isolated Codex runtime with API-key variables excluded. This proves that bounded connection path; it does not establish scientific quality, all-model compatibility or autonomy.

## Test-contract migration

The owner's new definition explicitly supersedes the older requirement that any matching plain prompt automatically start a fixed workflow. The historical affected run is retained:30cases,26PASS/3FAIL/1ERROR. These failures are contract conflicts after the intentional behavior change, not newly accepted exemptions.

| Previous expectation/test | Replacement and preserved obligation |
|---|---|
| test_auto_started_read_only_run_and_proposed_risky_run | test_model_proposed_risky_run_requires_approval_and_retains_the_real_run; model proposal, actual approval, stored run authorization and cancellation still checked. Explicit /lit execution remains covered by existing skill tests. |
| test_chat_intent_uses_the_skill | test_plain_question_does_not_force_a_keyword_selected_role_or_skill; full question reaches assistant without imposed keyword skill. Explicit /write and /gap role/instruction tests remain. |
| acceptance.P1_Prompt.test_plain_prompts_trigger_workflows | test_plain_requests_use_agent_proposals_before_workflow_execution; controlled model proposes the tool, no run executes before approval, approved real backend workflow reaches completion. This is MOCKED-model software acceptance, not live science. |
| Dashboard immediately expected a regex-created approval | Wait for the actual agent turn to finish, then retain the same run/approval/memory dashboard assertions. |

Do not retire remaining Feynman/OpenScience tests until their active functionality has moved to native tools and a separate replacement map exists. Security, memory isolation, provenance, research integrity, failure and recovery tests cannot be removed simply because a provider is retired.

## Remaining priorities

Finish affected/full software regression and preserve exact source evidence. Then address incremental stream/cancellation, context-fidelity stress tests and model-selectable tools through existing interfaces. Prepare paper-project migration before real-data writes. Consolidate providers and retire the two integrations with traced replacements. Qualify research-control/validation/learning on frozen guided and open-ended cases. Track RQ-01..RQ-14 in agent/research-quality-objectives.json; no new research engine or autonomy claim is warranted by this first pass.
