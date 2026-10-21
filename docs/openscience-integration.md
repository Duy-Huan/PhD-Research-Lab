# OpenScience integration: audited preview

This is an opt-in external research-engine adapter. It is **disabled by default**. It does not install or copy OpenScience skills, replace the LLM gateway, or provision compute. Architecture, evidence and the rollout decision are in [the ADR](adr/2026-10-21-openscience.md).

## Compatibility verified on 2026-10-21

| Component | Evidence | Limit |
|---|---|---|
| Installed OpenScience | Native Windows runtime 2.0.152; isolated real-server probe passed | No model inference was submitted |
| Runtime protocol | 1.0; deployment auth, effective permission policy, sessions, snapshots, replay, ahead-cursor conflict and empty artifact inventory checked | Cancellation of active tools and restart recovery still require a configured model |
| Official Python client | Source-preview `openscience-runtime` 0.1.0 at `d720862157d146d52b6faae1e5aff9d3973ed918`; upstream socket suite and adapter socket test | Not a published PyPI release; audit before upgrading |
| Feynman | Existing dispatch reused through a typed adapter; existing regression tests retained | No live Feynman/model benchmark in this increment |
| Results / Memory | Existing run outputs and human-reviewed pin proposals; engine manifest links native IDs, hashes and provenance | Generated claims remain unreviewed; no automatic memory promotion |
| ClearML / compute | Existing experiment and remote-compute paths preserved | OpenScience does not yet submit or import verified ClearML tasks |

Machine-readable live evidence: [`live-protocol.json`](../artifacts/openscience-audit/live-protocol.json). The probe creates isolated temporary state, uses a random deployment token, calls no model, then terminates and reaps its process tree. No user's OpenScience settings are modified. The audited `serve` command binds loopback internally; **there is no `--hostname` option**.

## Enable a reviewed runtime

