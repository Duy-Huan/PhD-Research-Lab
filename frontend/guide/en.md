# PhD Research Lab — User Guide

PhD Research Lab is a research workbench that runs on your own computer. It combines **cloud AI** (Claude, GPT, Gemini…) for deep reasoning and academic writing with **local AI** (Ollama or LM Studio) for fast, private, zero-cost extraction work. This guide covers installation, each tool, and the most effective end-to-end workflow for a PhD researcher.

> **Golden rule:** the AI drafts, **you** are the author. Verify every citation, number and claim before you submit.

## Quick start (5 minutes)

1. **Start the app:** Windows `run.bat`; Linux/macOS `./run.sh`. Your browser opens `http://127.0.0.1:8765`.
2. **Add an API key:** sidebar → *Cloud AI providers* → click a provider (e.g. Anthropic Claude) → paste the key → **↻ List** → pick a model → **Test connection** → **Save configuration**.
3. **(Optional) Local AI:** install **Ollama** (recommended) or LM Studio → *Developer* → **Start Server**. In the sidebar press **Load** next to the model you want (Ollama: type a model name and **⤓ Pull** if it is not downloaded).
   - **(Optional) Docker/GPU machine:** **🐳 Docker & System** tab → *🔎 Rescan machine* → *⚡ Apply recommended setup*.
4. **Create a project:** *📂 Research project* → **＋ New** → name your topic.
5. **Add literature:** *Papers & Writer* → *Reference Library* → drop full-text PDFs (IEEE, ACM, arXiv…).
6. **Run Tool 1:** *Lit2Plan* → describe your idea → **Generate research plan** → ask follow-ups in the chat below.

## Language

- **EN / VI** at the top right switches the whole interface and this guide. The choice is remembered per browser.
- **🌐 AI output language (Tools 1, 2, 4)** in the sidebar has three options: *Follow interface language*, *Always English*, *Always Vietnamese*. Technical terms, method names, citations, math and code stay in English.
- **LaTeX papers (Tool 3) are always written in English.** Chats answer in the language you write in.

## Architecture & cost

| Task | Recommended engine | Why |
|---|---|---|
| Query expansion, PDF metadata, BibTeX (3.1), data → LaTeX tables | 🖥 Local | Fast, private, free, well-structured tasks |
| Lit2Plan, experimental design, drafting (3.2), review (3.3), revision (3.4), Masterclass | ☁ Cloud | Needs deep reasoning and academic style |
| Follow-up chats (💬) | ☁ Cloud (or Local for short questions) | Answer quality is the whole point |

- Every agent has its own engine in *⚙ Agent engines*: **Default** cloud provider, **Local**, or a specific provider. Example: Claude drafts, GPT reviews. Using two different models for drafting and reviewing makes the review more independent.
- Keep *Fall back to Claude if local fails* on so work continues when LM Studio is closed.
- **Saving tokens:**
  - Turn off *🔗 Shared context* for quick questions.
  - Attach only the documents you really need.
  - Use Local for repetitive work.

## Research projects

Each project has its own **data folder** (workspace, outputs, chats, 📌 notes, library) and **references folder** (PDFs). API keys and AI settings are shared by all projects.

- **＋ New** creates a project (default location `projects/<name>`).
- **📂 Open… / 📁 Browse** (next to *Data folder*) opens any folder as a project, e.g. one copied from another PC or a shared drive.
- **📁** next to *References folder* chooses where this project's PDFs live.
- **✕** removes a project from the list only. **No files are deleted.**
- **Tip:** keep references *inside* the data folder. The whole project is then one folder, easy to back up, zip or sync with OneDrive/Google Drive.

## Tool 1 — Lit2Plan: research direction

**Input:** a raw idea plus constraints (data, hardware, time, target venue).
**Output:**
- Query expansion with ready-to-paste IEEE Xplore / ACM / Scopus search strings.
- SOTA taxonomy, research gaps G1…Gn, falsifiable hypotheses H1…Hn.
- A **6-month roadmap**, risk register and target venues.

