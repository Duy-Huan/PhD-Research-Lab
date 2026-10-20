# ARCHITECTURE — PhD Research Lab v3.2 (Research Control Plane)

> PhD Research Lab là **control plane**: sở hữu tri thức khoa học (câu hỏi, giả thuyết, quyết định, diễn giải, kết luận)
> và *con trỏ* tới hệ thống ngoài. Nó không clone VS Code, ClearML, Docker hay Kubernetes.

## 1. Tổng quan lớp

```
┌────────────────────────────── Frontend (SPA vanilla JS) ──────────────────────────────┐
│ Lit2Plan · Experiment · Workspace&Runs · Papers&Writer · Masterclass · Context ·       │
│ 🧭 Control Center (v3.2: dashboard, workspace, integrations, timeline, provenance) · …│
└───────────────────────────────────────┬────────────────────────────────────────────────┘
                                        │ REST + SSE (127.0.0.1, Host-checked)
┌───────────────────────────────────────┴────────────────────────────────────────────────┐
│ API: app.py (core) · api_v3.py · api_v31.py · api_v32.py (memory v2, integrations,     │
│      resources, provenance, critic, connectors, codex)                                 │
├──────────────────────── Research Core (KEEP) ──────────────────────────────────────────┤
│ prompts · paper · brief · review_ext · results · library · websearch · latex_build     │
├──────────────────────── Context Memory (backend/memory/) ──────────────────────────────┤
│ Write path (Memorizer, 1 writer):  compressor → pages (raw, append-only) + episodes     │
│                                     research (HYPE-xxx, experiments, failures)          │
│                                     knowledge (papers, concepts, methods)               │
│ Read path (Researcher, read-only): lod tree → retrieval (BM25 ‖ vector ‖ graph) → RRF   │
│                                     → reranker → compiler (deterministic Markdown)      │
├──────────────────────── Agents & LLM ──────────────────────────────────────────────────┤
│ config.AGENTS · llm.py (providers, stream) · llm_router.py (auto mode: task-kind,       │
│ online check, GPU-busy, fallback chain) · critic.py · coder.py · context_graph agent    │
├──────────────────────── Integration layer (backend/integrations/) ─────────────────────┤
│ base: IntegrationStatus(state ∈ disabled|unconfigured|unavailable|available|error)      │
│ workspace: VSCodeAdapter · DevContainer/Environment Manager · JupyterAdapter · Git info │
│ experiment: ExperimentBackend ← LocalRunsBackend (verified) · ClearMLAdapter (optional) │
│ agents:     AgentBackend ← CodexBackend (optional, CLI `codex exec --json`)             │
├──────────────────────── Resource governor (resources.py) ──────────────────────────────┤
│ hardware policy from sysinfo · hard caps · JIT VRAM unload · thermal guard · CPU fallback│
├──────────────────────── Execution ─────────────────────────────────────────────────────┤
│ sandbox.py = LocalDockerBackend / local venv · provenance.py (artifact sealing)         │
└────────────────────────────────────────────────────────────────────────────────────────┘
           │              │                 │               │             │
        VS Code         Docker          ClearML         Ollama/LM      Git/GitHub
       (+DevCont.)   (GPU passthrough)  (optional)      Studio         Codex CLI (opt.)
```

## 2. Ranh giới & quy tắc phụ thuộc

1. Research Core **không import SDK của nhà cung cấp**. ClearML SDK chỉ được import (lazy) trong `integrations/experiment.py`; Codex CLI chỉ được gọi trong `integrations/agents.py`; VS Code/Jupyter trong `integrations/workspace.py`.
2. Mọi adapter trả về `IntegrationStatus` thật: không cấu hình → `unconfigured`; thiếu SDK/CLI hoặc server không phản hồi → `unavailable`; không bao giờ báo `available` nếu chưa probe thành công.
3. Đường ghi Context Memory duy nhất là `memory.compressor` + API ghi tường minh của researcher (decisions, research records). Retrieval/compiler **không ghi** (trừ cache embedding — dữ liệu dẫn xuất có thể xóa).
4. Raw (chat sessions, run logs, page snapshots) là **nguồn sự thật bất biến**; memo/episode là dẫn xuất, luôn mang con trỏ `pages` để mở rộng lossless (LOD 7).
5. Credential chỉ nằm ở `data/config.json` (gitignored), luôn được mask khi trả về frontend, chỉ gửi tới endpoint của chính nhà cung cấp đó.
6. Mọi hành động tốn kém / phá hủy (chạy job GPU, ghi devcontainer đè file, đồng bộ ClearML, chạy Codex với quyền ghi) cần lời gọi tường minh từ người dùng.

