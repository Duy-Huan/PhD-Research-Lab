"""The research chat in the terminal — `phdlab` without arguments (like Claude Code: a chat that lives in the
terminal, "/" opens every command, answers stream in Markdown, proposals wait for /accept).

Same conversations, skills, proposals, runs, settings as the browser UI: both are clients of one backend, so what you do
here appears in the UI at once. In a real terminal it uses prompt_toolkit (completion menu with descriptions, history,
status bar) and rich (Markdown, live streaming); piped / scripted input falls back to plain text.

    › tìm research gap cho đề tài          a normal message (the orchestrator picks a skill when it fits)
    › /lit token pruning                   a research skill (type / to see them all, Tab completes)
    › /accept 1 · /reject all              decide on what waits for you (proposals, memory, runs)
    › /model · /reasoning high · /attach paper.pdf · /runs · /outline · /code vscode · /review · /config · /quit
Ctrl+C while an answer streams stops that answer; Ctrl+D (or /quit) leaves.
"""
from __future__ import annotations

import os
import re
import shlex
import time

from backend.cli import CLIError
from backend.core.config import APP_VERSION

HIDE = re.compile(r"```phdlab-(action|memory)\s*\n.*?```", re.S)
ACTION = {"update_outline": "Cập nhật đề cương", "start_run": "Chạy trong nền", "write_section": "Lưu phần bài báo",
          "commit_code": "Commit code", "add_decision": "Khoá quyết định", "propose_gap": "Ghi research gap",
          "create_hypothesis": "Thêm giả thuyết", "create_experiment": "Tạo thí nghiệm", "record_result": "Ghi kết quả",
          "pin_result": "Ghim kết quả", "propose_memory": "Ghi nhớ", "add_note": "Ghi chú"}
LEVELS = {"auto": "tự động", "off": "tắt", "low": "thấp", "medium": "vừa", "high": "cao"}


def clean(text: str) -> str:
    return HIDE.sub("", text or "").strip()


def visible(full: str) -> str:
    """What may be shown of a streaming answer: proposal blocks (listed as numbered items afterwards) are hidden,
    also while they are still arriving."""
    t = HIDE.sub("", full)
    m = re.search(r"```phdlab-(action|memory)[\s\S]*$", t)
    if m:
        t = t[:m.start()]
    k = t.rfind("```")
    if k >= 0 and "\n" not in t[k:] and "phdlab-".startswith(t[k + 3:k + 10]):
        t = t[:k]  # could be the start of a proposal block: wait for more text
    return re.sub(r"`{1,2}$", "", t)


def _split(text: str) -> list:
    """Arguments of a terminal command; Windows paths keep their backslashes, quotes group words."""
    return [x.strip('"') for x in shlex.split(text, posix=os.name != "nt")] if text else []


def _brief(a: dict) -> str:
    g = a.get("args") or {}
    if a["name"] == "start_run":
        return f"/{g.get('skill')} {str(g.get('input', ''))[:90]}"
    for k in ("title", "text", "message", "topic", "section"):
        if g.get(k):
            return str(g[k])[:120].replace("\n", " ")
    return a.get("reason", "")[:120]


class Out:
    """Terminal output: rich (Markdown, colours, live streaming) on a real terminal, plain text otherwise."""

    def __init__(self, stream, rich_ok: bool):
        self.stream = stream
        self.console = None
        if rich_ok:
            from rich.console import Console
            self.console = Console(file=stream, highlight=False, soft_wrap=False)

    def line(self, text: str = "", style: str = "") -> None:
        if self.console:
            self.console.print(text, style=style or None, markup=False)
        else:
            self.stream.write(text + "\n")
            self.stream.flush()

    def md(self, text: str) -> None:
        if self.console:
            from rich.markdown import Markdown
            self.console.print(Markdown(text or ""))
        else:
            self.line(text)

    def raw(self, text: str) -> None:
        self.stream.write(text)
        self.stream.flush()

    def panel(self, content, title: str = "", subtitle: str = "", border_style: str = "#d2602a", style: str = "") -> None:
        if self.console:
            from rich.panel import Panel
            from rich import box
            p = Panel(content, title=f"[bold]{title}[/bold]" if title else None,
                      subtitle=subtitle or None, box=box.ROUNDED, border_style=border_style,
                      style=style or None)
            self.console.print(p)
        else:
            if title:
                self.line(f"╭── {title} " + "─" * max(2, 50 - len(title)) + "╮")
            if isinstance(content, str):
                for l in content.splitlines():
                    self.line(f"│ {l}")
            else:
                self.line(str(content))
            if subtitle:
                self.line(f"╰── {subtitle} " + "─" * max(2, 50 - len(subtitle)) + "╯")
            elif title:
                self.line("╰" + "─" * 56 + "╯")


