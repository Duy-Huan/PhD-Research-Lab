# Multi-provider audit — trước v3.4

> Phase 1 của `PhD-Research-Lab-v3.4-Multi-Provider-ChatGPT-Antigravity-Upgrade-Prompt.md`, thực hiện trên mã đã có
> v3.3 Context Memory. Ngày: 2026-10-20.

| Hạng mục | Hiện trạng trước v3.4 |
|---|---|
| Provider adapters | `llm.py` + `llm_router.py`: **API key** (Anthropic native, 14 OpenAI-compatible, 9Router/OmniRoute local gateway) và local (LM Studio, Ollama). Không có đường subscription nào ngoài Codex. |
| Claude Code | Không tích hợp như provider. Chỉ có thể là **MCP client** của `/mcp` (3 tool sandbox) qua `mcp_stdio_bridge.py`. |
| ChatGPT | Codex CLI (`integrations/agents.py`, `codex exec --json`) dùng làm **coding agent** (sandbox read-only/workspace-write, git-derived changed files). Auth do `codex login` (ChatGPT plan) — app không lưu credential. Không dùng cho hỏi đáp nghiên cứu, không có context nghiên cứu, không scrub API key. |
| Antigravity / Gemini | Không có. |
| MCP | `mcp_server.py`: JSON-RPC 2.0 qua `POST /mcp`, protocol `2025-06-18`, 3 tool sandbox (chạy code, đọc/ghi file workspace, metric). **Không có**: tool nghiên cứu, token, kiểm Origin, rate limit, audit, validate schema phía server, session id. Bảo vệ duy nhất: middleware Host = localhost. |
| Context cho provider | `agent_block()` gắn compiled context vào system prompt của agent nội bộ. Không có gói context độc lập provider, không lọc sensitivity, không review trước khi gửi. |
| Streaming | SSE của `/api/chat/stream` gắn trực tiếp với format của `llm.py`; Codex run lưu event Codex nguyên dạng. Không có event chuẩn hoá. |
| Secrets | API key provider + token GitHub + secret ClearML **lưu plaintext** trong `config.json` (mask khi trả UI). |
| Binding | `start.py` bind `127.0.0.1:8765`; middleware chặn Host lạ (421). |
| Test | 90 (v3.2) → 129 sau v3.3; không test nào cho provider/MCP security. |
| Baseline hiệu năng | MCP: chưa đo; context compile (v3.3): 41–84 ms. |

## Kết luận audit

1. Không cần microservice hay process mới: FastAPI app hiện có đủ chỗ cho Context Gateway + MCP research tools.
2. Đường chính thức khả dụng cho từng nhà cung cấp (đã kiểm tra tài liệu chính thức, 2026-10):
   - **ChatGPT**: Codex CLI với "Sign in with ChatGPT" (headless `codex exec --json`). Connector MCP của ChatGPT web/desktop
     (developer mode) chỉ gọi được **endpoint HTTPS công khai** → không tương thích với nguyên tắc local-only mặc định.
   - **Claude**: Claude Code CLI `claude -p --output-format stream-json` dùng đăng nhập subscription; **lưu ý**: nếu
     `ANTHROPIC_API_KEY` có trong môi trường thì dùng API billing, và `--bare` bỏ qua đăng nhập subscription.
   - **Google**: Antigravity IDE/app là MCP client (`~/.gemini/config/mcp_config.json`, khoá `serverUrl`); Antigravity CLI
     `agy -p --output-format stream-json` (đăng nhập Google, credential cache). Gemini CLI `gemini -p --output-format
     stream-json` vẫn có nhưng được thông báo thay bằng Antigravity CLI cho một số loại tài khoản.
3. MCP hiện tại là bề mặt tấn công lớn nhất (chạy code + đọc/ghi file, không xác thực ngoài Host) → phải có token tuỳ chọn,
   Origin check, rate limit, audit và công tắc cho nhóm tool sandbox trước khi mời thêm client.
4. Không được tạo bộ nhớ riêng theo provider: Context Memory v3.3 là nguồn sự thật duy nhất.
