# PhD Interactive Autonomous Research Lab — v4.0.0

A local desktop web app for Windows 11 (and Linux/macOS) that runs an end-to-end research workflow on a **hybrid AI architecture**: any of 14 cloud AI providers for deep reasoning and academic writing, plus local models in **Ollama** (recommended) or **LM Studio** for fast, private, zero-cost work.

**v3.0 — a unified, stateful multi-agent research IDE:**
- 💻 **Code IDE** tab *(replaced in v3.2 by VS Code + Workspace & Runs)*: runs/metrics/figures, Source Control with **Publish to GitHub**, and an AI **co-coding agent** that writes code from your Tool 2 blueprint, runs it in a **Docker sandbox** (GPU passthrough) and fixes errors from stderr by itself.
- 🐳 **Docker & System** tab: live, detailed monitor of Docker, the sandbox container, GPU/VRAM, host RAM/CPU/disk, jobs and logs; it scans your PC and offers a one-click **recommended setup**.
- 🧠 **Context** tab: knowledge graph of everything the agents know (📌 pin = must follow, 🗑 purge = hidden), a Context Decision Agent, and **3-tier project memory** kept small by a background summarizer running on your local model.
- 🔒 **Lit2Plan decisions:** lock directions/hypotheses/rejections from the chat; 🔄 regenerate the research overview after many discussions; 🕘 versions.
- 🖥 LM Studio **Load / Unload** buttons, 🦙 Ollama support (pull, load, unload), per-agent model choice with **live badges** in every chat.
- 🔌 MCP server (`sandbox_run_code`, `sandbox_manage_files`, `sandbox_get_metrics`) and `project_export.zip`.

**v3.1:** 📥 upload results you produced outside the app (figures, PDF, LaTeX, Markdown, CSV/Excel, notebooks…) — they become context for every agent; 🎯 a **brief per paper section** (directions, which results to present and how, structure, must/avoid, tone, length, references) plus a paper-wide brief.

**v3.2 — research control plane** (details: `CHANGELOG.md`, `ARCHITECTURE.md`, `INTEGRATION_STATUS.md`, `DEVELOPMENT.md`):
- 🧭 **Control Center** tab: dashboard, research timeline (hypothesis → experiment → result → decision), workspace hand-off to **VS Code / Dev Containers / Jupyter**, integration status, Codex runs, hardware policy, provenance inspector, memory inspector, dataset search.
- 🧠 **Context Memory v2**: stable hypothesis ids (`HYPE-NNN`), experiment records pointing to runs, git commits and **ClearML** tasks; tri-search retrieval + deterministic context compiler; watermark compressor (16k → 2k tokens) with a write-once raw page-store.
- 💻 **Workspace & Runs** replaces the Monaco Code IDE: write code in **VS Code + the Codex extension**; run, follow logs/curves, keep runs, self-debugging agent and Git/GitHub here.
- ⚙ **Hardware governor** for one GPU: sandbox caps from your PC (e.g. 16 GB / 6 CPUs on 32 GB / 16 threads), **GPU runs refused while Ollama/LM Studio hold VRAM** (press 🧹 Unload, or run on CPU), thermal guard and CPU fallback, GPU-aware `auto` LLM routing (+ DeepInfra, 9Router, OmniRoute).
- 📈 **ClearML without a server**: `pip install clearml` (done by `setup.bat`) and every run is recorded as a ClearML offline session in the project — import it into a ClearML Server later if you want the web UI.
- 🩺 **Live critic** while the Paper Writer streams; 🛡 **provenance** sealed into run figures/tables; 🧬 Hugging Face / Kaggle dataset connectors.
- 🧪 Automated tests: `python -m unittest discover -s tests -p "test_*.py"`.
- 🧪 Coverage (dev): `pip install -r requirements-dev.txt`, then `python -m coverage run -m unittest discover -s tests -p "test_*.py"` and `python -m coverage report`; frontend: `node --test "tests/frontend/*.test.js"`.

