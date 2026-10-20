# ARCHITECTURE AUDIT — PhD Research Lab (baseline v3.1.0 → v3.2.0)

> Milestone 1 deliverable. Ngày audit: 2026-10-20. Mọi kết luận dưới đây dựa trên mã nguồn thực tế (đường dẫn + symbol),
> không dựa trên mô tả trong các file prompt. Không chứa secret.

## 0. Tóm tắt điều hành

| Hạng mục | Hiện trạng thực tế (v3.1.0) |
|---|---|
| Kiến trúc | Monolith **FastAPI** (`backend/app.py` + 2 router `api_v3.py`, `api_v31.py`, 88 route) + **SPA vanilla JS** (`frontend/index.html` 3 440 dòng + 5 module `frontend/app/*.js`). Không có build step, không DB server: toàn bộ state là **file JSON theo project** trong `data/` hoặc `projects/<name>/`. |
| Khởi động | `start.py` (kiểm tra file/version, tự cài package, bind `127.0.0.1:8765`, uvicorn pure-Python `h11`). |
| Điểm mạnh (giữ) | Pipeline viết bài Author→Reviewer→Editor theo từng section, Section Briefs (v3.1), Citation Guard, LaTeX build cục bộ, Paper Review ngoài, 3-tier memory + Context Graph + Context Decision Agent, sandbox Docker/local có self-debug loop, quét phần cứng. |
| Điểm yếu chính | (1) Context Memory chưa có retrieval (chỉ "nhồi" Tier 3 + episode mới nhất theo budget ký tự), không có compiler xác định, không tách raw/memo rõ ràng; (2) không có integration layer — Docker/Git/LLM gọi trực tiếp trong module nghiệp vụ; (3) không có ClearML, VS Code, Jupyter, Codex; (4) không có điều phối VRAM khi chạy GPU job; (5) **không có test tự động nào**; (6) API không có kiểm tra `Host` (rủi ro DNS-rebinding với endpoint chạy lệnh shell). |
| Môi trường audit | Windows 11, Python 3.14.8, RTX 3060 12 GB (driver OK, 846 MiB dùng, 41 °C), Docker Desktop **cài nhưng daemon không chạy**, Git có, VS Code CLI `code` có, Ollama chạy (chưa load model), LM Studio CLI không có, ClearML SDK/server **không có**, Jupyter **không có**, Codex CLI **không có**, LaTeX **không có**, pytest/Pillow **không có**. Chưa cấu hình API key cloud nào. |
| Baseline | `python start.py --check` → *Installation OK*; `from backend.app import app` → 88 route. Không có test suite để chạy. |

## 1. Cấu trúc repository

```
start.py, run.bat, run.sh, setup.bat     launcher / cài đặt
mcp_stdio_bridge.py                       cầu nối MCP stdio → POST /mcp
requirements.txt                          fastapi, uvicorn, httpx, pypdf, python-multipart, GitPython
backend/
  app.py            (1276) route lõi: config, project, library, Tool 1/2/4, chat SSE, paper pipeline, LaTeX, paper review
  api_v3.py         ( 788) local AI, system scan, sandbox/docker, IDE files, co-coding agent, git, memory, context graph, export, MCP
  api_v31.py        ( 222) results (kết quả ngoài) + section briefs
  config.py         ( 435) PROVIDERS (15 provider), AGENTS (23 agent), DEFAULTS, project registry, path resolver
  llm.py            ( 440) router LLM: Anthropic native + OpenAI-compatible + LM Studio/Ollama, stream, fallback cloud
  local_ai.py       ( 217) LM Studio/Ollama: status, load, unload (keep_alive 0), pull
  memory.py         ( 434) 3-tier memory + Summarization Agent + worker nền
  context_graph.py  ( 334) đồ thị tri thức dẫn xuất + overlay pin/purge + Context Decision Agent
  context_hub.py    ( 136) shared context giữa các tool + pinned notes
  sandbox.py        ( 635) Docker CLI / local venv, Job, runs/, metrics parser, best_metrics
  sysinfo.py        ( 300) quét phần cứng pure-Python (ctypes, nvidia-smi, docker info, wsl) + recommend()
  coder.py          ( 148) co-coding agent: giao thức ```file=``` / ```run```, self-debug
  ide_fs.py         ( 223) file system an toàn cho code/ (Monaco IDE)
  gitops.py         ( 231) git CLI/GitPython + publish GitHub qua REST
  paper.py, prompts.py, brief.py, latex_build.py, library.py, attachments.py, websearch.py,
  review_ext.py, review_prompts.py, results.py, chat_store.py, fs_browse.py, mcp_server.py
frontend/
  index.html        SPA: 8 tab (Lit2Plan, Experiment, Code IDE, Papers & Writer, Masterclass, Context, Docker & System, Guide)
  app/ide.js (Monaco+xterm IDE), docker.js, context.js (vis-network), results.js, brief.js, v3.css
  vendor/           monaco, xterm, vis-network, katex, marked, DOMPurify, highlight.js (offline)
data/               (gitignored một phần) config.json, Default project: workspace/, memory/, runs/, code/, sandbox/, results/, system/
```

