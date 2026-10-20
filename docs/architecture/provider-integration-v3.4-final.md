# PhD Research Lab v3.4 — Multi-provider integration: báo cáo cuối

> Spec: `PhD-Research-Lab-v3.4-Multi-Provider-ChatGPT-Antigravity-Upgrade-Prompt.md`. Audit: `multi-provider-v3.4-audit.md`.

## 1. Kiến trúc trước / sau

Trước: provider = API key (`llm.py`) + Codex coding agent; MCP = 3 tool sandbox không xác thực. Sau: Context Gateway
(`backend/gateway/`) với contract `ProviderConnector` cho 4 đường **first-party**, event chuẩn hoá, MCP research tools có
bảo mật, mọi provider dùng chung Context Memory v3.3. `llm.py` (agent nội bộ dùng API key) **giữ nguyên** — không có gì
bị gỡ bỏ.

## 2. ChatGPT

Codex CLI đăng nhập ChatGPT (`codex exec --json --sandbox read-only`), health thật trên máy: `CONNECTED (signed in with
ChatGPT)`. Đăng nhập API key bị từ chối khi không bật fallback. ChatGPT web/desktop connector: **không hỗ trợ mặc định**
vì OpenAI yêu cầu endpoint HTTPS công khai (`docs/integrations/chatgpt.md`).

## 3. Antigravity

MCP client (đăng ký `serverUrl` vào `~/.gemini/config/mcp_config.json`, có nút đăng ký merge + backup) + Antigravity CLI
`agy -p` stream-json. Gemini CLI là connector phụ.

## 4. Claude Code

Connector `claude -p --output-format stream-json --verbose --include-partial-messages`, PhD-Lab MCP qua `--mcp-config`
tạm + `--allowedTools` chỉ 9 tool đọc. Không `--bare`, `ANTHROPIC_API_KEY` bị xoá → subscription. Đăng ký MCP thường trực:
`claude mcp add --transport http phd-research-lab http://127.0.0.1:8765/mcp`. Phiên Claude Code hiện tại của bạn
(chính công cụ đang viết mã này) dùng được ngay các research tools sau khi đăng ký.

## 5. MCP

12 tool `research_*` (9 đọc, 3 ghi → candidate) + 3 tool sandbox cũ; schema strict, validate phía server,
`structuredContent` + provenance, Mcp-Session-Id → clientInfo cho provenance/audit. Xem `mcp-research-tools.md`.

## 6. Context Gateway

Canonical packet schema 1.0, prompt giống hệt cho mọi provider, review-before-external, session đa provider, compare,
write-back qua candidate. Xem `context-gateway-v3.4.md`.

## 7. Context Memory

Không có memory theo provider. Bổ sung cho v3.4: sensitivity per node, `[withheld]` cho id bị chặn, `agent_block` áp
policy khi engine không local, origin provider/session trên decision/candidate.

## 8. Security model

`docs/security/provider-security.md`, audit `docs/security/v3.4-security-audit.md` (16 kiểm tra đạt, 5 phát hiện mở).

## 9. Streaming

Vendor JSONL → `events.py` (4 normaliser) → 8 loại InternalEvent → SSE `/api/gateway/requests/{id}/stream`. UI không phụ
thuộc format vendor.

## 10. Benchmark

MCP tool 25–72 ms (target < 200), prepare 59–110 ms, overhead start-up 11 ms (`docs/benchmarks/multi-provider-v3.4-benchmark.md`).

## 11. Test

36 test mới cho v3.4: `tests/providers/` (contract, cost guard, lỗi, cancel, đăng ký MCP), `tests/streaming/`,
`tests/mcp/`, `tests/context_gateway/`, `tests/security/`, `tests/integration/test_acceptance.py` (toàn bộ 15 bước §25,
qua HTTP + MCP, CLI vendor thay bằng fake CLI giữ nguyên định dạng JSONL chính thức). Toàn suite: 165 test, OK, 4 skip.

## 12. Giới hạn theo provider

| Provider | Giới hạn |
|---|---|
| ChatGPT | chỉ qua Codex CLI; không đọc được quota; web connector cần endpoint công khai |
| Claude Code | không có lệnh auth-status ổn định → `UNKNOWN` tới request đầu; `--include-partial-messages` cần bản CLI mới |
| Antigravity | `--output-format` chỉ có ở bản CLI mới; headless không có approval (tool cần duyệt bị soft-deny); MCP tools mặc định "Ask" trong IDE |
| Gemini CLI | đang được thay bằng Antigravity CLI cho một số tài khoản; schema stream-json chỉ có tên event chính thức, field được parse khoan dung |
| Tất cả | chưa chạy thử với CLI thật ngoài health probe của Codex (cần đồng ý gửi dữ liệu ra ngoài) |

## 13. Quyết định nhạy cảm về chính sách

- Chọn Codex CLI thay vì bất kỳ cách nào "dùng ChatGPT web như API".
- Không tự mở tunnel cho ChatGPT web; ghi tài liệu thay vì làm vòng.
- Xoá API key của **mọi** vendor khỏi tiến trình con (agent có thể dùng key khác qua shell).
- Từ chối Codex đăng nhập API key trừ khi researcher bật fallback.
- MCP `record_*` chỉ tạo candidate; evidence AI không tự validate.
- Không bao giờ dùng `--dangerously-skip-permissions` / `--bare` / sandbox ghi khi gateway gọi provider.

## 14. Việc còn lại

UI (bảng provider, review-before-external, hàng đợi candidate, compare view); chạy live với CLI thật; token MCP theo
client; keyring cho secret cũ; cân nhắc đổi mặc định `expose_sandbox`. Phát hành dưới phiên bản **4.0.0**.