### Supported cloud providers
| Provider | API style | Get a key |
|---|---|---|
| Anthropic Claude | native Messages API | console.anthropic.com |
| OpenAI ChatGPT | OpenAI | platform.openai.com/api-keys |
| Google Gemini | OpenAI-compatible endpoint | aistudio.google.com/apikey |
| xAI Grok, DeepSeek, Mistral AI, Alibaba Qwen (DashScope), Moonshot Kimi, Cohere, Perplexity, Groq, Together AI | OpenAI-compatible | each vendor's console ("Get API key ↗" link in the app) |
| OpenRouter | OpenAI-compatible, one key for hundreds of models | openrouter.ai/keys |
| Custom | any OpenAI-compatible endpoint (vLLM, Ollama, Azure proxy, …) | — |

Every agent can be routed to **Default cloud**, **Local (LM Studio)**, or **a specific provider** — e.g. drafting with Claude, peer review with GPT, PDF parsing locally. If a local call fails, the app can fall back to the default cloud provider.

Default model names are suggestions; click **List** next to the Model box to load exactly the models your key can access.

---|---|---|
| ☁ **Claude API** | Lit2Plan planning, experimental design, 3.2 Academic Author, 3.3 Peer Reviewer, 3.4 Revision Editor, Masterclass | deep reasoning & academic writing |
| 🖥 **LM Studio** (`http://localhost:1234/v1`) | query expansion, PDF metadata parsing, 3.1 BibTeX Extractor, data → LaTeX table extraction | fast, private, zero API cost |

Every agent can be switched between Cloud and Local from the sidebar. If a local call fails, the app can fall back to Claude automatically.

---

> 🌐 **English / Tiếng Việt:** switch the interface with **EN / VI** at the top right; *AI output language* (sidebar) lets Tools 1, 2, 4 answer in Vietnamese while LaTeX papers stay English.
>
> 📘 **Full user guide inside the app:** tab **Guide** (Vietnamese / English) — quick start, every tool, recommended 6-month workflow, tips and troubleshooting. Source: `frontend/guide/`.

## 1. Install (once) — Windows 11

1. Install **Python 3.10+** from python.org (tick *Add python.exe to PATH*). Tested up to Python 3.14.
2. Double-click **`setup.bat`** — creates `.venv`, installs FastAPI, Uvicorn, httpx, pypdf, GitPython (all pure Python, no native DLLs → no Smart App Control prompts) and lists which optional tools were found.
3. Optional tools — each one only enables a feature; the app works without them:

| Tool | Enables | Install |
|---|---|---|
| **Docker Desktop** + WSL2 | Sandbox runs, GPU containers, Dev Containers | docker.com → install with the *WSL 2 backend*; in PowerShell (admin) `wsl --install` if WSL2 is missing; reboot; start Docker Desktop |
| **NVIDIA driver** (Game Ready / Studio, recent) | GPU passthrough (`--gpus all`) | Windows driver only — do **not** install a Linux driver inside WSL. Test: ▶ *Test GPU* in the Docker & System tab |
| **Ollama** (recommended local AI) | local agents (coder, summarizer, extraction) | ollama.com/download → the sidebar 🦙 section pulls/loads models, e.g. `qwen2.5-coder:14b` |
| **LM Studio** | local agents | download a model → **Developer** → **Start Server** (port 1234). Enable the `lms` CLI so the app can load models itself |
| **Git for Windows** | Source Control, Publish to GitHub | git-scm.com/download/win |
| **MiKTeX / TeX Live / Tectonic** | PDF preview of the paper | miktex.org |

4. Start the app (`run.bat`), open **🐳 Docker & System** → *🔎 Rescan machine* → *⚡ Apply recommended setup*. It picks the sandbox image (PyTorch+CUDA when a GPU is usable, else `python:3.11-slim`), RAM/CPU limits, and the local model size for your VRAM (12 GB → 14B Q4_K_M, 8k context).

