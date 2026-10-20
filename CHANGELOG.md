# Changelog

## v4.1.0 — 2026-10-20 — Model lifecycle · secure CLI space · workflow orchestrator (Optuna HPO, model intelligence)
All v4.0 data, settings and APIs keep working. Reports: `docs/architecture/v4.1-audit.md`, `docs/architecture/v4.1-final-report.md`.
- **Model lifecycle** (`backend/model_lifecycle.py`, Settings → Model lifecycle & resources): Load → task → unload /
  Keep loaded / Unload when idle, chosen separately for local background tasks, local chats, CLI agents, MCP tools &
  sandbox container and cloud connections. Background agents and embeddings unload their local model after the task
  by default. Live VRAM panel (also in Settings → Local AI): resident models, owner, countdown, manual **Unload** /
  **Unload all**. A model that is answering is never unloaded; your own loads are respected; one PhD-Lab model in VRAM
  at a time; opt-in automatic VRAM release before GPU training. Cloud calls reuse pooled HTTPS connections.
- **Secure CLI space** (`backend/gateway/workspace.py`): Codex / Claude Code / Antigravity / Gemini CLI now run in a
  per-session workspace (never the project folder) with an allowlisted environment, a read-only context manifest,
  time limit and process-tree cleanup. Security profiles review / assisted, fail-closed per provider (consent for
  weaker isolation). Fix: a CLI process was left running when the client disconnected right after the first event.
- **Workflow Orchestrator** (`backend/workflow/`, new 🧭 Workflows page): manual / assisted / bounded / custom modes,
  per-step autonomy, approve / edit / revise / reject / provide-result gates, budgets (trials, cycles, agent calls,
  runtime), pause / resume / cancel, recovery after restart, nested workflows, 11 versioned templates, SSE timeline.
- **HPO**: deterministic search-space validator (bounds, log, conditions, leakage, budget), Optuna (TPE / random /
  grid / NSGA-II, pruning, persistent resumable studies) with a builtin fallback, local sequential runner, Ray Tune
  adapter behind a flag (refuses until validated), Pareto fronts, confirmation runs with 95 % CI.
- **Model Intelligence**: spec / PyTorch (sandbox) / ONNX adapters; params, MACs/FLOPs, memory, latency, feasibility
  vs. this PC — every value labelled MEASURED / ESTIMATED / UNAVAILABLE.
- Tests: 184 → 341 (+ Node frontend tests). New modules: 100 % line + branch coverage; changed lines: 100 %.

## v4.0.0 — 2026-10-20 — Research-state-aware Context Memory · AI Gateway (ChatGPT / Claude / Antigravity) · environments · new UI
All v3.2 APIs, data files and settings keep working (v3.2 records are read as-is; new fields are optional). Reports:
`docs/architecture/backend-v3.3-final.md`, `docs/architecture/provider-integration-v3.4-final.md`.
- **Research State** (`memory/state.py`): objective, active hypothesis (researcher focus first), current experiment, baseline,
  constraints/hardware, locked decisions, known failures, best validated results, `context_version`.
- **State-aware, explainable retrieval** (`memory/engine.py`): keyword (stemmed BM25) · vector · state · graph · metadata ·
  intent · temporal → weighted RRF → per-role scoring; every hit says *why* (`components`, `ranks`, `reasons`),
  `POST /api/memory/explain`. Metadata filters, current/history temporal modes.
- **Role-aware compiler** (7 roles, explicit `Budget`, RESEARCH STATE and EVIDENCE & CLAIMS sections, dedup, per-tier
  low-value cut, LOD compression, CONTEXT TRACE). Same function signatures as v3.2.
- **Evidence layer** (Claims/Evidence with copied provenance; AI evidence is never self-validated), **provenance chain**
  (`/api/provenance/chain/{id}`), **structured failure memory**, decisions with evidence/provider/session/supersedes.
- **Memory lifecycle**: AI/provider/MCP writes become review **candidates** (classified, deduplicated) — `/api/memory/candidates`.
- **Performance** (profiled first): sparse hashing vectors, fingerprint-keyed caches. At ~4–5k nodes retrieval 614 → 59 ms,
  compilation 635 → 84 ms; golden-task recall@5 0.47 → 0.94 (dev), clean held-out MRR 0.64 → 0.89.