**Use it well:**
1. Be **specific** and state context and constraints. Example: *"Hyperspectral denoising on UAVs, 2 W budget, Indian Pines available, 6 months, targeting IEEE TGRS"*.
2. **Load your PDFs first**. The planner then cites your own library as `[bib_key]` instead of relying on general knowledge.
3. Use the generated search strings to find more papers, add their PDFs, then **re-run** Lit2Plan. Each loop grounds the plan more firmly in the literature.
4. Go deeper in 💬 chat. Examples: *"Critique H1 like a tough reviewer"*, *"Which gap is most publishable in 6 months?"*, *"Turn Month 1 into a weekly plan"*.
5. **Lock 🔒 directions** right in the chat: press 🔒 *Lock* under an answer (or select text in the plan → *🔒 Lock selected text*) and choose the kind: direction / hypothesis / gap / constraint / rejected. Locked decisions appear in the *🔒 Locked decisions* card, **bind every agent** (Tools 2–4, Code IDE, Writer) and show as 📌 nodes in the Context tab.
6. After many rounds of discussion press **🔄 Regenerate overview from discussion**: the plan is rewritten from the chat and the locked decisions. Earlier versions stay in **🕘 Versions** (restorable).

## Tool 2 — Experimental design

**Output:**
- Mathematical formulation, metrics with formulas, ablation matrix and statistical protocol.
- A runnable **`experiment_skeleton.py`** that works with synthetic data out of the box.

**Use it well:**
1. Describe in *Novelty*: the new contribution, the hypothesis it tests, and the baselines it must beat.
2. State compute limits, e.g. *"1× RTX 4090, 3 weeks"*. The design becomes realistic.
3. Download `experiment_skeleton.py`, run it on synthetic data, then replace the `Dataset` with your real data.
4. In 💬 chat, attach **training logs, `.py` files or plot images** for debugging, code changes or statistical advice.
5. Click **→ Use as paper method notes** to carry the design into the Paper Writer.

### 📥 Your research results (v3.1)
When you code and run experiments outside the app, bring the results in with the **📥 Your research results** card (bottom of the Experiment Design tab):
1. **Drop files** (or click to choose): PNG/JPG/SVG/EPS images, PDF, `.tex`, `.md`, `.csv/.tsv`, `.xlsx`, `.docx`, `.ipynb`, `.json`, `.log`, code… You can write a **shared description** and **tags** before dropping. Or **＋ Type a result** (paste numbers, a Markdown table).
2. **Describe each result** on its card: which experiment, dataset, setting, baseline, what it shows. The agents rely on this (especially for images).
3. **✨ Analyze:** the AI reads the file or the **image** (vision model) and writes the key numbers, findings, caveats and a suggested caption — only from the file, never invented.
4. **▦ LaTeX table:** CSV/Markdown/Excel/.tex → booktabs table added to the Paper Writer.
5. **📌 Pin** (every agent must take it into account) or **🙈 Hide from AI** (file kept). Results also appear as nodes in the 🧠 Context tab.
6. **✍ Use in paper:** choose a section (e.g. Experiments and Results) and how to present it (table, figure, numbers in the text, comparison, headline) — it is added to that section's 🎯 Brief.

Every chat, the experiment designer (which then proposes the experiments still missing) and the writing agents receive a digest of these results. Files are kept in the project's `data/results/`; deleting moves them to `data/results/_trash/`.

## Tool 3 — Library, Data Chat & Paper Writer

### 1. Reference Library
- Drop full-text PDFs. The app extracts title, authors, abstract, DOI and year. Click **✨ AI-parse** to let the AI normalise the metadata.
- Click **👁 Read** (or a paper title) to **read the PDF right in the app**. It uses the browser's built-in viewer, so you can zoom, search and print. Use ‹ › or the ← → keys for the previous/next paper; click the key to copy it.
- Click **Edit** to fix metadata or lock a **BibTeX key**. Untick **Use** to exclude a paper from the paper.
- **3.1 Generate references.bib** builds a clean BibTeX file.
- Scanned PDFs (images only) need OCR first, e.g. with `ocrmypdf`.

