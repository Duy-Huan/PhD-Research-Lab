# MCP research tools (v3.4)

Endpoint: `POST http://127.0.0.1:8765/mcp` (Streamable HTTP, JSON response, protocol `2025-06-18`). Client chỉ hỗ trợ
stdio: `python mcp_stdio_bridge.py` (env `PHDLAB_MCP_URL`, `PHDLAB_MCP_TOKEN`). `initialize` trả `Mcp-Session-Id`; gửi
lại header này để candidate và audit ghi đúng client (`clientInfo.name`) và phiên.

Tên tool dùng `_` (nhiều client chỉ chấp nhận `^[A-Za-z0-9_-]{1,64}$`); tên có dấu chấm của spec
(`research.get_current_state`) được chấp nhận làm alias trong `tools/call`.

| Tool | Nhóm | Input (strict, `additionalProperties: false`) | Trả về |
|---|---|---|---|
| `research_get_current_state` | đọc | — | Research State (objective, active hypothesis, current experiment, baseline, constraints, decisions, failures, best results) |
| `research_search_memory` | đọc | `query`, `role?`, `k?≤50`, `filters?{types,dataset,model,source_type,evidence_status,since,until}` | hit + `why` (lý do được chọn) |
| `research_get_hypothesis` | đọc | `id` `HYPE-…` | hypothesis + experiments + claims + failures |
| `research_get_experiment` | đọc | `id` `EXP-…` | experiment + evidence + failures + provenance (commit, dataset, env, ClearML, run, artifacts) |
| `research_get_evidence` | đọc | `query` \| `claim_id` \| `experiment_id`, `status?` | evidence + claims |
| `research_get_decisions` | đọc | `include_superseded?` | decisions (+ evidence_ids, provider, session) |
| `research_get_failures` | đọc | `query?`, `model?`, `dataset?` | failure memory có cấu trúc |
| `research_get_context` | đọc | `query`, `role?`, `budget_tokens? 400–20000`, `trace?` | context đã biên dịch (+ CONTEXT TRACE) |
| `research_get_provenance` | đọc | `id` (HYPE/EXP/FAIL/CLM/EVID/D…) | chain nodes/edges + answers |
| `research_record_observation` | ghi → candidate | `text`, `experiment_id?`, `claim_id?`, `stance?`, `metric?{name,value,unit}` | candidate `CAND-…` |
| `research_record_decision` | ghi → candidate | `text`, `kind?`, `evidence_ids?`, `supersedes?` | candidate |
| `research_record_experiment_result` | ghi → candidate | `experiment_id`, `text`, `metric?`, `verdict?`, `conclusion?` | candidate |
| `sandbox_run_code`, `sandbox_manage_files`, `sandbox_get_metrics` | sandbox (v3.0) | như trước | — |

Mỗi kết quả: `structuredContent = {"result": …, "provenance": {source, project_id, context_version, record_ids,
sensitivity_allowed, retrieved_at}}` + cùng nội dung ở `content[0].text`.

## Quyền và cấu hình (`config.mcp`)

| Khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `enabled` | true | tắt toàn bộ `/mcp` (403) |
| `expose_research` | true | nhóm `research_*` |
| `allow_writes` | true | nhóm `record_*` (chỉ tạo candidate — không bao giờ là memory) |
| `expose_sandbox` | true (tương thích v3.0) | nhóm `sandbox_*` (chạy code, đọc/ghi file) — **khuyến nghị tắt** cho client chỉ cần hỏi đáp nghiên cứu |
| `token` | "" | khi đặt: mọi request cần `Authorization: Bearer <token>` (so sánh constant-time) |
| `rate_limit_per_min` | 240 | theo IP client, 429 khi vượt |
| `audit` | true | `<project>/gateway/mcp_audit.jsonl`: tool, client, session, ok/lỗi, **tên** khoá argument, latency — không có giá trị |

Không có tool SQL/đọc file tuỳ ý. Mọi kết quả đi qua sensitivity policy (bản ghi RESTRICTED/SENSITIVE không được trả về, kể
cả khi hỏi đúng id → "not found") và `sanitize()` (redact credential, bỏ code block nếu `gateway.block_source_code`).

## Đăng ký từng client

| Client | Cách đăng ký (`GET /api/gateway/providers/{id}/mcp` sinh sẵn) |
|---|---|
| Claude Code | `claude mcp add --transport http phd-research-lab http://127.0.0.1:8765/mcp` |
| Codex (ChatGPT plan) | `~/.codex/config.toml` `[mcp_servers.phd-research-lab]` với stdio bridge |
| Antigravity | `~/.gemini/config/mcp_config.json` `{"serverUrl": …}` — hoặc nút đăng ký (`POST …/antigravity/register-mcp`) |
| Gemini CLI | `~/.gemini/settings.json` `{"httpUrl": …}` |
| Claude Desktop | `claude_desktop_config.json` với stdio bridge (như v3.0) |
| ChatGPT web | không hỗ trợ mặc định — cần endpoint công khai (xem `chatgpt.md`) |
