# Cloud runtime v5.1: audit, changes and validation

Audit date: 21 October 2026. The checkout already contained uncommitted v5.1 changes before this work; those changes were retained. This document describes the runtime additions, not a claim that every proposed integration is production ready.

## What the audit found

* The terminal REPL already existed in `backend/cli/repl.py`: streaming Markdown, slash-command completion, conversation reuse, approvals and Ctrl+C. `chat.bat` now opens it directly. Start the backend with `run.bat`, then open `chat.bat` once and type questions at the prompt; no command prefix is needed per message.
* Gateway → orchestrator used `events()` followed by a 200 ms sleep. Gateway events grew without a limit. Browser SSE already used a session condition variable.
* Gateway CLI calls refused an unavailable provider without automatic fallback. Research runs behaved differently: an unavailable Feynman could be replaced with `app`, whose router could then choose a small local model. The original question about automatic local fallback therefore depends on the execution path: it was possible through research runs, not through direct gateway chat.
* The orchestrator compiled context, then the gateway retrieved memory again. Context caches already used project identity, write generation and file signatures; replacing them with a session-wide frozen prompt would have risked stale context.
* ClearML recorded offline sessions; it was not an online experiment-management backend. There was no Colab adapter or authenticated resumable dataset transfer layer.

## Implemented behavior

### Streaming and latency

Gateway consumers use `wait_events()` and a condition variable, with bounded waits for cancellation checks. Each request retains a 512-event hot window; JSONL on disk supplies older cursor ranges in ordered batches. Terminal notification occurs after worker cleanup, including lifecycle failures. Events are redacted before storage and consumption. Duplicate `send()` calls on an active/completed request do not start another process; cancelled/failed requests must be explicitly recreated. Persisted requests that lost their process after restart become failed with retained partial output.

Request metadata records context preparation, total preparation, OS process creation (`cli_startup`), first CLI output, first normalized provider event, first text and total duration. `cli_startup` measures `Popen`, not a fully initialized agent. `chat.context` spans cover the upstream compiler. `chat.sse_delivery` measures the first delta's age at the server's SSE handoff, not network delivery or browser paint. SSE data objects remain unchanged; SSE `id` lines and `Last-Event-ID` support resume from the client's cursor.

CLI chat now uses the already compiled turn context instead of retrieving memory a second time. Each new turn still recompiles/version-checks its context; standalone gateway requests retain their memory compiler.

Timeout/cancellation cleanup reaps CLI processes. Windows cleanup can enumerate descendants of a verified, still-owned process handle before falling back to taskkill/parent termination. This fixes the reproduced case where a Python child retained a directory lock after its shell was stopped. MCP grants are revoked in `finally`.

### Codex app-server prototype

`gateway.codex_app_server` defaults to `false`. Enable it in Settings → Research providers for opt-in testing. The prototype starts a stdio process per request, initializes RPC, starts/resumes a native thread, starts a turn, streams message deltas and checks the terminal turn status. It keeps the existing workspace, environment cost guard and sandbox profile. Interactive approval requests fail closed; an approval UI bridge is not implemented.

Initialization failures may fall back to `codex exec`. Once `turn/start` might have been sent, there is **no automatic replay**, including ambiguous delivery. A failed/interrupted turn is never treated as completed. Native thread IDs are remembered under the existing lifecycle policy.

This is not a persistent warm-process pool. Reusing a long-lived process with refreshed MCP grants, auth renewal and isolated concurrent turns remains future work. Defaults must not switch without successful real-provider latency and continuity evidence.

An explicit Codex catalog refresh calls `model/list` without inference. The returned catalog is not proof of account entitlement. Other CLI catalogs can be configured explicitly in settings, and Claude's standard model aliases are offered. API catalogs can be refreshed from their configured provider. Local lists come from the installed LM Studio/Ollama models. Custom API model IDs remain supported through “Custom…” in the model list.

### Provider settings and failover

Settings include search, distinct Local/API sections, CLI catalog configuration, a separate MCP & ChatGPT tab, ordered per-task router choices and model-specific fallback qualification lists. Chat displays providers grouped by transport and a model dropdown for the selected provider. Changing provider clears the prior model override.

`routing.capability_aware` defaults to true. Local models are eligible by default for extraction, summary, context and lightweight critique tasks, not research reasoning/code/writing. For those stronger tasks, automatic alternatives must appear in `routing.verified_fallbacks[kind]` as `provider:model`. A changed model ID does not inherit qualification. The first configured available primary remains the primary; qualification is a researcher decision, not a conclusion inferred from a connection test or model name. Explicitly selecting a fixed engine is still available.

Unavailable Feynman/coding providers now pause a research run for a decision instead of changing its provider. Quota/auth failures do not consume automatic retries. Completed steps are kept; only the pending/failed step is resumed after the researcher restores access or chooses another provider. Feynman interruptions collect available workspace artifacts, partial output and an interruption manifest. Native resume *inside* a Feynman workflow has not been verified; the app must not claim that it can resume the precise internal hypothesis-critique operation.

### Remote compute / ClearML MVP

`backend/execution/remote_compute.py` supplies durable experiment records with run/project/experiment/hypothesis IDs, code commit, dataset version/manifest, compute target, approvals, metrics and artifact references. Records are independent of notebook state and enter the research context with cache invalidation. Targets are represented as `local-gpu`, `docker` and `colab-gpu`; existing local/Docker runners continue operating as before.

The chat can propose `prepare_remote_experiment`. Accepting the proposal prepares a local bundle of explicitly selected files from the active code project. It rejects traversal, private/config/cache paths, detected credentials and oversized code bundles. It includes file checksums, a manifest, a launcher and a Colab notebook. It never recursively packages the repository or automatically uploads datasets.