## 2. Kết quả audit theo 13 mục bắt buộc (PhD_Research_Lab_Target.md §2)

| # | Hạng mục | Hiện trạng (bằng chứng) |
|---|---|---|
| 1 | Cấu trúc repo | Như §1. Mỗi research project = 1 thư mục dữ liệu (`config.py: create_project`, `data_dir()`, `workspace()`). |
| 2 | Frontend | SPA vanilla JS, tab-based (`index.html:590-598`), module tự đăng ký qua sự kiện `tab-shown`; i18n EN/VI (`i18n.js`). Không framework, không bundler. |
| 3 | Backend | FastAPI, sync route chạy threadpool, SSE cho streaming (`app.py: sse_job`, `chat_stream`). |
| 4 | Database | Không có DBMS. JSON + ghi nguyên tử (`tmp` + `os.replace`) với `threading.Lock` (`memory.py: save/update`, `context_graph.py: save_overlay`, `results.py: _save`). |
| 5 | Context Memory | `memory.py`: Tier 1 **tính động** (`tier1()` = chat chưa tóm tắt + log run), Tier 2 episodes (`summarize`, `_summarize_runs`, `_consolidate`), Tier 3 (goals/hypotheses/constraints/best_metrics/references) + `decisions`. Inject qua `app.py: _v3_context` = `pinned_block()` + `memory_block()` + `results.digest()`. Worker nền `memory.worker` (lifespan). **Không có** vector/BM25/graph retrieval, reranker, compiler cấu trúc, page-store riêng, liên kết ClearML. |
| 6 | AI agents | 23 agent khai báo trong `config.AGENTS`, mỗi agent có engine (`cloud`/`local`/`ollama`/`claude`/provider id) + model override; `llm.call_agent` / `stream_agent`. Không có Research Director/orchestrator đa agent; Context Decision Agent (`context_graph.agent`) đề xuất op → người dùng duyệt. |
| 7 | Deep Learning Lab | Tool 2 sinh `experiment_design.md` + `experiment_skeleton.py` (`app.py: experiment`), Code IDE + co-coding agent (`api_v3.py: ide_agent`) với self-debug tối đa N lần, metrics tự parse (`sandbox.parse_metrics_text`, `collect_run`). Chưa có spec experiment có cấu trúc (seed, dataset version…). |
| 8 | Execution / sandbox | `sandbox.start_job`: Docker `exec` trong container sống lâu `phdlab-<hash>` (mount `code/`→`/workspace`, `runs/`→`/runs`, `--gpus all`, `-m`, `--cpus`, `--shm-size`) hoặc local venv (`shell=True`). Timeout, stop (pkill trong container / taskkill). |
| 9 | Docker | Docker CLI (không docker-py). Fallback CPU nếu `--gpus` lỗi khi tạo container (`ensure_container`). Không có Dockerfile/devcontainer generator. Mặc định `memory_gb=8, cpus=4` (lệch so với policy phần cứng 12-16 GB / 6 core). |
| 10 | Git / GitHub | `gitops.py`: status/diff/commit/discard/push/pull/publish (GitHub REST `POST /user/repos`), token chỉ truyền qua `-c http.extraheader` (không ghi vào `.git/config`) — tốt. **Run không ghi lại commit SHA** → mất truy vết Experiment→Commit. |
| 11 | Experiment tracking | Tự xây: `runs/<id>/run.json, stdout.log, stderr.log, metrics.json, metrics_parsed.json, figures/`; `best_metrics()`. Không ClearML/MLflow. |
| 12 | Model serving | **Không có** (không registry, không serving). |
| 13 | Đã hoàn thiện & đang dùng | Lit2Plan (+ web search, versions, regenerate theo decisions), Experiment Design, Paper Writer deep pipeline + briefs + LaTeX build, Paper Review (R1-R3, AC, issues, fixes, response letter), Data chat, Masterclass, Code IDE + Git + GitHub publish, Docker & System monitor, Context graph, MCP server (`/mcp`, 3 tool sandbox). |

