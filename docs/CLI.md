# Terminal research client

`phdlab` connects to the same running backend as the browser. Start `run.bat` (or `phdlab serve`) once, then open another terminal for the client. On Windows use `.\phdlab.bat`; on Linux/macOS use `./phdlab`. The examples below abbreviate this as `phdlab`.

## Connect and start a conversation

```text
phdlab
phdlab --server http://127.0.0.1:8765
phdlab chat --new
phdlab chat --session as-0123456789
phdlab ask "/lit token pruning for edge transformers"
phdlab --json status
```

`PHDLAB_URL` changes the default server. Global `--server` and `--json` options go before the command. The terminal client keeps no separate research database.

In chat, Tab completes commands. Type a normal question or a research skill such as `/lit`, `/plan`, `/write` or `/verify`. `/help` lists both research skills and terminal commands. Ctrl+C during an answer requests cancellation; Ctrl+D or `/quit` exits the client. Exiting the client does not shut down the shared server.

## Accept or reject proposals

A response can propose a file, a memory change or a background run. `/pending` prints numbered decisions. `/accept 1` accepts one proposal, `/reject 1` rejects it, and `/accept all` accepts every currently listed proposal. Inspect the list before using `all`. Code and compute requests still use the backend's risk and budget rules.

Use `/runs` to find background work, `/run RR-...` to inspect it and `/follow RR-...` to watch progress. A run in `NEEDS_USER_ACTION` keeps its recovery proposal. Outside chat:

```text
phdlab runs show RR-01234567
phdlab runs approve RR-01234567
phdlab runs resume RR-01234567 --accept
phdlab runs provider RR-01234567 S1 app
phdlab runs cancel RR-01234567
```

## Projects, documents and experiments

```text
phdlab project new "Edge transformers" --topic "Token pruning"
phdlab outline set direction "Keep inference within a 2W budget"
phdlab outline attach proposal.docx
phdlab code new baseline
phdlab code vscode
phdlab code sync
phdlab library add reference.pdf
phdlab review new manuscript.md
```

A research project contains several code projects; code actions require one to be open. `/attach path/to/file` attaches a document to the next chat message. Model selection uses `/model`, while `/reasoning` sets the requested reasoning level supported by that provider. Keys and endpoint settings can also be edited in the browser Settings page.

## Terminal slash commands

The table is generated from the current REPL registry. Research skills are loaded separately from `backend/agent/skills/` and user/project skills; `/help` and `phdlab skills list` show the current list.

| Command | Arguments | Description |
|---|---|---|
| `/help` |  | mọi lệnh / (kỹ năng + lệnh terminal) |
| `/quit` |  | thoát |
| `/exit` |  | thoát |
| `/new` |  | cuộc trò chuyện mới |
| `/sessions` |  | các cuộc trò chuyện của dự án |
| `/open` | <id> | mở một cuộc trò chuyện |
| `/rename` | <tên> | đổi tên cuộc trò chuyện |
| `/model` | [provider] | mô hình cho cuộc trò chuyện (không tham số: danh sách) |
| `/reasoning` | [auto\|off\|low\|medium\|high] | cấp độ tư duy |
| `/attach` | <file> | đính kèm file vào tin nhắn tiếp theo |
| `/pending` |  | những gì đang chờ bạn duyệt |
| `/accept` | <số\|all> | chấp nhận đề xuất / run |
| `/reject` | <số\|all> | bỏ qua đề xuất / huỷ run |
| `/runs` | [all] | các run chạy nền |
| `/run` | <RR-id> | chi tiết một run |
| `/follow` | <RR-id> | theo dõi một run |
| `/cancel` | <RR-id> | huỷ một run |
| `/outline` | [show\|set <cấp> <nội dung>\|attach <file>] | đề cương nghiên cứu (không tham số: AI đề xuất) |
| `/library` | [add <file.pdf>] | tài liệu PDF của dự án |
| `/code` | [list\|new <tên>\|open <tên>\|vscode\|sync\|jobs] | thí nghiệm trong VS Code |
| `/review` | [list\|new <file>\|run <id>] | phản biện bài báo |
| `/pins` |  | kết quả đã ghim |
| `/providers` |  | research providers (Feynman, Claude Code, Codex…) |
| `/models` |  | agent và mô hình đang dùng |
| `/unload` |  | gỡ mô hình local khỏi VRAM |
| `/config` | [khoá [giá trị JSON]] | xem / đổi cài đặt (vd /config runs.max_minutes 60) |
| `/project` | [list\|new <tên>\|use <thư mục>] | dự án nghiên cứu |
| `/dashboard` |  | tiến độ (như trang Theo dõi) |
| `/clear` |  | xoá màn hình |

## Script commands