class Repl:
    def __init__(self, x):
        self.x, self.c = x, x.c
        self.sid = ""
        self.items: list = []      # numbered decisions: (kind, id, label)
        self.atts: list = []       # attachments for the next message: (id, name)
        self.skills: list = []
        self.inp = getattr(x, "inp", None)
        import sys
        self.tty = self.inp is None and _isatty(x.out) and _isatty(sys.stdin)
        if self.inp is None and not self.tty:
            self.inp = input  # piped / scripted: plain lines
        self.o = Out(x.out, self.tty)
        self.session = None        # prompt_toolkit PromptSession (terminal only)
        self.language = 'vi'
        self.commands = self._commands()

    def t(self, vi: str, en: str) -> str:
        return en if self.language == 'en' else vi

    def refresh_language(self, cfg=None):
        cfg = self.c.get('/api/config') if cfg is None else cfg
        self.language = 'en' if (cfg.get('ui') or {}).get('language') == 'en' else 'vi'
        self.commands = self._commands()
        return cfg

    # ------------------------------------------------------------------ loop
    def new_session(self) -> str:
        return self.c.post("/api/chat/sessions", {})["id"]

    def run(self, session: str = "", new: bool = False) -> int:
        if session:
            self.c.get(f"/api/chat/sessions/{session}")
            self.sid = session
        elif not new:
            last = self.c.get("/api/chat/sessions", limit=1)["sessions"]
            self.sid = last[0]["id"] if last else ""
        self.skills = self.c.get("/api/skills")["skills"]
        self.banner()
        if self.sid:
            self.pending(quiet=True)
        while True:
            try:
                line = self.read()
            except EOFError:
                self.o.line("")
                return 0
            except KeyboardInterrupt:
                continue
            line = (line or "").strip()
            if not line:
                continue
            try:
                if self.handle(line) == "quit":
                    return 0
            except CLIError as e:
                self.o.line(f"⚠ {e}", "yellow")

    def read(self) -> str:
        self.refresh_language()
        if self.inp is not None:
            return self.inp("\n› ")
        if self.session is None:
            try:
                self.session = self._prompt_session()
            except Exception:  # e.g. Git Bash / mintty without a Windows console: plain input still works
                self.inp = input
                return self.inp("\n› ")
        return self.session.prompt("❯ ", bottom_toolbar=self.toolbar)

    def banner(self) -> None:
        cfg = self.refresh_language()
        title = self.c.get(f"/api/chat/sessions/{self.sid}")["title"] if self.sid else self.t('cuộc trò chuyện mới', 'new conversation')
        proj = cfg.get("project") or {}
        pname = proj.get("name") or self.t('Dự án Hiện tại', 'Current Project')
        ver = cfg.get("version", APP_VERSION)
        agents = cfg.get("agent_models") or {}
        model_str = agents.get("assistant") or self.t('tự động', 'auto')
        if self.o.console:
            from rich.panel import Panel
            from rich.text import Text
            from rich import box
            t = Text()
            t.append("● PhD Research Lab ", style="bold #d2602a")
            t.append(f"v{ver}  ·  Claude CLI Mode\n", style="bold cyan")
            t.append(self.t(f"Dự án: {pname}   Mô hình: {model_str}\n", f'Project: {pname}   Model: {model_str}\n'), style="bold white")
            t.append(self.t(f"Đoạn chat: {title}\n", f'Conversation: {title}\n'), style="cyan")
            t.append("─" * 60 + "\n", style="dim")
            t.append(self.t('Gõ câu hỏi hoặc / để chọn lệnh/kỹ năng · Tab hoàn thành · /help · Ctrl+D thoát\n', 'Ask a question or / for commands · Tab to complete · /settings · /help · Ctrl+D to exit\n'), style="yellow")
            t.append(self.t('Hỗ trợ toàn diện mọi workflow: /lit, /outline, /workflow, /code, /review, /paper', 'Research workflows: /lit, /outline, /workflow, /code, /review, /paper'), style="dim green")
            self.o.console.print(Panel(t, title="[bold #d2602a]✦ Claude CLI Terminal[/bold #d2602a]", border_style="#d2602a", box=box.ROUNDED, expand=False))
        else:
            self.o.line(f"PhD Research Lab — {pname} · {title}")
            self.o.line(self.t('gõ câu hỏi hoặc /lệnh · /help · /accept · /quit', 'ask a question or /command · /settings · /help · /accept · /quit'))

    def toolbar(self):
        try:
            s = self.c.get(f"/api/chat/sessions/{self.sid}") if self.sid else {"settings": {}, "pending_approvals": 0}
            st = s.get("settings") or {}
            n = sum(1 for a in s.get("approvals") or [] if a["status"] == "pending")
        except CLIError:
            st, n = {}, 0
        model = st.get("provider") or self.t('tự động', 'auto')
        lvl = LEVELS.get(st.get("reasoning") or "auto", self.t('tự động', 'auto'))
        att = f" · 📎 {len(self.atts)}" if self.atts else ""
        return self.t(f" ✦ {model} · tư duy {lvl}{att} · {n} chờ duyệt · /workflow · [?] /help · [Enter] gửi · [Alt+Enter] dòng mới ", f' ✦ {model} · reasoning {lvl}{att} · {n} pending · /settings · /workflow · [?] /help · [Enter] send · [Alt+Enter] newline ')

    def _prompt_session(self):
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.key_binding import KeyBindings
        kb = KeyBindings()

        @kb.add("escape", "enter")
        def _(event):  # Alt+Enter: new line
            event.current_buffer.insert_text("\n")
        hist = os.path.join(os.path.expanduser("~"), ".phdlab_history")
        return PromptSession(history=FileHistory(hist), completer=Completer(self), complete_while_typing=True,
                             key_bindings=kb, multiline=False)

    # ------------------------------------------------------------------ dispatch
    def handle(self, line: str):
        self.refresh_language()
        m = re.match(r"^/([\w-]+)(?:\s+([\s\S]*))?$", line)
        name = m.group(1) if m else ""
        if name in self.commands:
            return self.commands[name][0]((m.group(2) or "").strip())
        if not self.sid:
            self.sid = self.new_session()
        self.send(line)
        return None

    def _commands(self) -> dict:
        """name → (handler, usage, description). Server skills (/lit, /idea …) are sent to the chat as they are."""
        return {
            "help": (self.c_help, "", self.t('mọi lệnh / (kỹ năng + lệnh terminal)', 'all / commands (skills and terminal commands)')),
            "settings": (self.c_settings, "[section|set <path> <JSON>]", self.t('menu cài đặt dùng chung với web', 'shared web settings menu')),
            "language": (self.c_language, "[en|vi|ai auto|en|vi]", self.t('ngôn ngữ giao diện và AI', 'interface and AI language')),
            "workflow": (self.c_workflow, self.t('[list|run <tên>|status]', '[list|run <name>|status]'), self.t('điều phối và thực thi mọi quy trình nghiên cứu', 'coordinate research workflows')),
            "harness": (self.c_workflow, self.t('[list|run <tên>|status]', '[list|run <name>|status]'), self.t('quy trình harness tự động hoá và kiểm định', 'harness automation and validation')),
            "quit": (lambda a: "quit", "", self.t('thoát', 'exit')), "exit": (lambda a: "quit", "", self.t('thoát', 'exit')),
            "new": (self.c_new, "", self.t('cuộc trò chuyện mới', 'new conversation')),
            "sessions": (self.c_sessions, "", self.t('các cuộc trò chuyện của dự án', 'project conversations')),
            "open": (self.c_open, "<id>", self.t('mở một cuộc trò chuyện', 'open a conversation')),
            "rename": (self.c_rename, self.t('<tên>', '<name>'), self.t('đổi tên cuộc trò chuyện', 'rename conversation')),
            "model": (self.c_model, "[provider]", self.t('mô hình cho cuộc trò chuyện (không tham số: danh sách)', 'conversation provider (no argument: list)')),
            "reasoning": (self.c_reasoning, "[auto|off|low|medium|high]", self.t('cấp độ tư duy', 'reasoning level')),
            "attach": (self.c_attach, "<file>", self.t('đính kèm file vào tin nhắn tiếp theo', 'attach a file to the next message')),
            "pending": (lambda a: self.pending(), "", self.t('những gì đang chờ bạn duyệt', 'pending approvals')),
            "accept": (lambda a: self.decide("accept", a), self.t('<số|all>', '<number|all>'), self.t('chấp nhận đề xuất / run', 'accept proposal or run')),
            "reject": (lambda a: self.decide("reject", a), self.t('<số|all>', '<number|all>'), self.t('bỏ qua đề xuất / huỷ run', 'reject proposal or cancel run')),
            "runs": (self.c_runs, "[all]", self.t('các run chạy nền', 'background runs')),
            "run": (self.c_run, "<RR-id>", self.t('chi tiết một run', 'run details')),
            "follow": (self.c_follow, "<RR-id>", self.t('theo dõi một run', 'follow a run')),
            "cancel": (self.c_cancel, "<RR-id>", self.t('huỷ một run', 'cancel a run')),
            "outline": (self.c_outline, self.t('[show|set <cấp> <nội dung>|attach <file>]', '[show|set <level> <content>|attach <file>]'), self.t('đề cương nghiên cứu (không tham số: AI đề xuất)', 'research outline (no argument: ask AI)')),
            "library": (self.c_library, "[add <file.pdf>]", self.t('tài liệu PDF của dự án', 'project PDF library')),
            "code": (self.c_code, self.t('[list|new <tên>|open <tên>|vscode|sync|jobs]', '[list|new <name>|open <name>|vscode|sync|jobs]'), self.t('thí nghiệm trong VS Code', 'experiments in VS Code')),
            "review": (self.c_review, "[list|new <file>|run <id>]", self.t('phản biện bài báo', 'paper review')),
            "pins": (self.c_pins, "", self.t('kết quả đã ghim', 'pinned results')),
            "providers": (self.c_providers, "", "model gateway, Hermes and native CLI providers"),
            "models": (self.c_models, "", self.t('agent và mô hình đang dùng', 'active agents and models')),
            "unload": (self.c_unload, "", self.t('gỡ mô hình local khỏi VRAM', 'unload local models from VRAM')),
            "config": (self.c_config, self.t('[khoá [giá trị JSON]]', '[key [JSON value]]'), self.t('xem / đổi cài đặt (vd /config runs.max_minutes 60)', 'view or change settings (e.g. /config runs.max_minutes 60)')),
            "project": (self.c_project, self.t('[list|new <tên>|use <thư mục>]', '[list|new <name>|use <directory>]'), self.t('dự án nghiên cứu', 'research projects')),
            "dashboard": (self.c_dashboard, "", self.t('tiến độ (như trang Theo dõi)', 'progress dashboard')),
            "clear": (self.c_clear, "", self.t('xoá màn hình', 'clear screen')),
        }

    # ------------------------------------------------------------------ one turn, streamed
    def send(self, text: str, timeout: float = 900) -> int:
        overrides = {}
        if self.atts:
            overrides["sources"] = [f"att:{a}" for a, _ in self.atts]
            text += "\n\n" + "\n".join(f"📎 {n}" for _, n in self.atts)
            self.atts = []
        before = self.c.get(f"/api/chat/sessions/{self.sid}")["last_seq"]
        t = self.c.post(f"/api/chat/sessions/{self.sid}/turns", {"text": text, "overrides": overrides})
        tid, after, shown, full = t["id"], before, 0, ""
        end = time.time() + timeout
        status = t["status"]
        live = None
        if self.o.console and self.o.console.is_terminal:
            from rich.live import Live
            from rich.markdown import Markdown
            live = Live(Markdown(""), console=self.o.console, refresh_per_second=8, vertical_overflow="visible")
            live.start()
        try:
            while time.time() < end:
                for e in self.c.get(f"/api/chat/sessions/{self.sid}/events", after=after)["events"]:
                    after = e["seq"]
                    if e["turn_id"] != tid:
                        continue
                    d = e.get("data") or {}
                    if e["type"] == "message.delta":
                        full += d.get("text", "")
                        vis = visible(full)
                        if live:
                            from rich.markdown import Markdown
                            live.update(Markdown(vis))
                        elif len(vis) > shown:
                            self.o.raw(vis[shown:])
                        shown = max(shown, len(vis))
                    elif e["type"] == "message.completed" and not full:
                        self.o.md(clean(d.get("text", "")))
                    elif e["type"] == "status.updated" and d.get("intent"):
                        self.o.line(self.t(f"· kỹ năng /{d['intent']}", f"· skill /{d['intent']}"), "dim")
                    elif e["type"] == "tool.started":
                        self.o.line(self.t(f"· công cụ {d.get('tool', '')}", f"· tool {d.get('tool', '')}"), "dim")
                    elif e["type"] == "turn.failed":
                        self.o.line(f"✗ {d.get('message', '')}", "red")
                    elif e["type"] == "run.updated":
                        self.o.line(f"· run {d.get('run_id')}: {d.get('status')}", "dim")
                s = self.c.get(f"/api/chat/sessions/{self.sid}")
                status = next((x["status"] for x in s["turns"] if x["id"] == tid), status)
                if status in ("completed", "failed", "cancelled", "awaiting_launch", "waiting_approval"):
                    break
                time.sleep(0.15)
        except KeyboardInterrupt:
            self.c.post(f"/api/chat/sessions/{self.sid}/turns/{tid}/cancel")
            self.o.line(self.t('(đã dừng)', '(stopped)'), "yellow")
            return 130
        finally:
            if live:
                live.stop()
        if full and not live:
            rest = HIDE.sub("", full)[shown:]
            if rest.strip():
                self.o.raw(rest)
            self.o.line("")
        if status == "awaiting_launch":
            self.o.line(self.t('Chế độ thủ công: duyệt ngữ cảnh rồi gửi trong giao diện web (hoặc đổi chế độ trong /config).', 'Manual mode: review context and send in the web interface (or change mode in /config).'))
        self.pending(quiet=False, turn=tid)
        return 0 if status in ("completed", "waiting_approval", "awaiting_launch") else 1

    # ------------------------------------------------------------------ decisions
    def pending(self, quiet: bool = False, turn: str = "") -> list:
        if not self.sid:
            self.items = []
            if not quiet:
                self.o.line(self.t('Không có gì chờ duyệt.', 'No pending approvals.'))
            return []
        s = self.c.get(f"/api/chat/sessions/{self.sid}")
        items = []
        for a in s["approvals"]:
            if a["status"] == "pending":
                label = (self.t('Công cụ ', 'Tool ') + a["name"]) if a["kind"] == "tool" else ACTION.get(a["name"], a["name"])
                items.append(("ap", a["id"], f"{label} — {_brief(a)}"))
        for it in s.get("memory_items") or []:
            if it["status"] in ("pending", "duplicate"):
                items.append(("mem", it["id"], self.t(f"Ghi nhớ ({it['type']}) — {it['text'][:120]}", f"Memory ({it['type']}) — {it['text'][:120]}")))
        for r in self.c.get("/api/runs", session=self.sid, status="APPROVAL_PENDING,NEEDS_USER_ACTION")["runs"]:
            items.append(("run", r["id"], f"Run {r['id']} {r['status']} — {r['title'][:70]}: {r['next_decision'] or r['reason']}"[:200]))
        self.items = items
        if items:
            if self.o.console:
                from rich.panel import Panel
                from rich import box
                text_card = self.t('Chờ bạn duyệt:\n\n', 'Awaiting your approval:\n\n')
                for i, (_, _, label) in enumerate(items, 1):
                    text_card += f"  [{i}] {label}\n"
                text_card += self.t('\n  → /accept <số|all> · /reject <số|all>', '\n  → /accept <number|all> · /reject <number|all>')
                self.o.console.print(Panel(text_card.rstrip(), title=self.t('[bold yellow]⚠ Quyết định & Phê duyệt[/bold yellow]', '[bold yellow]⚠ Decisions & Approvals[/bold yellow]'), border_style="yellow", box=box.ROUNDED))
            else:
                self.o.line(self.t('Chờ bạn duyệt:', 'Awaiting your approval:'), "bold")
                for i, (_, _, label) in enumerate(items, 1):
                    self.o.line(f"  [{i}] {label}")
                self.o.line(self.t('  → /accept <số|all> · /reject <số|all>', '  → /accept <number|all> · /reject <number|all>'), "dim")
        elif not quiet and not turn:
            self.o.line(self.t('Không có gì chờ duyệt.', 'No pending approvals.'))
        return items

    def decide(self, what: str, arg: str) -> None:
        if not self.items:
            self.pending(quiet=True)
        if not self.items:
            self.o.line(self.t('Không có gì chờ duyệt.', 'No pending approvals.'))
            return
        if arg == "all":
            idx = list(range(1, len(self.items) + 1))
        else:
            try:
                idx = [int(arg or "1")]
            except ValueError:
                raise CLIError(2, self.t('dùng /accept <số> hoặc /accept all', 'use /accept <number> or /accept all'))
        for i in idx:
            if not 1 <= i <= len(self.items):
                raise CLIError(2, self.t(f"không có mục số {i}", f'no item numbered {i}'))
            kind, iid, _ = self.items[i - 1]
            if kind == "ap":
                r = self.c.post(f"/api/chat/sessions/{self.sid}/approvals/{iid}", {"decision": "approve" if what == "accept" else "reject"})
                self.o.line(f"[{i}] {r['status']}" + (f" · {r.get('result')}" if r.get("result") else ""))
                run = (r.get("result") or {}).get("run")
                if run and what == "accept":
                    self.c_follow(run)
            elif kind == "mem":
                self.c.post(f"/api/memory/candidates/{iid}/{'approve' if what == 'accept' else 'reject'}", {})
                self.o.line(f"[{i}] {'đã lưu' if what == 'accept' else 'đã bỏ qua'}")
            elif what == "reject":
                self.o.line(f"[{i}] {self.c.post(f'/api/runs/{iid}/cancel')['status']}")
            else:
                r = self.c.get(f"/api/runs/{iid}")
                path = "approve" if r["status"] == "APPROVAL_PENDING" else "resume"
                self.c.post(f"/api/runs/{iid}/{path}", {"accept": True} if path == "resume" else {})
                self.c_follow(iid)
        self.items = []

    # ------------------------------------------------------------------ terminal commands
    def c_help(self, a):
        lines = [self.t('**Kỹ năng nghiên cứu** (chạy trên máy chủ, giống khung chat web):', '**Research skills** (on the server, shared with web chat):')]
        lines += [f"- `/{s['name']}{(' ' + s['usage']) if s['usage'] else ''}` — {s['description']}" for s in self.skills]
        lines += ["", self.t('**Lệnh terminal:**', '**Terminal commands:**')]
        lines += [f"- `/{n}{(' ' + u) if u else ''}` — {d}" for n, (_, u, d) in self.commands.items() if n != "exit"]
        self.o.md("\n".join(lines))

    def c_new(self, a):
        self.sid = self.new_session()
        self.o.line(self.t('— cuộc trò chuyện mới —', '— new conversation —'), "dim")

    def c_sessions(self, a):
        for s in self.c.get("/api/chat/sessions", limit=20)["sessions"]:
            mark = "●" if s["id"] == self.sid else " "
            self.o.line(f"{mark} {s['id']}  {s['title'][:60]}" + (self.t(f"  ({s['pending_approvals']} chờ duyệt)", f"  ({s['pending_approvals']} pending approvals)") if s["pending_approvals"] else ""))

    def c_open(self, a):
        s = self.c.get(f"/api/chat/sessions/{a}")
        self.sid = a
        for msg in s["messages"][-6:]:
            if msg["role"] == "user":
                self.o.line("› " + msg["content"][:1500], "bold")
            else:
                self.o.md(clean(msg["content"])[:4000])
        self.pending(quiet=True)

    def c_rename(self, a):
        self._need_session()
        self.o.line(self.c.put(f"/api/chat/sessions/{self.sid}", {"title": a})["title"])

    def _need_session(self):
        if not self.sid:
            self.sid = self.new_session()

    def c_model(self, a):
        if not a:
            d = self.c.get("/api/models")
            for p in d["providers"]:
                mark = "✓" if p["available"] else "·"
                self.o.line(f" {mark} {p['id']:<22} {p['label'][:40]:<40} {'' if p['available'] else p['state']}")
            self.o.line("→ /model <id> · /model auto", "dim")
            return
        self._need_session()
        body = {"settings_reset": ["provider"]} if a == "auto" else {"settings": {"provider": a}}
        self.c.put(f"/api/chat/sessions/{self.sid}", body)
        self.o.line(self.t(f"mô hình: {a}", f'provider: {a}'))

    def c_reasoning(self, a):
        if a not in LEVELS:
            raise CLIError(2, self.t('dùng /reasoning auto|off|low|medium|high', 'use /reasoning auto|off|low|medium|high'))
        self._need_session()
        body = {"settings_reset": ["reasoning"]} if a == "auto" else {"settings": {"reasoning": a}}
        self.c.put(f"/api/chat/sessions/{self.sid}", body)
        notes = self.c.get(f"/api/chat/sessions/{self.sid}/effective").get("notes") or []
        self.o.line(self.t(f"cấp độ tư duy: {LEVELS[a]}", f'reasoning level: {LEVELS[a]}') + (f" ({notes[0]['note']})" if notes else ""))

    def c_attach(self, a):
        path = a.strip().strip('"')
        if not os.path.isfile(path):
            raise CLIError(2, self.t(f"không thấy file {path}", f'file not found: {path}'))
        r = self.c.upload("/api/chat/attachments", path)
        self.atts.append((r["id"], os.path.basename(path)))
        self.o.line(self.t(f"📎 {os.path.basename(path)} ({r.get('chars', 0)} ký tự) — gửi kèm tin nhắn tiếp theo", f"📎 {os.path.basename(path)} ({r.get('chars', 0)} characters) — attached to the next message"))

    def c_runs(self, a):
        rows = self.c.get("/api/runs", session="" if a == "all" or not self.sid else self.sid, limit=20)["runs"]
        for r in rows:
            self.o.line(f"  {r['id']}  {r['status']:<18} {r['done']}/{r['steps']}  {r['title'][:60]}")
        if not rows:
            self.o.line(self.t('Chưa có run.', 'No runs yet.'))

    def c_run(self, a):
        r = self.c.get(f"/api/runs/{a}")
        self.o.line(f"{r['id']} · {r['title']} · {r['status']}" + (" · SYNTHETIC" if r.get("synthetic") else ""), "bold")
        for s in r["steps"]:
            self.o.line(f"  {s['id']} {s['status']:<8} {s['label']} ({s['provider']})" + (f" — {s['error']}" if s["error"] else ""))
        if r.get("proposal"):
            self.o.line(self.t(f"  đề xuất: {r['proposal'].get('text', '')}", f"  proposal: {r['proposal'].get('text', '')}"))
        for o in r["outputs"]:
            self.o.line(f"  ⇒ {o['path']}")

    def c_follow(self, a):
        from backend.cli import _follow_run
        _follow_run(self.x, a, 900)

    def c_cancel(self, a):
        self.o.line(self.c.post(f"/api/runs/{a}/cancel")["status"])

    def c_outline(self, a):
        parts = _split(a)
        if not parts:
            self._need_session()
            return self.send(self.t('/outline Hãy đề xuất cấp tiếp theo của đề cương.', '/outline Suggest the next outline level.'))
        if parts[0] == "show":
            o = self.c.get("/api/outline")
            self.o.md(self.t(f"**Đề cương cấp {o['level']}/5** · {o['level_label'] or '-'}\n\n"
                      f"- Từ khoá: {', '.join(o['keywords'])}\n- Chủ đề: {o['topic']}\n- Định hướng: {o['direction']}\n"
                      f"- Phương pháp: {o['method']}\n\n{o['proposal'][:3000]}", f"**Outline level {o['level']}/5** · {o['level_label'] or '-'}\n\n- Keywords: {', '.join(o['keywords'])}\n- Topic: {o['topic']}\n- Direction: {o['direction']}\n- Method: {o['method']}\n\n{o['proposal'][:3000]}"))
            for f in o["attachments"]:
                self.o.line(self.t(f"  📎 {f['name']} ({f['chars']} ký tự)", f"  📎 {f['name']} ({f['chars']} characters)"))
        elif parts[0] == "set" and len(parts) >= 3:
            o = self.c.put("/api/outline", {parts[1]: " ".join(parts[2:])})
            self.o.line(self.t(f"đề cương cấp {o['level']}/5", f"outline level {o['level']}/5"))
        elif parts[0] == "attach" and len(parts) == 2:
            r = self.c.upload("/api/outline/attach", parts[1])
            self.o.line(self.t(f"đã đính kèm {r['name']} ({r['chars']} ký tự)", f"attached {r['name']} ({r['chars']} characters)"))
        else:
            raise CLIError(2, self.t('dùng /outline · /outline show · /outline set <keywords|topic|direction|method|proposal> <nội dung> · /outline attach <file>', 'use /outline · /outline show · /outline set <keywords|topic|direction|method|proposal> <content> · /outline attach <file>'))

    def c_library(self, a):
        parts = _split(a)
        if parts[:1] == ["add"] and len(parts) > 1:
            for f in parts[1:]:
                r = self.c.upload("/api/library/upload", f, "files")
                self.o.line(f"{f}: " + (self.t('đã thêm', 'added') if r["saved"] else self.t('bỏ qua (không phải PDF)', 'skipped (not a PDF)')))
            return
        for e in self.c.get("/api/library")["references"]:
            self.o.line(f"  {'✓' if e.get('include', True) else ' '} {e.get('key', ''):<20} {str(e.get('year', '')):<5} {(e.get('title') or e['file'])[:70]}")

    def c_code(self, a):
        parts = _split(a) or ["list"]
        cmd = parts[0]
        if cmd == "list":
            for p in self.c.get("/api/code")["projects"]:
                self.o.line(f"  {'●' if p['active'] else ' '} {p['name']:<20} {p['path']}")
        elif cmd == "new" and len(parts) == 2:
            self.o.line(self.c.post("/api/code", {"name": parts[1]})["name"] + self.t(' đã tạo (git + venv)', ' created (git + venv)'))
        elif cmd == "open" and len(parts) == 2:
            self.o.line(self.c.post("/api/code/open", {"name": parts[1]})["name"] + self.t(' đang mở', ' open'))
        elif cmd == "vscode":
            self.o.line(self.c.post("/api/code/vscode").get("note", "ok"))
        elif cmd == "sync":
            self._need_session()
            r = self.c.post("/api/code/sync", {"session_id": self.sid})
            self.o.line(self.t(f"{len(r['changes'])} file thay đổi · {len(r['metrics'])} file metrics · {r['proposals']} đề xuất", f"{len(r['changes'])} changed files · {len(r['metrics'])} metric files · {r['proposals']} proposals"))
            self.pending(quiet=True)
        elif cmd == "jobs":
            for j in self.c.get("/api/jobs", limit=15)["jobs"]:
                self.o.line(f"  {j['id']}  {j['status']:<8} {(j.get('cmd') or '')[:50]}  {j.get('metrics') or ''}")
        else:
            raise CLIError(2, self.t('dùng /code list|new <tên>|open <tên>|vscode|sync|jobs', 'use /code list|new <name>|open <name>|vscode|sync|jobs'))

    def c_review(self, a):
        parts = _split(a) or ["list"]
        if parts[0] == "list":
            for r in self.c.get("/api/review")["reviews"]:
                self.o.line(self.t(f"  {r['id']}  {(r['title'] or '')[:60]}  {r.get('decision') or ''}  {r.get('n_issues') or 0} vấn đề", f"  {r['id']}  {(r['title'] or '')[:60]}  {r.get('decision') or ''}  {r.get('n_issues') or 0} issues"))
        elif parts[0] == "new" and len(parts) == 2:
            r = self.c.upload("/api/review/upload", parts[1])
            self.o.line(self.t(f"phiên phản biện {r['meta']['id']} · {r['meta']['title']} — /review run {r['meta']['id']}", f"review session {r['meta']['id']} · {r['meta']['title']} — /review run {r['meta']['id']}"))
        elif parts[0] == "run" and len(parts) == 2:
            from backend.cli import _review_run
            _review_run(self.x, parts[1])
        else:
            raise CLIError(2, self.t('dùng /review list|new <file>|run <id>', 'use /review list|new <file>|run <id>'))

    def c_pins(self, a):
        for p in self.c.get("/api/pins")["pins"]:
            self.o.line(f"  ★ [{p['status']}] {p['title']} — {p['body'][:90]}")

    def c_providers(self, a):
        for p in self.c.get("/api/providers", fresh=1)["providers"]:
            self.o.line(f"  {'✓' if p['ready'] else '·'} {p['label']:<36} {p['state']:<15} {p['detail'][:70]}")

    def c_models(self, a):
        for k, v in self.c.get("/api/models")["agents"].items():
            self.o.line(f"  {k:<9} {v['engine_label']:<36} {v['model']}")

    def c_unload(self, a):
        r = self.c.post("/api/models/unload", {"engine": "all"})
        self.o.line(self.t(f"đã gỡ: {r}", f'unloaded: {r}'))

    def c_config(self, a):
        import json
        parts = a.split(None, 1) if a else []
        cfg = self.c.get("/api/config")
        if not parts:
            for k in ("runs", "research_providers", "aiws", "lifecycle"):
                self.o.line(f"{k}: {json.dumps(cfg.get(k), ensure_ascii=False)[:300]}")
            return
        keys = parts[0].split(".")
        if len(parts) == 1:
            v = cfg
            for k in keys:
                v = (v or {}).get(k)
            self.o.line(json.dumps(v, ensure_ascii=False, indent=1))
            return
        try:
            value = json.loads(parts[1])
        except ValueError:
            value = parts[1]
        patch: dict = value
        for k in reversed(keys):
            patch = {k: patch}
        self.c.post("/api/config", patch)
        shown = '[REDACTED]' if re.search(r'key|token|secret|password', parts[0], re.I) else json.dumps(value, ensure_ascii=False)
        self.o.line(f"{parts[0]} = {shown}")
        self.refresh_language()

    def c_language(self, a):
        parts = a.split()
        if not parts:
            cfg = self.refresh_language()
            self.o.line(f"{self.t('Ngôn ngữ', 'Language')}: {self.language}; AI: {(cfg.get('ui') or {}).get('ai_language', 'auto')}")
            return
        ai = parts[0] == 'ai'
        value = parts[1] if ai and len(parts) == 2 else parts[0] if len(parts) == 1 else ''
        if value not in (('auto', 'en', 'vi') if ai else ('en', 'vi')):
            raise CLIError(2, '/language en|vi or /language ai auto|en|vi')
        cfg = self.c.post('/api/config', {'ui': {'ai_language' if ai else 'language': value}})
        self.refresh_language(cfg)
        self.o.line(f"{self.t('Đã lưu ngôn ngữ', 'Language saved')}: {value}")

    def c_settings(self, a):
        import json
        cfg = self.refresh_language()
        sections = {
            'models': (self.t('Mô hình & Tác nhân AI', 'Models & AI Agents'), ('providers', 'default_cloud', 'agent_modes', 'agent_models', 'local_model', 'lmstudio_base_url', 'ollama_model', 'ollama_base_url', 'gateway', 'hermes', 'fallback_to_cloud', 'lifecycle')),
            'research': (self.t('Công cụ Nghiên cứu', 'Research Engines'), ('research_providers', 'research_engines', 'research_os', 'runs')),
            'search': (self.t('Tìm kiếm & Xếp hạng', 'Search & Ranking'), ('search', 'ranking')),
            'experiments': (self.t('Thí nghiệm & Phần cứng', 'Experiments & Hardware'), ('sandbox', 'resources', 'compute')),
            'memory': (self.t('Bộ nhớ & Ngữ cảnh', 'Memory & Context'), ('memory', 'aiws')),
            'security': (self.t('MCP & Tường lửa Bảo mật', 'MCP & Security Firewall'), ('mcp', 'firewall', 'mcp_agent', 'privacy')),
            'skills': (self.t('Kỹ năng & Tiện ích mở rộng', 'Skills & Plugins'), ('skills', 'plugins')),
            'appearance': (self.t('Giao diện & Ngôn ngữ', 'Appearance & Language'), ('ui',)),
        }
        if not a:
            self.o.line(self.t('Cài đặt — dùng chung với giao diện web', 'Settings — shared with the web interface'))
            for key, (label, _) in sections.items():
                self.o.line(f'  /settings {key:<12} {label}')
            assigned = {key for _, keys in sections.values() for key in keys}
            extra = sorted(set(cfg) - assigned - {'version', 'project', 'provider_specs', 'agents'})
            if extra:
                self.o.line(self.t('Cấu hình khác: ', 'Other settings: ') + ', '.join(extra))
            self.o.line('/settings <section> | /settings set <path> <JSON> | /language en|vi | /language ai auto|en|vi')
            return
        if a.startswith('set '):
            parts = a[4:].split(None, 1)
            if len(parts) != 2:
                raise CLIError(2, '/settings set <path> <JSON>')
            try:
                value = json.loads(parts[1])
            except ValueError as exc:
                raise CLIError(2, self.t('Giá trị JSON không hợp lệ', 'Invalid JSON value')) from exc
            if parts[0] == 'ui.language':
                if value not in ('en', 'vi'):
                    raise CLIError(2, '/settings set ui.language "en"|"vi"')
                return self.c_language(value)
            if parts[0] == 'ui.ai_language':
                return self.c_language('ai ' + str(value))
            return self.c_config(parts[0] + ' ' + json.dumps(value, ensure_ascii=False))
        if a in sections:
            label, keys = sections[a]
            self.o.line(label)
            values = {key: cfg[key] for key in keys if key in cfg}
        elif a in cfg:
            values = {a: cfg[a]}
        else:
            raise CLIError(2, self.t('Không có nhóm cài đặt: ', 'Unknown settings section: ') + a)
        self.o.line(json.dumps(values, ensure_ascii=False, indent=2))

    def c_project(self, a):
        parts = _split(a) or ["list"]
        if parts[0] == "list":
            cur = self.c.get("/api/config")["project"]["data_dir"]
            for p in self.c.get("/api/projects")["projects"]:
                self.o.line(f"  {'●' if p['data_dir'] == cur else ' '} {p['name']:<28} {p['data_dir']}")
        elif parts[0] == "new" and len(parts) >= 2:
            p = self.c.post("/api/projects", {"name": " ".join(parts[1:])})
            self.sid = ""
            self.o.line(self.t(f"dự án mới: {p['name']} — bắt đầu với /outline", f"new project: {p['name']} — start with /outline"))
        elif parts[0] == "use" and len(parts) == 2:
            p = self.c.post("/api/projects/activate", {"data_dir": parts[1]})
            self.sid = ""
            self.o.line(self.t(f"đang dùng dự án {p['name']}", f"using project {p['name']}"))
        else:
            raise CLIError(2, self.t('dùng /project list|new <tên>|use <thư mục>', 'use /project list|new <name>|use <directory>'))

    def c_dashboard(self, a):
        from backend.cli import _status
        _status(self.x, type("A", (), {})())

    def c_workflow(self, a):
        self.t('Điều phối và thực thi mọi quy trình nghiên cứu của PhD Research Lab.', 'Coordinate PhD Research Lab workflows.')
        parts = _split(a) or ["list"]
        sub = parts[0]
        workflows = [
            {"id": "lit", "name": self.t('Khảo sát Tài liệu & Research Gap', 'Literature & Research Gaps'), "desc": self.t('Thu thập bài báo, trích xuất phương pháp & lập bản đồ khoảng trống', 'Collect papers, extract methods and map research gaps'), "cmd": self.t('/lit <từ khoá>', '/lit <keywords>')},
            {"id": "outline", "name": self.t('Đề cương Nghiên cứu 5 Cấp độ', 'Five-Level Research Outline'), "desc": self.t('Phát triển đề cương từng bước từ ý tưởng đến bài báo hoàn chỉnh', 'Develop an outline from idea to manuscript'), "cmd": "/outline"},
            {"id": "experiment", "name": self.t('Thực nghiệm & Mã nguồn Sandbox', 'Sandbox Experiments & Code'), "desc": self.t('Sinh mã, chạy thử nghiệm cô lập và tích hợp VS Code', 'Generate code, run isolated experiments and use VS Code'), "cmd": "/code"},
            {"id": "paper", "name": self.t('Soạn thảo Bài báo LaTeX', 'LaTeX Manuscript Writing'), "desc": self.t('Viết từng mục bài báo, biên dịch LaTeX online & local', 'Write paper sections and compile LaTeX locally or online'), "cmd": "/paper"},
            {"id": "review", "name": self.t('Hội đồng Bình duyệt R1–R3', 'R1–R3 Review Board'), "desc": self.t('Đánh giá học thuật nghiêm ngặt, chấm điểm và gợi ý sửa đổi', 'Review, score and suggest revisions'), "cmd": "/review"},
            {"id": "deepresearch", "name": self.t('Nghiên cứu Toàn diện Đa Tác nhân', 'Multi-Agent Research'), "desc": self.t('Tự động hóa hoàn toàn chu trình nghiên cứu đa bước', 'Coordinate a bounded multi-step research workflow'), "cmd": self.t('/deepresearch <chủ đề>', '/deepresearch <topic>')},
            {"id": "harness", "name": self.t('Harness Tự động hoá Tùy biến', 'Custom Harness Automation'), "desc": self.t('Quy trình kiểm thử giả thuyết và chạy thí nghiệm tự hành', 'Hypothesis testing and bounded experiments'), "cmd": "/harness run <id>"},
        ]
        if sub == "list":
            if self.o.console:
                from rich.table import Table
                from rich import box
                tbl = Table(title=self.t('[bold #d2602a]✦ Danh mục Quy trình Nghiên cứu PhD Lab[/bold #d2602a]', '[bold #d2602a]✦ PhD Lab Research Workflow Catalog[/bold #d2602a]'), box=box.ROUNDED, border_style="#d2602a")
                tbl.add_column(self.t('Mã', 'ID'), style="bold cyan")
                tbl.add_column(self.t('Tên Quy trình', 'Workflow'), style="bold white")
                tbl.add_column(self.t('Lệnh thực thi', 'Command'), style="green")
                tbl.add_column(self.t('Mô tả', 'Description'), style="dim")
                for w in workflows:
                    tbl.add_row(w["id"], w["name"], w["cmd"], w["desc"])
                self.o.console.print(tbl)
            else:
                self.o.line(self.t('Danh mục Quy trình Nghiên cứu PhD Lab:', 'PhD Lab Research Workflow Catalog:'))
                for w in workflows:
                    self.o.line(f"  {w['id']:<14} {w['name']:<32} {w['cmd']:<24} {w['desc']}")
            self.o.line(self.t('→ Gõ /workflow run <mã> hoặc gõ trực tiếp lệnh của quy trình đó', '→ Use /workflow run <id> or enter the workflow command'), "dim")
        elif sub == "run" and len(parts) >= 2:
            wid = parts[1]
            extra = " ".join(parts[2:]) if len(parts) > 2 else ""
            if wid in ("lit", "deepresearch"):
                self._need_session()
                return self.send(f"/{wid} {extra or 'machine learning'}")
            elif wid == "outline":
                return self.c_outline(extra)
            elif wid in ("code", "experiment"):
                return self.c_code(extra or "list")
            elif wid == "paper":
                self._need_session()
                return self.send(f"/paper {extra or 'tổng hợp kết quả bài báo'}")
            elif wid == "review":
                return self.c_review(extra or "list")
            else:
                r = self.c.post(f"/api/harness/workflows/{wid}/run", {"input": extra})
                self.o.line(self.t(f"Đã khởi động quy trình {wid}: Run {r.get('run_id', 'RR')}", f"Started workflow {wid}: Run {r.get('run_id', 'RR')}"))
                if r.get("run_id"):
                    self.c_follow(r["run_id"])
        elif sub == "status":
            self.c_runs("")
        else:
            raise CLIError(2, self.t('dùng /workflow list | /workflow run <mã> | /workflow status', 'use /workflow list | /workflow run <id> | /workflow status'))

    def c_clear(self, a):
        self.o.raw("\033[2J\033[H" if self.tty else "\n")