- **Fixes**: libraries over 300 papers silently lost papers; Windows read/replace race under concurrent writers; a corrupt
  JSON store was overwritten on the next write (now quarantined as `.corrupt-<time>`); consolidation dropped raw-page
  pointers; same-second ordering of decisions/experiments.
- **Context Gateway** (`backend/gateway/`): one canonical research context for every provider; first-party connectors
  only — ChatGPT via Codex CLI (ChatGPT sign-in), Claude Code CLI, Google Antigravity (MCP client + `agy` CLI), Gemini CLI;
  normalised streaming (SSE), multi-provider sessions and comparison, review-before-external, sensitivity classes
  (PUBLIC/INTERNAL/SENSITIVE/RESTRICTED), credential redaction, cost guard (vendor API keys removed from CLI processes, no
  automatic fallback), content-free audit.
- **MCP research tools**: 12 `research_*` tools (strict schemas, structured results with provenance; `record_*` only create
  candidates) beside the sandbox tools; optional bearer token, Origin check, rate limit, audit (`config.mcp`).
- **Telemetry**: `/api/telemetry` (p50/p95, cache hit rates); never logs prompts or memory content.
- Tests: 90 → 165.
- **Execution environments** (`backend/envs.py`, `backend/deps.py`, Workspace & Runs → Environment): Auto / Python
  environment (any interpreter found on the machine — also those not on PATH, conda, py launcher — as a project venv or
  used directly) / Docker (recommended image, vetted catalog, local images, Docker Hub search with tags, custom names).
  **Automatic dependencies**: requirements/pyproject/environment.yml + imports of .py/.ipynb, installed inside the target
  environment right before the run in the same log (only what is missing; CUDA PyTorch wheels on NVIDIA machines).
  "Prepare environment" does it ahead of time. Guide: `docs/integrations/environments.md`.