Run `phdlab <command> --help` or `phdlab <group> <command> --help` for flags. `phdlab commands --markdown` prints this registry.

| Command | Arguments | Description |
|---|---|---|
| `phdlab acceptance` |  | The eight AI Research OS acceptance criteria and their executable evidence |
| `phdlab api` | <method> <path> [--data DATA] | Call any backend route: phdlab api GET /api/dashboard |
| `phdlab ask` | <text> [--session SESSION] [--timeout TIMEOUT] | One turn in the research chat, printed, then exit ("/skill …" works too) |
| `phdlab chat` | [--session SESSION] [--new] | Open the research chat (the default when phdlab runs without a command) |
| `phdlab commands` | [--markdown] | Every CLI command (--markdown: the table of the CLI guide) |
| `phdlab events` | [--after AFTER] | Changes made by any client (UI or CLI) since an event number |
| `phdlab providers` |  | Research providers (Feynman, Claude Code, Codex, Gemini, Antigravity, Python, Docker, LaTeX) |
| `phdlab serve` | [--port PORT] [--open-browser] | Start the backend server in this terminal (UI + CLI share it) |
| `phdlab status` |  | Goal, current step, status, what waits for you, pinned results |
| `phdlab code jobs` | [--limit LIMIT] | Experiment jobs (venv / Docker) with their metrics |
| `phdlab code list` |  | Code projects |
| `phdlab code new` | <name> | Create a code project (git + Python venv) and open it |
| `phdlab code open` | <name> | Make a code project the active one |
| `phdlab code sync` | [--session SESSION] | Bring VS Code work back: proposals in a conversation (commit, new metrics) |
| `phdlab code vscode` |  | Open the active code project in VS Code |
| `phdlab history list` | [--q Q] | Conversations of the project |
| `phdlab history show` | <id> | A conversation as text |
| `phdlab library add` | <files> | Add PDF files to the project library |
| `phdlab library list` |  | Reference PDFs of the project |
| `phdlab models list` |  | The agents and the providers the chat can use |
| `phdlab models unload` | [--force] | Unload local models from VRAM (LM Studio / Ollama) |
| `phdlab outline attach` | <file> | Attach a proposal file (PDF, Word .docx, Markdown, text, LaTeX) |
| `phdlab outline set` | <field> <text> | Set one level: keywords \| topic \| direction \| method \| proposal (@file.md reads a file) |
| `phdlab outline show` |  | The research outline (level 1–5) and attached files |
| `phdlab project list` |  | Research projects |
| `phdlab project new` | <name> [--dir DIR] [--topic TOPIC] | Create a research project and switch to it |
| `phdlab project use` | <data_dir> | Switch to another research project |
| `phdlab review list` |  | Paper review sessions |
| `phdlab review new` | <file> | Start a review from a manuscript (PDF, DOCX, TEX, MD, TXT) |
| `phdlab review run` | <id> | Run reviewers → area chair → issue list (streams) |
| `phdlab runs approve` | <id> | Accept a run that waits for approval |
| `phdlab runs cancel` | <id> | Cancel a run |
| `phdlab runs follow` | <id> [--timeout TIMEOUT] | Print a run's timeline until it ends or needs you |
| `phdlab runs list` | [--status STATUS] | Research runs of the project |
| `phdlab runs new` | <skill> [input] [--follow] | Start a run with a skill: phdlab runs new lit "token pruning" |
| `phdlab runs provider` | <id> <step> <provider> | Move a pending / failed step to another provider |
| `phdlab runs resume` | <id> [--accept] [--command COMMAND] | Answer NEEDS_USER_ACTION: --accept applies the recovery proposal; --command overrides the step |
| `phdlab runs show` | <id> | One run: steps, outputs, proposal |
| `phdlab skills add` | <file> [--scope SCOPE] | Create / replace your skill from a Markdown file |
| `phdlab skills list` |  | Every / command (built-in, yours, this project's) |

## Exit codes and troubleshooting

| Code | Meaning |
|---|---|
| 0 | Command succeeded |
| 1 | Backend refused the operation or the requested run needs attention |
| 2 | Invalid command or arguments |
| 3 | Backend is unreachable |
| 130 | Interrupted by Ctrl+C |

If the server is unreachable, start the backend and verify the URL. If a provider is unavailable, inspect `phdlab providers` and its sign-in/configuration detail. If a code action returns `NO_CODE_PROJECT`, run `phdlab code list`, then create or open a code project. Journal/search API keys and imported rankings are configured in the browser Settings page; paper search is also reachable through `phdlab api POST /api/search --data @query.json`.

For scripted JSON requests use `--data @file.json` instead of embedding complex JSON in shell arguments. Never include actual API keys in a command saved to shell history.
