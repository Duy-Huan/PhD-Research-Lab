# Context Memory v3.3 — thiết kế

> Mục tiêu (spec v3.3 §28): agent khôi phục **đúng** research state, evidence, decision, failure và artifact **đúng lúc
> cần**, với lượng context tối thiểu. Mọi thành phần dưới đây local-first, chỉ dùng stdlib, xác định (deterministic).

## 1. Vòng xử lý

```
query + role (+ session, filters)
   │
   ▼
Research State (memory/state.py) ── objective · active hypothesis · current experiment · baseline · constraints/hardware
   │                                 · recent decisions · known failures · best results · datasets/models · focus
   ▼
RetrievalContext (memory/engine.py) ── query + state_query + role + filters + temporal mode + sensitivity
   │
   ▼
Index (cache theo fingerprint) ──► 7 ranking: keyword(BM25 stemmed) · vector · state · graph · metadata · intent · temporal
   │                                  └─ weighted RRF ─► pool = top fused ∪ top-6 mỗi nguồn
   ▼
Explainable scoring (policy.py theo role) ─► hit {score, components, ranks, reasons}
   │
   ▼
Context Compiler (compiler.py) ─► budget tường minh → section → dedup → low-value (theo tier) → nén LOD → drop + trace
   │
   ▼
[CONTEXT SYSTEM INJECTION] … ↳ Focus        (+ trace / CONTEXT TRACE khi debug)
```

## 2. Research State (`memory/state.py`)

Tính lại từ store (không copy → không thể lệch), cache theo fingerprint + focus. Quy tắc:
- *Active hypothesis* = focus của researcher (`PUT /api/memory/focus`) rồi các hypothesis `testing`; chỉ khi không có
  hypothesis nào đang test mới dùng `proposed`.
- *Current experiment* = focus → experiment mới nhất của active hypothesis → experiment mới nhất (cùng giây: id sau).
- *Baseline* = experiment mới nhất có chữ "baseline" trong title/conclusion.
- *Known failures* = failure của active hypothesis trước, bổ sung tối đa 3 failure mới nhất khác.
- *Best results* = metric của evidence `validated` (ưu tiên) + best metric của sandbox.
- `context_version` = hash fingerprint → mọi provider/MCP client biết chúng đang nhìn cùng một trạng thái.

## 3. Retrieval state-aware (`memory/engine.py`)

| Nguồn | Nội dung | Trọng số RRF |
|---|---|---|
| keyword | BM25 trên token đã stem nhẹ (refuted≈refutes; ID/SHA không stem) | 1.0 |
| vector | hashing sparse (mặc định) hoặc Ollama dense, unit vector | 1.0 |
| metadata | node có dataset/model khớp từ trong câu hỏi (vd. "CAVE" → CAVE-v2) | 1.0 |
| intent | loại bản ghi câu hỏi yêu cầu ("papers", "experiments", "fail/OOM", "decision", "commit", "next/should") | 1.0 |
| graph | spreading activation từ top kw/vec **và** từ bản ghi của research state | 0.8 |
| state | bản ghi state theo thứ tự (hypothesis, experiment, baseline, failures, decisions) + BM25 của state query | 0.7 |
| temporal | bản ghi nghiên cứu mới nhất, chỉ với câu hỏi "current/latest/best/next" | 0.5 |

**Metadata filter** (cứng): `types, tiers, dataset, model, source_type, evidence_status, origin, since, until, ids`.
**Temporal**: `current` phạt bản ghi `superseded` / hypothesis `refuted|abandoned`; `history` ("previous", "why did",
"tried") không phạt — failure và quyết định cũ vẫn tìm được.

### Điểm giải thích được (thay heuristic rerank)