## 3. Phân loại subsystem (KEEP / ADAPT / REPLACE / REMOVE / UNKNOWN)

| Subsystem | Phân loại | Lý do (bằng chứng) |
|---|---|---|
| Research Core: Lit2Plan, Experiment Design, Masterclass (`app.py`, `prompts.py`) | **KEEP** | Giá trị cốt lõi, hoạt động, không trùng nền tảng ngoài. |
| Paper Writer pipeline + Section Briefs + Citation Guard (`paper.py`, `brief.py`, `app.py: paper_stream`) | **KEEP** | Đúng triết lý CLAUDE_RESEARCH_ALIGNMENT §2.1. Bổ sung Local Critic (ADAPT nhẹ, không đổi logic lõi). |
| Paper Review ngoài (`review_ext.py`, `review_prompts.py`) | **KEEP** | Độc lập, hoạt động. |
| LaTeX build (`latex_build.py`) | **KEEP** | Tự tìm latexmk/tectonic/pdflatex, phân log theo section. |
| Context Memory (`memory.py`) | **KEEP + ADAPT** | Giữ dữ liệu & API cũ; mở rộng thành package `backend/memory/` (page-store, LOD tree, retrieval, compiler, compressor) theo CONTEXT_MEMORY.md. |
| Context Graph + Decision Agent (`context_graph.py`) | **KEEP + ADAPT** | Thêm node Research Memory (hypothesis HYPE-xxx, experiment record với `clearml_task_id`, `git_sha`) và cạnh entity-wiring. |
| AI agent registry + LLM router (`config.AGENTS`, `llm.py`) | **KEEP + ADAPT** | Thêm provider (DeepInfra, 9Router, OmniRoute), chế độ `auto` (SmartMultiRouter theo task-kind + fallback chain + kiểm tra online + nhận biết GPU bận), Ollama CPU-offload. Hành vi cũ giữ nguyên với các mode cũ. |
| Local AI control (`local_ai.py`) | **KEEP** | Dùng lại cho JIT VRAM unload. |
| System scan (`sysinfo.py`) | **KEEP + ADAPT** | Thêm hardware policy (caps) dẫn xuất từ máy thật. |
| Sandbox / Docker runner (`sandbox.py`) | **ADAPT** | Giữ làm `LocalDockerBackend` (đã kiểm chứng được); thêm hook: JIT unload, hard caps, thermal guard/CPU fallback, git SHA, provenance. Không thay bằng ClearML Agent cho tới khi ClearML được cấu hình & kiểm chứng. |
| Experiment tracking tự xây (`runs/`, `best_metrics`) | **ADAPT** | Giữ làm `LocalRunsBackend` (offline-first). ClearML là backend tùy chọn qua `ExperimentBackend`; không xây thêm dashboard metrics. |
| Monaco Code IDE (`ide.js`, vendor/monaco, xterm) | **REMOVED (v3.2, người dùng duyệt 2026-10-20)** | Thay bằng VS Code + extension Codex (`openai.chatgpt`). Tab mới `workspace.js` giữ chạy sandbox, runs, agent tự sửa lỗi, Git/GitHub. `ide_fs.py` (backend) giữ lại cho agent/MCP/Environment Manager. |
| Co-coding agent (`coder.py`, `/api/ide/agent`) | **KEEP + ADAPT** | Self-healing (CUSTOMER_REQUIREMENT kịch bản 2) — giữ; Codex là backend agent tùy chọn bổ sung, không thay. |
| Git ops + GitHub publish (`gitops.py`) | **KEEP** | Dùng Git native (không tự xây Git) — đúng Target §7. Thêm metadata commit vào run. |
| Docker & System tab (`docker.js`) | **KEEP** | Giám sát vận hành; trạng thái tích hợp chuyển thêm sang Control Center. |
| MCP server (`mcp_server.py`) | **KEEP** | Công cụ cho agent bên ngoài; cần bảo vệ Host header. |
| Results pool (`results.py`) | **KEEP** | Kết quả ngoài + pool cho brief. |
| Model registry / serving | **UNKNOWN → chưa có** | Thiết kế abstraction ở M7, không triển khai Kubernetes/KServe (máy đơn RTX 3060). |
| Custom IDE terminal (xterm qua job stream) | **REMOVED (v3.2)** | VS Code terminal; log job hiển thị dạng văn bản trong tab Workspace & Runs. |