## 2. Run

Double-click **`run.bat`** → the browser opens at **http://127.0.0.1:8765**.
The server binds to `127.0.0.1` only (not reachable from your network).

Manual start (any Python 3.9+): open a terminal in this folder and run `python start.py`.
`start.py` checks the Python version, installs missing packages into the Python that runs it, picks a free port if 8765 is busy, and opens the browser only once the server is ready.

## 2b. Linux / macOS
```bash
unzip PhD-Research-Lab-v3.1.0.zip && cd PhD-Research-Lab-v3.1.0
./run.sh            # or: python3 start.py
```
- If the system Python refuses `pip install` (PEP 668 "externally-managed-environment", Ubuntu 23.04+/Debian 12+), `start.py` automatically creates `./.venv`, installs the packages there and restarts inside it. If `venv` itself is missing: `sudo apt install python3-venv`.
- Optional: `sudo apt install python3-tk` enables the native "Select folder" dialog (otherwise the built-in folder browser is used).
- `python3 start.py --check` verifies files, version and packages without starting the server.

## 2c. Upgrading to a new version
Extract the **whole** new zip into a **new, empty folder** — never copy single files over an old version (that mixes versions; `start.py` now detects this and explains what is missing). Then copy your user data from the old folder: `data/`, `references/` and `projects/` (if present).

## 3. Configure (sidebar)

- **Cloud AI providers** → click a provider, paste its API key, press **↻ List** to load the models your key can use, pick one from the searchable model list (type to filter, ↑/↓ + Enter), then **Test connection**. Choose the **Default cloud provider**.
- **LM Studio Base URL** + **Local model**: the list shows every downloaded model with **Load** / **⏏ Unload** / **Use** buttons (load uses the LM Studio REST API, then the `lms` CLI, then just-in-time loading).
- **🦙 Ollama** Base URL (`http://localhost:11434`) + model: Load / Unload (frees VRAM) / Use, and ⤓ Pull to download a model.
- **Agent engines**: each agent → Default cloud, a specific provider, Local (LM Studio) or Local (Ollama), plus an optional model per agent. Changes save immediately; the **badge in every chat header** shows the engine · model in use and opens a quick switcher.
- **Reference directory** — any folder, e.g. `C:\Users\you\PhD\references`. Defaults to `./references`.
- **Agent engines** — per agent: Default cloud / Local / a specific provider. *Save configuration*.

Settings live in `data/config.json` (plain text on your machine — keep the folder private). Each key is only sent to its own provider. Upgrading: copy your old `data/` and `references/` folders into the new version's folder.

---

## 3b. Research projects (v1.6)
One installation can hold any number of research projects. The **📂 Research project** box at the top of the sidebar switches between them; the active one is shown at the top right.

| Per project (separate) | Shared by all projects |
|---|---|
| Data folder: `workspace/` (paper, outputs, chat sessions, 📌 notes), `library.json`, `project_meta.json` | API keys, providers, models |
| References folder (full-text PDFs) — default `<data folder>/references`, or any folder you choose | Agent engine choices, LM Studio settings |

