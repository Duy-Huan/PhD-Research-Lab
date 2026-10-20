# INTEGRATION STATUS — v3.2.0 (2026-10-20)

Máy kiểm chứng: Windows 11 · i5-14400F (16 luồng) · RTX 3060 12 GB · 31.8 GB RAM · Python 3.14.8 · Docker Desktop 29.8.2 (runtime `nvidia`)
· VS Code 1.142.0 · Git · Ollama (chưa có model) · không có: ClearML, Jupyter, Codex CLI, LM Studio CLI, LaTeX.

Ký hiệu: ✅ kiểm chứng thật trên máy này · 🧪 kiểm chứng bằng unit test (mock/stub) · ⏳ adapter có, **chưa kiểm chứng với dịch vụ thật** · ❌ chưa có.

## 1. Ma trận tích hợp

| Tích hợp | Trạng thái | Bằng chứng | Hạn chế / bước tiếp |
|---|---|---|---|
| Docker sandbox + hard caps + GPU passthrough | ✅ | Chạy thật `python:3.11-slim`: RAM "không giới hạn" → **15 GB**, CPU 12 → **6** (có cảnh báo), `nvidia-smi` trong container thấy RTX 3060, metrics thu đúng; container + image đã xoá sau test. | Container cũ có giới hạn cao hơn policy chỉ được **cảnh báo** (Recreate để áp dụng) — không tự xoá vì mất package đã cài. |
| Local sandbox (venv) + git SHA + provenance | ✅ | `tests/test_sandbox_e2e.py` (không mock): run thật → metrics, `environment`, `git.sha` 40 ký tự, PNG + CSV được niêm phong, tra ngược qua `provenance.inspect`. | — |
| Thermal guard / GPU preflight | ✅ / 🧪 | Preflight đọc `nvidia-smi` thật (41-42 °C). Quá nhiệt → CPU: unit test. | — |
| Cổng VRAM + unload thủ công (quy tắc của người dùng) | ✅ | **LM Studio thật** (`nemotron-3-nano-4b`): nạp → VRAM 11 136 MB → run GPU bị từ chối (409, UI hiện hộp thoại) → bấm *Unload & run* → VRAM 1 128 MB sau 1,6 s → run chạy. Không có unload tự động (test khẳng định). Phát hiện & sửa lỗi: bản LM Studio này chỉ unload qua REST v1 với `instance_id`. | Ollama: chưa có model để thử thật (unit test). |
| CPU fallback sau GPU fault | 🧪 | `classify_failure` + chạy lại với `CUDA_VISIBLE_DEVICES=""` (một lần). OOM chỉ gợi ý, không chạy lại. | Không thể giả lập lỗi driver thật. |
| VS Code (open folder/file, `vscode://`) + extension Codex | ✅ (probe) / ⏳ | `code --version` = 1.142.0, `--list-extensions` đọc được; mở thư mục / mở file tại dòng (`code <dir> -g file:line`). Nút cài extension chỉ nhận allow-list (`openai.chatgpt`, Dev Containers, Python, Jupyter). | Extension Codex & Dev Containers **chưa cài** trên máy. Monaco IDE đã gỡ. |
| Environment Manager (Dockerfile + devcontainer.json) | ✅ / 🧪 | Sinh file với caps của máy (16 GB/6 CPU trên máy tham chiếu), image PyTorch đã thẩm định, mount `/runs`, `/datasets` read-only; không bao giờ ghi đè nếu chưa xác nhận. | Chưa build thử image GPU (≈ 8 GB). |
| Jupyter | ⏳ | Phát hiện CLI → `unavailable` + hướng dẫn. Launcher: `--ServerApp.ip=127.0.0.1`, token ngẫu nhiên, chờ `/api/status` = 200 mới báo chạy. | Cài `pip install jupyterlab` để kiểm chứng. |
| Git / GitHub | ✅ | `gitops.head_info()` dùng trong mọi run; publish GitHub giữ nguyên v3.0. | — |
| ClearML — **offline mode** (Python SDK, no server) | ✅ | `clearml 2.1.12` on Python 3.14: sandbox run → offline session (params, curves, final metrics, log, artifacts, research-code commit) in `<project>/clearml/offline/*.zip`, read back without the SDK; auto-record after each run; UI *Record* button; artifacts re-sealed with the task id. All SDK calls run in a subprocess (`clearml_worker.py`). | A training script that calls `Task.init` itself needs `clearml` installed inside the sandbox (container / sandbox venv). |
| ClearML — **server mode** / import of offline sessions | ⏳ | Status `unconfigured/unavailable/available` only after `GET {api}/debug.ping`; `import_offline_session`, `get_task`, `submit_remote`, fine-grained ops through the same worker. | **Not verified against a live ClearML Server.** Opt-in test: `PHDLAB_CLEARML_LIVE=1`. |
| Codex CLI (`CodexBackend`) | ⏳ | Cờ/sự kiện đối chiếu tài liệu chính thức (non-interactive mode): `codex exec --json --sandbox read-only|workspace-write -`, sự kiện `thread.started`, `item.completed`, `turn.completed`, `turn.failed`. Mapping sự kiện có unit test. | CLI chưa cài. `codex login status` dùng để đoán trạng thái đăng nhập (best-effort). Test opt-in: `PHDLAB_CODEX_LIVE=1`. |
| LLM auto router (SmartMultiRouter) | 🧪 | Kế hoạch theo task-kind, offline → chỉ local, GPU bận → cloud trước / LM Studio bị loại, fallback tuần tự. | Chưa có API key nào được cấu hình nên chưa gọi thật provider mới. |
| DeepInfra / 9Router / OmniRoute | ⏳ | Đăng ký provider OpenAI-compatible; gateway local: key tùy chọn, chỉ dùng khi `/models` phản hồi. Header tùy chỉnh chỉ nhận tên `X-…` (lọc injection). | Header `X-9Router-Skills` lấy từ spec, **chưa kiểm chứng** với 9Router thật — để trống mặc định. |
| Ollama CPU offload (`num_gpu: 0`) | 🧪 | Dùng API native `/api/chat` (endpoint OpenAI-compatible của Ollama không nhận `options`). | Cần model để kiểm chứng thật. |
| Embeddings (Ollama `/api/embed`) | ⏳ | `auto` → dùng `hashing-512` (lexical, **được ghi nhãn không phải neural**) vì Ollama chưa có `nomic-embed-text`. | `ollama pull nomic-embed-text` để bật vector neural. |
| Reranker HTTP (bge-reranker) | ⏳ | Hỗ trợ endpoint `/rerank` kiểu TEI/Jina/Cohere; lỗi → heuristic. | Cần một server reranker. |
| Hugging Face connector | ⏳ | API công khai `huggingface.co/api/datasets?search=` — chưa gọi mạng trong test. | — |
| Kaggle connector | 🧪 | Không token → `unconfigured`. Đọc token từ `~/.kaggle/kaggle.json` / env (app không lưu). | — |
| Model serving (vLLM/BentoML/KServe) | ❌ | Ngoài phạm vi v3.2 (M7). | Không cài Kubernetes trên máy đơn. |