def _isatty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


try:  # prompt_toolkit is optional for scripted use; the completer is only built in a terminal
    from prompt_toolkit.completion import Completer as _PTCompleter, Completion
except ImportError:  # pragma: no cover - the app's requirements install it
    _PTCompleter, Completion = object, None


class Completer(_PTCompleter):
    """The "/" menu: every skill and terminal command with its description; values for /model and /reasoning."""

    def __init__(self, repl: Repl):
        self.r = repl
        self.models = None

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        if " " not in text:
            q = text[1:].lower()
            for s in self.r.skills:
                if s["name"].startswith(q):
                    yield Completion("/" + s["name"] + " ", -len(text), display="/" + s["name"], display_meta=s["title"])
            for n, (_, usage, desc) in self.r.commands.items():
                if n.startswith(q) and n != "exit":
                    yield Completion("/" + n + (" " if usage else ""), -len(text), display="/" + n, display_meta=desc)
            return
        cmd, _, arg = text.partition(" ")
        if cmd == "/reasoning":
            for k, v in LEVELS.items():
                if k.startswith(arg):
                    yield Completion(k, -len(arg), display_meta=v)
        elif cmd == "/model":
            if self.models is None:
                self.models = self.r.c.get("/api/models")["providers"]
            for p in self.models:
                if p["id"].startswith(arg) and p["available"]:
                    yield Completion(p["id"], -len(arg), display_meta=p["label"])
