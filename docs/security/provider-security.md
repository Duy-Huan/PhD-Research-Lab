# Provider security model (v3.4)

## Chính sách không thương lượng (spec §0) — cách thực thi

| Cấm | Thực thi trong mã |
|---|---|
| Trích cookie/session trình duyệt | không có mã nào đọc profile trình duyệt hay token store của vendor; connector chỉ `Popen` CLI chính thức |
| Endpoint riêng / không tài liệu | không có HTTP client nào tới chatgpt.com / claude.ai / gemini web; chỉ CLI của vendor nói chuyện với vendor |
| Scrape DOM | không có |
| Giả client / user-agent | không có |
| Vượt quota, xoay tài khoản/IP | không có; `RATE_LIMITED` chỉ hiển thị trạng thái |
| Fallback tự động tạo billing | `*_api_fallback = False` mặc định → xoá biến API key của mọi vendor khỏi tiến trình con; không fallback provider tự động (`alternatives` cho researcher chọn) |
| Lưu credential plaintext (mới) | gateway không lưu credential nào; token MCP (do bạn tự đặt) mask trong UI |

## Phân loại dữ liệu

`PUBLIC` (paper, concept) · `INTERNAL` (mặc định cho record nghiên cứu) · `SENSITIVE` · `RESTRICTED`, đặt theo node:
`PUT /api/memory/sensitivity {"id": "EXP-004", "level": "SENSITIVE"}`. Chính sách (`config.gateway`):
`allow_internal` (true), `allow_sensitive` (false); RESTRICTED không bao giờ ra ngoài. Áp dụng **trước** mọi request
provider, cho mọi kết quả MCP, và cho `agent_block` khi engine của agent không phải local (LM Studio/Ollama). Id của bản
ghi bị chặn được thay bằng `[withheld]` cả khi một bản ghi khác nhắc tới nó. `block_source_code` (true) bỏ mọi code block
khỏi text gửi đi. *Review before external AI* (`review_before_external` hoặc `review: true`): request dừng ở `review`,
hiển thị `includes` / `included_ids` / `blocked` / `sanitize`; researcher gửi (có thể sửa prompt) hoặc huỷ.

## Bề mặt mạng

- Bind `127.0.0.1` (start.py); middleware Host: chỉ localhost/127.0.0.1/::1 (+ `PHDLAB_ALLOWED_HOSTS`) → 421.
- `/mcp`: Origin của trình duyệt phải là localhost (chống DNS rebinding theo khuyến nghị MCP); token tuỳ chọn; rate limit;
  JSON-RPC sai dạng → 400; tool lỗi → `isError` với thông điệp đã redact.

## Log

Telemetry, audit gateway, audit MCP: chỉ id, số đếm, latency, trạng thái. `telemetry._clean` từ chối chuỗi tự do;
`redact()` che `sk-…`, `sk-ant-…`, `ghp_…`, `github_pat_…`, `AKIA…`, `AIza…`, `xox?-…`, `Bearer …`, `api_key=…`,
`password=…`, JWT. Prompt và câu trả lời chỉ nằm trong `<project>/gateway/requests/<id>.json` trên máy của bạn.

## Tiến trình con

Danh sách argument (không shell), prompt qua stdin, cwd = thư mục code của project, `CREATE_NO_WINDOW`, huỷ bằng
`taskkill /T`. File cấu hình MCP tạm cho Claude Code được xoá khi request kết thúc. Path traversal: `ide_fs` resolve trong
`code/` (test `../../config.json` bị từ chối); id ở mọi API/MCP có regex.

## Rủi ro còn lại

- API key provider *cũ* (v1–v3.2), token GitHub, secret ClearML vẫn plaintext trong `config.json` (mask ở UI). Khuyến
  nghị v3.5: Windows Credential Manager / keyring.
- `mcp.expose_sandbox = true` mặc định (tương thích) cho phép MCP client chạy code — tắt khi chỉ cần research tools.
- Không có xác thực theo từng client MCP (một token chung).
- Rate limit theo IP (mọi client local cùng IP 127.0.0.1).