### 2. Data Chat Console
- Paste or attach logs, CSVs, ablation results, SystemC-AMS/MATLAB output or Excel files.
- The AI returns **booktabs LaTeX tables** (best values in bold, mean ± std) plus observations based only on the numbers.
- Click **➕ Add table to paper** to put a table into the paper.

### 3. Paper Writer — section by section, in depth
**Prepare:** open **Paper project** and fill in:
- title and authors (`Name | Affiliation | email | Country`);
- IEEE/ACM template and **target venue** (e.g. *IEEE TGRS (Q1)*), which calibrates the reviewers;
- contribution, method notes and results notes.

**The control bar** stays pinned at the top while you scroll. It has two modes:
- **🔬 Deep · section by section** (recommended): each section runs through *write → review that section → revise* before the next one starts. The abstract is written last.
  - **Rounds:** 1–3 review → revise rounds per section. A section that scores ≥ 9/10 is not revised again.
  - **Skip accepted:** sections you marked ✓ Accept are left untouched.
  - **Pause after each section:** asks before moving on, so you can read and edit.
  - **Final whole-paper review:** Agent 3.3 reads the assembled main.tex.
- **⚡ Quick pipeline:** all sections in one pass: 3.1 → 3.2 → Assemble → 3.3 → 3.4 → Assemble.
- Every step in the progress bar is a button. Click it to **run only that step**, e.g. re-run 3.3 alone.
- **■ Stop** interrupts the agent immediately, even mid-sentence. Finished steps are kept. The interrupted step is discarded, so the section keeps its previous text.

**Section board (left):** each section shows:
- a status dot: empty · drafted · reviewed · revised · accepted;
- its word count and section-review score /10;
- quick actions: ✍ Write · 🔍 Review · ✎ Revise · 🔬 Deep cycle.

**Workspace (right):**
- **LaTeX:** watch the agent write live. Edit by hand, then 💾 Save.
- **🔍 Section review:** a score, Critical/Major/Minor issues with exact quotes, missing content, a citation and evidence check, and before → after rewrites.
- **🎯 Brief · directions & results** (v3.1, replaces *Instructions for AI*): every part is optional; sent to the Author (3.2), the Editor (3.4) and the section Reviewer (3.3 — which reports deviations from the brief), and takes precedence over reviewer suggestions.
  - **🧭 Directions & wishes:** what the section must argue or emphasise. Click the ＋ suggestions to add common ones (e.g. *"End with a bullet list of 3 contributions"*, *"Report mean ± std"*).
  - **📊 Results to present:** *＋ Choose results…* from your uploads (Experiment Design), Code IDE runs and figures, Writer LaTeX tables and results notes. For each: **present as** (auto / table / figure / numbers in the text / comparative analysis / headline result), a **note** (e.g. *"highlight the +1.2 dB over QRNN3D"*) and the order ↑↓. Tick *Present only the selected results* to keep other results out. Figures are inserted with the exact `\includegraphics{figures/…}` line and shipped with the PDF preview and `latex.zip`.
  - **🧱 Structure:** ordered outline (one paragraph or subsection per line). **✅ Must include / ⛔ Must avoid.** **🎚 Tone & length** (or target words). **📚 References to emphasise.**
  - **👁 Preview what the AI receives**, **⧉ Copy this brief to other sections**, **✍ Write with this brief**. Sections with a brief show 🎯 on the board.
  - **🧭 Paper-wide brief** (in *Paper project*, or the *Paper-wide brief…* button): overall story & key claims, style, terminology & notation, never-do — applied to every section.
- **🔬 In-depth writing:** longer, more detailed output for single ✍ Write / ✎ Revise runs.
- **✓ Accept:** marks the section as final.