- **Jupyter / Dev Container fixed**: JupyterLab is found in any Python on the machine (a `pip install jupyterlab` into
  the system Python was invisible to the app's own .venv); notebooks get a "PhD-Lab · <project>" kernel of the project
  environment. Dev Container is one click: installs the Dev Containers extension and generates `.devcontainer/` from the
  sandbox image when missing.
- **UI for v3.3/v3.4 backend**: Context tab → Context Memory (Research state with focus, Retrieval & trace with reasons and
  sharing level, Evidence & claims, Candidates review, Storage tiers); new **AI Gateway** page (ChatGPT/Claude/Antigravity/
  Gemini status, sign-in, MCP setup, ask/compare with review-before-sending, streamed answers, save to memory); Settings →
  MCP & privacy.
- **Fixes**: Space could not be typed in the Dataset / Memory-inspector search (a key handler returned false); Browse
  buttons on every project path field (new/open project, datasets folder) — choosing the data folder suggests the name.
- **Frontend shell (2026 refresh)**: the top tab bar and the configuration sidebar are replaced by one left **navigation
  rail** (grouped Research / Knowledge / System, line icons, collapsible to icons, drawer on phones, arrow-key navigation)
  and one **Settings** page (Research project · Cloud AI · Local AI · Agent engines · Internet search · Language &
  appearance · links to the feature-level settings), with section search, scroll-spy menu and a sticky save bar that
  shows unsaved changes. Slim top bar with page title, **command palette** (Ctrl+K) and a light/dark toggle; deep links
  (`#settings/cloud`, `#ide`). New design tokens (neutral surfaces, single accent, AA contrast in both themes, visible
  focus, `prefers-reduced-motion`). All element ids are unchanged; `frontend/app/shell.css`, `frontend/app/shell.js`.

## v3.2.0 — 2026-10-20 — Research control plane: Context Memory v2, integrations, hardware governor
All v3.1 features and data are kept (backward compatible). See `ARCHITECTURE_AUDIT.md`, `ARCHITECTURE.md`, `MIGRATION_PLAN.md`, `INTEGRATION_STATUS.md`.
- **🧠 Context Memory v2** (`backend/memory/` package; `memory.py` moved to `memory/__init__.py`, same API and data):
  - Working / Research / Knowledge memory. **Research Memory** gives plan hypotheses stable `HYPE-NNN` ids and stores experiment records (`EXP-NNN`: hypothesis, run, **ClearML task id**, git commit, dataset version, observation, interpretation, decision, conclusion, next action, verdict) and validated failures (`FAIL-NNN`) — pointers + scientific meaning, never a copy of the tracker.
  - **Retrieval engine**: BM25 ‖ vector (Ollama embeddings, or labelled lexical hashing vectors) ‖ graph spreading → reciprocal-rank fusion → reranker (heuristic or an HTTP bge-reranker).
  - **Deterministic context compiler**: `[CONTEXT SYSTEM INJECTION]` with *Current working state / Related experiment evidence (ClearML pointer) / Foundational scientific knowledge*, token-budgeted, TREEFRAG-style levels of detail, focus line at the end against lost-in-the-middle. Used by every chat, Lit2Plan, Experiment Design and the co-coding agent (legacy block as fallback; `memory.v2_pipeline`).
  - **Compressor**: watermarks 16 000 → 2 000 tokens, 3 500-token chunks summarised in parallel to strict JSON memos with timeouts, hierarchical reduce, entity wiring (run ids, task ids, commits, HYPE ids) into the context graph. Raw turns are snapshotted into a write-once **page-store** first (GAM-style write isolation); chat files are never deleted.
- **💻 Workspace & Runs replaces the Monaco Code IDE** (Monaco, xterm and `ide.js` removed, −6.6 MB): code is written in VS Code with the Codex extension (`openai.chatgpt`, one-click install) or Codex CLI. The tab keeps sandbox runs with live log and curves, runs (metrics, figures, git commit), the self-debugging agent (text diffs, files open in VS Code) and Git/GitHub. Experiment Design → *Open in VS Code*.
- **VRAM rule for GPU training**: a GPU run is refused (HTTP 409 `vram_busy`, dialog in the UI) while Ollama / LM Studio hold a model; the researcher presses 🧹 *Unload* or runs on CPU — nothing is unloaded automatically. Fixed LM Studio unload for builds that require `instance_id` (REST v1); loaded-model detection also reads REST v1.
- **ClearML through the Python SDK, no server needed (offline mode, default):** `pip install clearml` is a separate, non-fatal step of `setup.bat` (and a button in Control Center → Integrations). Every finished sandbox run is recorded as a ClearML offline session in `<project>/clearml/offline/` (parameters, curves, final metrics, log tail, artifacts, research-code git commit), listed and read back in the UI, linked from the run and Research Memory; scripts that call `Task.init` themselves get `CLEARML_OFFLINE_MODE=1` and their session is linked instead of duplicated. Server mode and *Import to server* use the same worker. The SDK only runs in a subprocess (`clearml_worker.py`).
- **JupyterLab, Codex CLI and ClearML wired to the app's Python environment:** JupyterLab starts as `python -m jupyterlab` (found without PATH), token-protected on 127.0.0.1, kernels get the project context and ClearML offline mode (a notebook's `Task.init` lands in the project's sessions); research notebook template; 📓 Jupyter / ＋ Notebook buttons. Codex runs through `node codex.js`, with the Windows sandbox passed per run (`codex.windows_sandbox`, default *unelevated* — without it Codex blocked every shell command) and a correct `resume` command; verified with real runs. The local sandbox venv now inherits the app Python's packages (`inherit_packages`).
- **🧭 Control Center tab**: dashboard, **research timeline**, workspace hand-off, integration status, Codex, resources, provenance inspector, memory inspector, dataset search.
- **Integration layer** (`backend/integrations/`): honest status contract; VS Code open/deep link/Dev Container; **Environment Manager** (Dockerfile + devcontainer.json with the machine's caps); Jupyter launcher; `ExperimentBackend` with local runs and **ClearMLAdapter** (sync run, get task, remote submit with local fallback); **CodexBackend** (`codex exec --json`, read-only by default).
- **Hardware governor** (`backend/resources.py`): policy derived from the scanned PC, hard sandbox caps, VRAM gate + manual unload, thermal guard, CPU re-run after GPU faults, GPU-busy aware routing, Ollama CPU offload (`num_gpu: 0`).
- **LLM gateway**: DeepInfra, 9Router, OmniRoute providers; engine mode **`auto`** (SmartMultiRouter: task kind, online check, GPU state, sequential fallback); optional sanitised `X-…` gateway headers.
- **Live critic** in the Paper Writer: LaTeX/math/citation checks while the section streams (+ optional local-model critic), red badges that jump to the line.
- **Provenance**: run artifacts (PNG/JPEG/SVG/CSV) sealed with run id, git commit and ClearML task; `runs/<id>/provenance.json`; inspector finds the run (and ClearML task) from a dropped figure.
- **Traceability**: every run records the git commit (+ dirty flag) and its environment.
- **Data connectors**: `backend/connectors/` registry with Hugging Face and Kaggle plugins; `/hf`, `/kaggle`, `/dataset` in the Data chat.
- **Security**: the server only answers `Host: localhost/127.0.0.1/[::1]` (DNS-rebinding protection); ClearML secrets masked like other keys.
- **Tests**: first automated suite (`tests/`, stdlib unittest, 72 tests incl. real sandbox runs); opt-in live tests for ClearML, Codex and LM Studio.

## v3.1.0 — 2026-10-18 — Writing briefs & your own results
- **Fix: "I run run.bat but do not see the new tabs".** When an older copy of the lab was still running (its black window open), `run.bat` used to open the browser on that old server. The launcher now checks the version (and folder) of the running server: a different version → it starts the new one on the next free port and prints a clear warning to close the old window. The page is served with `no-cache` and versioned script links, so a browser can no longer show stale files after an upgrade; a red banner appears if page and server versions differ. New `GET /api/version`.
- **📥 Your research results (Experiment Design tab):** drop results you produced outside the app — images (PNG/JPG/SVG/EPS), PDF, LaTeX, Markdown, CSV/TSV, Excel, Word, notebooks, JSON, logs, code — or type a result by hand.
  - Stored per project in `data/results/` (original file + extracted text + your description, tags, metrics); deleting moves to `data/results/_trash/`.
  - **✨ Analyze:** the Results analyst agent reads the file or the **image (vision)** and writes the key numbers, findings, caveats and a suggested caption — grounded only in the file.
  - **▦ LaTeX table:** CSV / Markdown / Excel / .tex → booktabs table added to the Paper Writer (a `.tex` table is kept verbatim; non-table model output is rejected).
  - **Context:** every chat and the Experiment designer receive a digest of your results; results appear as nodes in the 🧠 Context graph; 📌 pin (must-follow) or 🙈 hide from AI per result.
  - **✍ Use in paper:** send a result to any section's brief, choosing how to present it.
- **🎯 Brief per paper section (Paper Writer):** replaces "Instructions for AI" (old instructions are kept as the directions).
  - Directions & wishes with one-click suggestions per section; **results to present** chosen from uploads, Code IDE runs and run figures, Writer tables and results notes — each with *present as* (auto / table / figure / numbers in text / comparative analysis / headline result), a note, and an order; "present only the selected results".
  - Required structure (ordered outline), must include, must avoid, tone, length or target words, references to emphasise.
  - **🧭 Paper-wide brief:** overall story & key claims, style, terminology & notation, never-do — applied to every section.
  - Sent to the Author (3.2), the Editor (3.4) and the section Reviewer (3.3, which now reports deviations from the brief) in quick and deep modes. **👁 Preview what the AI receives**, ⧉ copy a brief to other sections, 🎯 marks on the section board.
  - **Figures:** a figure chosen in a brief is inserted with the exact `\includegraphics{figures/…}` line and label; the file is copied into the PDF preview build, `latex.zip` (`figures/`) and `project_export.zip`.
- New agent: 📊 Results analyst (cloud by default; vision-capable models read figures). New endpoints under `/api/results/*` and `/api/paper/brief*`.

## v3.0.0 — 2026-10-18 — Unified stateful multi-agent research IDE
All earlier features are kept; three new tabs and a shared project state connect them.
- **💻 Code IDE tab (VS Code-style):** activity bar (Explorer, Search, Source Control, Runs, Docker), Monaco editor with tabs, diff view, image preview, LaTeX/BibTeX highlighting; xterm terminal with a command line; live metric charts; resizable panels.
  - **Co-coding agent:** 💡 Suggest (proposals with diff / apply / apply all) or ⚡ Auto (apply → run → read stderr → fix, up to N attempts). Context: locked decisions, pinned items, memory, Tool 2 blueprint, workspace snapshot, last run.
  - **Start from the blueprint** seeds `data/code/` from Tool 2. Files deleted from the explorer go to `code/.trash/`.
  - **Runs:** every run is stored in `data/runs/<id>/` with logs, `metrics.json`, parsed log metrics and figures; run view with curves; *Use results in the paper* → Writer notes + booktabs table of measured numbers.
  - **Source Control / GitHub:** init, status, diff, commit, discard, push, pull, **Publish to GitHub** (public/private) with a Personal Access Token (stored in `data/config.json`, sent only to GitHub, never written to `.git/config`). Uses GitPython when installed, the git CLI otherwise.
- **🐳 Docker sandbox:** one persistent container per project via the Docker CLI (`docker exec` jobs, Stop kills the process), memory/CPU/shm limits, optional network, **GPU passthrough** with automatic CPU fallback, image pull with progress; local venv mode when Docker is absent.
- **🐳 Docker & System tab:** detailed live monitor (2 s): Docker daemon, sandbox container, GPU util/VRAM/temperature/power, container CPU/RAM/PIDs/IO, host RAM/CPU/disk, sparklines; container actions; Test GPU; settings; jobs with log viewer; images/containers; local AI servers.
  - **Machine scan + recommended setup:** OS, CPU, RAM, NVIDIA GPU/driver/CUDA, Docker (+ GPU runtime), WSL2, Git, LaTeX, Ollama/LM Studio → sandbox image and limits, local model size for your VRAM, agent engines; one click to apply. Scan cached in `data/system/`.
- **🧠 Context tab:** vis-network knowledge graph of the project (objectives, hypotheses, decisions, constraints, literature, code assumptions, metrics, episodes); inspect / edit / **📌 pin** (MUST-FOLLOW context for every agent) / **🗑 purge** (hidden from agents, purged papers leave the reference digest) / add / delete; **Context Decision Agent** that proposes graph operations you approve.
- **Hierarchical memory** (`data/memory/project_state.json`): Tier 1 working memory (recent turns + sandbox logs), Tier 2 episodes written by a **background summarizer on the local model** when Tier 1 passes the threshold, Tier 3 long-term knowledge (goals, hypotheses, constraints, best metrics, references, decisions). Injected into every chat within a token budget.
- **Lit2Plan ⇄ chat:** 🔒 Lock decisions from any answer or selected text (direction / hypothesis / gap / constraint / rejected); locked decisions bind all agents; **🔄 Regenerate overview** from the discussion; **🕘 Versions** with restore.
- **Local AI fixes:** LM Studio model list with **Load / Unload / Use** (REST API → `lms` CLI → JIT); **Ollama** support (list, load with keep-alive, unload, pull with progress); per-agent model override; changing an agent's engine/model now updates every open chat immediately (**live engine · model badge** + quick switcher in each chat header).
- **MCP server:** `POST /mcp` (JSON-RPC: initialize, tools/list, tools/call) with `sandbox_run_code`, `sandbox_manage_files`, `sandbox_get_metrics`; `mcp_stdio_bridge.py` for stdio clients.
- **⬇ project_export.zip:** paper, plan, code, runs/metrics/figures and memory in one archive.
- New agents: Co-coding (local), Memory summarizer (local), Context decision (cloud). New settings: `ollama_base_url`, `ollama_model`, `agent_models`, `github`, `memory`.
- Vietnamese interface covers all new views. `setup.bat` reports optional tools; `start.py --check` lists Docker/Git/GPU/LaTeX/Ollama.
- Vendored offline: Monaco 0.52.2, xterm.js 5.5.0, vis-network 9.1.9 (licenses included).

## v2.7.0 — 2026-10-17
- **📄 PDF preview in the Paper Writer:** compiles main.tex + references.bib with the LaTeX installed on your computer.
  - Engines: pdfLaTeX + BibTeX, latexmk, XeLaTeX or Tectonic, found on PATH and in the usual MiKTeX / TeX Live / MacTeX folders.
  - The PDF appears right under the editor, with a full-screen reader and ⬇ main.pdf.
  - **Auto-compile** after every agent run and every Save.
  - **Error list mapped to sections:** click an error to jump to and select the offending LaTeX in the editor. Undefined references/citations and leftover placeholders are reported. The build log is viewable.
  - **Quick layout:** if IEEEtran / acmart is not installed, the preview is compiled with the article class (with shims for IEEE/ACM commands), so it always shows; a note tells how to install the real class.
  - Install help when no LaTeX is found. Optional, opt-in online compilation (LaTeX-on-HTTP).
- **LaTeX syntax highlighting** in the section editor and the main.tex preview: commands, environments, sections, citations/refs/labels, math, comments, braces and red [TBD]/[CITATION NEEDED] placeholders, in both themes; also while the agents stream.
- Editor: Tab inserts spaces; Ctrl+S saves the section.
- New endpoints: `GET /api/latex/engines`, `POST /api/latex/compile`, `GET /api/latex/pdf`, `GET /api/latex/log`.

## v2.6.2 — 2026-10-17
- **Read PDFs directly in the app:** 👁 Read button (or click a paper title) in the Reference Library opens a large in-app reader using the browser's built-in PDF viewer (zoom, search, page thumbnails, print).
  - Title, authors, venue and the BibTeX key (click to copy) are shown above the PDF.
  - Previous/next paper with ‹ › or the ← → keys; open in a new tab or download.
- Citation chips: "📕 Read PDF" opens the same reader.

## v2.6.1 — 2026-10-17
- **📌 Shared-context button in the header** (next to the project name): shows the number of pinned notes, pulses when a new note is pinned, and opens the shared-context window from any tab.
- **Shared-context window redesigned:**
  - Each pin collapses to a one-line preview or expands to the full note; Expand all / Collapse all.
  - **Keyword search** across text, source and tool, with highlighted matches; previews jump to the first match, and a few matches open automatically. Esc clears the search.
  - Filter by tool; copy or delete a single note; larger scrollable window; "Add a note manually" folded away.

## v2.6.0 — 2026-10-17
- **Internet search for the AI agents.**
  - **🌐 selector in every chat:** off / 📚 papers / 🌐 web / both, remembered per tool.
  - **Sources:** papers from OpenAlex, arXiv and Semantic Scholar (free, no key); web from DuckDuckGo (free) or Tavily / Brave (API key).
  - **Per question:** a planner agent writes the queries (with a year filter for "latest" questions). Results are de-duplicated by DOI and numbered [S1]…, injected into the prompt with strict cite-only-listed-sources rules, and the answer cites them as links.
  - **Search progress is streamed live.** Sources are saved with the message and included in Markdown exports.
- Under each answer: a sources list with 📥 *save open-access PDF to the Reference Library* (with database metadata) and 📎 *attach full text*.
- **Lit2Plan:** optional online literature search while planning, adding a "Key Papers Found Online" section and a sources card (restored after refresh).
- **Reference Library:** new **🔎 Find papers online** box.
- **Sidebar → 🔎 Internet search:** web engine and keys (stored locally, masked), results per search, Semantic Scholar key, OpenAlex e-mail, read top pages.
- New agent **🌐 Search query planner**. New endpoints: `POST /api/search`, `POST /api/references/fetch`; chat endpoints accept `web`.

## v2.5.0 — 2026-10-17
- **Paper Writer redesigned as a section workshop:**
  - **⚡ Quick pipeline** or **🔬 Deep · section by section**: write → in-depth section review (score /10, Critical/Major/Minor issues with quotes, missing content, citation check, rewrites) → revise, 1–3 rounds per section; skip accepted sections, pause after each section, final whole-paper review.
  - Sticky control bar with a clickable stepper (run any step alone).
  - Section board (status, words, score, quick actions) and a workspace with live-streamed LaTeX, a section-review tab, and per-section instructions for the AI.
  - ✓ Accept, plus an in-depth writing option for single runs.
- **■ Stop** for every agent run: aborts the stream and cancels the upstream AI request; finished steps are kept and the interrupted step is discarded (the section keeps its previous text).
- **New ④ Paper Review flow** for finished manuscripts (PDF/DOCX/TEX/MD):
  - **Venue calibration:** conference by ICORE rank C/B/A/A* or h5-index band, journal by Q1–Q4. Optional venue name and track, double-blind mode, and 1–3 reviewer personas.
  - **Review stages:** automatic desk check (anonymity leaks, missing sections, leftover placeholders); streamed reviewer reports; area-chair / editor meta-review with decision and phased revision roadmap; de-duplicated issue list Critical → Typo with quote verification.
  - **Revising:** quick fixes with word-level diff and action plans; batch "Fix critical / Fix all"; apply accepted fixes to the LaTeX source (`…_revised.tex`).
  - **Outputs:** response-to-reviewers letter, Markdown report and fixes, and a follow-up chat with the area chair.
- New agent engine option **✳ Claude preferred** (Anthropic when it has a key, otherwise the default provider), used by the review agents.
- Paper project: new **Target venue** field (calibrates the section reviewer).
- New endpoints: `POST /api/paper/stream` (SSE: draft / review_section / revise / review); `/api/review/*` (upload, settings, source, stage, fix, issue, apply, download).

## v2.4.0 — 2026-10-17
- Interface language **English / Tiếng Việt** (EN / VI switch in the header, auto-detected from the browser, remembered). All labels, placeholders, tooltips, dialogs, toasts, pipeline logs and dynamically created UI are translated; AI answers, Markdown output, code, formulas and user input are never touched. The Guide follows the interface language.
- **AI output language (Tools 1, 2, 4):** follow interface / always English / always Vietnamese; technical terms, citations, math and code stay in English; LaTeX papers are always English.
- Fix: a provider returning non-JSON now gives a clear error instead of HTTP 500.

## v2.3.0 — 2026-10-17
- New **📘 Guide** tab: detailed user guide in Vietnamese and English (quick start, architecture & cost, projects, Tools 1–4 best practices, chats/attachments/shared context, 6-month workflow, quality tips, shortcuts, backup/upgrade, troubleshooting) with table of contents, scroll-spy and search; language remembered.

## v2.2.1 — 2026-10-17
- `start.py` verifies the installation before starting: all required files present and `start.py`/`backend` versions identical; a partial upgrade (new files copied over an old version) now gives a clear explanation and the 3-step fix instead of a ModuleNotFoundError.
- Linux/macOS: automatic `./.venv` when the system Python is externally managed (PEP 668); an existing `.venv` is reused even when started with the system `python3`.
- New `run.sh` launcher; `start.py --check`.
- Tested on Linux with Python 3.14.

## v2.2.0 — 2026-10-17
- 📁 Browse buttons for the project Data folder and References folder: native OS folder dialog, with a built-in themed folder browser as fallback (drives, Home, up, new folder, PDF count, project detection).
- New searchable model picker (cloud and LM Studio) replacing the browser's datalist/select: grouped "Suggested" / "Available on your account", filter-as-you-type, keyboard navigation, current/default markers, follows light/dark theme; fetched model lists are remembered.
- New endpoints: `POST /api/fs/pick-folder`, `GET /api/fs/list`, `POST /api/fs/mkdir`.

## v2.1.0 — 2026-10-17
- Light / dark / auto (follow OS) appearance, switch in the header; applied before first paint (no flash); code highlighting theme follows.
- Fix: wide code blocks, tables or formulas no longer stretch the result column past the window; each tab now scrolls on its own.
- Fix: tab handler no longer captures other header buttons.

## v2.0.0 — 2026-10-17
- Claude-style chat UI for every tool: streaming answers (SSE) with Stop, Retry, Edit-and-resend, reading view, jump-to-latest.
- Attachments: files (PDF/DOCX/PPTX/XLSX/CSV/code/notebooks/HTML), images (vision input for Claude, GPT, Gemini…), web links and online PDFs, papers from the project library; drag & drop, paste, previews; stored per project.
- Rich offline rendering: marked + DOMPurify + KaTeX + highlight.js bundled in `frontend/vendor/` (no CDN needed); code blocks with Copy/Save; math no longer applied inside code blocks (fixes broken LaTeX tables) or to prices like "$5"; `\(…\)` and `\[…\]` math supported.
- Citation chips for `[bib_key]` / `\cite{}` with Open PDF / DOI / Attach-to-chat.
- Enter-to-send with IME (Vietnamese Telex) protection; auto-growing composer.
- New endpoints: `POST /api/chat/stream`, `POST /api/attachments`, `/api/attachments/link`, `/api/attachments/paper`, `GET /api/attachments/{id}/raw|text`, `GET /api/library/catalog`, `GET /api/references/file/{name}`.

## v1.6.0 — 2026-10-17
- Multiple research projects: each project has its own data folder (workspace, outputs, chat sessions, pinned notes, library) and its own references folder; switch from the sidebar, active project shown in the header.
- New / open existing folder / rename / remove-from-list (non-destructive) / open in Explorer.
- Existing `data/` + `references/` become the "Default project" automatically; API keys and engines stay global.
- New endpoints: `GET/POST /api/projects`, `POST /api/projects/open|activate|forget|open-folder`, `PUT /api/projects/rename`.

## v1.5.0 — 2026-10-17
- Follow-up chat for every tool: Tool 1 (Lit2Plan), Tool 2 (Experiment), Tool 3 (Data chat + new Paper chat), Tool 4 (Masterclass), built on one reusable chat component with per-tool session lists.
- Shared Context Hub: optional sharing of other tools' latest outputs, recent chats and 📌 pinned notes; pin a whole answer or a text selection.
- Sessions snapshot the tool output they discuss; a new tool output starts a new follow-up session automatically.
- Tool 1/2/4 outputs restored after refresh; masterclass guide now saved to the workspace.
- New endpoints: `POST /api/tool-chat`, `GET /api/tool/output/{tool}`, `GET/POST/DELETE /api/context/notes`; `/api/chat/sessions?tool=`.
- New agents in the engine selector: Chat · Tool 1-4.

## v1.4.0 — 2026-10-17
- Multiple chat sessions: session picker, ＋ New chat, rename, delete (to `_trash/`), export to Markdown.
- One JSON file per session in `data/workspace/chat_sessions/`; titles generated from the first question until renamed.
- "Auto-open last session on start" option (saved in config); off = start with a fresh chat.
- New endpoints `GET/POST /api/chat/sessions`, `GET/PUT/DELETE /api/chat/sessions/{id}`; `/api/chat` accepts `session_id`.
- v1.3 `chat_session.json` is migrated automatically into a session.

## v1.3.0 — 2026-10-17
- Chat session persistence: every completed Q&A turn is saved by the backend to `data/workspace/chat_session.json`; the UI restores the full history (messages, LaTeX tables, "table added" state, engine, timestamps) on page load.
- New endpoints: `GET/PUT/DELETE /api/chat/session`.
- The question is saved before the AI answers, so a refresh or crash mid-answer does not lose it.
- Atomic writes, input sanitisation, automatic recovery from a corrupted file, backup on Clear.
- Consecutive user messages (e.g. an unanswered question after a refresh) are merged before calling the LLM.

## v1.2.0 — 2026-10-17
- Multi-provider cloud AI: Anthropic Claude, OpenAI ChatGPT, Google Gemini, xAI Grok, DeepSeek, Mistral, Alibaba Qwen, Moonshot Kimi, Cohere, Perplexity, Groq, OpenRouter, Together AI, and any custom OpenAI-compatible endpoint.
- Per-provider API key, model (with live "List models"), base URL, and connection test.
- Per-agent engine selector: Default cloud / Local (LM Studio) / specific provider.
- Automatic handling of provider parameter differences (`max_completion_tokens`, fixed temperature).
- v1.0/v1.1 settings are migrated automatically (Claude key and model kept).

## v1.1.0 — 2026-10-17
- Robust launcher `start.py` (checks Python, installs missing packages, frees port, opens browser when ready).
- Works under Windows 11 Smart App Control: pure-Python PDF engine (pypdf) fallback and pure-Python server stack.

## v1.0.0 — 2026-10-17
- Initial release: Lit2Plan, Experimental Design, PDF library + Data Chat + multi-agent LaTeX writer, Masterclass, `latex.zip` export.
