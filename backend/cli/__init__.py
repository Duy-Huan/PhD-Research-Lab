"""`phdlab` — the terminal client of PhD Research Lab. Without arguments it opens the research chat (the same
conversations, "/" skills, proposals and runs as the browser UI); the sub-commands are shortcuts for scripts.

The CLI is a second client of the SAME backend (default http://127.0.0.1:8765, override with --server or PHDLAB_URL).
Everything is an HTTP call: approvals, budgets, hardware guard and the context firewall apply exactly as in the UI, and a
change made here appears in the UI immediately (and the other way round).

    phdlab                         research chat (REPL) — type a question, a /skill, or /accept 1
    phdlab ask "/lit token pruning"   one turn, printed, then exit
    phdlab status                  goal · current step · what waits for you
    phdlab runs [show|approve|cancel|resume|follow] …
    phdlab serve                   start the server in this terminal
    phdlab commands                every command
Exit codes: 0 ok · 1 the server refused (message printed) · 2 usage error · 3 server not reachable.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time

DEFAULT_URL = "http://127.0.0.1:8765"
COMMANDS: dict = {}   # (group, name) → {"fn", "args", "help"}
GROUP_HELP = {"": "general", "runs": "background research runs", "project": "research projects", "outline": "research outline",
              "code": "code projects (VS Code)", "library": "reference PDFs", "review": "paper review sessions",
              "models": "models and VRAM", "skills": "the / commands", "history": "conversations"}


class CLIError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


def cmd(group: str, name: str, help: str, *args):
    def deco(fn):
        COMMANDS[(group, name)] = {"fn": fn, "args": args, "help": help}
        return fn
    return deco


def A(*flags, **kw):
    return (flags, kw)


# ------------------------------------------------------------------ HTTP client
class Client:
    def __init__(self, base: str = "", http=None, timeout: float = 120):
        import httpx
        self.base = (base or os.environ.get("PHDLAB_URL") or DEFAULT_URL).rstrip("/")
        self.http = http or httpx.Client(base_url=self.base, timeout=timeout, headers={"X-PhDLab-Client": "cli"})

    def call(self, method: str, path: str, body=None, params: dict | None = None, files=None):
        import httpx
        try:
            if files is not None:
                r = self.http.request(method, path, files=files, params=params or {})
            else:
                r = self.http.request(method, path, json=body, params={k: v for k, v in (params or {}).items() if v not in (None, "")})
        except httpx.TransportError as e:
            raise CLIError(3, f"Cannot reach the PhD Research Lab server at {self.base} ({type(e).__name__}). "
                              "Start it with `phdlab serve` (or run.bat) — the CLI and the UI share that server.")
        ct = r.headers.get("content-type", "")
        data = r.json() if "json" in ct else r.text
        if r.status_code >= 400:
            d = data.get("detail") if isinstance(data, dict) else data
            msg = d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)
            if "NO_CODE_PROJECT" in str(data):
                msg += "\n  → `phdlab code list`, then `phdlab code open <name>` or `phdlab code new <name>`"
            raise CLIError(1, f"HTTP {r.status_code}: {msg}")
        return data

    def get(self, url, **params):
        return self.call("GET", url, params=params)

    def post(self, url, body=None):
        return self.call("POST", url, {} if body is None else body)

    def put(self, url, body=None):
        return self.call("PUT", url, body or {})

    def delete(self, url, **params):
        return self.call("DELETE", url, params=params)

    def upload(self, url, path: str, field: str = "file"):
        with open(path, "rb") as f:
            return self.call("POST", url, files={field: (os.path.basename(path), f.read())})


# ------------------------------------------------------------------ output
def _cell(v) -> str:
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    s = "" if v is None else str(v)
    return s if len(s) <= 60 else s[:57] + "…"


def table(rows: list, cols: list) -> str:
    if not rows:
        return "(none)"
    w = {c: max(len(c), *(len(_cell(r.get(c))) for r in rows)) for c in cols}
    head = "  ".join(c.upper().ljust(w[c]) for c in cols)
    return "\n".join([head] + ["  ".join(_cell(r.get(c)).ljust(w[c]) for c in cols) for r in rows])


class Ctx:
    def __init__(self, client: Client, out, as_json: bool):
        self.c, self.out, self.json = client, out, as_json

    def p(self, *parts) -> None:
        self.out.write(" ".join(str(x) for x in parts) + "\n")
        self.out.flush()

    def w(self, text: str) -> None:
        self.out.write(text)
        self.out.flush()

    def show(self, data, cols=None) -> None:
        if self.json or cols is None or not isinstance(data, list):
            self.p(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            self.p(table(data, cols))


def _json_arg(v: str):
    if not v:
        return None
    if v.startswith("@"):
        with open(v[1:], encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(v)
    except ValueError:
        raise CLIError(2, "expected JSON (or @file.json)")


# ================================================================== the research chat
@cmd("", "chat", "Open the research chat (the default when phdlab runs without a command)",
     A("--session", default="", help="continue this conversation (as-…)"), A("--new", action="store_true"))
def _chat(x, a):
    from backend.cli.repl import Repl
    return Repl(x).run(a.session, a.new)


@cmd("", "ask", "One turn in the research chat, printed, then exit (\"/skill …\" works too)",
     A("text"), A("--session", default=""), A("--timeout", type=float, default=900))
def _ask(x, a):
    from backend.cli.repl import Repl
    r = Repl(x)
    r.sid = a.session or r.new_session()
    return r.send(a.text, a.timeout)


@cmd("", "status", "Goal, current step, status, what waits for you, pinned results")
def _status(x, a):
    d = x.c.get("/api/dashboard")
    if x.json:
        return x.show(d)
    x.p(f"Project   {d['project']}")
    x.p(f"Goal      {d['goal'] or '(none yet — /outline)'}   [outline {d['outline_level']}/5]")
    c = d["current"]
    x.p(f"Now       {c['title']} — {c['step']} ({c['provider']}) · {c['status']} · {c['progress']}" if c else "Now       nothing running")
    x.p(f"Status    {d['status']}")
    from backend.cli.repl import ACTION
    for p in d["pending"][:10]:
        x.p(f"  • waits: [{p['kind']}] {ACTION.get(p['title'], p['title'])} — {p['text'][:100]}")
    for p in d["pins"][:6]:
        x.p(f"  ★ {p['title']} ({p['status']})")
    if d["next_decision"]:
        x.p(f"Next      {d['next_decision']}")


@cmd("", "serve", "Start the backend server in this terminal (UI + CLI share it)",
     A("--port", type=int, default=8765), A("--open-browser", action="store_true"))
def _serve(x, a):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    argv = [sys.executable, os.path.join(root, "start.py"), "--port", str(a.port)] + ([] if a.open_browser else ["--no-browser"])
    x.p("$ " + " ".join(shlex.quote(s) for s in argv))
    return subprocess.call(argv, cwd=root)


@cmd("", "api", "Call any backend route: phdlab api GET /api/dashboard",
     A("method", choices=["GET", "POST", "PUT", "DELETE", "get", "post", "put", "delete"]), A("path"),
     A("--data", default="", help="JSON body or @file.json"))
def _api(x, a):
    if not a.path.startswith("/"):
        raise CLIError(2, "path must start with /")
    x.show(x.c.call(a.method.upper(), a.path, _json_arg(a.data)))


@cmd("", "events", "Changes made by any client (UI or CLI) since an event number", A("--after", type=int, default=0))
def _events(x, a):
    x.show(x.c.get("/api/events", after=a.after)["events"], ["seq", "type", "client", "method", "path"])


@cmd("", "commands", "Every CLI command (--markdown: the table of the CLI guide)", A("--markdown", action="store_true"))
def _commands(x, a):
    rows = [{"command": f"phdlab {g + ' ' if g else ''}{n}", "args": " ".join(_usage(spec)), "help": spec["help"]}
            for (g, n), spec in sorted(COMMANDS.items())]
    if a.markdown:
        x.p("| Command | Arguments | What it does |\n|---|---|---|")
        for r in rows:
            x.p(f"| `{r['command']}` | {('`' + r['args'] + '`') if r['args'] else ''} | {r['help']} |")
        return
    x.show(rows, ["command", "args", "help"])


def _usage(spec) -> list:
    out = []
    for flags, kw in spec["args"]:
        f = flags[0]
        if f.startswith("-"):
            out.append(f"[{f}]" if kw.get("action") == "store_true" else f"[{f} {f.strip('-').upper()}]")
        else:
            out.append(f"[{f}]" if kw.get("nargs") in ("?", "*") else f"<{f}>")
    return out


@cmd("", "acceptance", "The eight AI Research OS acceptance criteria and their executable evidence")
def _acceptance(x, a):
    d = x.c.get("/api/acceptance")
    if x.json:
        return x.show(d)
    x.p(f"report: {d.get('report') or '(no acceptance run yet — python -m unittest discover -s tests/acceptance)'}")
    x.show([{"prio": c["priority"], "criterion": c["title"], "verdict": c["verdict"], "evidence": c["evidence"]}
            for c in d["criteria"]], ["prio", "criterion", "verdict", "evidence"])


@cmd("", "providers", "Model gateway, native research tools and installed CLI runtimes")
def _providers(x, a):
    x.show(x.c.get("/api/providers", fresh=1)["providers"], ["id", "category", "state", "detail"])


# ================================================================== runs
def _follow_run(x, rid: str, timeout: float = 600) -> int:
    after, end, last = 0, time.time() + timeout, ""
    while time.time() < end:
        for e in x.c.get(f"/api/runs/{rid}/events", after=after)["events"]:
            after = e["seq"]
            d = e.get("data") or {}
            if e["type"] == "run.state":
                x.p(f"  [{d.get('status')}] {d.get('reason', '')}")
            elif e["type"] == "step.started":
                x.p(f"  → {d.get('step')} {d.get('label')} ({d.get('provider')}, attempt {d.get('attempt')})")
            elif e["type"] == "step.failed":
                x.p(f"  ✗ {d.get('step')}: {d.get('error')}")
            elif e["type"] == "step.log" and d.get("checkpoint"):
                x.p(f"  · day {d['checkpoint']}: {d.get('user', '')[:90]}")
        r = x.c.get(f"/api/runs/{rid}")
        if r["status"] != last and r["status"] in ("COMPLETED", "CANCELLED", "NEEDS_USER_ACTION", "APPROVAL_PENDING"):
            x.p(f"run {rid}: {r['status']} — {r.get('next_decision') or r.get('reason', '')}")
            for o in r["outputs"][:12]:
                x.p(f"    {o['path']}")
            return 0 if r["status"] == "COMPLETED" else 1
        last = r["status"]
        time.sleep(0.3)
    x.p("(still running — `phdlab runs follow " + rid + "`)")
    return 0


@cmd("runs", "list", "Research runs of the project", A("--status", default=""))
def _runs_list(x, a):
    x.show(x.c.get("/api/runs", status=a.status)["runs"], ["id", "status", "title", "done", "steps", "synthetic"])


@cmd("runs", "show", "One run: steps, outputs, proposal", A("id"))
def _runs_show(x, a):
    r = x.c.get(f"/api/runs/{a.id}")
    if x.json:
        return x.show(r)
    x.p(f"{r['id']} · {r['title']} · {r['status']}" + (" · SYNTHETIC" if r["synthetic"] else ""))
    for s in r["steps"]:
        x.p(f"  {s['id']} {s['status']:<8} {s['label']} ({s['provider']})" + (f" — {s['error']}" if s["error"] else ""))
    if r.get("proposal"):
        x.p(f"  proposal: {r['proposal'].get('text', '')}")
    for o in r["outputs"]:
        x.p(f"  ⇒ {o['path']}")


@cmd("runs", "new", "Start a run with a skill: phdlab runs new lit \"token pruning\"", A("skill"), A("input", nargs="?", default=""),
     A("--follow", action="store_true"))
def _runs_new(x, a):
    r = x.c.post("/api/runs", {"skill": a.skill, "input": a.input})
    x.p(f"run {r['id']} · {r['status']}")
    return _follow_run(x, r["id"]) if a.follow else 0


@cmd("runs", "approve", "Accept a run that waits for approval", A("id"))
def _runs_approve(x, a):
    x.p(x.c.post(f"/api/runs/{a.id}/approve")["status"])


@cmd("runs", "cancel", "Cancel a run", A("id"))
def _runs_cancel(x, a):
    x.p(x.c.post(f"/api/runs/{a.id}/cancel")["status"])


@cmd("runs", "resume", "Answer NEEDS_USER_ACTION: --accept applies the recovery proposal; --command overrides the step",
     A("id"), A("--accept", action="store_true"), A("--command", default=""))
def _runs_resume(x, a):
    x.p(x.c.post(f"/api/runs/{a.id}/resume", {"accept": a.accept, "patch": {"command": a.command} if a.command else None})["status"])


@cmd("runs", "provider", "Move a pending / failed step to another provider", A("id"), A("step"), A("provider"))
def _runs_provider(x, a):
    r = x.c.post(f"/api/runs/{a.id}/provider", {"step": a.step, "provider": a.provider})
    x.p(next(s["provider"] for s in r["steps"] if s["id"] == a.step))


@cmd("runs", "follow", "Print a run's timeline until it ends or needs you", A("id"), A("--timeout", type=float, default=3600))
def _runs_follow(x, a):
    return _follow_run(x, a.id, a.timeout)


# ================================================================== projects, outline, skills, chat history
@cmd("project", "list", "Research projects")
def _proj_list(x, a):
    x.show(x.c.get("/api/projects")["projects"], ["name", "data_dir"])


@cmd("project", "new", "Create a research project and switch to it", A("name"), A("--dir", default=""),
     A("--topic", default="", help="start the outline with a topic"))
def _proj_new(x, a):
    body = {"name": a.name, "data_dir": a.dir or None}
    if a.topic:
        body["outline"] = {"topic": a.topic}
    x.show(x.c.post("/api/projects", body))


@cmd("project", "use", "Switch to another research project", A("data_dir"))
def _proj_use(x, a):
    x.show(x.c.post("/api/projects/activate", {"data_dir": a.data_dir}))


@cmd("outline", "show", "The research outline (level 1–5) and attached files")
def _outline_show(x, a):
    o = x.c.get("/api/outline")
    if x.json:
        return x.show(o)
    x.p(f"level {o['level']}/5 · {o['level_label'] or '-'}")
    x.p(f"keywords:  {', '.join(o['keywords'])}")
    for k in ("topic", "direction", "method"):
        x.p(f"{k + ':':<10} {o[k]}")
    if o["proposal"]:
        x.p("proposal:\n" + o["proposal"][:3000])
    for f in o["attachments"]:
        x.p(f"  📎 {f['name']} ({f['chars']} chars)")


@cmd("outline", "set", "Set one level: keywords | topic | direction | method | proposal (@file.md reads a file)",
     A("field", choices=["keywords", "topic", "direction", "method", "proposal"]), A("text"))
def _outline_set(x, a):
    text = a.text
    if text.startswith("@"):
        with open(text[1:], encoding="utf-8") as f:
            text = f.read()
    o = x.c.put("/api/outline", {a.field: text})
    x.p(f"outline level {o['level']}/5")


@cmd("outline", "attach", "Attach a proposal file (PDF, Word .docx, Markdown, text, LaTeX)", A("file"))
def _outline_attach(x, a):
    r = x.c.upload("/api/outline/attach", a.file)
    x.p(f"attached {r['name']} · {r['chars']} chars")


@cmd("skills", "list", "Every / command (built-in, yours, this project's)")
def _skills_list(x, a):
    x.show(x.c.get("/api/skills")["skills"], ["name", "mode", "category", "origin", "title"])


@cmd("skills", "add", "Create / replace your skill from a Markdown file", A("file"), A("--scope", choices=["project", "user"], default="project"))
def _skills_add(x, a):
    with open(a.file, encoding="utf-8") as f:
        s = x.c.post("/api/skills", {"text": f.read(), "scope": a.scope})
    x.p(f"/{s['name']} saved ({s['origin']})")


@cmd("history", "list", "Conversations of the project", A("--q", default=""))
def _chat_list(x, a):
    x.show(x.c.get("/api/chat/sessions", q=a.q)["sessions"], ["id", "title", "messages", "pending_approvals", "status"])


@cmd("history", "show", "A conversation as text", A("id"))
def _chat_show(x, a):
    s = x.c.get(f"/api/chat/sessions/{a.id}")
    if x.json:
        return x.show(s)
    from backend.cli.repl import clean
    for m in s["messages"]:
        x.p(("› " if m["role"] == "user" else "") + clean(m["content"]) + "\n")


# ================================================================== code (VS Code), library, review, models
@cmd("code", "list", "Code projects")
def _code_list(x, a):
    d = x.c.get("/api/code")
    x.show(d["projects"], ["name", "active", "path"])


@cmd("code", "new", "Create a code project (git + Python venv) and open it", A("name"))
def _code_new(x, a):
    x.p(x.c.post("/api/code", {"name": a.name})["name"])


@cmd("code", "open", "Make a code project the active one", A("name"))
def _code_open(x, a):
    x.p(x.c.post("/api/code/open", {"name": a.name})["name"])


@cmd("code", "vscode", "Open the active code project in VS Code")
def _code_vscode(x, a):
    x.p(x.c.post("/api/code/vscode").get("note", "ok"))


@cmd("code", "sync", "Bring VS Code work back: proposals in a conversation (commit, new metrics)", A("--session", default=""))
def _code_sync(x, a):
    sid = a.session or x.c.post("/api/chat/sessions", {"title": "VS Code sync"})["id"]
    r = x.c.post("/api/code/sync", {"session_id": sid})
    x.p(f"{len(r['changes'])} changed files · {len(r['metrics'])} metrics files · {r['proposals']} proposals in {sid}")


@cmd("code", "jobs", "Experiment jobs (venv / Docker) with their metrics", A("--limit", type=int, default=20))
def _code_jobs(x, a):
    x.show(x.c.get("/api/jobs", limit=a.limit)["jobs"], ["id", "status", "mode", "cmd", "metrics"])


@cmd("library", "list", "Reference PDFs of the project")
def _lib_list(x, a):
    x.show(x.c.get("/api/library")["references"], ["key", "year", "title", "include"])


@cmd("library", "add", "Add PDF files to the project library", A("files", nargs="+"))
def _lib_add(x, a):
    for f in a.files:
        r = x.c.upload("/api/library/upload", f, "files")
        x.p(f"{f}: " + ("added" if r["saved"] else "skipped (not a PDF)"))


@cmd("review", "list", "Paper review sessions")
def _rv_list(x, a):
    x.show(x.c.get("/api/review")["reviews"], ["id", "title", "decision", "n_issues"])


@cmd("review", "new", "Start a review from a manuscript (PDF, DOCX, TEX, MD, TXT)", A("file"))
def _rv_new(x, a):
    r = x.c.upload("/api/review/upload", a.file)
    x.p(f"review {r['meta']['id']} · {r['meta']['title']}")


@cmd("review", "run", "Run reviewers → area chair → issue list (streams)", A("id"))
def _rv_run(x, a):
    return _review_run(x, a.id)


def _review_run(x, rid: str) -> int:
    meta = x.c.get(f"/api/review/{rid}")["meta"]
    stages = [{"stage": "reviewer", "idx": i, "fresh": i == 1} for i in range(1, meta.get("n_reviewers", 3) + 1)]
    for body in stages + [{"stage": "meta"}, {"stage": "issues"}]:
        x.w(f"{body['stage']} {body.get('idx', '')}: ")
        done = None
        with x.c.http.stream("POST", f"/api/review/{rid}/stage", json=body) as r:
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                ev = json.loads(line[6:])
                if ev["type"] == "error":
                    raise CLIError(1, ev["detail"])
                if ev["type"] == "done":
                    done = ev
        x.p("done" if done else "no result")
    st = x.c.get(f"/api/review/{rid}")["state"]
    x.p(f"{len(st['issues'])} issues · decision: {(st.get('meta') or {}).get('decision', '')}")
    return 0


@cmd("models", "list", "The agents and the providers the chat can use")
def _models_list(x, a):
    d = x.c.get("/api/models")
    x.show([{"agent": k, "engine": v["engine_label"], "model": v["model"]} for k, v in d["agents"].items()], ["agent", "engine", "model"])
    x.show([p for p in d["providers"]], ["id", "state", "available"])


@cmd("models", "unload", "Unload local models from VRAM (LM Studio / Ollama)", A("--force", action="store_true"))
def _models_unload(x, a):
    x.show(x.c.post("/api/models/unload", {"engine": "all", "force": a.force}))


# ------------------------------------------------------------------ parser / main
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="phdlab", description="PhD Research Lab — research chat and commands in the terminal.",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Without a command: the research chat.  phdlab commands — every command")
    p.add_argument("--server", default="", help=f"backend URL (default PHDLAB_URL or {DEFAULT_URL})")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="group", metavar="<group|command>")
    groups = {}
    for (g, n), spec in sorted(COMMANDS.items()):
        if not g:
            sp = sub.add_parser(n, help=spec["help"], description=spec["help"])
        else:
            if g not in groups:
                gp = sub.add_parser(g, help=GROUP_HELP[g], description=GROUP_HELP[g])
                groups[g] = gp.add_subparsers(dest="name", metavar="<command>")
            sp = groups[g].add_parser(n, help=spec["help"], description=spec["help"])
        for flags, kw in spec["args"]:
            sp.add_argument(*flags, **kw)
        sp.set_defaults(_spec=(g, n))
    return p


def main(argv: list | None = None, http=None, out=None, inp=None) -> int:
    out = out or sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8", errors="replace")
    import contextlib
    p = parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            a = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if not getattr(a, "_spec", None):
        if a.group:  # a group without its command
            out.write(f"usage: phdlab {a.group} <command> — phdlab {a.group} --help\n")
            return 2
        a._spec, a.session, a.new = ("", "chat"), "", False
    x = Ctx(Client(a.server, http), out, a.json)
    x.inp = inp
    try:
        return int(COMMANDS[a._spec]["fn"](x, a) or 0)
    except CLIError as e:
        out.write(f"error: {e}\n")
        return e.code
    except KeyboardInterrupt:
        out.write("\ninterrupted\n")
        return 130