**📄 PDF preview** (right under the workspace):
- **▶ Compile PDF** assembles main.tex and compiles it with the LaTeX on your computer: pdfLaTeX + BibTeX, latexmk, XeLaTeX or Tectonic. The PDF appears below, with **⤢ Full screen** and **⬇ main.pdf**.
- **Auto-compile** recompiles after every agent run and every Save (Ctrl+S).
- **LaTeX errors** are listed per section. Click one to jump to the exact spot in the editor. Undefined references/citations and leftover placeholders are reported too; details are in **📜 Log**.
- **Quick layout:** without the IEEEtran/acmart class, the preview is compiled with `article`, so you can always read the draft.
- **No LaTeX yet?**
  - Windows: `winget install TectonicTypesetting.Tectonic`, or MiKTeX;
  - Ubuntu: `sudo apt install texlive-latex-extra texlive-publishers texlive-bibtex-extra latexmk`;
  - macOS: `brew install tectonic` or MacTeX.

  Until then you can tick *Allow online compilation*; the paper is then sent to an external service.

**LaTeX syntax highlighting:** the editor colours commands, environments (`\begin{…}`), `\section`, `\cite`/`\ref`/`\label`, math `$…$`, `%` comments and red `[TBD]` placeholders, even while an agent is writing. **Tab** inserts two spaces, **Ctrl+S** saves.

**Tips:**
- Run Deep mode once, then read every section review.
- Write instructions for the weak sections, then 🔬 Deep-cycle only those.
- Use **💬 Paper chat**, e.g. *"Which claims are not supported by the results?"*.
- Finally **⬇ Export latex.zip** → Overleaf (*New Project → Upload Project*).

**Integrity guard:**
- Any `\cite{}` that is not in `references.bib` is removed automatically.
- Claims without supporting evidence are marked with a red `[CITATION NEEDED]`.
- Missing numbers are marked with a red `[TBD]`.
- **Never submit while placeholders remain.**

### 4. Paper Review (a finished manuscript)
A separate flow to **stress-test a paper before you submit it**. The app reads the full manuscript and reviews it the way a real conference programme committee or journal board would, then helps you fix everything from critical flaws to typos.

**Claude is the default reviewer** (*✳ Claude preferred*). Without a Claude key the default provider is used. Change this in ⚙ Agent engines → 📝 Review.

**1. Manuscript:** drop a **PDF**, **Word (.docx)**, **LaTeX (.tex)** or Markdown file. An automatic desk check (no AI) reports:
- pages, words, figures, tables and references;
- missing standard sections;
- **anonymity leaks** for double-blind review: e-mails, an Acknowledgment section, *"our previous work"*, GitHub links, a filled `\author{}`;
- leftover placeholders: `??`, TODO, TBD, "Error! Reference source not found".

If you have the **.tex source**, click **📎 Attach .tex**. Fixes are then written in LaTeX and can be applied for you.

**2. Venue standard:**

| Type | Criterion | Levels |
|---|---|---|
| 🎤 Conference | **ICORE / CORE** rank | C → B → A → A* |
| 🎤 Conference | **h5-index** (Google Scholar) | <10 · 10–24 · 25–49 · 50–99 · 100+ |
| 📰 Journal | International **quartile** (SJR / JCR) | Q4 → Q3 → Q2 → Q1 |

Each level shows the bar the reviewers apply. For example, A* demands a significant advance over the state of the art, and Q1 usually means Major Revision on the first submission. You can add the **venue name** (e.g. CVPR, IEEE TGRS) and a **field / track**.

Choose **1–3 reviewers:**
- **R1, domain expert:** novelty, significance, related work.
- **R2, methods & experiments:** the demanding "Reviewer 2" (maths, baselines, statistics).
- **R3, presentation:** structure, writing, figures and venue fit.