## 3. Context Memory v2 (CONTEXT_MEMORY.md)

| Thành phần | File | Vai trò |
|---|---|---|
| Legacy 3-tier + worker | `memory/__init__.py` | API cũ giữ nguyên (`load`, `update`, `summarize`, `memory_block`, decisions, Tier 3). |
| Working Memory | `memory/working.py` | `current_task`, trạng thái runtime agent theo session; token accounting Tier 1. |
| Research Memory | `memory/research.py` | Hypotheses `HYPE-NNN`, experiment records (`run_id`, `clearml_task_id`, `git_sha`, `hypothesis_id`, observation, interpretation, decision, conclusion, next_action, verdict), validated failures. |
| Knowledge Memory | `memory/knowledge.py` | Papers (dẫn xuất từ library), concepts, proven methods. |
| Page-store | `memory/pages.py` | Snapshot raw append-only (`memory/pages/<id>.txt` + `pages.json` header) — GAM page `{header, content}`. |
| LOD tree | `memory/lod.py` | Mỗi item → `MemoryNode` với 7 LOD (TREEFRAG). |
| Retrieval | `memory/retrieval.py`, `memory/embeddings.py` | BM25 (sparse) ‖ vector (Ollama embeddings nếu có, nếu không hashing-vector, có ghi nhãn) ‖ graph (overlay edges + entity links, 2-hop) → Reciprocal Rank Fusion → reranker (heuristic mặc định; HTTP `/rerank` kiểu TEI/bge-reranker nếu cấu hình). |
| Compiler | `memory/compiler.py` | Xuất đúng khối `[CONTEXT SYSTEM INJECTION]` với 3 mục; ngân sách token theo mục; thứ tự xác định; mục quan trọng ở đầu & cuối. |
| Compressor | `memory/compressor.py` | Watermark 16 000 → 2 000 token; chunk 3 500 token; tóm tắt song song có giới hạn + timeout bằng local model; reduce phân cấp; entity wiring (run_id, task_id, git_sha, HYPE). |

## 4. Tài nguyên phần cứng (HARDWARE_RESOURCE_CONSTRAINT.md)

`resources.policy()` suy ra trần từ máy thật (mặc định cho i5-14400F/RTX 3060/32 GB: VRAM an toàn 11 GB, local AI ≤ 8 GB, sandbox RAM 16 GB, 6 CPU, local AI 4 thread) và cho phép override trong `config.resources`. Trước mỗi run GPU: **cổng VRAM** — nếu Ollama / LM Studio còn nạp model thì run bị từ chối (HTTP 409 `vram_busy`); người dùng bấm 🧹 Unload (thủ công: `keep_alive: 0` / REST v1 `instance_id`, chờ VRAM < ngưỡng) hoặc chọn chạy CPU. Sau đó kiểm tra nhiệt / GPU khả dụng → chạy; lỗi GPU-fault → chạy lại 1 lần trên CPU (`CUDA_VISIBLE_DEVICES=`). Khi GPU bận, agent mode `auto`/local được định tuyến lên cloud, hoặc Ollama `num_gpu=0` (CPU offload) nếu offline.

## 5. Luồng truy vết (Target §7, §14)

```
Hypothesis HYPE-007 ──▶ Experiment record ──▶ run_id ──▶ git_sha (+dirty) ──▶ environment(image, gpu)
        ▲                     │                  │
        │                     └──▶ clearml_task_id ──▶ ClearML Web UI (deep link)
   Decision/Conclusion ◀── interpretation ◀── metrics/figures (sealed with provenance)
```
