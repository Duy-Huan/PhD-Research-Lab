# Changelog

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