**3. ▶ Start review:**
1. Each reviewer writes a full report: recommendation (Accept … Reject), score /10, confidence, criteria table, questions for the authors, and page-referenced comments **(p. N)**.
2. The **Area Chair** (conference) or **Editor** (journal) weighs the reviews and issues a **decision**. They also write a **phased revision roadmap**: Phase 1 critical → Phase 2 major → Phase 3 minor → Phase 4 polish, with effort estimates.
3. The reviews become a de-duplicated **issue list**, ordered **Critical → Major → Minor → Typo**. Every quoted passage is **checked automatically** against the manuscript: ✓ found in the paper, or ⚠ not verbatim — check it.

**4. Quick fixes (🛠 Issues & fixes):**
- Use **✨ Quick fix** on one issue, **✨ Fix critical**, or **✨ Fix all (critical → typo)**.
- Each fix shows **original ↔ revised** with a word-level diff. Issues that need new experiments get an **action plan** and `[TBD]` placeholders; the AI never invents numbers.
- For each issue you can:
  - **✓ Accept fix**, **Copy revised**, or **Retry with instructions…**;
  - mark it **✓ Done** or **✕ Won't fix** to track progress.
- With a .tex source attached, **⚙ Apply accepted fixes to .tex** downloads `…_revised.tex`. Your original is never modified.

**5. Outputs:**
- **✉ Response letter:** a point-by-point reply to the reviewers. Open issues get `[AUTHOR: …]` placeholders, so the letter never claims a change you did not make.
- **⬇ Full review report (.md):** the meta-review, an issue checklist with status, and all reviewer reports.
- **💬 Chat** with the Area Chair, e.g. *"What must I fix first to get accepted?"*, *"Draft a rebuttal for R2"*, *"Is this a better fit for a B-ranked venue?"*.
- **■ Stop** works at every stage. Finished stages are kept.

> A simulated review is a realistic rehearsal, not a guarantee of the real outcome. Acceptance rates and rank proportions are typical figures for calibration only.

## Tool 4 — Masterclass

Pick a milestone, e.g. rebuttal, major revision, grant proposal, thesis defense, PRISMA. Add your context (field, stage, deadline, reviewer comments) to get a guide with templates and checklists.

In 💬 chat you can ask the mentor to **role-play an examiner or reviewer**. Example: *"Be my examiner and ask me 5 hard questions"*.

## Chats, attachments & shared context

**Sending messages:**
- **Enter** sends, **Shift+Enter** adds a new line. Vietnamese/Telex input does not send by accident.
- Answers stream in word by word. Press **■** to stop; the partial answer is kept.
- **↻ Retry** regenerates the answer. **✎ Edit** lets you change a question and resend it.

**Attachments:**
- 📎 **Files:** PDF, DOCX, PPTX, XLSX, CSV, LaTeX, code, notebooks, **images**. Drag & drop or paste both work.
- 🔗 **Links:** web pages, arXiv, DOI, online PDFs. Paste a link and the app offers to attach it.
- 📚 **Paper:** attach the full text of a library paper.
- Click an attachment chip to see **exactly what the AI receives**.

**Citations:** `[bib_key]` is shown as a chip (e.g. *He et al. 2016*). Click a chip for details, Open PDF, DOI, or to attach the paper to the chat.

**🔗 Shared context:**
- When on, each tool's AI also sees the latest output and recent messages of the other tools, plus all 📌 notes.
- **📌 Pin** an answer, or just the text you selected in it, so every tool can use it.
- The **📌 (count)** button at the top right, next to the project name, opens the **Shared context** window from any tab. In the window you can:
  - **search by keyword**, with matches highlighted;
  - filter by tool;
  - click a pin to **expand / collapse** it, or use *Expand all / Collapse all*;
  - copy or delete single notes.

**Chat sessions:**
- Each tool keeps its own session list: new, rename, delete, export to Markdown.
- *Auto-open* decides whether the last session reopens on start.

**Limits per message:** about 150,000 characters of documents and at most 8 images. The newest message's attachments get priority.

## 💻 Code IDE (v3.0)

The **Code IDE** tab is a small VS Code wired to the Docker sandbox and the agents:

