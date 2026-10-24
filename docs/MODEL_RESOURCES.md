# Agent model resources

Settings → Models & agents assigns a source and optional model to Research, Reviewer and Utility. The chat picker’s **Auto** entry invokes these assignments; selecting a fixed chat provider takes precedence for that conversation. An agent whose source is **Auto** uses the existing capability-aware routing chain and each provider’s own default model. It does not apply one model ID across vendors.

## API keys, gateways and local models

Choose OpenAI to see only its catalog, its configured default and that agent’s custom override. Changing the source clears the previous override atomically. The same rule applies to other vendors. Cloud/Claude aliases track their resolved provider, including authentication changes. Catalogs are suggestions until actual account access is verified; **↻ Models** requests that provider’s current catalog without performing inference.

Expand **Endpoint** in an API row to set a provider-specific base URL. Custom OpenAI-compatible, 9Router and OmniRoute remain available. Only that provider’s configured key is used for its API requests. A failed key save retains the entered value for retry; successfully saved keys are masked by the backend.

LM Studio and Ollama expose model lists through the existing local probe. Their models appear in the corresponding agent dropdown, with a Custom model option. Local lifecycle leases, background unload policies and hardware controls retain their existing behavior. The new cloud fallback switch lets a fixed local agent remain local on failure; enabling fallback can incur charges on a configured cloud API. Capability qualification for automatic reasoning/code/writing fallback remains explicit.

CLI subscription providers remain selectable in the chat picker with their existing sign-in, workspace firewall and scoped MCP-tool policies. This change does not silently turn their subscriptions into API keys or advertise unverified entitlement.

## MCP inference tool

MCP is a tool protocol. To use an MCP-backed agent, explicitly configure a server tool that actually performs inference. PhD Lab does not automatically treat a filesystem, search or memory server as a model.

The optional `mcp_agent` config section defaults to disabled. It contains `enabled`, `url`, `token`, `tool`, `models` and `timeout_s` (5–600 seconds; default 120). The model catalog is a user-configured list of model IDs owned by this server; it is not account-access verification. Each agent can select a different model from this list or use the server default.

Example configuration, without a credential:

```json
{
  "mcp_agent": {
    "enabled": true,
    "url": "http://127.0.0.1:8766/mcp",
    "tool": "infer",
    "models": ["my-local-model", "my-remote-model"],
    "timeout_s": 120
  },
  "agent_modes": {"research": "mcp"},
  "agent_models": {"research": "my-local-model"}
}
```

The selected tool must expose an object `inputSchema` with `system` of type `string` and `messages` of type `array`. Supported argument names are:

| Argument | Value |
|---|---|
| `system` | Agent system/context string |
| `messages` | Conversation messages, as JSON objects with role/content |
| `model` | Selected model ID, or an empty string for server default |
| `max_tokens` | Integer output limit requested by PhD Lab |
| `temperature` | Numeric generation setting |

Only arguments declared by the tool are sent. Required arguments outside this contract are rejected. A selected model override is rejected if the tool has no `model` property. Return MCP text content, for example:

```json
{"content": [{"type": "text", "text": "Answer with source references"}]}
```

The client initializes MCP, sends the initialized notification, checks `tools/list` (bounded pagination), then calls only the configured tool. It supports correlated JSON and SSE replies, handles session/protocol headers, caps replies at 2 MiB and limits total time. Protocol versions supported here are `2024-11-05`, `2025-03-26`, `2025-06-18`. HTTP is limited to literal loopback hosts; remote endpoints require HTTPS. URL credentials/query tokens and redirects are refused. Configured bearer tokens are masked in public config and sent only to the configured endpoint; PhD Lab provider keys are not forwarded.

This adapter returns the text after tool completion rather than claiming token streaming. Incompatible tools, transport/authentication failures and error/empty replies fail explicitly; no paid cloud fallback is attempted. Stop cancels the local request and closes its transport, while actual remote compute termination depends on the server. Direct stdio transport, arbitrary tool-argument mapping and server-side model discovery are outside this adapter’s current contract.

## Independent research engines

Use the **OpenScience · Feynman** sidebar entry with a selected Topic. Create/link a workspace, then open the engine or the same folder in VS Code. On Windows, engine startup runs in its own visible PowerShell terminal with a safely encoded argv and the registered workspace cwd. OpenScience’s native `web` command opens its browser workspace; Feynman starts its interactive CLI. The terminal remains available for native sign-in or startup errors. Repeated open requests reuse the tracked window.

No research prompt is submitted by opening a window. Native tools use their own authentication/configuration, and PhD Lab does not inject its model keys. Sync observes persisted files only. Launch acceptance is a local-process receipt, not proof of successful inference, authentication, quota or full session capture.