Install the optional official SDK into the same Python environment used by PhD Lab:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-openscience.txt
```

The requirement pins the upstream commit. No extra dependency is added to the base requirements. SDK source can also be supplied explicitly to the probe without installation:

```powershell
.venv/Scripts/python.exe tools/probe_openscience_runtime.py --sdk-path C:/path/to/audited/openscience/tooling/sdk/python
```

Configure OpenScience's own model access using its official setup instructions. Use a dedicated OpenScience instance/data directory for PhD Lab. Do not point a research job at an instance holding unrelated private projects. PhD Lab never forwards its API keys to OpenScience.

Example launch in a dedicated terminal, with the deployment token supplied by your environment or secret manager (do not paste it into source control):

```powershell
$env:OPENSCIENCE_DATA_DIR = 'D:/PhDLab-OpenScience/runtime-data'
$env:OPENSCIENCE_CONFIG_DIR = 'D:/PhDLab-OpenScience/runtime-config'
$env:OPENSCIENCE_DISABLE_AUTOUPDATE = '1'
$env:OPENSCIENCE_CONFIG_CONTENT = .venv/Scripts/python.exe -c "import json; from backend.research_engines.openscience import policy; print(json.dumps({'permission': policy(False)}))"
# OPENSCIENCE_AUTH_TOKEN must already contain your deployment token.
openscience serve --port 4096 --format json
```

This example intentionally sets the read-only adapter policy. To opt into execution later, review the execution environment and use the matching `policy(True)` on the dedicated runtime, then enable execution in PhD Lab. Conflicting global/environment/project permission overrides are rejected before prompt submission. OpenScience may also read home-level/project configuration and plugins; inspect the effective configuration and extensions of this dedicated instance. Use an isolated OS account/container for untrusted code. A project directory selector and native tool permissions are not an OS sandbox.

OpenScience has scientific trace-sharing settings for signed-in accounts. Review its **usage logging** controls before sending private research; the public settings endpoint is `/settings/usage-logging/`. An external inference provider also receives task content. The acknowledgement in PhD Lab confirms this operator review; it does not automatically change upstream privacy settings.

In **Settings → Research providers → Research Engines**:

1. Set the loopback URL and deployment token; enable the adapter and acknowledge the runtime/privacy review.
2. Keep execution disabled for the first protocol/read-only acceptance.
3. Use `/science <bounded task>` or select OpenScience Only. Approve the run card before it submits work.
4. Set explicit native model provider/model ID and qualify individual task categories only after testing that exact model/runtime. Changing endpoint/model clears qualification on the backend. A healthy endpoint alone does not qualify research reasoning.

Auto uses `research_providers.engine_priority` (default Feynman then OpenScience) and verified task categories. The priority order is configurable through `/api/config`; the UI exposes mode and model qualification. Manual modes remain available. Collaborative creates exactly one primary step and one cross-review, followed by the existing verification/report stages. It does not create an engine-to-engine loop. `POST /api/runs` accepts an `engine_mode` override for an individual workflow.

## Contracts and failure recovery

`backend/research_engines/contracts.py` defines schema 1.0 tasks, events, results and normalized failures. `registry.py` lazily resolves adapters. OpenScience's optional SDK is imported only when needed. New adapters must pass the same boundary/version/capability checks and their transport-specific recovery tests. Engine identity remains separate from model-provider identity.

Each workflow step receives a dedicated native session and workspace under `<project>/research-engines/workspaces/`. Context is rebuilt from the current PhD Lab project brief when a **new operation** starts, then sanitized and frozen with a SHA-256 in its journal. An observation resume uses the admitted operation's original context and model. To include changed evidence/model in inference, create a new operation. This increment shares the selected project brief, not the whole repository or attached datasets; explicit file/dataset transfer is a later gate.

Journal files under `<project>/research-engines/jobs/` persist exact sanitized input, request identity, native session/run IDs, processed cursor and partial output. They contain research data and should use the same storage protections as the project. No deployment token is stored there.

* Uncertain prompt admission: no automatic prompt retry. Use the run card's explicit admission recovery; it reuses the **same** session, request ID, message and model. Lost session creation requires manual reconciliation; it does not create another session automatically.
* Socket inactivity: the SDK read timeout is shorter than the server heartbeat. Reconnect observation only after a successful snapshot/receipt check; preserve the processed cursor and the original prompt. Cursor gaps reconcile to a snapshot and pause for explicit observation resume. Completion always comes from a durable receipt and authoritative final message.
* Pending permission/question: use a fresh runtime snapshot. The chat card exposes only once/reject and explicit answers, never global grants. Historical events are not approval authority. Native continuations can expire after runtime restart.
* Timeout/cancel: request cancellation of the recorded native run. A still-running response or lost response remains `cancellation_unconfirmed`. Cancelling a paused workflow also requests native cancellation. Inspect or repeat native cancellation through the engine-job endpoint until settled. Local workflow cancellation is not proof that native tools or detached work stopped.
* Engine switch: an existing native operation must have an authoritative terminal receipt before a different engine can replace the step. No automatic quota fallback to a local model. Confirmed failed/interrupted work starts a new native attempt only after explicit researcher resume; completed workflow steps are retained.
* Artifact import: use the public artifact store, never `sourcePath` or URLs supplied in text. Validate native IDs, filename containment, symlinks, count, total bytes, size and SHA-256. Failed transfers leave no partial file. Downloaded files are untrusted research artifacts and are not executed automatically.

The bounded event queue holds 256 items. SDK events are limited to 1 MiB, metadata responses to 4 MiB, and artifacts to 32 files/64 MiB total by default. Time budgets are capped at 7,200 seconds. Native delegation and remote compute permissions are denied. One unresolved OpenScience admission per project is allowed, including tasks waiting for decisions. Existing CLI/GPU resource admission applies while the local workflow observes the native run; it does **not** enforce device isolation or control tools already running externally. Do not enable native execution as a substitute for the existing supervised compute backend.

API inventory: `GET /api/research-engines`; `GET /api/research-engines/jobs/{job}`; `POST .../decisions`; `POST .../recover-admission`; `POST .../cancel`. Job lookup is scoped to the active research project. Existing run/chat event contracts are preserved; `engine.event` adds versioned engine progress, and normal `run.updated` refreshes the chat card. The SDK/session cursor is not the PhD Lab SSE cursor.

## Results, ClearML and scientific acceptance

Each successful OpenScience step writes `engine-evidence-<step>.json` beside the existing run reports. It contains the workflow/step IDs, native IDs, artifact hashes, context hash, optional hypothesis/experiment references, `scientific_review: pending` and `clearml_task_id: null`. A real ClearML ID must come from the compute workflow, never a generated description. The existing Results pin proposal retains the research-run link; Research Memory consumes approved knowledge through its current review path.

The next increment should use the existing experiment manager to accept an approved, versioned experiment bundle from an engine result. Verify dataset/code/config lineage, register the actual ClearML task, run via the existing compute backend, and import metrics/artifacts only after local verification. Keep notebooks as artifacts/execution formats. Do not give OpenScience a second scheduler or duplicate training dashboard.

Scientific acceptance remains **pending**. Use five supplied papers and a fixed approved model/budget: two gaps with source references, one human-approved hypothesis, one baseline submitted to the real ClearML backend, verified metrics/checkpoints, then a cited cross-review. Record all IDs, dataset version and code commit. Repeat with stream loss, quota during cross-review, runtime restart and corrupted artifacts. The acceptance criteria are:

* Every gap/claim has traceable evidence or an explicit unsupported label.
* No code/compute/model escalation occurs without the required approval.
* A failure preserves completed stages and never silently repeats training.
* Artifact checksums and real ClearML task state agree before experiment completion.
* Final conclusions remain pending human scientific review; tuning and held-out evaluation stay separate.

## Repeatable checks

```powershell
# Install optional SDK first, or set PYTHONPATH to the audited tooling/sdk/python directory.
.venv/Scripts/python.exe tools/run_tests.py test_research_engines test_runs test_config test_skills test_orchestrator test_api
node --test tests/frontend/*.test.js
.venv/Scripts/python.exe tools/probe_openscience_runtime.py
```

Without the SDK, its optional socket integration test skips explicitly; the application and other adapters remain usable. The test suite's deterministic peers prove contract/recovery behavior, not scientific quality or live provider access.

## Upstream references and licensing

* [Pinned source and native architecture](https://github.com/synthetic-sciences/openscience/tree/d720862157d146d52b6faae1e5aff9d3973ed918)
* [Official Python SDK and conformance tests](https://github.com/synthetic-sciences/openscience/tree/d720862157d146d52b6faae1e5aff9d3973ed918/tooling/sdk/python)
* [Public runtime routes](https://github.com/synthetic-sciences/openscience/blob/d720862157d146d52b6faae1e5aff9d3973ed918/backend/cli/src/server/routes/runtime.ts)
* [Public artifact routes](https://github.com/synthetic-sciences/openscience/blob/d720862157d146d52b6faae1e5aff9d3973ed918/backend/cli/src/server/routes/file.ts)
* [Apache-2.0 license](https://github.com/synthetic-sciences/openscience/blob/d720862157d146d52b6faae1e5aff9d3973ed918/LICENSE) and [NOTICE with third-party/skill terms](https://github.com/synthetic-sciences/openscience/blob/d720862157d146d52b6faae1e5aff9d3973ed918/NOTICE)

No upstream native skill tree is redistributed. Review skill-specific, dependency and connected-service terms when deploying the external runtime; Apache-2.0 at the top level does not relicense every bundled component.