```
score = w_rel·relevance
      + w_cent·centrality · (1 nếu câu hỏi planning/current, ngược lại relevance)
      + gate · Σ w_d·prior_d                    prior ∈ {importance, recency, confidence, evidence_strength,
      + 0.8 · gate · intent_fit                          failure_prevention, task_fit}
      − w_low · low_confidence                  low = candidate / AI-originated / rejected / superseded
gate  = max(relevance, w·centrality)            w = 1 (planning) | 0.6
relevance = 0.65·(fused/max fused | cross-encoder) + 0.35·coverage(stemmed query terms)
```
*Gate* là điểm mấu chốt rút ra từ đánh giá: prior chỉ **khuếch đại** bản ghi liên quan — một failure của nhánh khác hay
một decision pin không thể vượt bản ghi đúng chủ đề. Trọng số theo role nằm ở `policy.py` (một chỗ duy nhất).

Mỗi hit trả về `components`, `ranks` (hạng ở từng nguồn), `reasons` (vd. *"found by keyword #3, vector #1"*, *"prior
failure — prevents repeating it"*, *"part of the current research state"*). `POST /api/memory/explain {id, query}` trả lời
cả câu "vì sao **không** được chọn" (không có trong memory / bị sensitivity chặn / không nguồn nào xếp hạng).
Cross-encoder (bge-reranker qua `memory.rerank_url`) vẫn dùng được: nó thay thành phần relevance, các thành phần khác giữ.

## 4. Role-aware Context Compiler (`memory/compiler.py`, `memory/policy.py`)

| Role (tool → role) | state floor | research | evidence | knowledge | working |
|---|---|---|---|---|---|
| literature (`lit2plan`, search) | 12 % | 20 | 30 | **40** | 10 |
| experiment_designer (`experiment`) | 15 % | **45** | 25 | 15 | 15 |
| coder (`ide`, codex) | 12 % | 35 | 15 | 15 | **35** |
| reviewer (`reviewer`, critic, results) | 12 % | 30 | **40** | 20 | 10 |
| writer (`author`, `editor`, paper) | 12 % | 30 | 30 | 30 | 10 |
| director (`context_agent`) | 18 % | **40** | 25 | 15 | 20 |
| default (`data`, …) | 12 % | 35 | 15 | 20 | 30 |

`Budget(max_tokens, reserved_tokens, system_tokens, task_tokens, safety_margin)` → `memory_budget` → section (state floor
trước, phần còn lại theo share, budget thừa chảy sang section sau theo `research → evidence → working → knowledge`).
Khi vượt budget, theo thứ tự: (1) bỏ trùng/gần trùng (Jaccard token ≥ 0.8); (2) bỏ low-value (< 35 % điểm tốt nhất
**cùng tier**, trừ bản ghi protected/pinned/khớp trực tiếp top-3 keyword/vector); (3) nén LOD 6→5→4; (4) mới bỏ "budget".
Bản ghi đã nằm trọn trong RESEARCH STATE (decision, hypothesis, failure) không render lại. Mọi lựa chọn có trong `trace`
(`selected` kèm lý do, `dropped` kèm lý do, `blocked`, token từng section, compression ratio); `trace_text()` in đúng
dạng *CONTEXT TRACE* của spec §18 (`POST /api/memory/v3/compile {"trace": true}`).

Tương thích ngược: chữ ký `compile_context(tool, session_id, query, budget_tokens, purged, cfg)` và `agent_block(...)` giữ
nguyên; ba heading v3.2 vẫn có; role suy ra từ tool.

## 5. Evidence layer & provenance (`memory/evidence.py`, `memory/trace.py`)

```
Hypothesis ◀─tests─ Experiment ─produced─▶ Evidence ─supports/refutes─▶ Claim ─informs─▶ Hypothesis
Paper ◀─stated_in─ Claim          Decision ─informed_by─▶ Evidence/Experiment/Claim       Failure ─observed_in─▶ Experiment
Experiment ─executed_as─▶ Run ─▶ artifacts (sha256 từ provenance.json) · git commit · dataset · environment · ClearML task
```
- `CLM-`/`EVID-` theo quy ước id của research.py; evidence **chép** provenance (run, git, ClearML, dataset, environment)
  từ experiment lúc ghi.
- Integrity: chỉ evidence `validated` đổi trạng thái claim (`supported/refuted/contested`); evidence có origin AI/provider
  luôn bị hạ về `candidate`; evidence validated không xoá được (chỉ `rejected`).
- `trace.chain(id)` trả lời: *kết luận đến từ đâu, experiment nào sinh metric, commit nào sinh artifact, dataset/version
  nào, decision nào dựa trên evidence này* (`GET /api/provenance/chain/{id}`, MCP `research_get_provenance`).
- Decision có `evidence_ids`, `origin`, `provider`, `session`, `supersedes` (bản cũ được mở khoá + `superseded_by`, không xoá).

## 6. Failure memory

`add_failure(text, …, model, dataset, environment, configuration, error, cause, observation, lesson, avoidance_rule,
experiment_id)` — record v3.2 vẫn đọc được (trường mới rỗng). Failure có `failure_prevention = 1`, được kéo vào bởi intent
"fail/OOM/crash" và mọi câu hỏi planning, và xuất hiện trong RESEARCH STATE kèm *lesson*.

## 7. Lifecycle (`memory/lifecycle.py`)

`ephemeral (working.json) → working (Tier 1) → episodic (Tier 2 + tier2_archive) → research / knowledge / evidence`, và
trạng thái mới **candidate**: mọi thứ AI/provider/MCP muốn ghi → `propose()` (phân loại `ai_suggestion | ai_claim |
verified_observation | experiment_result | human_decision | validated_evidence`, dedup với bản ghi thật và candidate đang
chờ, confidence) → `approve()` (hành động của researcher, giữ origin/provider/session/request trên bản ghi) hoặc
`reject()` (giữ lại để audit). Consolidation giờ giữ `pages`/`links` của các episode được gộp và chuyển chúng vào
`tier2_archive` — raw không bao giờ bị xoá chỉ vì đã có summary.

## 8. Cache & invalidation (`memory/cache.py`)

Chỉ thêm sau khi profile (audit §8). Khoá luôn chứa **mọi** thứ ảnh hưởng kết quả:
`fingerprint = (thư mục project, generation trong process, (mtime_ns, size) của mọi file nguồn của collect())`.
- `NODES`: Index (node, BM25, vector, adjacency) theo fingerprint + purged + embedding engine.
- `RESULTS`: kết quả retrieval theo fingerprint + hash RetrievalContext (query, role, filters, temporal, k, purged,
  sensitivity, state version) + reranker.
- `VECTORS`: vector theo hash nội dung (không bao giờ stale), float32 cho dense.
- Store không phải nguồn retrieval (`working.json`, cache embedding, page index, candidates) **không** bump generation —
  nếu không, mỗi lượt chat (ghi current_task) sẽ xoá sạch cache.
- Ghi từ tiến trình khác / sửa tay file được phát hiện qua mtime+size (có test).

## 9. Độ tin cậy

Reader lấy lock per-file; `os.replace`/đọc retry khi Windows báo sharing violation; file JSON hỏng được giữ lại
(`<file>.corrupt-<UTC>`) trước khi dùng mặc định; file `.tmp` sót lại sau crash bị bỏ qua; legacy store dùng `RLock`.
Giới hạn còn lại: lock chỉ trong một tiến trình (app là single-process; launcher không cho chạy 2 instance cùng cổng).

## 10. Quan sát (`backend/telemetry.py`)

`span(operation, …)` ghi `request_id, session_id, project_id, agent_id, provider, role, latency_ms, cache_hit,
candidate_count, selected_count, dropped_count, context_tokens, memory_tokens, blocked_count, context_version, error`
vào ring buffer + `<global>/telemetry/ops.jsonl` (xoay vòng 5 MB). Chỉ nhận số, bool và định danh ngắn — chuỗi tự do
(query, prompt, nội dung memory) bị từ chối ngay trong `_clean()`; lỗi được `redact()`. `GET /api/telemetry` trả p50/p95,
số lỗi, cache hit rate theo operation và thống kê từng cache.
