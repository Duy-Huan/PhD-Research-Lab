# CLI studio 6.6.3: evidence

Contract: `docs/qa/contracts/FQC-CLI-STUDIO-663.json`. Base: `19a1b3e` on `dev` (v6.6.2 released as `da8dbdb`).

## What changed

- **Chat CLI** opens in the main area instead of the narrow right drawer. The prompt is the bottom block. The transcript has its own frame, and every AI answer has its own frame, labelled with the provider that wrote it.
- Providers come from `/api/models` (`transport: cli`); unavailable ones are disabled and their tooltip gives the reason. The chosen provider is sent with each turn and saved as the conversation's provider.
- Turn states: manual launch button, inline failures (no `alert()`), run cards, and approvals listed one by one. `/accept all` reports what it approved.
- The CLI keeps its own conversation; its id survives a reload.
- **Open in cmd** (`POST /api/chat/sessions/{sid}/console`) continues the same conversation in `phdlab chat --session <id>` in a new console. It runs a fixed command, the session id is validated, the console talks to the server's own loopback port, and API keys are not passed on.
- Labels follow the active language, colours follow the theme. Phones get one-line scrolling strips and icon-only actions.
- Found during QA and fixed:
  - **Mobile sidebar:** it stayed open over the CLI on phones.
  - **Floating "Right menu" handle:** it covered the header. It is now icon-only at 820px and narrower.
  - **Saved theme:** it was not applied after a reload, so every reload fell back to the system theme.

## RED / GREEN

| Layer | RED | GREEN |
|---|---|---|
| Backend `tests/test_cli_console.py` | `red-backend.json`: 6 tests on `19a1b3e`, 9 errors (no endpoint) | `green-backend.json`: 6/6 PASS, including a real `cmd.exe` quoting run |
| Vitest, CLI and settings | `red-vitest.json`: the first 9 CLI tests, all FAIL on the old component | `green-vitest.json`: 57/57 PASS (CLI, settings, shell) |
| Playwright `cli_studio.spec.ts` + `shell_layout.spec.ts` | `red-e2e-overlap-360-en.md`: title over the "Open in cmd" button at 360px (4 variants failed)<br>`red-e2e-theme-reload.md`: saved theme not applied (19/19 failed)<br>`red-e2e-sidebar-1024-en.md`: sidebar defects at 1024px<br>`red-e2e-handle-library-1440.md`: the handle covered Upload PDF (8 of 20 shell tests failed) | `green-e2e.json`: 39/39 PASS (CLI 19, shell 20), screenshot bodies stripped. Three earlier consecutive CLI runs also passed 19/19. |

These tests were each run and seen to FAIL before their implementation, but the failing runs were only captured in the session log:
- the "Open in cmd" UI test;
- the two provider-sync tests;
- the theme start-up test.

The e2e 100-message case uses a MOCKED session served by `page.route`. It checks layout only, not model output.

## Live acceptance (owner's accounts, disposable data folder `D:/qa663`, port 8791)

- **Claude Code**, before the fix: the turn (default selection, sent before the provider list had loaded) failed with `Not logged in · Please run /login`, even though readiness said `CONNECTED`. The container home had no credentials. **Fixed** by `FQC-CLAUDE-SIGNIN-663`. After the fix, readiness reads "this computer's Claude subscription sign-in is shared with PhD Lab's runtime". A live turn (session `as-e26cfb53c8`) completed with `provider: cli:claude_code`, and the container's copy has no refresh token.
- **Codex:** the turn completed, the message provider was `cli:codex`, and the answer was `2 + 2 bằng 4.`
- **Open in cmd:** `cmd.exe /d /k "chcp 65001 >nul & "<python>" -m backend.cli chat --session as-ed3757fbc5"` started. The server log shows the console client reading that session. The tester closed the window by killing only that process tree.
- **`chat.bat` in `cmd.exe`:**
  - `status`, `/model` (lists `cli:codex`, `cli:claude_code`; Gemini `AUTH_EXPIRED`), `/pending` and `/exit` work.
  - Vietnamese text renders under UTF-8.

## Findings from the same pass, fixed in 6.6.3

- **Sidebar at 1024–1280px:**
  - the brand title wrapped onto three lines;
  - "Models & AI connections" and "Native code & experiments" had their icons squeezed to 0–8 px;
  - the guide and settings buttons fell outside the sidebar;
  - the workspace pill was truncated without a tooltip;
  - the 20–22 px icon buttons overflowed.

  Root causes in the shared CSS: icons could shrink (`.btn svg`), and `.icon` kept the browser's button padding. Fixed shell-wide.
- **"Right menu" handle:** it covered Upload PDF in the Library at 1024 and 1440 px. It is now icon-only, with its name in the tooltip and aria-label. Settings, Dashboard, Review, Harness, chat and CLI were checked clear.
- **Still open:** the first `/api/models` call takes several seconds while the CLIs are probed. The CLI shows "Checking CLI tools…", and a turn sent meanwhile uses the stored provider.
