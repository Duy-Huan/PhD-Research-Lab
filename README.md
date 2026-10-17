# PhD Interactive Autonomous Research Lab — v1.6.0

A local desktop web app for Windows 11 that runs an end-to-end research workflow on a **hybrid AI architecture**: any of 14 cloud AI providers for deep reasoning and academic writing, plus local models in **LM Studio** (`http://localhost:1234/v1`) for fast, private, zero-cost extraction work.

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

## 1. Install (once)

1. Install **Python 3.10+** from python.org (tick *Add python.exe to PATH*).
2. Install **LM Studio** → download a model (e.g. Qwen3-8B / Llama-3.1-8B-Instruct / Mistral-Small) → **Developer** tab → **Start Server** (port 1234).
3. Double-click **`setup.bat`** (creates `.venv` and installs FastAPI, Uvicorn, httpx, pypdf).

## 2. Run

Double-click **`run.bat`** → the browser opens at **http://127.0.0.1:8765**.
The server binds to `127.0.0.1` only (not reachable from your network).

Manual start (any Python 3.9+): open a terminal in this folder and run `python start.py`.
`start.py` checks the Python version, installs missing packages into the Python that runs it, picks a free port if 8765 is busy, and opens the browser only once the server is ready.

## 3. Configure (sidebar)

- **Cloud AI providers** → click a provider, paste its API key, press **List** to choose a model, then **Test connection**. Choose the **Default cloud provider**.
- **LM Studio Base URL** + **Local model** (↻ lists models loaded in LM Studio).
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
   - **▶ Run full pipeline** chains 3.1 → 3.2 → assemble → 3.3 → 3.4 → assemble. Every section stays hand-editable.
   - **⬇ Export latex.zip**.

### 📖 Tool 4 — Masterclass
Rebuttal letters, major revisions, grant writing, thesis defense, qualifying exams, PRISMA reviews, venue choice, reproducibility packages, job applications — tailored to the context you provide.

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
│   └── prompts.py    all agent system prompts
├── frontend/index.html   single-page UI
├── references/       default PDF pool
└── data/             config.json, library.json, workspace/ (project.json, main.tex, review.md, …)
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

**Academic integrity:** the lab drafts; you are the author. Verify every citation, number and claim before submission, and follow your venue's policy on disclosing AI assistance. Publisher PDFs in `references/` are for personal use — don't redistribute them.
