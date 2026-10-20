# Context Gateway v3.4 — báo cáo cuối

| Hạng mục DoD (spec §26) | Trạng thái | Ở đâu |
|---|---|---|
| Provider-agnostic backend | ✅ | `gateway/connectors.py` contract + 4 connector |
| Context Gateway | ✅ | `gateway/service.py`, `gateway/context.py` |
| Canonical Research Context | ✅ schema 1.0 | `canonical_packet()`, `POST /api/gateway/packet` |
| MCP Gateway | ✅ | `mcp_server.py` + `gateway/mcp_tools.py` |
| Provider adapters | ✅ | Codex, Claude Code, Antigravity (MCP + agy), Gemini CLI |
| Streaming normalisation | ✅ | `gateway/events.py`, SSE |
| ChatGPT official path / no cookie / no private API | ✅ | Codex CLI; web connector ghi tài liệu, không làm vòng |
| Streaming / disconnect / error handling / API fallback off | ✅ | test providers + gateway |
| Antigravity MCP, research tools, context/evidence/experiment retrieval, decision write-back, permission boundaries | ✅ | test mcp + acceptance |
| Shared memory across providers | ✅ | không có store theo provider; test `same_context` + acceptance bước 10, 15 |
| Research-state-aware, evidence-aware, token budget, role-aware, provenance | ✅ | Context Memory v3.3 |
| Sensitivity filtering | ✅ | `gateway/policy.py`, áp dụng gateway + MCP + agent_block |
| Secrets protected | ⚠️ một phần | gateway không lưu credential; secret cũ vẫn plaintext (`v3.4-security-audit.md`) |
| Local-only default, MCP authorization, audit logs | ✅ | Host + Origin + token + audit |
| No cookie extraction / quota bypass / unofficial endpoints | ✅ | xem `provider-security.md` |
| Baseline + post benchmark, MCP latency, retrieval, streaming start-up, cache | ✅ (start-up = overhead PhD-Lab) | `multi-provider-v3.4-benchmark.md` |
| Review before external AI | ✅ backend · ❌ UI | `review_before_external`, `review: true` |

Acceptance §25: `tests/integration/test_acceptance.py` chạy cả 15 bước (ChatGPT/Codex hỏi → context có hypothesis,
experiment, failure, baseline, ràng buộc phần cứng, evidence → chỉ prompt đã biên dịch được gửi → stream → Antigravity qua
MCP thấy cùng `context_version` và gọi `get_evidence/get_failures/get_experiment` → researcher ghi decision kèm provider,
session, evidence → sau "restart" Claude Code (client MCP khác) khôi phục decision trong state và context).