## 4. Chức năng trùng lặp nên ủy nhiệm cho nền tảng ngoài

| Đang tự làm | Ủy nhiệm cho | Kế hoạch |
|---|---|---|
| Text editor Monaco + file tree + search | VS Code | v3.2: nút Open in VS Code / Dev Container; M6: ẩn IDE cũ sau khi duyệt. |
| Biểu đồ metrics/run list | ClearML Web UI | v3.2: `ClearMLAdapter.sync_run()` + deep-link; PhD Lab chỉ giữ tóm tắt khoa học. |
| Terminal job log | VS Code terminal / ClearML console | Giữ log job tối thiểu cho self-debug. |
| Notebook | Jupyter | v3.2: phát hiện + khởi chạy JupyterLab có token, gắn với project. |

## 5. Đối chiếu CHECKLIST_PROMPT.md (trạng thái baseline v3.1.0)

Ký hiệu: ✅ có · ❌ thiếu · ⚠️ có nhưng lệch yêu cầu.

| Module | Hạng mục | Baseline | Bằng chứng |
|---|---|---|---|
| 1 | Sysinfo monitor 2 s, pure-python | ✅ | `sysinfo.live`, `docker.js` refresh 2 s, không native ext. |
| 1 | JIT VRAM unload trước sandbox | ❌ | Chỉ có nút unload thủ công (`/api/local/unload`); `start_job` không gọi. |
| 1 | Docker limits 12-16 G / 6 core / `--gpus all` | ⚠️ | Có cờ, mặc định 8 G / 4 core, không có trần cứng. |
| 1 | Graceful degradation → CPU | ⚠️ | Chỉ khi `--gpus` lỗi lúc tạo container; không xử lý quá nhiệt / mất GPU khi chạy. |
| 2 | VS Code deep link / Dev Container | ❌ | Không có. Monaco vẫn là editor chính. |
| 2 | ClearML local/remote switch | ❌ | Không có ClearML. |
| 2 | Jupyter session link | ❌ | Không có. |
| 2 | Git metadata (`git_commit_sha`, `repository_url`, token ẩn) | ⚠️ | Token ẩn ✅, URL remote ✅ (status), SHA không gắn vào run ❌. |
| 3 | Tier 1 / Tier 2 / Tier 3 | ✅/⚠️ | Có 3 tier; ngưỡng 24k (CONTEXT_MEMORY yêu cầu watermark 16k→2k, chunk 3 500). |
| 3 | Graph node ↔ ClearML `task_id` | ❌ | Không có trường. |
| 3 | Context Decision Agent pin/purge | ✅ | `context_graph.agent`, `apply_ops`. |
| 4 | Author→Reviewer→Editor từng section | ✅ | `paper_stream` actions `draft/review_section/revise`. |
| 4 | Section briefs & result injection | ✅ | `brief.py`, `api_v31.py`. |
| 4 | Citation guard + `[CITATION NEEDED]`/`[TBD]` đỏ | ✅ | `paper.fix_citations`, `assemble` report. |
| 4 | Local Critic async khi stream | ❌ | Không có. |
| 4 | Deterministic LaTeX compile + log theo section | ✅ | `latex_build.compile_pdf`, `parse_log`. |
| 5 | DataConnectorRegistry `backend/connectors/` | ❌ | Không có. |
| 5 | Artifact provenance injection | ❌ | Không có. |

## 6. Mapping CUSTOMER_REQUIREMENT.md → hệ thống