- **Activity bar** (left): Explorer, Search in files, Source Control (Git/GitHub), Runs, and a shortcut to the Docker tab. ✳ toggles the agent panel on the right. Panels are resizable.
- **Start:** *🧪 Start from the blueprint* creates `src/`, `README.md`, `requirements.txt` from Tool 2 — or use *→ 💻 Open in Code IDE* in the Experiment Design tab.
- **Editing:** Monaco editor, tabs, **Ctrl+S** save, **Ctrl+Enter** run the open file. If the agent or a run changes a file you are editing, the app asks which version to keep.
- **Running:** ▶ runs in the sandbox; output streams to *Terminal*; log lines like `epoch 3 loss=0.12 psnr=28.4` are plotted live under *Live metrics*. The command line below the terminal runs `pip install …`, `nvidia-smi`, `ls`…
- **Co-coding agent** (right panel):
  - **💡 Suggest:** the agent proposes file changes; ⇄ shows the diff, ✓ applies, or *Apply all*.
  - **⚡ Auto:** apply → run in the sandbox → read stderr → fix, up to N *tries*. Each round shows ❌/✅. ■ stops at any time.
  - It knows your locked decisions, 📌 items, project memory, the Tool 2 blueprint, the file tree and the last run. Put the *Co-coding* agent on Ollama/LM Studio (a 14B coder) or Claude.
- **Runs:** each run is kept in `data/runs/<id>/` (logs, `metrics.json`, `figures/`). Open a run to see metrics, curves and figures; **Use results in the paper** fills the results notes and adds a LaTeX table of the **measured** numbers to the Writer (or *⇣ Import results from Code IDE* in the Writer).
- **Source Control / GitHub:** *Initialize repository* → changes, diff → *Commit* → *Push/Pull*. **🚀 Publish to GitHub**: repo name, public or private. Needs a **Personal Access Token** (⚙ GitHub settings): stored in `data/config.json`, sent only to GitHub, never written to `.git/config`.
- Write `metrics.json` (a dict of numbers, or a list per epoch) in the working folder or `/runs/<id>/` for exact metrics; save `.png/.svg/.pdf` plots to `figures/`.

## 🐳 Docker & System (v3.0)

A detailed monitor that refreshes every 2 seconds:

- **5 status cards:** Docker (version, WSL2 backend, containers) · Sandbox (engine, image, container, limits) · GPU (utilization, VRAM, temperature/power, driver/CUDA) · Host (RAM, CPU, disk holding `data/`) · Container usage (CPU, RAM, processes, I/O), plus 4 sparklines.
- **Sandbox container:** ▶ Start, ■ Stop, ↻ Restart, ♻ Recreate (applies a new image/limits), ⤓ Pull image (with progress), 🎮 Test GPU.
- **Sandbox settings (per project):** engine (Auto / Docker only / local venv), image, RAM/CPU/shared-memory limits, GPU passthrough, network (needed for `pip install`), time limit, self-debug attempts.
- **Jobs:** every run with status, duration, exit code and a log viewer.
- **Recommended setup:** the app scans the machine (OS, CPU, RAM, GPU, Docker, WSL2, Git, LaTeX, Ollama/LM Studio) and proposes a PyTorch+CUDA image when the GPU is usable in Docker, RAM/CPU limits, the **local model size for your VRAM** (12 GB → 14B Q4_K_M, 8k context) and agent engines. Press *⚡ Apply recommended setup*.
- **MCP server:** other AI apps on this computer (Claude Desktop, VS Code…) can use the sandbox via `http://127.0.0.1:8765/mcp` or `mcp_stdio_bridge.py`.

**Windows 11 setup (Docker Desktop + WSL2 + GPU):**
1. Install a recent NVIDIA driver for **Windows** (no Linux driver inside WSL).
2. PowerShell (Admin): `wsl --install` (or `wsl --update`), reboot.
3. Install Docker Desktop with *Use WSL 2 based engine*; start it.
4. In the app: Docker tab → *🎮 Test GPU*. The first time downloads the PyTorch+CUDA image (≈ 8 GB).
5. 12 GB card: **⏏ unload the Ollama/LM Studio model** in the sidebar before long GPU training runs.