- **＋ New** — name + optional data/references folders (default `projects/<name>/`).
- **📂 Open…** — register an existing project folder, e.g. one copied from another PC or a shared drive.
- **📁 Browse** next to *Data folder* (open any folder as a project) and *References folder* (choose where this project's PDFs live) — opens the Windows folder dialog; if that is unavailable it falls back to a built-in folder browser (drives, Home, ⬆, ＋ New folder, PDF count).
- **✎** rename · **✕** remove from the list (files are never deleted) · **↗** open the folder in Explorer.
- Your previous data (`data/` + `references/`) becomes the **★ Default project** automatically.
- A project folder is self-contained (references are stored relative to it when inside), so you can zip, back up or move it as a whole.

## 4. Workflows

### 🛠️ Tool 1 — Lit2Plan & Research Direction Architect
Idea → (local) query expansion with ready-to-paste IEEE Xplore / ACM / Scopus / Scholar search strings → (Claude) SOTA taxonomy, research gaps, falsifiable hypotheses, **6-month roadmap table**, risk register, target venues. Grounded in the PDFs already in your library (cited by BibTeX key). Download as `lit2plan.md`.

### 🔬 Tool 2 — Experimental Design & Methodology
Novelty + domain (hyperspectral, FOG signals, RISC-V SoC, …) → formulation in LaTeX math, metrics with formulas, ablation matrix, statistical protocol, reproducibility checklist and a runnable **`experiment_skeleton.py`** (synthetic-data fallback so it runs immediately). *→ Use as paper method notes* pushes it into the Paper Writer.

### 📚 Tool 3 — Papers & Writer
1. **Reference Library** — drag-and-drop full-text PDFs from IEEE Xplore / ACM DL (or copy them into the folder and *Rescan*). The PDF engine (PyMuPDF if available, otherwise pure-Python pypdf) extracts embedded metadata, the title (largest font on page 1), abstract, DOI and year; the local model then refines this into clean structured metadata. Edit any field, lock a custom BibTeX key, or exclude a paper.
2. **Data Chat Console** — paste or attach training logs, CSVs, ablation results, SystemC-AMS / MATLAB output. The Data Extractor returns booktabs LaTeX tables (best values bolded, mean ± std) + factual observations. *➕ Add table to paper*. **Chat sessions** are saved automatically (one file per conversation in `data/workspace/chat_sessions/`). Use the session bar to switch, start a **＋ New chat**, rename, export to Markdown or delete (moved to `_trash/`). *Auto-open last session on start* decides whether the app reopens your last conversation or starts a fresh one.
3. **Paper Writer Pipeline**
   - **3.1 BibTeX Extractor** (local) — normalises every included PDF and writes `references.bib` (deterministic formatting, unique keys like `smith2023spectral`).
   - **3.2 Academic Author** (Claude) — drafts Introduction, Related Work, Methodology, Experiments & Results, Discussion, Conclusion, then the Abstract, in raw LaTeX with `\cite{key}` only from `references.bib`.
   - **Citation guard** — any `\cite` key not in `references.bib` is stripped automatically; unsupported claims become a red `[CITATION NEEDED]`. Missing numbers become red `[TBD]` — results are never invented.
   - **3.3 Peer Reviewer** (Claude) — scores, major/minor issues tagged by section, citation-grounding audit against reference abstracts.
   - **3.4 Revision Editor** (Claude) — rewrites each section to address the review (section-by-section, so long papers never hit output limits; degenerate rewrites are rejected).
   - **Two modes (v2.5):**
     - **⚡ Quick pipeline** chains 3.1 → 3.2 → assemble → 3.3 → 3.4 → assemble.
     - **🔬 Deep · section by section** runs each section through *write → section review (score /10, Critical/Major/Minor issues with quotes) → revise*, for 1–3 rounds, before moving on. Options: skip accepted sections, pause after each section, final whole-paper review.
   - **Section workshop:** a board with status, word count and score for every section. The editor shows the agents writing live. A per-section review tab, and per-section **instructions for the AI** that take precedence over reviewer comments. ✓ Accept marks a section as final.
   - **■ Stop** interrupts the running agent at once: the upstream AI request is cancelled, finished steps are kept, and the interrupted step changes nothing. Each pipeline step can also be run on its own.
   - **📄 PDF preview (v2.7):** compiles the paper with your local LaTeX (pdfLaTeX/BibTeX, latexmk, XeLaTeX or Tectonic).
     - Auto-compiles after every agent run or Save.
     - Errors are mapped to sections (click to jump); a full-screen reader is included.
     - A *quick layout* still compiles when IEEEtran/acmart is missing.
     - Online compilation is optional and opt-in.
   - **LaTeX syntax highlighting** in the section editor (Tab, Ctrl+S).
   - **⬇ Export latex.zip**.
4. **④ Paper Review (v2.5)** — a separate flow for a finished manuscript (PDF / DOCX / TEX / MD), reviewed by Claude by default.
   - **Venue standard:** conference by **ICORE rank C → B → A → A\*** or **h5-index band**, or journal by **Q4 → Q1**. Optional venue name and track, double-blind mode, and 1–3 reviewer personas (domain expert, methods/experiments "Reviewer 2", presentation).
   - **Pipeline:**
     - automatic desk check: pages, sections, references, anonymity leaks, leftover `??`/TODO;
     - reviewer reports with recommendation, score and confidence;
     - area-chair / editor meta-review with decision and phased revision roadmap;
     - de-duplicated issue list Critical → Major → Minor → Typo, with every quote verified against the paper.
   - **Quick fixes:** an original ↔ revised word diff per issue, an action plan for issues that need new experiments, Accept / Done / Won't fix, and batch "Fix critical" or "Fix all".
   - **Outputs:** with the `.tex` source attached, accepted fixes are applied into `…_revised.tex` (the original is never modified). Also a response-to-reviewers letter, a Markdown report, and a follow-up chat with the area chair.

### 📖 Tool 4 — Masterclass
Rebuttal letters, major revisions, grant writing, thesis defense, qualifying exams, PRISMA reviews, venue choice, reproducibility packages, job applications — tailored to the context you provide.

### 📥 Your research results (v3.1, Experiment Design tab)
Drop files produced outside the app — images, PDF, `.tex`, `.md`, `.csv/.tsv`, `.xlsx`, `.docx`, `.ipynb`, `.json`, logs, code — or **＋ Type a result**. Describe each one (experiment, dataset, setting): agents rely on that description. **✨ Analyze** extracts key numbers and findings (images are read by a vision model), **▦ LaTeX table** adds a booktabs table to the Writer, **📌 Pin** makes a result must-follow context, **🙈 Hide from AI** removes it from every prompt, **✍ Use in paper** adds it to a section brief. Files live in `data/results/`.

### 🎯 Section briefs (v3.1, Paper Writer)
Select a section → tab **🎯 Brief**: directions & wishes (with suggestions), **results to present** (uploads, sandbox runs/figures, Writer tables) with *present as* table / figure / numbers in text / comparison / headline and a note each, required structure, must include / must avoid, tone & length, references to emphasise. **🧭 Paper-wide brief** (story, style, terminology, never-do) applies to all sections. The brief goes to the Author, Editor and section Reviewer; **👁 Preview** shows exactly what the AI receives. Chosen figures are inserted with `\includegraphics{figures/…}` and shipped in the PDF preview and `latex.zip`.

### 💻 Workspace & Runs (v3.2 — replaces the v3.0 Code IDE)
- **Code is written in VS Code** with the **Codex extension** (`openai.chatgpt`; ⤓ one-click install from the tab) or the Codex CLI (🧭 Control Center → 🤖 Codex). *🚀 Open in VS Code*, *🐳 Dev Container*, and ↗ on any proposed / changed file open it in VS Code.
- **Start from blueprint** creates `src/`, `README.md`, `requirements.txt` from Tool 2 (`experiment_skeleton.py` + design).
- **Run** a command in the sandbox with a live log and **live metric curves** (log lines like `epoch 3 loss=0.12 psnr=28.4`).
- **⛔ VRAM rule:** a GPU run is refused while Ollama / LM Studio hold a model in VRAM — press **🧹 Unload local LLMs** (or *Unload & run*), or tick *Run on CPU*. Nothing is unloaded automatically.
- **Self-debugging agent:** 💡 *Suggest* (text diff, apply) or ⚡ *Auto* (apply → run → read stderr → fix, up to N attempts). It sees locked decisions, pinned context, compiled memory, the blueprint, the workspace and the last run.
- Code runs with `docker exec` in one persistent container per project (`phdlab-…`): workspace at `/workspace`, run outputs at `/runs`. Without Docker it falls back to a private Python venv.
- Every run is kept in `data/runs/<id>/` (`stdout.log`, `stderr.log`, `metrics.json`, `figures/`, `provenance.json`, git commit). *Use results in the paper* fills the Writer's results notes and adds a booktabs table with the **measured** numbers; *Record as experiment* links it to a hypothesis.
- **Source Control:** init, changes, text diff, commit, push/pull, **🚀 Publish to GitHub** (public/private). The Personal Access Token stays in `data/config.json`, is sent only to GitHub and is passed to `git push` for that one command — never written to `.git/config`.

### 🐳 Docker & System (v3.0)
Status cards (Docker, sandbox, GPU, host, container usage) and sparklines refresh every 2 s: GPU util/VRAM/temperature/power, container CPU/RAM/PIDs/IO, host RAM/CPU/disk. Container actions (start, stop, restart, recreate), image pull with progress, **Test GPU**, sandbox settings (engine, image, RAM/CPU/shm limits, GPU, network, time limit, self-debug attempts), jobs table with log viewer, images/containers, local AI servers, machine scan (OS, CPU, RAM, GPU/driver/CUDA, Docker, WSL2, Git, LaTeX, `lms`) and recommendations.

### 🧠 Context & memory (v3.0)
- **Graph** of objectives, hypotheses, decisions, constraints, literature, code assumptions, metrics and memory episodes. Click a node to inspect/edit, **📌 pin** (injected as MUST-FOLLOW context into every agent) or **🗑 purge** (hidden from all agents; purged papers leave the reference digest; data is kept).
- **Context Decision Agent:** describe the change in plain language ("prune the old CNN assumptions, focus on FLOPs"); it proposes pin/purge/add/edit operations that you tick and apply.
- **Memory:** Tier 1 = recent chat turns + sandbox logs; when it passes the threshold (default 24k tokens) the **summarizer agent (local model)** writes Tier 2 episodes in the background; Tier 3 = goals, hypotheses, constraints, best metrics, validated references, locked decisions. Stored in `data/memory/project_state.json`.

### 🔒 Lit2Plan decisions & regenerate (v3.0)
🔒 on any chat answer (or select text in the plan → *Lock selected text*) records a direction, hypothesis, gap, constraint or rejected direction. Locked decisions bind every agent. **🔄 Regenerate overview** rewrites the research plan from the discussion + locked decisions; **🕘 Versions** keeps and restores earlier overviews.

### 🔌 MCP & export (v3.0)
`POST http://127.0.0.1:8765/mcp` (Streamable HTTP JSON-RPC) exposes `sandbox_run_code`, `sandbox_manage_files`, `sandbox_get_metrics`. For stdio clients (Claude Desktop): `{"mcpServers": {"phd-research-lab": {"command": "python", "args": ["<app folder>/mcp_stdio_bridge.py"]}}}`. **⬇ project_export.zip** (Writer) bundles paper, plan, code, runs/metrics/figures and memory.

### 🔎 Internet search (v2.6)
Every chat has a **🌐 search** selector with four settings: off, 📚 papers, 🌐 web, or both.
- **Paper sources:** OpenAlex, arXiv and Semantic Scholar (free, no key).
- **Web sources:** DuckDuckGo (free), or Tavily / Brave with an API key.
- **Per question:** a small planner agent writes the queries (with a year filter for "latest" questions). Results are de-duplicated by DOI and numbered [S1]…, and the answer cites them as links.
- **Under each answer:** a sources list with 📥 *save open-access PDF to the Reference Library* (with database metadata) and 📎 *attach full text*.
- **Lit2Plan** can ground the plan in papers found online, adding a "Key Papers Found Online" section.
- **Reference Library** has a **🔎 Find papers online** box.

Settings are in the sidebar. Only search queries are sent out. `PHDLAB_SEARCH_BASE` redirects all search endpoints, e.g. to an institutional proxy.

### ✳ Claude-style chat & rich results (v2.0)
All five chats (Tool 1, Tool 2, Data chat, Paper chat, Tool 4) share one Claude-web-like interface:
- **Streaming answers** with a live cursor and a **■ Stop** button (a stopped answer is kept); **↻ Retry** the last answer; **✎ Edit** any question and resend.
- **Attachments** — 📎 files (PDF, DOCX, PPTX, XLSX, CSV/TSV, JSON, LaTeX, BibTeX, Python/MATLAB/C++/Verilog…, Jupyter notebooks, HTML), **images** (sent as vision input to models that support it), drag & drop or paste; 🔗 **links** (web pages, arXiv/DOI pages, online PDFs — pasting a URL offers to attach it); 📚 **papers** from the project library (full text). Click a chip to preview exactly what the AI receives. Attachments are stored per project in `workspace/attachments/` and stay attached in the saved session.
- **Rich rendering, fully offline** — Markdown, tables, KaTeX math (`$…$`, `$$…$$`, `\(…\)`, `\[…\]`), syntax-highlighted code with Copy / Save, LaTeX kept verbatim inside code blocks, and **citation chips**: `[bib_key]` or `\cite{key}` become chips showing authors, venue, *Open PDF*, *DOI* and *Attach to chat*.
- **Appearance:** ☀ light / 🌙 dark / 🖥 follow the OS — switch at the top right (remembered per browser; code highlighting switches too).
- **Enter** sends, **Shift+Enter** new line (safe with Vietnamese/Telex input), ⤢ reading view, 📌 pin, export to Markdown.
- Tool outputs (Lit2Plan, Experiment design, Masterclass, review) use the same renderer with a reading view.

### 💬 Follow-up chats & Shared Context Hub (v1.5)
Every tool has its own **follow-up chat** under its output — Tool 1 (plan), Tool 2 (methodology + code), Tool 3 (Data chat and Paper chat on `main.tex` + review), Tool 4 (mentor). Each tool keeps its own list of saved sessions (switch, new, rename, delete, export).
- **Context snapshot:** a session remembers the tool output it was started on; generating a new output automatically starts a new follow-up session, while old sessions keep their original context.
- **🔗 Share context with other tools** (per tool, on by default): the chat also receives the latest outputs of the other tools, the recent messages of their active chats, and all pinned notes.
- **📌 Pin:** pin any AI answer — or just the text you selected in it — to the shared context; manage notes from the 📌 button. Pinned notes have the highest priority in every tool's chat.
- Each chat's engine (cloud provider or local) is set in the sidebar like any other agent ("💬 Chat · Tool N").
- Tool 1/2/4 outputs are restored after a refresh.

---

## 5. `latex.zip` structure

```text
latex.zip/
├── main.tex          IEEEtran (conference) or acmart (sigconf), \bibliography{references}
├── references.bib    standalone BibTeX of all included PDFs
├── README.md         Overleaf / TeX Live compilation instructions
└── references/       the full-text PDFs used in the project
```

Upload directly to Overleaf (*New Project → Upload Project*) or compile with `latexmk -pdf main.tex`.

---

## 6. Project layout

```text
phd-research-lab/
├── run.bat / setup.bat
├── requirements.txt
├── backend/
│   ├── app.py        FastAPI routes
│   ├── config.py     settings + agent registry
│   ├── llm.py        hybrid router (Claude Messages API + LM Studio OpenAI API, fallback)
│   ├── library.py    PyMuPDF ingestion, metadata store, BibTeX formatter
│   ├── paper.py      project state, LaTeX templates, citation guard, zip export
│   ├── prompts.py    agent system prompts (Tools 1-4, section workshop)
│   ├── review_ext.py      ④ Paper Review: storage, desk check, quote verification, fix apply
│   ├── review_prompts.py  venue standards (ICORE / h5 / Q1-Q4) and reviewer prompts
│   ├── latex_build.py     LaTeX → PDF preview (engine discovery, quick layout, log parsing)
│   ├── websearch.py       internet search (OpenAlex, arXiv, Semantic Scholar, DuckDuckGo/Tavily/Brave)
│   ├── chat_store.py, context_hub.py, attachments.py, fs_browse.py
│   ├── api_v3.py          v3 routes (local AI, system, sandbox, IDE, git, memory, context, MCP)
│   ├── sandbox.py         Docker CLI sandbox / local venv, jobs, runs, metrics
│   ├── sysinfo.py         machine scan + recommended setup (no native packages)
│   ├── local_ai.py        LM Studio / Ollama model management
│   ├── ide_fs.py, coder.py, gitops.py, memory.py, context_graph.py, mcp_server.py
│   ├── results.py, brief.py, api_v31.py   v3.1 uploaded results + section briefs
├── mcp_stdio_bridge.py    MCP stdio ↔ HTTP bridge
├── frontend/index.html    single-page UI  ·  frontend/app/ (ide.js, docker.js, context.js, v3.css)
├── frontend/vendor/       marked, KaTeX, highlight.js, Monaco, xterm.js, vis-network (offline)
├── references/            default PDF pool
└── data/                  everything you create, per project:
    ├── config.json        API keys, GitHub token, engines (shared by all projects)
    ├── system/            machine scan cache
    ├── workspace/         project.json, main.tex, chats, lit2plan_versions/, paper_reviews/, …
    ├── code/              code workspace, opened in VS Code (a git repo; mounted at /workspace)
    ├── runs/<id>/         run.json, stdout/stderr logs, metrics.json, figures/ (mounted at /runs)
    ├── sandbox/           settings.json, venv/ (local mode)
    ├── memory/            project_state.json, context_graph.json, context_chat.json
    └── results/           research results you uploaded (index.json, <id>/file + extracted.txt, _trash/)
```

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot reach LM Studio" | LM Studio → Developer → Start Server; load a model; check the URL ends in `/v1`. |
| Local model returns invalid JSON when parsing PDFs | Use a stronger instruct model (≥7B) or switch *PDF Metadata Parser* to Cloud. |
| PDF shows "no extractable text" | It is a scanned image — OCR it first (e.g. `ocrmypdf in.pdf out.pdf`). |
| Provider 401 / 403 | Wrong or expired API key, or billing not enabled on that account. |
| Provider 404 / model not found | Click **List** and pick a model your key can access. |
| Port 8765 busy | Edit the port in `run.bat`. |
| Local reviewer/author loses context on long papers | Keep 3.2–3.4 on Cloud, or load a long-context model in LM Studio. |
| After an upgrade the new tabs are missing | An older copy is still running (its black window). Close every old window, run `run.bat` again; if the browser still shows the old page press **Ctrl+F5**. Since v3.1 the launcher detects this and starts the new version on another port. |
| Workspace says "Docker not running" | Start Docker Desktop (whale icon steady), then ↻ in the Docker & System tab. Until then runs use the local venv. |
| `--gpus all` fails / Test GPU shows no GPU | Update the NVIDIA Windows driver, Docker Desktop → Settings → Resources → WSL integration on, `wsl --update`. The app retries on CPU automatically. |
| CUDA out of memory while a local model is loaded | ⏏ Unload the LM Studio / Ollama model in the sidebar before long training runs (12 GB cards cannot hold both). |
| First run is slow | The sandbox image is being downloaded (PyTorch+CUDA ≈ 8 GB). Progress shows in the Docker & System tab. |
| Publish to GitHub: 401 | Token missing scopes — fine-grained token with *Contents: read/write* and *Administration: read/write* (to create repos), or classic `repo`. |
| `pip install` in the sandbox fails | Enable 🌐 Network in sandbox settings, then ♻ Recreate the container. |

**Academic integrity:** the lab drafts; you are the author. Verify every citation, number and claim before submission, and follow your venue's policy on disclosing AI assistance. Publisher PDFs in `references/` are for personal use — don't redistribute them.
