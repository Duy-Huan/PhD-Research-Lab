# Backend audit — PhD Research Lab v3.2 (baseline cho v3.3)

> Phase 1 của `PhD-Research-Lab-v3.3-Backend-Context-Memory-Upgrade-Prompt.md`. Ngày audit: 2026-10-20, nhánh
> `feature/v3.2-research-os` (HEAD `f858d1b` + thay đổi chưa commit của nhánh). Mọi kết luận dựa trên mã nguồn và số đo,
> không dựa trên mô tả trong các file prompt. Số đo baseline chạy trên **mã HEAD nguyên gốc** (git worktree riêng).

## 0. Tóm tắt

| Hạng mục | Hiện trạng v3.2 |
|---|---|
| Kiến trúc | Monolith FastAPI cục bộ (`backend/app.py` + router `api_v3/31/32`), bind `127.0.0.1`, middleware chặn `Host` lạ (DNS-rebinding). Không DB server: mọi state là file JSON theo project. |
| Context Memory | Package `backend/memory/` (v3.2): Working / Research / Knowledge + Tier 2 episodes + page-store, retrieval BM25 ‖ vector ‖ graph → RRF → rerank heuristic, compiler 3 section, compressor watermark. |
| Test | 90 test (unittest, stdlib), **90 pass, 4 skip** (live opt-in) trong 36 s. Một cảnh báo thread từ mock `P` không có `wait()` trong `test_integrations` (vô hại, đến từ thay đổi chưa commit của nhánh). |
| Điểm mạnh | Ghi tách biệt (single writer + page-store bất biến), ID nghiên cứu ổn định (HYPE/EXP/FAIL), con trỏ ClearML/git trên experiment, compiler xác định, LOD (TREEFRAG), atomic write. |
| Điểm yếu đo được | (1) retrieval không biết research state — chỉ query string; (2) tỷ lệ section cố định 35/40/25 cho mọi agent; (3) không có Evidence/Claim; (4) không giải thích được *vì sao* một memory được chọn; (5) latency tăng tuyến tính, 600 ms ở ~4k node; (6) **3 bug thật** (mục 8). |

## 1. Kiến trúc hiện tại (phần liên quan)

```
FastAPI app.py ── api_v3.py (memory, context graph, MCP /mcp, sandbox) ── api_v32.py (memory v2, research, integrations)
      │
      ├── memory/__init__.py   legacy store project_state.json: tier2 episodes, tier3 (goals, hypotheses, constraints,
      │                        best_metrics, references), decisions; summarizer + background worker
      ├── memory/store.py      JsonStore: 1 RLock/file, atomic tmp+os.replace
      ├── memory/research.py   research.json: hypotheses HYPE-, experiments EXP- (run/git/ClearML/dataset), failures FAIL-
      ├── memory/knowledge.py  knowledge.json: concepts, methods; papers đọc live từ library.json
      ├── memory/working.py    working.json: current_task, agents
      ├── memory/pages.py      page-store bất biến (raw chat/run snapshots), pages.json
      ├── memory/lod.py        collect(): dựng MemoryNode (LOD 1-7) từ mọi store mỗi lần gọi
      ├── memory/embeddings.py hashing 512-d (mặc định) hoặc Ollama; cache embeddings.json
      ├── memory/retrieval.py  BM25 ‖ cosine ‖ graph → RRF(k=60) → heuristic/HTTP rerank
      ├── memory/compiler.py   compile_context() 3 section + agent_block() (gắn vào system prompt mọi agent)
      └── memory/compressor.py watermark 16k→2k, chunk 3.5k, JSON memo, entity wiring; ghi duy nhất vào long-term
 context_graph.py (overlay: pin/purge/custom nodes/edges)   provenance.py (seal artifact)   critic.py (live critic)
 integrations/ (ClearML worker, Codex CLI, workspace)       mcp_server.py (3 tool sandbox, JSON-RPC)   llm.py/llm_router.py
```

## 2. Memory lifecycle (v3.2)

```
chat turn / sandbox run ──► Tier 1 (tính live, không copy)
        │ worker 180 s: tokens ≥ high watermark
        ▼
compressor: snapshot raw → page-store (bất biến) ─► LLM summarizer → JSON memo ─► Tier 2 episode (pages, links)
        │ > 40 episode
        ▼
_consolidate(): gộp 12 episode cũ nhất → 1 period summary   ⚠ xoá 12 episode gốc, KHÔNG giữ pages/links của chúng
Tier 3: refresh từ sandbox best_metrics, library, lit2plan.md (goals/hypotheses) ─► research.sync_from_plan (HYPE ids)
```
Research/Knowledge chỉ được ghi bởi hành động của researcher (API) — đúng nguyên tắc integrity.

## 3. Write path / Read path

- **Write**: `JsonStore.update(fn)` = lock file → load → fn → ghi `.tmp` → `os.replace`. Legacy store dùng `threading.Lock`
  module-level. Validation ở từng module (`ResearchError`).
- **Read**: `load()` **không** lấy lock; `lod.collect()` đọc lại *mọi* file JSON + library + notes + overlay ở **mỗi**
  lần retrieval/compile; không có cache nào ngoài cache embedding Ollama (file JSON đọc lại toàn bộ mỗi lần `embed()`).