## 🧠 Context & memory (v3.0)

- **Knowledge graph:** everything the agents know about the project — objectives, hypotheses, locked decisions, constraints, literature, code assumptions, metrics, summaries. Filter by type, search, *show purged*.
- Click a node to **inspect / edit**, **📌 Pin** (every agent *must* follow it — injected into every chat as MUST-FOLLOW context), **🗑 Purge** (hidden from every agent; purged papers leave the reference digest; data is kept and can be restored), or delete nodes you added.
- **Context Decision Agent:** say it in plain words, e.g. *"Prune the old CNN assumptions and focus on tensor-decomposition FLOPs reduction"*. It proposes operations (pin, purge, add constraint…); tick them and press *✓ Apply selected*.
- **3-tier memory** (`data/memory/project_state.json`):
  - **Tier 1 · Working memory:** recent chat turns of every tool + sandbox logs.
  - **Tier 2 · Episodic summaries:** when Tier 1 passes the threshold (default 24,000 tokens) the **background summarizer on the local model** compresses older turns into episodes. *🗜 Summarize now*, keep (never merge) or delete episodes.
  - **Tier 3 · Long-term knowledge:** goals, hypotheses, constraints (taken from Lit2Plan, editable), best metrics from runs, validated references, locked decisions.
  - The agents remember the whole project without overflowing a 14B model's context.

## Internet search (v2.6)

The AI agents can **search the internet for papers and up-to-date information** before answering. Results are real records from scholarly databases and search engines; the AI reads and cites them and never invents sources.

**On/off per chat:** use the **🌐** selector next to the message box. It is available in every tool that has a chat:
- **🌐 Search: off** — as before, no searching.
- **📚 Search papers** — OpenAlex, arXiv, Semantic Scholar (free, no key).
- **🌐 Search web** — DuckDuckGo (free), or Tavily / Brave with your own key.
- **🌐📚 Papers + web** — both.

The choice is remembered per tool.

**How it works:** for each question,
1. a small planner agent writes 1–3 English queries. "Latest" or "since 2023" questions add a year filter automatically;
2. the app searches, merges duplicates (by DOI) and numbers the results **[S1], [S2]…**;
3. the AI answers with link citations like **[S1](url)**.

Under every answer, a **🌐 sources** list shows authors, year, venue and citation count. For each source:
- **📥 Library** downloads the open-access PDF into your Reference Library, with clean metadata (title, authors, DOI).
- **📎** attaches the full page or PDF to your next question.

**Tool 1 Lit2Plan:** choose *🌐 Internet search while planning*. The plan is then grounded in real, recent papers, gets an extra **9. Key Papers Found Online** section, and shows a **Literature found online** card for saving PDFs.

**Reference Library → 🔎 Find papers online:** search a topic (optional "since year"), then 📥 to add papers directly.

**Settings (sidebar → 🔎 Internet search):**
- web search engine and API key (Tavily, Brave);
- results per search;
- Semantic Scholar key and OpenAlex e-mail (optional, faster and more reliable);
- whether to read the top web pages.

> Only the search queries leave your computer, never your files or project data. Paper results include only the abstract, so open the paper before citing details. Without an internet connection the app reports the error and still answers from your local library.

## Recommended 6-month workflow

| Phase | Main actions in the app | Result |
|---|---|---|
| Weeks 1–2 | Create project → load 20–40 core PDFs → Lit2Plan → deepen in chat → pin decisions | Direction, H1–H3, roadmap |
| Weeks 3–4 | Tool 2 → run `experiment_skeleton.py` → fix code with logs in chat | Working experiment pipeline |
| Months 2–4 | Run experiments → Data Chat → add tables to the paper | LaTeX result tables |
| Month 5 | Paper Writer: 🔬 Deep mode → read section reviews → instructions + hand edits → Paper chat | Full draft |
| Month 6 | ④ Paper Review at the target venue level → quick-fix critical → minor → verify citations and numbers → Masterclass (cover letter) → latex.zip → Overleaf | Submission |

