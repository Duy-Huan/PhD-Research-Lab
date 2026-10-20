# Google Antigravity (và Gemini CLI)

## Hai đường chính thức

1. **Antigravity IDE / app làm MCP client** (đường chính của spec): Antigravity gọi `research_*` tools của PhD-Lab.
2. **Antigravity CLI `agy`** (headless) cho Context Gateway: PhD-Lab gửi context đã biên dịch và nhận stream.

### 1. Đăng ký MCP

`POST /api/gateway/providers/antigravity/register-mcp` (hành động của researcher) ghép vào
`~/.gemini/config/mcp_config.json` (giữ server khác, tạo bản `.bak`):
```json
{"mcpServers": {"phd-research-lab": {"serverUrl": "http://127.0.0.1:8765/mcp"}}}
```
Có `mcp.token` → thêm `"headers": {"Authorization": "Bearer <token>"}`. Theo project: `.agents/mcp_config.json`.
Antigravity chỉ chấp nhận `serverUrl` cho server HTTP (không phải `url`/`httpUrl`). Tool MCP chưa cấu hình mặc định ở
chế độ **Ask** trong Antigravity; có thể cho phép nhóm đọc bằng chính sách `mcp(phd-research-lab/research_get_*)`.

### 2. Antigravity CLI

| | |
|---|---|
| Xác thực | chạy `agy` tương tác một lần, đăng nhập Google; headless dùng credential cache, thiếu thì lỗi `authentication required` (→ `AUTH_EXPIRED`) |
| Lệnh | `agy -p --output-format stream-json --input-format stream-json --sandbox`, prompt gửi qua stdin dạng `{"event":"user","message":{"content":…}}` |
| Quyền | không có approval ở headless → tool cần duyệt bị soft-deny; `--dangerously-skip-permissions` **không bao giờ** được dùng |
| Billing | biến `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`… bị xoá (trừ khi bật `gateway.antigravity_api_fallback`) |
| Phiên | `--conversation <id>` |
| Lưu ý phiên bản | `--output-format` có từ các bản CLI mới; bản cũ báo lỗi flag → health `ERROR`, cập nhật `agy` |

Khi chỉ có đường MCP (chưa cài `agy`): health `CONNECTED` (MCP đã đăng ký), `send/stream = NOT_SUPPORTED` — Gateway trả
lỗi rõ ràng thay vì giả lập.

## Gemini CLI

Connector `gemini_cli` (`gemini -p "<instruction>" --output-format stream-json`, context qua stdin). Đăng nhập "Login with
Google". Google đã thông báo thay Gemini CLI bằng Antigravity CLI cho một số loại tài khoản — ưu tiên `antigravity`.
MCP cho Gemini CLI: `~/.gemini/settings.json` với `httpUrl` (snippet: `GET /api/gateway/providers/gemini_cli/mcp`).

## Data flow & giới hạn

Antigravity nhận **chỉ** những gì tool trả về (đã lọc sensitivity, redact) hoặc prompt đã biên dịch. Mọi `record_*` thành
candidate có `origin.provider = <clientInfo.name>` và Mcp-Session-Id. Không biến subscription Antigravity thành API chung,
không đọc token OAuth của Antigravity (`mcp_oauth_tokens.json`).
