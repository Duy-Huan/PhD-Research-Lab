# Context Gateway v3.4 — thiết kế

Một bộ não nghiên cứu cục bộ, nhiều "động cơ" AI thay thế được. Gateway không có memory riêng: mọi thứ đến từ Context
Memory v3.3 (`backend/memory/`) và quay lại đó qua candidate review.

```
Provider request (query, provider, role, session)
   │ gateway/service.prepare()
   ▼
Research State ─► state-aware hybrid retrieval ─► evidence selection ─► sensitivity policy ─► role-aware compiler
   │                                                                     (allowed classes)      (Budget = gateway.context_budget_tokens)
   ▼
sanitize (credential redaction, source-code rule) ─► PREAMBLE + compiled context + question  = prompt
   │
   ├── review_before_external → status "review" (includes / blocked / sanitize hiển thị) ─► send(edited_prompt?) | cancel
   ▼
connector.stream_message (CLI chính thức, stdin) ─► InternalEvent ─► request.events ─► SSE
   │
   ▼
answer lưu cục bộ ─► (researcher chọn) propose ─► lifecycle candidate ─► approve ─► memory (origin, provider, session, request)
```

## Canonical research context (`gateway/context.canonical_packet`, schema 1.0)

```json
{"schema_version": "1.0", "project_id": "…", "context_version": "…", "query": "…", "role": "experiment_designer",
 "objective": [], "active_hypothesis": {}, "active_experiment": {}, "constraints": [], "recent_decisions": [],
 "relevant_evidence": [], "known_failures": [], "relevant_records": [], "best_results": {}, "artifacts": [],
 "provenance": [{"id": "EXP-004", "commits": [], "datasets": [], "clearml_tasks": [], "runs": []}],
 "retrieval_trace": {"hits": [{"id", "score", "reasons"}], "diagnostics": {}}, "blocked": []}
```
`POST /api/gateway/packet`. Packet **không** được gửi nguyên vẹn; compiler chọn từ nó. Cùng query + role ⇒ cùng prompt cho
mọi provider (có test `test_same_context_for_every_provider`); `context_version` cho phép client MCP kiểm tra rằng nó
thấy cùng trạng thái.

## Request lifecycle

`review → ready → running → completed | failed | cancelled`. Trạng thái health trước khi gửi: `DISCONNECTED`,
`UNAVAILABLE`, `AUTH_EXPIRED`, `RATE_LIMITED`, `ERROR` → request `failed` ngay, kèm `alternatives` (provider khác đang
khả dụng) — **không** tự gửi sang provider khác, không sang API.

## Multi-provider session & comparison

`session_id` (`gs-…`) gom request của nhiều provider; `GET /api/gateway/sessions/{id}`. `POST /api/gateway/compare
{query, providers[]}` biên dịch **một lần**, tạo một request mỗi provider (chung `compare_id`), `same_context: true`.
Câu trả lời của provider này không bao giờ được chuyển cho provider khác.

## Write-back

`POST /api/gateway/requests/{id}/propose {kind, text, …}` → candidate với `origin.provider/session/request_id`,
phân loại `ai_suggestion` / `ai_claim` …; researcher duyệt ở `/api/memory/candidates/{id}/approve`. Quyết định do chính
researcher ghi (bước 13 của acceptance) dùng `POST /api/research/decisions` (origin human, có `provider`, `session`,
`evidence_ids`).

## API

| Method | Path |
|---|---|
| GET | `/api/gateway/providers` — health + capabilities mọi connector (+ ghi chú ChatGPT web) |
| POST | `/api/gateway/providers/{id}/connect` `{launch?}` · `/disconnect` `{revoke?}` |
| GET | `/api/gateway/providers/{id}/mcp` — snippet đăng ký MCP · POST `/api/gateway/providers/antigravity/register-mcp` |
| POST | `/api/gateway/packet` · `/api/gateway/requests` `{query, provider, role?, session_id?, review?, send?, budget_tokens?, resume_session?}` |
| POST | `/api/gateway/requests/{id}/send` `{prompt?}` · `/cancel` · `/propose` |
| GET | `/api/gateway/requests/{id}` · `/events?after=n` · `/stream` (SSE, kết thúc bằng `event: end`) |
| POST/GET | `/api/gateway/compare` · `/api/gateway/sessions/{id}` · `/api/gateway/audit` |

## Observability

Span `gateway.request` (request_id, provider, session_id, streaming, context_tokens, context_version, status, latency),
`memory.compile`, `memory.retrieve`, `mcp.tool`; audit gateway `<project>/gateway/audit.jsonl` (prepared / refused /
completed / cancel với id đã include, số bị chặn, ghi chú sanitize, first_token_s) — không có nội dung.