## Tips for high quality

- **Feed real material:** the more full-text PDFs, logs and numbers you give, the less generic the answers.
- **Constrain prompts:** venue, length, hypothesis, compute limits.
- **One chat session per topic:** use ＋ New instead of one long, mixed thread.
- **Cross-review:** draft with one model, review with another (3.3), or re-review in Paper chat.
- **Pin decisions:** key constraints (venue, scope, parameter budget) belong in 📌 so every tool respects them.
- **Always verify:** open every citation chip, compare table numbers with raw logs, search for `[TBD]` and `[CITATION NEEDED]`.

## Shortcuts & quick actions

| Action | How |
|---|---|
| Send / new line | Enter / Shift+Enter |
| Stop an answer / a running agent | ■ in chats, **■ Stop** in Paper Writer and Paper Review |
| Close dialogs and menus | Esc |
| Pick a model | Type to filter, ↑/↓ to move, Enter to pick |
| Quick attach | Drop files or paste images into the chat box |
| Reading view | ⤢ button |
| Light/dark theme | ☀ / 🌙 / 🖥 at the top right |
| Interface language | **EN / VI** at the top right |

## Data, backup & upgrades

- **Your data lives in:** `data/` (settings, API keys, Default project), `references/` (PDFs of the Default project) and `projects/` (other projects).
- Inside every project's data folder (v3.0): `workspace/` (paper, chats, Lit2Plan versions), `code/` (Code IDE, git repo), `runs/` (logs, metrics, figures), `sandbox/` (settings, venv), `memory/` (memory, context graph), `results/` (results you uploaded). `data/system/` caches the machine scan. **⬇ project_export.zip** (Writer) bundles it all.
- **Backup:** zipping the project's data folder is enough.
- **Upgrading:**
  1. Extract the **whole** new zip into a **new folder**.
  2. Copy `data/`, `references/` and `projects/` over from the old folder.
  3. **Never** copy single files over an old version. `start.py` detects mixed versions.
- **Security:** API keys are stored as plain text in `data/config.json`, so keep that folder private. Each key is only sent to its own provider. The server listens on `127.0.0.1` only, so other machines on your network cannot reach it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Page does not open | Keep the black window open; read the `[ERROR]` line; try `python start.py --check` |
| "Cannot reach LM Studio" | LM Studio → Developer → Start Server; the URL must end with `/v1` |
| 401/403 from a provider | Wrong or expired key, or billing not enabled |
| 404 "model not found" | Click ↻ List and pick a model your account has |
| PDF "no extractable text" | Scanned PDF → run OCR first |
| Link cannot be read | Page needs login/JavaScript → download the PDF and attach it |
| Windows blocks a DLL (Smart App Control) | The app switches to pypdf automatically; no need to disable security |
| Ubuntu "externally-managed-environment" | `start.py` creates `.venv` automatically; if missing: `sudo apt install python3-venv` |
| New tabs missing after an upgrade | An older copy is still running (old black window). Close all old windows and run `run.bat` again; if the browser still shows the old page press **Ctrl+F5**. Since v3.1 the launcher detects this and starts the new version on another port |
| Code IDE says "Docker not running" | Start Docker Desktop and wait for the whale icon to settle; meanwhile code runs in the local venv |
| GPU not available in Docker | Update the NVIDIA Windows driver, enable WSL integration in Docker Desktop, `wsl --update`. The app retries on CPU |
| CUDA out of memory | ⏏ Unload the Ollama/LM Studio model in the sidebar before training |
| `pip install` fails in the sandbox | Turn on 🌐 Network in sandbox settings, then ♻ Recreate the container |
| Publish to GitHub returns 401 | Token lacks permissions: fine-grained needs *Contents* + *Administration* (read/write), or classic `repo` |
