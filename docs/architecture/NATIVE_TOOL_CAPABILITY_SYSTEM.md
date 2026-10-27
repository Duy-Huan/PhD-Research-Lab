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
