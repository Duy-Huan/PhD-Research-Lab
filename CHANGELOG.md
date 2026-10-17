# Changelog

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