## 4. Retrieval pipeline (v3.2)

query string → `collect()` → BM25 (dựng index mới mỗi lần) ‖ hashing vector 512-d **dense** cho mọi node (tính lại mỗi lần)
→ cosine thuần Python ‖ graph spreading từ top kw/vec → RRF → pool 40 → heuristic rerank (RRF×60 + coverage + exact id +
pinned + recency + status) → top k. Không có: research state, metadata filter, temporal mode, role, lý do chọn.

## 5. Context compilation (v3.2)

Section cố định Working 35 % / Research 40 % / Knowledge 25 % của `context_budget_tokens` (3 500), carry-over budget,
LOD 6 cho 2 hit đầu mỗi section, `always` = pinned + hypothesis testing/proposed + episode của session. Không dedup, không
trace, không nén theo bậc (chỉ 6→5 rồi bỏ), research state không có section riêng.

## 6. Agent interaction

`app._v3_context()` và `coder.py` gọi `agent_block(tool, sid, query, purged)` → compiled block nối vào system prompt.
Tool name (`lit2plan`, `experiment`, `author`, `reviewer`, `ide`, `data` …) **không** ảnh hưởng nội dung (không role-aware).
MCP `/mcp`: chỉ 3 tool sandbox (run code, file read/write, metrics) — không có tool nghiên cứu, không token, không audit.

## 7. Storage model & dependency graph

`<project>/memory/{project_state, research, knowledge, working, pages, embeddings, context_graph}.json`, `pages/*.txt`,
`<project>/library.json`, `<project>/runs/<id>/{run.json, provenance.json}`. Phụ thuộc:
`compiler → retrieval → embeddings, lod → (memory, research, knowledge, library, context_hub, context_graph)`;
`compressor → memory, pages, llm`. Không vòng phụ thuộc lúc import (import trễ trong hàm).

## 8. Bottleneck & bug — đo được

Corpus golden (đề tài HSI denoising) + distractor, hashing embedder, Windows 11 / Python 3.14, `benchmarks/bench_memory.py`.

| Distractors | Node | retrieve (median) | compile (median) | collect | ghi 1 experiment |
|---|---|---|---|---|---|
| 0 | 25 | 14 ms | 23 ms | 9 ms | 5 ms |
| 300 | 1 054 | 163 ms | 172 ms | 16 ms | 10 ms |
| 1 500 | 3 994 | 617 ms | 640 ms | 39 ms | 31 ms |

**cProfile** (1 500 distractor, 1 lần retrieve = 1.85 s dưới profiler): 67 % trong `sum()` của cosine dense
(2 M phép nhân), 41 % dựng lại `hashing_vector` cho 3 995 node, 6 % dựng BM25. → Tối ưu có căn cứ: vector sparse + cache.

Bug phát hiện (đều đã có test tái hiện):
1. **Mất paper khi thư viện > 300 mục** — `knowledge.papers(limit=300)` cắt theo thứ tự key, paper có key xếp sau (vd.
   `liang2021swinir`) biến mất khỏi memory, retrieval và context.
2. **Race đọc/ghi trên Windows** — reader không lấy lock; `os.replace` gặp file đang mở → `PermissionError`; reader đọc
   đúng lúc replace → nhận dict rỗng → lỗi giả "Hypothesis not found" (test 6 thread × 10 ghi: 4 lỗi).
3. **File JSON hỏng bị ghi đè im lặng** — `load()` trả mặc định khi JSON lỗi; lần ghi tiếp theo xoá toàn bộ dữ liệu.
4. **Consolidation làm mất provenance** — period summary không thừa hưởng `pages`/`links`, 12 episode gốc bị xoá.

## 9. Concurrency risks

| Rủi ro | Mức | Ghi chú |
|---|---|---|
| Reader không lock + Windows sharing violation | **Cao** (bug 2) | user + agent + summarizer cùng lúc |
| Đa tiến trình (2 instance app cùng project) | Trung bình | lock chỉ trong process; launcher đã chặn chạy 2 app trên 1 cổng |
| Summarizer và researcher cùng ghi `project_state.json` | Thấp | cùng một lock module |
| `context_graph.save_overlay`, `chat_store` dùng `os.replace` không retry | Thấp | ngoài phạm vi v3.3, ghi nhận |

## 10. Technical debt

- `lod.collect()` không cache; mọi request dựng lại toàn bộ cây node.
- Token ước lượng `chars/4` (không tokenizer thật) — đủ cho budget tương đối, ghi rõ trong tài liệu.
- Tỷ lệ section và trọng số rerank là hằng số rải rác; không có nơi khai báo policy.
- Không có bộ đánh giá chất lượng retrieval → mọi thay đổi trước đây không đo được.

## 11. Thứ tự nâng cấp đề xuất (đã thực hiện theo đúng thứ tự)

1. Golden corpus + benchmark + profile (không đổi code) → 2. sửa bug 1-4 → 3. Research State → 4. retrieval state-aware có
giải thích + cache theo fingerprint → 5. compiler role-aware có budget/trace → 6. Evidence/Claim + provenance chain →
7. lifecycle (candidate) → 8. đánh giá lại (dev + held-out) → 9. hardening (concurrency, migration, corruption).
