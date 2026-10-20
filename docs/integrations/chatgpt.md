# ChatGPT

## Đường tích hợp được hỗ trợ

**ChatGPT plan qua OpenAI Codex CLI** — connector `codex`. Đây là client chính thức của OpenAI, đăng nhập bằng tài khoản
ChatGPT trong trình duyệt; PhD-Lab chỉ khởi chạy CLI.

| | |
|---|---|
| Yêu cầu tài khoản | gói ChatGPT có Codex (Plus/Pro/Business/Edu/Enterprise — theo chính sách hiện hành của OpenAI) |
| Cài đặt | `npm install -g @openai/codex` (Node 18+) |
| Xác thực | `codex login` → "Sign in with ChatGPT" (trình duyệt). `POST /api/gateway/providers/codex/connect {"launch": true}` mở terminal chạy đúng lệnh này |
| Lưu trữ cục bộ | credential do Codex tự giữ (`~/.codex/`); PhD-Lab không đọc, không copy |
| Ngắt kết nối | `POST …/codex/disconnect` (PhD-Lab ngừng dùng); đăng xuất hẳn: `codex logout` |
| Quyền | `codex exec --json --sandbox read-only` trong thư mục code của project |
| Billing | chỉ subscription: API key bị xoá khỏi môi trường; nếu Codex đang đăng nhập bằng API key → bị từ chối trừ khi bật `gateway.codex_api_fallback` |
| Streaming | JSONL `codex exec --json` → InternalEvent → SSE |
| Phiên | `resume_session` = thread id (`codex exec resume`) |

## Data flow

Câu hỏi → Context Gateway biên dịch research context (state, evidence, failure… đã lọc sensitivity, redact credential,
bỏ code block nếu `block_source_code`) → **chỉ prompt đã biên dịch** đi qua stdin của Codex → OpenAI. Câu trả lời lưu ở
`<project>/gateway/requests/<id>.json`, **không** thành memory cho tới khi researcher đề xuất (`propose`) và duyệt.

Codex cũng có thể tự gọi research tools qua MCP (stdio bridge):
```toml
# ~/.codex/config.toml   (GET /api/gateway/providers/codex/mcp sinh đúng snippet này)
[mcp_servers.phd-research-lab]
command = "python"
args = ["D:/git-repo/PhD-Research-Lab/mcp_stdio_bridge.py"]
env = { PHDLAB_MCP_URL = "http://127.0.0.1:8765/mcp" }
```

## Không hỗ trợ (có chủ đích)

- **ChatGPT web/desktop custom connector (developer mode)**: OpenAI gọi MCP server từ máy chủ của họ, nên cần endpoint
  HTTPS **công khai**. PhD-Lab chỉ bind `127.0.0.1` và không tự mở tunnel. Nếu bạn tự expose `/mcp` (ngrok/Cloudflare
  Tunnel) thì **bắt buộc** đặt `mcp.token`, tắt `mcp.expose_sandbox`, và hiểu rằng mọi nội dung tool trả về đi qua OpenAI.
  Lưu ý thêm: chế độ này có thể yêu cầu Developer Mode và điều kiện gói tài khoản mà OpenAI thay đổi theo thời gian.
- Không dùng endpoint riêng của chatgpt.com, cookie phiên, giả user-agent hay vượt quota — xem `docs/security/provider-security.md`.
- Quota/giới hạn sử dụng: không có API chính thức để đọc → PhD-Lab không hiển thị; `RATE_LIMITED` chỉ được suy ra từ lỗi.
