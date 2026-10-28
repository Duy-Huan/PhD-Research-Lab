# Native tool capability system (v6.6.0)

The environment provides tools; the agent decides how to use them. Authority always comes from a runtime **Grant**
issued by application code, never from a model message, a tool specification or tool output.

```
agent (any model)                  backend/tools
  │  search / describe / call ──►  agent_loop ──► registry ──► builtin MCP tools (research_*, web_*, sandbox_*)
  │  propose_tool / validate_tool   │              │          manifests  <project>/tools/<id>/<version>/tool.json
  │  final (+ evidence job ids)     │              │          external MCP snapshots  <project>/tools/_mcp/
  ◄── observations (data) ──────────┘              │          Google Colab / Drive (optional, isolated)
                                    runtime ◄──────┘
                                      grants · budgets · async jobs · streamed observations · timeout/cancel
                                      retry (retryable + idempotent only) · schema validation
                                      hash-chained provenance  <project>/tool_runs/provenance.jsonl · replay
                                    adapters: native · python · cli · mcp (HTTP + stdio) · container
```

| Module | Responsibility |
|---|---|
| `spec.py` | `ToolSpec` (id, semver, kind, capabilities, input/output schema, permissions, mutates, idempotent, retries, budget), `ToolError` codes, version constraints (`*`, exact, `^1.2`, `>=1.0.0`) |
| `schema.py` | Bounded JSON Schema subset; unsupported keywords make a schema invalid instead of silently unchecked |
| `registry.py` | Central versioned index, active-version pointer, app compatibility, BM25-style search with capability/kind/permission filters, lazy `describe`, cached availability probes, external MCP discovery |
| `adapters.py` | One execution contract per kind; process tools run with allowlisted environment, `python -I`, no shell, private working directory and whole-tree kill; containers read-only, `cap-drop ALL`, no network unless granted |
| `runtime.py` | `submit`/`run`/`wait`/`events`/`cancel`/`replay`; every attempt (including denied) is recorded before its terminal status is published |
| `agent_loop.py` | Model-driven loop with no tool-specific logic; empty/truncated replies are protocol errors; cited evidence must be succeeded jobs |
| `proposals.py` | Agent-written tools in an isolated area; validation bound to the proposal digest and to the proposer's permissions; promotion by a named human only; immutable versions and rollback |
| `google_mcp.py` | Optional Google Colab / Drive MCP confined to `<project>/google_mcp/` (see below) |

Chat sessions keep `tool_mode: "legacy"` by default. `tool_mode: "agent"` replaces keyword tool pre-selection with the
model-driven loop; its grant is the session MCP allowlist, read-only, at most 12 calls within `aiws.max_turn_s`.

HTTP: `GET /api/tools`, `/api/tools/search`, `/api/tools/{id}`; `POST /api/tools/{id}/invoke`;
`GET /api/tools/jobs/{job}` `/events` `/stream`; `POST /api/tools/jobs/{job}/cancel`; `GET /api/tools/provenance` `/verify`;
MCP servers, proposals (`/validate`, `/promote`), rollback and `/api/tools/google/*`.

## Optional Google MCP tools (isolated)

Both servers are **off** until enabled for a project. Everything lives in `<project data>/google_mcp/`:
`settings.json`, `secrets/` (OAuth client and token), `colab/` (working directory, HOME, caches, temp of the Colab
bridge), `drive/` (discovered tool snapshot), `logs/`.

