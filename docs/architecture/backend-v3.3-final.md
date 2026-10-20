# PhD Research Lab v3.3 — Backend & Context Memory: báo cáo cuối

> Spec: `PhD-Research-Lab-v3.3-Backend-Context-Memory-Upgrade-Prompt.md`. Audit: `backend-v3.3-audit.md`.
> Thiết kế: `context-memory-v3.3.md`. Số đo: `docs/benchmarks/backend-v3.3-benchmark.md`,
> `docs/benchmarks/context-memory-v3.3-evaluation.md`.

## 1. Những gì đã thay đổi

| Module | Mới / sửa | Nội dung |
|---|---|---|
| `memory/state.py` | mới | Research State có cấu trúc (objective, active hypothesis, current experiment, baseline, constraints/hardware, decisions, failures, best results, datasets/models, focus, `context_version`) |
| `memory/engine.py` | mới | RetrievalContext + 7 nguồn xếp hạng + weighted RRF + điểm giải thích được + `explain()` |
| `memory/policy.py` | mới | 7 role policy, `Budget` tường minh, ánh xạ tool → role |
| `memory/compiler.py` | viết lại (giữ API) | section RESEARCH STATE + EVIDENCE & CLAIMS, budget theo role, dedup, low-value theo tier, nén LOD, trace + `trace_text()` (CONTEXT TRACE), sensitivity |
| `memory/evidence.py` | mới | Claim/Evidence với provenance, integrity (AI không tự validate) |
| `memory/trace.py` | mới | provenance chain + `decisions_based_on()` |
| `memory/lifecycle.py` | mới | candidate → phân loại → dedup → approve/reject |
| `memory/cache.py` | mới | fingerprint + 3 cache có invalidation |
| `telemetry.py` | mới | span có cấu trúc, không nội dung, redaction |
| `memory/research.py` | sửa | failure memory có cấu trúc, `update_failure` |
| `memory/__init__.py` | sửa | decision có evidence/origin/provider/session/supersedes; consolidation giữ provenance + archive; RLock; quarantine |
| `memory/store.py` | sửa | reader lấy lock, retry Windows, quarantine file hỏng, generation counter |
| `memory/embeddings.py`, `retrieval.py` | sửa | sparse vector, stem, BM25 nhận tokenizer (API cũ giữ nguyên) |
| `memory/lod.py`, `knowledge.py` | sửa | tier `evidence`, metadata, sensitivity, render không lặp, env; bỏ giới hạn 300 paper |
| `api_v33.py` | mới | `/api/memory/state|focus|policies|v3/retrieve|v3/compile|explain|sensitivity|candidates`, `/api/evidence*`, `/api/research/decisions`, `/api/research/failures/{id}`, `/api/provenance/chain/{id}`, `/api/telemetry` |
| `tests/` | +75 test | `test_memory_v33.py`, `memory_eval/` (golden + regression gate) |

## 2. Vì sao

Mỗi thay đổi xuất phát từ một số đo hoặc một bug có test tái hiện (audit §8): latency tuyến tính 600 ms do cosine dense;
recall@5 0.47 vì retrieval không biết research state, không biết người hỏi cần *loại* bản ghi nào; 4 bug dữ liệu
(mất paper, race Windows, ghi đè file hỏng, consolidation mất provenance). Không thêm hạ tầng: không DB, không vector
store, không service — profile cho thấy vấn đề là thuật toán và cache.

## 3. Kiến trúc trước / sau

```
v3.2  query ─► collect() ─► BM25 ‖ dense cosine ‖ graph ─► RRF ─► heuristic ─► 3 section cố định ─► LLM
v3.3  query + role ─► Research State ─► RetrievalContext ─► Index(cache) ─► 7 nguồn ─► weighted RRF ─► explainable score
      ─► role policy + Budget ─► 5 section (state đầu tiên) ─► dedup/low-value/LOD/drop + trace ─► sensitivity ─► LLM
      LLM/provider output ─► candidate ─► review ─► research / evidence memory (origin + provenance)
```

## 4. Context Memory trước / sau

| | v3.2 | v3.3 |
|---|---|---|
| Đơn vị đầu vào | chuỗi query | RetrievalContext (query + state + role + filters + temporal + sensitivity) |
| Research state | rải rác (tier3, research.json) | một object có cấu trúc, phiên bản hoá (`context_version`) |
| Failure | text + reason | 10 trường có cấu trúc, ưu tiên khi planning |
| Evidence | không có | Claim/Evidence + provenance + integrity |
| Ghi từ AI | không có đường ghi | chỉ qua candidate có review |
| Giải thích | không | mọi hit có components + ranks + reasons; `explain()` cả trường hợp không chọn |

## 5. Retrieval trước / sau

Thêm metadata filter, temporal mode, intent, state ranking, graph seed từ state, stemming, pool đảm bảo top mỗi nguồn,
gate relevance cho prior. Dev recall@5 0.47 → 0.94, held-out-2 sạch 0.83 → 1.00, MRR 0.64 → 0.89 (N = 1 500).

## 6. Context Compiler trước / sau

Static 35/40/25 → 7 policy theo role với state floor; ngân sách tường minh; thứ tự xử lý vượt budget đúng spec §7 (bỏ
trùng → nén → giữ state/evidence/decision/failure → không bao giờ cắt mù); trace đầy đủ. Context nhỏ hơn 55–58 % mà chứa
nhiều record đúng hơn (efficiency ×2.6–2.9).

