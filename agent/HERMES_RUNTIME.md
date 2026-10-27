# Hermes runtime continuation and operator guide

Owner extension2026-10-26: Hermes is a separately isolated **agent runtime**, not a replacement Research Engine and not a framework dependency of FastAPI. Preserve native PhD agents, existing L1-L4 harness, memory, multi-agent workflows, evidence and research data. Target deep-learning research quality: data/split integrity, reproducible training, baselines, ablations, compute budgets, failure analysis and grounded papers. Adding Hermes alone proves no L3/L4 intelligence or scientific correctness.

Develop only on the existing dev branch. Complete the requested feature implementation before the consolidated testcase/regression/coverage campaign, as the latest owner explicitly requested. All actual mandatory checks still must pass before push/promotion. Never delete skills/ or agent/ files.

Chronology is recorded honestly: the four explicit runtime/provider/paper/integrity campaign contracts may use `IMPLEMENTATION_FIRST_OWNER_AUTHORIZED` with `OWNER-20261026-HERMES-FEATURE-FIRST`, an actual hash-bound all-PASS acceptance report and every traced scenario executed. They cannot invent a RED run, substitute skipped cases, or waive full regression/live/QA gates. Other contracts retain actual RED/GREEN requirements. The executable checks are in devtools/verification/contracts.py; this is the owner's order, not a skill-created exception.

## Pinned boundary

- Upstream Hermes Docker image: `nousresearch/hermes-agent@sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d`.
- Actual image version inspected without network/model calls:0.22.5, upstream revision `bf0203a794a07aac3ff764972ab9087baa4e4f4e`.
- Actual run_agent.py SHA256 `33c7195fc6efa9122f1a6700d416fd283f9634712189af3fd72feb01bcea054f`.
- Adapter protocol1. Build label additionally binds the Dockerfile/service/proxy sources. No floating update, host Hermes import or dependency installation in FastAPI.
- Reference: [official Python library guide](https://hermes-agent.nousresearch.com/docs/guides/python-library). Reviewed installed development guidance: ai-agents-architect, agent-memory-systems, agent-evaluation, security-best-practices; frontend-design and web-design-reviewer before UI work. These are guidance, not certification.

React -> existing FastAPI/gateway -> runtime:hermes -> authenticated loopback HTTP/RPC -> trusted proxy -> Unix RPC socket -> isolated Python AIAgent. Owner2026-10-26 explicitly requires unrestricted Internet for Hermes. The runtime uses Docker bridge networking with direct outbound Internet, no model/web domain allowlist and no forced proxy environment. The reused sidecar listener remains only for independently enforced ephemeral native MCP grants. This supersedes earlier restricted-network guidance for Hermes only; other CLI provider policies are unchanged. No Docker socket, host source/system/home, PhD API keys or global MCP credential is mounted. Runtime home and workspace are separate dedicated descendants of the active research project data directory, distinct per permission profile. Review workspace is mounted read-only; memory/skills remain writable in that project's Hermes home.

The proxy receives a short-lived tool grant, strips its bearer token before passing the job to Hermes and forwards only its authorized MCP endpoint. The model cannot expand that grant. Hermes web tools are enabled with direct Internet; native host tools still require scoped PhD grants. No arbitrary host plugin paths are mounted. Backend restart does not stop containers; proxy and runtime use independent Docker lifecycle. Runtime restart marks unfinished jobs INTERRUPTED; it never silently replays inference. Durable explicit conversation history supports subsequent turns; this is not an assertion that every upstream internal capability survives every failure.

## Operate

Use the supported project Python and a running Docker Linux engine. Set PHDLAB_DATA_DIR to disposable data during qualification.

```powershell
python tools/prepare_hermes_runtime.py
python tools/manage_hermes_runtime.py start --profile review
python tools/manage_hermes_runtime.py status --profile review
python tools/manage_hermes_runtime.py login --profile review
python tools/manage_hermes_runtime.py models --profile review
python tools/manage_hermes_runtime.py job --profile review --job <actual-job-id>
python tools/manage_hermes_runtime.py stop --profile review
```

Login launches the official Hermes/Nous OAuth command in its own container. The user completes any required login/challenge. Do not extract host browser cookies or copy PhD credentials. Model choices come from the actual account catalog. Free-only admission requires explicit zero input/output prices in the current catalog and never substitutes a paid model. Public promotion examples are not permanent entitlements. An unavailable free model blocks inference; do not spend credits to get PASS.

Stop preserves home/memory/skills/history/workspace. Explicit start can replace only ownership-verified adapter containers. Do not delete volumes or research folders to resolve failures. Upgrading requires reviewing a new immutable upstream image, API signatures/source identity, protocol compatibility and real integration/recovery evidence.

## Qualification still required

Current implementation work is uncommitted and NOT qualified. After features stabilize: protocol/auth/size/idempotency/security contracts, project isolation, token non-disclosure, free-only admission, durable history, backend/runtime restart, cancellation/deadline, scoped tools, frontend model/config state, real Nous inference, deep-learning experiment/replay/paper lineage and full2Dthen3D/nativeCLI/software regression. Keep fixture/mock/infrastructure and live/scientific results separate. Preserve every failure. Protected dev->qa->main promotion remains blocked until every mandatory current-source gate actually passes.

## v6.6.2 native environment (owner decisions 2026-10-27)

- One Hermes per project: memory, history and workspace stay under `<project>/agent-runtimes/hermes/<profile>/`. The workspace mode follows the owner's agent profile (`tools.client_profiles.hermes`, default "agent"): `workspace_write` -> `assisted` (writable), otherwise `review` (read-only). The old global `gateway.cli_profile` no longer selects Hermes' profile.
- Shared across projects (app data `hermes-shared/`): the Nous sign-in through Hermes' own `HERMES_SHARED_AUTH_DIR` (`/opt/shared-auth`), and an owner-reviewed skill library mounted read-only at `/opt/shared-skills` and linked through `skills.external_dirs` in a newly created project `config.yaml` (an existing config is never rewritten). Share a learned skill with `POST /api/runtimes/hermes/share-skill {"skill", "approved_by"}`; list with `GET /api/runtimes/hermes/skills`.
- No work budgets: jobs send no deadline/iteration/token limit unless the owner sets `hermes.deadline_s/max_iterations/max_tokens` above 0 (Hermes' own defaults are unlimited, verified in the pinned image). The backend observes without a deadline; only a runtime that does not answer for 120 s is an error. The user's cancel still stops the job.
- Hermes always receives the registry meta-tools `phdlab_tools_search/describe/call`.
- Only the open project's Hermes runs: starting it stops (never removes) other projects' Hermes containers.
- The proxy container no longer receives the unused `PHDLAB_ALLOWED_DOMAINS` variable; the runtime keeps unrestricted Internet as before.
- Real Docker smoke (no sign-in, no inference) is recorded in `docs/qa/evidence/hermes-native-662/live-docker-smoke.json`. Docker Desktop bind mounts from `%LOCALAPPDATA%\Temp` failed with EIO on this host; use project folders on a normal drive.