## 2. Đối chiếu CHECKLIST_PROMPT.md sau nâng cấp

| Module | Hạng mục | v3.1 | v3.2 | Ghi chú / file |
|---|---|---|---|---|
| 1 | Sysinfo 2 s, pure-python | ✅ | ✅ | `sysinfo.py`, `docker.js` |
| 1 | Giải phóng VRAM trước khi train | ❌ | ✅ | theo yêu cầu người dùng: **chặn + unload thủ công** (`resources.vram_gate` ← `sandbox.start_job`), kiểm chứng với LM Studio thật |
| 1 | Docker limits 12-16 G / 6 core / `--gpus all` | ⚠️ | ✅ | `resources.clamp_sandbox`, `sandbox.ensure_container` |
| 1 | Graceful degradation → CPU | ⚠️ | ✅ | thermal guard + `_after_run` CPU re-run |
| 2 | VS Code deep link / Dev Container | ❌ | ✅ | `integrations/workspace.py`; Monaco IDE **đã gỡ**, tab Workspace & Runs |
| 2 | ClearML local/remote switch | ❌ | ✅ / ⏳ | offline mode (local, verified) ↔ server mode; `/api/compute/submit` target `clearml` + local fallback (server not verified) |
| 2 | Jupyter session link | ❌ | ⏳ | token ngẫu nhiên, chỉ 127.0.0.1 |
| 2 | Git metadata (`git_commit_sha`, `repository_url`, token ẩn) | ⚠️ | ✅ | `run.json → git{sha, branch, dirty, remote}` |
| 3 | 3-tier memory | ✅ | ✅ | watermark 16k → 2k, chunk 3 500 (`memory/compressor.py`) |
| 3 | Graph node ↔ ClearML `task_id` | ❌ | ✅ | `EXP-*` có `clearml_task_id`; cạnh EXP→HYPE/run |
| 3 | Context Decision Agent pin/purge | ✅ | ✅ | thêm edit/delete cho `HYPE/EXP/FAIL` |
| 4 | Author → Reviewer → Editor theo section | ✅ | ✅ | không đổi |
| 4 | Section briefs | ✅ | ✅ | không đổi |
| 4 | Citation guard + đỏ `[CITATION NEEDED]`/`[TBD]` | ✅ | ✅ | + critic báo key không có trong `references.bib` khi đang stream |
| 4 | Local critic async khi stream | ❌ | ✅ | `critic.py`, SSE event `critic`, badge đỏ/vàng, bấm nhảy tới dòng |
| 4 | Deterministic LaTeX compile | ✅ | ✅ | không đổi (máy kiểm chứng chưa có TeX) |
| 5 | DataConnectorRegistry | ❌ | ✅ | `backend/connectors/` (HF, Kaggle), lệnh `/hf` `/kaggle` `/dataset` trong Data chat |
| 5 | Artifact provenance injection | ❌ | ✅ | PNG tEXt / JPEG COM / SVG / CSV + `provenance.json` (SHA-256) |

## 3. Cách chạy kiểm thử

```bash
python -m unittest discover -s tests -p "test_*.py"     # 60 test, ~25 s, dữ liệu tạm (không đụng data/)
PHDLAB_CLEARML_LIVE=1 python -m unittest tests/test_live_integrations.py   # cần ClearML server
PHDLAB_CODEX_LIVE=1  python -m unittest tests/test_live_integrations.py    # cần codex login (tốn quota)
```
Kết quả lần chạy cuối: **81 test OK, 3 skipped** (live ClearML-server / Codex / LM Studio). ClearML offline tests chạy thật với SDK đã cài. Live LM Studio: `PHDLAB_LMSTUDIO_LIVE=1` → OK.