The generated `launch.py` checks code/config and dataset hashes, checks GPU availability when required, creates a real ClearML task with `General/run_id`, executes the approved entrypoint, then uploads all explicitly required outputs and scalar metrics. Training code writes outputs under `RUN_DIR`; default required outputs are `metrics.json` and `best.pt`. Add logs, figures and other files to `required_artifacts` when creating the record. The notebook is an attended way to invoke this launcher, not the job-state database.

The dashboard shows simple run cards. A researcher releases the reviewed bundle, runs it in the configured environment and links the actual ClearML task. Online collection uses the SDK in a separate worker with the user's configured `clearml.conf`/environment; no ClearML credentials enter the bundle. `General/run_id` must match. Collection downloads raw files without pickle deserialization, checks available remote checksums, records local SHA-256 hashes and rechecks the local files. A completed remote task remains `awaiting_collection` until required outputs are verified locally. ClearML links use the actual task and ClearML project IDs.

Enable `clearml.server_enabled` and set the Web URL in Settings → hardware. Configure the SDK separately with `clearml-init`. A Colab runtime must be able to reach the API/file server; `localhost` on the PC is not accessible from Colab. No server is installed, exposed or reconfigured automatically.

Example bundle request:

```json
{
  "files": ["train.py", "evaluate.py", "requirements.txt", "config.yaml"],
  "entrypoint": "train.py",
  "compute_target": "colab-gpu",
  "experiment_id": "exp-unet-baseline",
  "hypothesis_id": "HYPE-003",
  "dataset_version": "v1",
  "required_artifacts": ["metrics.json", "best.pt", "training.log", "comparison.png"]
}
```

Use `POST /api/compute/runs`, `POST /api/compute/runs/{run_id}/approve`, `GET /api/compute/runs/{run_id}/bundle`, and `POST /api/compute/runs/{run_id}/sync` with `{ "task_id": "actual-id", "collect": true }`. A mounted dataset manifest can contain `{ "path": "train/images.bin", "sha256": "<64 hex characters>" }`; set `PHDLAB_DATASET_DIR` in the execution runtime.

## Evidence and limits

Validation: the selected backend regression suite passed 144 tests (2 skipped), and all 82 frontend tests passed. A subsequent focused runtime/provider/gateway/process suite passed 35 tests after the partial-output preservation change. Logs are stored beside the benchmarks. These are targeted backend checks, not a full-repository coverage claim. The generated launcher was executed against a fake ClearML SDK and tested for checksum rejection under `python -O`; no real training or online ClearML job was run.

Installed versions verified with their own CLI help/version output:

| CLI | Version | Verified locally |
|---|---|---|
| Codex | 0.163.0 | app-server subcommand/stdio, exec/native resume argument builder |
| Claude Code | 2.1.304 | stream-json, partial-message and native resume flags |
| Gemini CLI | 0.64.0 | stream-json and resume flags; bundled session resolver accepts UUIDs |
| Antigravity | not found | no headless execution claim |

Gemini's adapter now forwards the remembered native session to `--resume`. Protocol fixtures verify native-session propagation; real inference and continuity still require working provider access.

Benchmarks are in `artifacts/cloud-runtime/`. The live test used only a trivial OK prompt in temporary data/workspaces:

* Codex reported `AUTH_EXPIRED` in this execution environment, so neither exec nor app-server could produce a token.
* Gemini reported no configured auth method in this environment.
* Claude's first attempt exceeded the 20-second test limit; the subsequent resume failed during execution. No successful cloud TTFT sample was obtained.
* Fake CLI and RPC peers exercise cold/warm paths, native session propagation, timing and cleanup. Their timings are harness measurements, not provider speed claims.

Re-run successful provider benchmarks after restoring the CLI sign-in/environment:

```powershell
.venv\Scripts\python.exe tools\benchmark_cloud_runtime.py --live --timeout 90 --output artifacts/cloud-runtime/exec-live.json
.venv\Scripts\python.exe tools\benchmark_cloud_runtime.py --live --providers codex --app-server --timeout 90 --output artifacts/cloud-runtime/app-server-live.json
```

“Cold” means the first request in a new benchmark process/workspace; “warm” means another request in the same workspace/native session with a freshly launched CLI process. OS/disk/model-server caches are not flushed. No paid API fallback is enabled by the benchmark.

Still not implemented/validated: a hosted ChatGPT connector to localhost; automatic access to “all free models”; an external Colab MCP client with dynamic tool-list notifications; authenticated resumable large-dataset upload/download; unattended Colab scheduling/recovery; an online ClearML end-to-end run against the user's server; a persistent app-server pool; autonomous HPO/Optuna loops; dedicated snapshot/budget-scheduler/failure-KB additions. The existing run budgets, evidence records and local/Docker execution remain available. Remote experiment records stay in exploration with final evaluation and researcher review pending; completion does not certify a scientific claim.

MCP supplies tools, not a free inference entitlement. OpenAI model/account access and managed services are separate from the open harness. The official Colab MCP repository requires a local client supporting `notifications/tools/list_changed`; PhD Lab's inbound research MCP endpoint alone does not provide that outbound client capability.

Sources: [OpenAI app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server), [Codex integration layers](https://developers.openai.com/blog/codex-as-a-platform), [official Colab MCP](https://github.com/googlecolab/colab-mcp), [ClearML artifact retrieval](https://clear.ml/docs/latest/docs/getting_started/logging_using_artifacts/).
