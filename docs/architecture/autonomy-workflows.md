# Independent L1–L4 workflows — development record

Reference: [AutoResearch AI, arXiv:2605.23204v1](https://arxiv.org/html/2605.23204v1), sections 1 and 4. Accessed 2026-10-24.

The paper treats L1 as bounded assistance, L2 as human-verified execution, L3 as AI-led coordination, and L4 as an aspirational scientific autonomy target. A software policy selector does not demonstrate scientific autonomy. In this implementation L3 and L4 are experimental **execution policies**, with scientific review explicitly pending. Novelty, validity and impact are not established by code coverage or a local dummy model.

## Audit before development

- Source baseline: `9003be4`; working tree initially clean. Existing Missions already provide typed capabilities, approvals, immutable plan digests, durable admissions, bounded reasoning and recovery. Keep these contracts.
- `research_jobs.worker` awaited one mission tick and each project in sequence. A slow inference delayed independent missions. `TeamPlan.max_parallel_tasks=1` is a per-mission constraint, not a four-workflow scheduler.
- Existing backend quality gate assigned PASS to coverage even without coverage, and to cross-platform checks on a single host. Historical live gate converted an entire suite outcome into per-feature PASS and emitted unconditional fault/compliance claims. These reports are not sufficient release evidence.
- Frontend baseline actually collected 149 tests, 64.98% lines, 65.75% branches, 51.29% functions. The README's historical 100% JavaScript claim does not describe the current React frontend.
- LM Studio advertises `qwen/qwen3.5-9b`. Listing a model is preflight only; actual application inference remains to be measured.

## Implementation contract

Use an optional, typed autonomy policy on existing MissionSpec; legacy missions preserve their behavior. L1 restricts capabilities to source inspection/synthesis and requires human acceptance of each bounded answer. L2 permits existing approved tools and requires human acceptance of each result. L3 runs its approved DAG and waits for final human review. L4 closes only a bounded technical workflow after independent artifact checks; scientific claims remain unreviewed. No level grants arbitrary shell access, expands budgets or silently enables Research OS.

Initial authorization always approves the exact plan. L1/L2 result acceptance binds the plan and result digests. Rejection stops that workflow. Interrupted admissions require reconciliation. A separate lifespan worker serves up to four independent missions, one task per mission, respecting existing hardware/provider slots. Parallel workflows can share a serialized local LLM slot.

Development and executed evidence will be appended here and in `docs/testing/autonomy-report.md`; unexecuted tests are never PASS.

## Development record — implementation

- Added optional `AutonomyPolicy`, digest-bound step review, L4 technical closure, and a lifespan worker with four independent in-flight ticks. Research jobs retain a separate worker. A single server process owns scheduling; multiple Uvicorn workers are not qualified by this change.
- Added the Missions → Workflows L1–L4 panel, local-model choice, source selection, optional already-approved protocol, exact plan/results and human review/rejection controls. Source-only runs explicitly say they have no experiment.
- Reproduced a real Qwen 3.5 integration defect: a 64-token `/no_think` request returned empty content, 64 reasoning tokens and `finish_reason=length`. The old adapter converted this to a nonempty truncation warning and could treat it as success. Added failing regressions, a local hard template switch and empty-answer rejection. A real request with `chat_template_kwargs.enable_thinking=false` and `reasoning_effort=none` returned READY with zero reasoning tokens in 0.54 seconds. This is a preflight result, not an E2E certificate. Reference: [official Qwen 3.5 model card](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/README.md).
- Corrected backend coverage and platform gates: absent measurement no longer passes; single-host results do not certify cross-platform operation. Release assessments now remain distinct from a successful test process exit code.

## Development record — live verification and remediation

- The initial live run correctly refused L4 numerical closure without an independent reproduction. L4 experiment plans now support two separately approved snapshots with the same digest and distinct approval nonces, followed by both independent verifications. No automatic protocol approval is added.
- Fixed a nested-transaction deadlock introduced in L4 closure: `checked_artifact` reuses the scoped Mission snapshot instead of opening a second write transaction. The initial failing evidence remains in `artifacts/autonomy-qa/live*`.
- CPU slot contention is checked before admitting an experiment. An occupied slot leaves attempts at zero, instead of consuming admission and failing the task.
- Fixed the historical research harness's stale `frontend/index.html` source manifest path after the React migration. Fresh v6.0/v6.2/v6.3 harnesses now fingerprint the actual React sources.
- Real browser screenshots revealed mobile drawer clipping even though document overflow was zero. Strengthened the oracle to require the inspector's full viewport bounds, then fixed the mobile inspector layout. Removed mandatory external Google Fonts requests; installed system-font fallbacks remain usable offline.
- Full dependency scans found four advisories in two installed packages. Raised production dependency floors and installed patched `pypdf`/`certifi`; subsequent Python and npm audits passed. SAST also reproduced XML entity expansion in arXiv parsing; added an adversarial test and `defusedxml` parsing.
- Removed the pre-existing coverage omission for `backend/execution/clearml_worker.py`. Frontend coverage now explicitly includes all production TS/TSX startup files. Missing code is reported, not omitted to improve a percentage.
- Windows blocked the installed SQLAlchemy binary extension. Reinstalled the same 2.1.5 version with its documented `DISABLE_SQLALCHEMY_CEXT=1` pure-Python build option; no Windows security policy was changed.
- HEAD advanced from `9003be4` to `0914d53` during work because an external change added `AUTORESEARCHAI.pdf`. That addition was preserved; source manifests distinguish the actual tested code bytes from the parent commit.
- Final L4 closure also rejects truncated model output, rather than accepting the provider's nonempty warning marker. Result digests are computed after output-policy checks so they refer to the exact persisted result.
- The initial legacy live run had two Team failures and one MCP timeout. All three passed in isolation and a fresh full repeat passed 70/71 with one CLI opt-in skip. Root cause of the initial intermittent behavior remains open; no retries are silently relabelled as first-attempt success.
- Final UI audit found the legacy Mission form submitted `max_reasoning_calls=4`, beyond the backend's maximum of 3. A regression assertion reproduced the mismatch; the form now submits 3. The launcher also probes the new defusedxml dependency and the two required workflow modules before starting.

## Agent-written experiment code (v6.6.4)

Before 6.6.4, `experiment.run` only ran the built-in denoising protocol, so an agent's own experiment ran outside
approval. An agent now calls `experiment.propose_protocol` with an entrypoint in the open code project, the conditions
(one is the baseline), the seeds, the metrics and the primary metric. The app copies the selected files into a
content-addressed store with a sha256 per file. It also pins the environment: the interpreter, its version and its
installed packages, or a Docker image digest. The protocol digest covers all of this.

The researcher reviews the frozen file list in Protocols and approves the digest. `experiment.protocol_status` then gives
the agent the single-use reference for `mission.experiment.run`, and the mission plan still needs approval.

The runner re-checks the frozen code and the environment, then runs every condition × seed once. Each run is a fresh
process on a fresh copy, with `PHDLAB_CONDITION`, `PHDLAB_SEED` and `PHDLAB_OUT` set. The code writes
`$PHDLAB_OUT/metrics.json` = `{"metrics": {...}}`. The runner never installs, edits, retries or re-plans.

`experiment.verify` (verifier `agent-code-recompute-v1`) re-reads the raw files, checks hashes, registration, code and
environment, and recomputes the paired comparison. It records a reproduction only from another separately approved run
of the same digest with matching metrics. It does not check how the agent's code computes a metric, and the best
condition is chosen on the same runs; both limits are stated in every report. Contract: FQC-AGENT-PROTOCOL-664.

## Harness canvas as a governed mission (v6.6.4)

Before 6.6.4 the Harness canvas runtime evaluated only control flow, so every agent and research node was blocked.
The team also came from keyword matching. Now a canvas runs through the mission runtime with a team the AI proposes.

**Team.** In the Team tab, the researcher picks an architect model from the model list (Settings → Models & AI
connections) and asks it for a team (`POST /api/harness/team/propose`). The architect proposes one to four agents, each
with a role, purpose, prompt, registry tools and a model from the same list. The app refuses unknown tools, unlisted
models and answers that are not JSON. An agent bound to an unavailable model stays in the team, marked as unavailable,
and is never swapped. The list leaves out Gemini CLI and Antigravity, whose terms forbid being driven, plus Hermes and
the router. Local engines count as available only after a short probe answers.

**Compile.** `POST /api/harness/compile` (`backend/agent/harness_compile.py`) maps each node to a mission step:

| Canvas node | Mission step |
|---|---|
| Agent node, code node | `agent.task` on the agent's model, with its tools |
| Literature node | `paper.discover` |
| Paper node | `paperorchestra.full_orchestration` |
| Approval node | `review.checkpoint` |
| Evaluation gate | `artifact.verify` of its input, with a note that a metric threshold needs an approved protocol |
| End node | `mission.report` |

The compiler refuses, and says why, for conditions, loops, a role no agent has, more than three model steps, and L4.
With `create: true` it stores a draft mission. The researcher approves the exact plan in Missions, and `teams.validate`
checks every role's authority.

**Run.**
- `agent.task` runs only on the bound model:
  - CLI agents run through `research.run_coding`, with a grant that carries the agent's registry tools under the
    owner's agent profile.
  - Local engines run locally.
  - Cloud engines run only when the mission allows API billing.
- If the model is unavailable, the mission pauses and says so. Nothing else is tried.
- `review.checkpoint` holds the mission in `awaiting_step_review` until the researcher reviews it, at any level.

Team missions need `research_os.team_enabled`, which is off by default; the owner decides that default. Live Codex
runs are recorded in `docs/qa/evidence/harness-team-664/`. Contract: FQC-HARNESS-TEAM-664.