**Google Colab** — official [googlecolab/colab-mcp](https://github.com/googlecolab/colab-mcp), a local stdio bridge to a
Colab notebook open in your browser. Requires `uv` (`pip install uv`).

```powershell
# enable (default command: uvx git+https://github.com/googlecolab/colab-mcp)
curl -X POST http://127.0.0.1:8765/api/tools/google/settings -H "Content-Type: application/json" -d '{"colab":{"enabled":true}}'
# open a Colab notebook in the browser, then discover its tools
curl -X POST http://127.0.0.1:8765/api/tools/google/google_colab/discover
```

The bridge process receives no PhD Lab, provider or GitHub credentials, and only `google_mcp/colab/` as its MCP root.
Code you run through it executes in the Colab runtime, not on this machine. Tools appear as `mcp.google_colab.*`
and need the `network` and `compute` permissions.

**Google Drive** — official Google Workspace remote MCP server `https://drivemcp.googleapis.com/mcp/v1`
(Developer Preview; [setup guide](https://developers.google.com/workspace/guides/configure-mcp-servers)). In Google
Cloud: enable the Drive API and Drive MCP API, create an OAuth client of type *Web application* ("Use this client for an
AI-powered agent") with redirect URI `http://127.0.0.1:8765/api/tools/google/drive/oauth/callback`.

```powershell
curl -X POST http://127.0.0.1:8765/api/tools/google/drive/oauth-client -H "Content-Type: application/json" -d '{"client_id":"…apps.googleusercontent.com","client_secret":"…"}'
curl -X POST http://127.0.0.1:8765/api/tools/google/settings -H "Content-Type: application/json" -d '{"drive":{"enabled":true,"folder_id":"<dedicated Drive folder id>"}}'
curl -X POST http://127.0.0.1:8765/api/tools/google/drive/oauth/start     # open the returned auth_url
curl -X POST http://127.0.0.1:8765/api/tools/google/google_drive/discover
```

Folder isolation is enforced by **FolderGuard**, default deny: reads, downloads, permissions and copies must prove the
file lies inside the dedicated folder (parent chain, bounded depth); create/copy are forced into that folder; search
and recent-file results are filtered to it; tools outside the policy (for example deletion) are never exposed; a call
whose containment cannot be verified is refused. The OAuth token is sent only to `*.googleapis.com`.

Limitations, stated plainly: Google's required scopes (`drive.readonly`, `drive.file`) still let the token read the
whole Drive — the folder boundary is enforced by this application, not by Google. Automated tests use local fixture
servers; compatibility with Google's live servers must be recorded separately before it is claimed.

## Provider pool (v6.6.1)

`tools.provider_pool` (Settings, owner-configured, empty = off) lists DIFFERENT providers in order, for example
`["cli:claude_code", "cli:codex", {"provider": "app:gemini", "model": "gemini-3.8-flash"}, {"provider": "app:local", "model": "spark-x2.5-4b"}]`.
In `tool_mode: "agent"` the loop continues on the next provider only when the current one reports quota or rate-limit
exhaustion; any other error stays with the model. A provider may appear once (no account rotation) and Antigravity
cannot be a member (its terms). Exhausted providers rest `pool_cooldown_s` (60-86400 s). Every tool job records its
`actor` (provider:model) in provenance, and chat records `providers_used` and `mixed_models`. All exhausted ends the
run BLOCKED.

## Antigravity as an interactive MCP client (v6.6.1)

`POST /api/tools/clients/antigravity/register` writes `{"mcpServers": {"phd-research-lab": {"serverUrl":
"http://127.0.0.1:<port>/mcp"}}}` into `~/.gemini/config/mcp_config.json` (other servers kept, previous file backed up,
invalid JSON never overwritten, bearer header only if `mcp.token` is set). Restart Antigravity, choose Gemini 3.8 Flash
and work in the same project; it reaches the registry through `phdlab_tools_search/describe/call` under
`tools.mcp_permissions`. `POST /api/tools/clients/antigravity/unregister` removes only this entry.


## Long registry calls return a job (v6.6.4)

`phdlab_tools_call` waits at most `wait_s` seconds (default 45, maximum 300), which is below the 60 s MCP tool timeout of
the CLI clients. A tool still running after that returns `status: "running"`, its job id, its latest observations and a
hint. The client then calls `phdlab_tools_job` with `{job, wait_s}` to wait for the result, or with `action: "cancel"` to
stop the tool. Only the principal that started a job can read or cancel it; any other job id answers `not_found`. A long
sandbox run through the Codex container proxy therefore no longer ends in HTTP 502 while the run continues.
Hermes and ChatGPT see `phdlab_tools_job` together with the other three meta-tools. Contract: FQC-TOOL-JOBS-664.
