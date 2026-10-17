# PhD Research Lab — User Guide

PhD Research Lab is a research workbench that runs on your own computer. It combines **cloud AI** (Claude, GPT, Gemini…) for deep reasoning and academic writing with **local AI** (LM Studio) for fast, private, zero-cost extraction work. This guide covers installation, each tool, and the most effective end-to-end workflow for a PhD researcher.

> **Golden rule:** the AI drafts, **you** are the author. Verify every citation, number and claim before you submit.

## Quick start (5 minutes)

1. **Start the app:** Windows `run.bat`; Linux/macOS `./run.sh`. Your browser opens `http://127.0.0.1:8765`.
2. **Add an API key:** sidebar → *Cloud AI providers* → click a provider (e.g. Anthropic Claude) → paste the key → **↻ List** → pick a model → **Test connection** → **Save configuration**.
3. **(Optional) Local AI:** LM Studio → *Developer* tab → load a 7–14B model → **Start Server**. The app shows "LM Studio online".
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
5. Pin 📌 key decisions (venue, scope, main hypothesis) so Tools 2–4 know them too.

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

## Tool 3 — Library, Data Chat & Paper Writer

### 1. Reference Library
- Drop full-text PDFs. The app extracts title, authors, abstract, DOI and year. Click **✨ AI-parse** to let the AI normalise the metadata.
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
- **📝 Instructions for AI:** your own requirements for this section, e.g. *"stress the 2 W budget, keep it under one page"*. They are sent on every write or revise and take precedence over reviewer suggestions.
- **🔬 In-depth writing:** longer, more detailed output for single ✍ Write / ✎ Revise runs.
- **✓ Accept:** marks the section as final.

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

**Chat sessions:**
- Each tool keeps its own session list: new, rename, delete, export to Markdown.
- *Auto-open* decides whether the last session reopens on start.

**Limits per message:** about 150,000 characters of documents and at most 8 images. The newest message's attachments get priority.

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