| Kịch bản / giai đoạn | Đã có | Thiếu (baseline) | Xử lý trong v3.2 |
|---|---|---|---|
| KB1 Lit2Plan: PDF → SOTA → gap → giả thuyết ID ghim lên graph | Thư viện PDF (`library.py`, pypdf), Lit2Plan, parse H1..Hn vào Tier 3 | ID giả thuyết bền (`HYPE-NNN`), node graph riêng, routing local→cloud có chủ đích | Research Memory cấp `HYPE-NNN` ổn định khi plan sinh ra; node hypothesis trên graph; router `auto`. |
| KB2 Self-healing sandbox | Co-coding agent AUTO mode, stderr → patch → chạy lại (`ide_agent`) | JIT VRAM unload trước khi chạy | Hook JIT unload trong `start_job`. |
| KB3 Truy vết minh chứng từ ảnh | — | Toàn bộ | `provenance.py` (PNG tEXt/JPEG COM/CSV header + sidecar), `/api/provenance/inspect`, tra run local + ClearML. |
| KB4 Live Critic | Citation guard sau khi viết xong | Critic chạy song song khi stream | `critic.py` (kiểm tra xác định + LLM local tùy chọn), event `critic` trong SSE, badge đỏ. |
| GĐ2 Open in VS Code + Dockerfile/devcontainer giới hạn 6 core/16 GB | — | Toàn bộ | `integrations/workspace.py` + Environment Manager. |
| GĐ2 Ghim `git_sha` | — | — | Run lưu `git.sha/branch/dirty`. |
| GĐ5 latex.zip + ClearML deep link | latex.zip ✅ | ClearML link | `ClearMLAdapter` + `web_url`. |

## 7. Rủi ro & ràng buộc

| Rủi ro | Mức | Ghi chú / giảm thiểu |
|---|---|---|
| Không có test → regression khi nâng cấp | Cao | v3.2 thêm bộ `unittest` (stdlib, không cần cài) chạy trên thư mục dữ liệu tạm (`PHDLAB_DATA_DIR`). |
| DNS-rebinding: trang web độc hại có thể gọi `127.0.0.1:8765/api/sandbox/run` (chạy shell) | Cao | Thêm kiểm tra `Host` (TrustedHost) — chỉ `localhost`/`127.0.0.1`/`[::1]`. Lưu ý: FastAPI yêu cầu `Content-Type: application/json` cho body dict nên CSRF form đơn giản bị chặn, nhưng rebinding thì không. |
| Local mode sandbox chạy `shell=True` trên host | Trung bình | Đã có từ v3.0, dùng cho người dùng cục bộ; giữ nguyên, ghi rõ trong tài liệu; khuyến nghị Docker. |
| 12 GB VRAM: LLM 14B (~9 GB) + training không vừa | Cao | JIT unload + GPU-busy routing (cloud hoặc Ollama CPU offload). |
| ClearML/Codex/Jupyter không có trên máy audit | Trung bình | Adapter báo trạng thái thật (`unavailable`/`unconfigured`), không giả lập thành công; test thật opt-in. |
| `data/` chứa config với API key | Cao | `data/config.json` đã gitignore; tài liệu & test không đọc/ghi config thật. |
| Đổi `memory.py` thành package | Trung bình | Giữ nguyên toàn bộ tên public (re-export), dữ liệu `project_state.json` tương thích ngược. |
| Python 3.14 trên máy, launcher hỗ trợ ≥ 3.9 | Thấp | Không dùng cú pháp > 3.9 trong module mới (`asyncio.wait_for` thay vì `asyncio.timeout`). |
| Console Windows cp1252 | Thấp | Subprocess dùng `encoding=utf-8, errors=replace` (đã có). |

## 8. Nguồn tham khảo cho thiết kế Context Memory

- Stingy Context / TREEFRAG — arXiv:2601.19929 (preprint, 1 tác giả, kết quả chưa được bình duyệt độc lập). Ý tưởng sử dụng: cây phân cấp 7 mức chi tiết (LOD 1 tên → 2 category → 3 type → 4 tag line → 5 mô tả ngắn → 6 commentary → 7 raw); chỉ serialize LOD thấp, raw bị loại trừ trừ khi mở rộng; đặt metadata then chốt ở **hai đầu prompt** để giảm "lost in the middle".
- General Agentic Memory (GAM) — arXiv:2511.18423. Ý tưởng sử dụng: Memorizer (offline) ghi *memo* gọn + *page* `{header, content=raw}` vào page-store; Researcher (online) chỉ đọc bằng vector + BM25 + truy cập theo page-id. Paper không dùng thuật ngữ "write isolation"; ở đây hiểu là **chỉ một đường ghi (memorizer) và raw không bao giờ bị sửa**, đường đọc không ghi ngược.