## 7. Evidence / provenance

Chuỗi Paper → Claim → Hypothesis → Experiment → Code (git) → Environment → Dataset → Run → Metrics → Artifact → Decision
truy vết được bằng `trace.chain()`; trả lời 5 câu hỏi của spec §10 (có test `test_provenance_chain_answers`).

## 8. Hiệu năng trước / sau (N = 1 500)

retrieve 614 → 59 ms (query mới) / 15 ms (lặp); compile 635 → 84 ms; peak RAM compile 70 → 27 MB; ghi 32 → 33 ms.
Mọi target spec §15 đạt.

## 9. Kết quả test

165 test (v3.2: 90), **165 OK, 4 skip** (live opt-in ClearML/Codex/LM Studio như trước). Bao phủ yêu cầu §22: CRUD,
dedup, promotion (candidate), consolidation, retrieval, RRF, rerank (explainable + HTTP cross-encoder giữ nguyên),
budgeting, role policy, provenance, failure memory, cache invalidation (ghi trong process, ghi ngoài process, ghi không
liên quan), concurrent writes (6 thread × 30 ghi), migration (file v3.2), corruption, crash giữa write/replace.

## 10. Đánh giá memory

Xem `context-memory-v3.3-evaluation.md`. Điểm trung thực nhất (held-out-2 sạch, N = 1 500): recall@5 1.00, MRR 0.89,
ids_in_context 1.00, fact_fidelity 0.83 (1.00 sau khi sửa lỗi render environment mà chính bộ này phát hiện).

## 11. Giới hạn đã biết

- Token ước lượng bằng chars/4; budget đúng tương đối, không chính xác theo tokenizer của từng model.
- Lock chỉ trong một tiến trình (app single-process). Hai instance trên cùng project không được bảo vệ.
- Embedding mặc định là hashing (lexical); semantic thật cần Ollama `nomic-embed-text`; bộ golden chưa chạy với nó.
- Stemmer tiếng Anh tối giản; truy vấn tiếng Việt chỉ khớp lexical/vector.
- Đánh giá trên corpus tổng hợp; chưa có đánh giá quyết định end-to-end với LLM thật.
- Không có UI cho candidate review, focus, sensitivity, CONTEXT TRACE — chỉ API (spec chỉ định milestone backend).
- `context_graph.save_overlay` và `chat_store` chưa dùng `replace_retry`.

## 12. So với các nguyên tắc Anthropic đã công bố

Chỉ so với tài liệu công khai: *Effective context engineering for AI agents* (Anthropic Engineering, 2025), *How we built
our multi-agent research system* (2025), *Building effective agents* (2024), tài liệu Claude Code / Agent SDK, memory tool
và context editing của Claude API. **Không biết** kiến trúc nội bộ của bất kỳ sản phẩm Anthropic nào; chúng tôi không tìm
thấy tài liệu kỹ thuật công khai nào mô tả một hệ thống tên "Claude Science", nên không so sánh với nó.

| Nguyên tắc công khai | PhD-Lab v3.3 | Tự đánh giá |
|---|---|---|
| Context là tài nguyên hữu hạn — tập token nhỏ nhất có tín hiệu cao | budget tường minh, dedup, low-value, LOD, efficiency ×2.7 | 8.5 |
| Compaction cho tác vụ dài | compressor watermark + memo JSON + page-store raw (v3.2) + consolidation giữ provenance | 8 |
| Structured note-taking / persistent memory ngoài context | research state, research/evidence memory, decision, failure — sống qua reset, restart, đổi provider | 9 |
| Just-in-time retrieval qua tool | MCP research tools (v3.4) + `explain`/`trace` | 8.5 |
| Multi-agent / lead-agent orchestration | **không nâng cấp trong milestone này** (pipeline Author→Reviewer→Editor có từ trước) | 5 |
| Artifact-first, nguồn và trích dẫn | provenance chain, seal artifact (v3.2), record id bắt buộc trong context | 8.5 |
| Evaluator–optimizer / actor–critic | live critic có từ v3.2; evidence AI không tự validate; chưa có critic kiểm chứng claim tự động | 6.5 |
| Đánh giá có hệ thống | golden + 2 held-out + regression gate | 7.5 |

**Tổng thể ~7.5–8/10 theo thang tự đánh giá này — chưa đạt mục tiêu 9/10.** Mạnh hơn ở state/provenance/failure
memory có cấu trúc và khả năng giải thích; yếu hơn ở orchestration đa agent, kiểm chứng claim tự động và đánh giá với
model thật.

## 13. Lộ trình đề xuất v3.4 / v4

1. (v3.4, đã làm — xem `provider-integration-v3.4-final.md`) Context Gateway + MCP research tools đa provider.
2. UI: hàng đợi candidate, chọn focus, đặt sensitivity, xem CONTEXT TRACE, review-before-external.
3. Critic kiểm chứng claim: so evidence ↔ claim, đánh dấu *contested* tự động (vẫn cần researcher xác nhận).
4. Lead-agent orchestration dùng research state làm "plan memory" chung cho subagent.
5. Chạy lại đánh giá với Ollama embedding + bge-reranker; thêm nDCG; đánh giá quyết định với LLM-as-judge + chấm tay.
6. Tokenizer thật (tiktoken/anthropic count_tokens khi có) cho budget; file lock liên tiến trình.
