# Provider architecture (v3.4)

```
                         Researcher (PhD-Lab UI / API)
                                   │
                         Context Gateway (backend/gateway/)
          ┌────────────────────────┼─────────────────────────┐
   service.py: prepare → review? → send → stream → answer    mcp_tools.py + mcp_server.py: POST /mcp
          │                                                    │
   connectors.py (ProviderConnector contract)                 MCP clients: Claude Code · Codex · Antigravity · Gemini CLI
   ├── CodexConnector        codex exec --json                (they call research_* tools themselves)
   ├── ClaudeCodeConnector   claude -p --output-format stream-json --verbose --include-partial-messages
   ├── AntigravityConnector  agy -p --output-format stream-json --input-format stream-json --sandbox  + MCP registration
   └── GeminiCliConnector    gemini -p … --output-format stream-json
          │
   events.py: vendor JSONL ─► InternalEvent ─► SSE /api/gateway/requests/{id}/stream
          │
   context.py: Research State + state-aware retrieval + role-aware compiler + sensitivity + sanitize (memory/ v3.3)
```

## Contract (`ProviderConnector`)

| Method | Ý nghĩa | Không hỗ trợ |
|---|---|---|
| `capabilities()` | `connect, disconnect, health, capabilities, send, stream, cancel, mcp_client` → `True` hoặc `"NOT_SUPPORTED"` | không bao giờ giả lập |
| `health()` | `CONNECTED · DISCONNECTED · AUTH_EXPIRED · RATE_LIMITED · UNAVAILABLE · ERROR · UNKNOWN` + `billing` + `path` | |
| `connect(launch)` | trả lệnh đăng nhập **chính thức** của vendor (tuỳ chọn mở terminal chạy lệnh đó) | app không bao giờ nhận password/token |
| `disconnect(revoke)` | PhD-Lab ngừng dùng provider; đăng xuất vendor làm trong app/CLI của vendor | |
| `start_session(context)` | phiên tạo ở message đầu; `resume_session` (Codex `exec resume`, Claude `--resume`, agy `--conversation`) | |
| `send_message` / `stream_message` | chạy CLI, prompt qua **stdin** (không giới hạn độ dài dòng lệnh Windows), parse JSONL | |
| `cancel(request_id)` | kill cây tiến trình (`taskkill /T` trên Windows) | |
| `mcp_registration(base_url)` | snippet/lệnh đăng ký PhD-Lab MCP cho client đó | |

Health không biết chắc sign-in (Claude/agy/Gemini không có lệnh status ổn định) → `UNKNOWN` cho tới request đầu; lỗi
xác thực / rate limit trong stream cập nhật health thành `AUTH_EXPIRED` / `RATE_LIMITED`. Codex có `codex login status`.

## Cost guard

`gateway.<provider>_api_fallback` (mặc định **False**): tiến trình CLI chạy với **mọi** biến API key của mọi vendor AI bị
xoá (`OPENAI_API_KEY, CODEX_API_KEY, ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY,
GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_APPLICATION_CREDENTIALS, …`) → chỉ còn đường subscription. Codex đăng nhập bằng API
key bị từ chối (`ERROR`, có hướng dẫn). Claude Code không bao giờ chạy `--bare`. `health()["billing"]` hiển thị đường đang
dùng. Không có fallback tự động sang provider khác hay sang API: request thất bại trả `alternatives` để researcher chọn.

## Permission mặc định khi gateway gọi provider

| Provider | Quyền |
|---|---|
| Codex | `--sandbox read-only`, `-C` = thư mục code của project |
| Claude Code | `--allowedTools` chỉ gồm 9 tool **đọc** `mcp__phd-research-lab__research_*`; mọi thứ cần approval khác bị từ chối (chế độ `-p`) |
| Antigravity CLI | `--sandbox`; headless không có approval → lệnh shell bị soft-deny |
| Gemini CLI | mặc định của CLI ở headless (tool cần xác nhận không chạy) |

Coding agent Codex hiện có (`integrations/agents.py`, workspace-write theo yêu cầu) giữ nguyên, tách biệt với gateway.

## Định dạng stream đã xác minh (tài liệu chính thức, 2026-10)

- Codex: `thread.started`, `item.started/completed` (`agent_message`, `command_execution`), `turn.completed`, `turn.failed`, `error`.
- Claude Code: `system/init`, `stream_event` (`text_delta`), `assistant`/`user` (`tool_use`/`tool_result`), `result`, `system/api_retry`.
- Antigravity CLI: `{"event":"init"}`, `step_update` (`text_delta`, `step_type: tool`, `tool_info`), `result` (`status`, `response`, `usage`).
- Gemini CLI: `init`, `message`, `tool_use`, `tool_result`, `error`, `result`.
Event không biết → `status` với `raw_type`, không đoán.
