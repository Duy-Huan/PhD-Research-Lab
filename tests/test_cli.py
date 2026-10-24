"""`phdlab`: every command and the terminal research chat (REPL) run against the real backend (in-process ASGI app,
the same routes as the UI). The last test fails when a registered command never ran successfully."""
import _env  # noqa: F401  (must be first)
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import cli
from backend.agent import launch, runs, sessions
from backend.app import app
from backend.cli import repl as R
from backend.core import config
from backend.execution import sandbox
from backend.providers import models as llm, research as RP

PASSED: set = set()


async def fake_stream(agent, system, messages, max_tokens=0, temperature=0.3):
    yield ("delta", "Answer **bold**.\n``")
    yield ("delta", '`phdlab-action\n{"action": "add_note", "args": {"text": "remember this"}}\n```\nDone.\n')
    yield ("meta", {"text": "Answer.\n**Recommendation:** Accept\n**Decision:** Accept\n"
                            '{"issues": [{"id": "I1", "severity": "minor", "title": "t", "quote": "", "problem": "p"}]}',
                    "engine": "fake", "note": ""})


def _track():
    for key, spec in cli.COMMANDS.items():
        if spec.get("_tracked"):
            continue
        fn = spec["fn"]

        def wrapped(x, a, _fn=fn, _key=key):
            rc = _fn(x, a)
            if not rc:
                PASSED.add(_key)
            return rc
        spec["fn"], spec["_tracked"] = wrapped, True


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _track()
        cls.tc = TestClient(app, headers={"X-PhDLab-Client": "cli"})
        cls.tc.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.tc.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("cli-" + self._testMethodName[:28])
        config.save_config({"runs": {"web_search": False}})
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False,
                               "gpu": False})
        provider_for = launch.provider_for
        for p in (mock.patch.object(llm, "stream_agent", fake_stream),
                  mock.patch.object(launch, "provider_for", side_effect=lambda skill: "app" if skill["provider"] == "feynman" else provider_for(skill)),
                  mock.patch.object(RP, "app_complete", return_value="lit text"),
                  mock.patch.object(RP, "describe_all", return_value=[{"id": "app", "label": "App", "category": "research",
                                                                       "state": "READY", "ready": True, "detail": "d"}])):
            p.start()
            self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp())

    def run_cli(self, *argv, rc=0, lines=None):
        out = io.StringIO()
        feed = iter(lines or [])

        def inp(prompt):
            try:
                return next(feed)
            except StopIteration:
                raise EOFError
        code = cli.main(list(argv), http=self.tc, out=out, inp=inp)
        self.assertEqual(code, rc, f"phdlab {' '.join(argv)} → {code}\n{out.getvalue()}")
        return out.getvalue()


class Commands(Base):
    def test_general(self):
        self.assertIn("Project", self.run_cli("status"))
        self.assertIn('"project"', self.run_cli("--json", "status"))
        self.assertIn("version", self.run_cli("api", "GET", "/api/version"))
        self.run_cli("api", "GET", "api/version", rc=2)
        self.run_cli("api", "POST", "/api/config", "--data", '{"runs": {"max_minutes": 50}}')
        f = self.tmp / "b.json"
        f.write_text('{"runs": {"max_minutes": 40}}', "utf-8")
        self.run_cli("api", "POST", "/api/config", "--data", f"@{f}")
        self.run_cli("api", "POST", "/api/config", "--data", "{bad", rc=2)
        self.run_cli("api", "GET", "/api/runs/RR-00000000", rc=1)
        self.assertIn("SEQ", self.run_cli("events"))
        self.assertIn("phdlab status", self.run_cli("commands"))
        self.assertIn("| Command |", self.run_cli("commands", "--markdown"))
        self.assertIn("criterion", self.run_cli("acceptance").lower())
        self.run_cli("--json", "acceptance")
        self.assertIn("app", self.run_cli("providers"))
        with mock.patch("subprocess.call", return_value=0) as call:
            self.run_cli("serve", "--port", "9999")
        self.assertIn("--no-browser", call.call_args[0][0])
        self.assertIn("usage: phdlab", self.run_cli("--help"))
        self.assertIn("usage", self.run_cli("runs", rc=2))

    def test_unreachable_server(self):
        import httpx
        out = io.StringIO()
        c = httpx.Client(transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("x"))), base_url="http://x")
        self.assertEqual(cli.main(["status"], http=c, out=out), 3)
        self.assertIn("phdlab serve", out.getvalue())

    def test_runs(self):
        out = self.run_cli("runs", "new", "lit", "vit", "--follow")
        self.assertIn("COMPLETED", out)
        rid = runs.list_runs()[0]["id"]
        self.assertIn(rid, self.run_cli("runs", "list"))
        self.assertIn("S1", self.run_cli("runs", "show", rid))
        self.run_cli("--json", "runs", "show", rid)
        e = json.loads(self.run_cli("--json", "api", "POST", "/api/runs", "--data", '{"skill": "run", "input": "python nope.py"}'))["id"]
        self.assertIn("docker", self.run_cli("runs", "provider", e, "S1", "docker"))
        self.run_cli("runs", "approve", e)
        runs.wait(e, 30)
        self.assertIn("NEEDS_USER_ACTION", self.run_cli("runs", "show", e))
        self.run_cli("runs", "resume", e, "--command", "python nope2.py")
        runs.wait(e, 30)
        self.run_cli("runs", "resume", e, "--accept")
        runs.wait(e, 30)
        self.assertIn("needs", self.run_cli("runs", "follow", e, "--timeout", "5", rc=1).lower())
        self.run_cli("runs", "cancel", e)
        self.run_cli("runs", "new", "idea", "x")
        self.assertIn("APPROVAL_PENDING", self.run_cli("runs", "follow", runs.list_runs()[0]["id"], "--timeout", "5", rc=1))
        with mock.patch.object(cli, "time", mock.Mock(time=mock.Mock(side_effect=[0, 99]), sleep=lambda s: None)):
            self.assertIn("still running", self.run_cli("runs", "follow", rid, "--timeout", "1"))

    def test_project_outline_skills_history(self):
        self.run_cli("project", "new", "Cli Proj", "--topic", "Edge ViT")
        self.assertIn("Edge ViT", self.run_cli("outline", "show"))
        d = json.loads(self.run_cli("--json", "outline", "show"))
        self.assertEqual(d["level"], 2)
        self.assertIn("Cli Proj", self.run_cli("project", "list"))
        self.run_cli("project", "use", config.data_dir().as_posix())
        self.run_cli("outline", "set", "keywords", "a, b")
        prop = self.tmp / "p.md"
        prop.write_text("# Full proposal", "utf-8")
        self.assertIn("5/5", self.run_cli("outline", "set", "proposal", f"@{prop}"))
        self.assertIn("attached", self.run_cli("outline", "attach", str(prop)))
        self.assertIn("proposal:", self.run_cli("outline", "show"))
        self.assertIn("lit", self.run_cli("skills", "list"))
        sk = self.tmp / "s.md"
        sk.write_text("---\nname: mine\n---\nx\n", "utf-8")
        self.assertIn("/mine saved", self.run_cli("skills", "add", str(sk)))
        s = sessions.create("Hist")
        sessions.add_message(s["id"], "user", "hello")
        sessions.add_message(s["id"], "assistant", 'hi\n```phdlab-action\n{"a":1}\n```')
        self.assertIn("Hist", self.run_cli("history", "list"))
        out = self.run_cli("history", "show", s["id"])
        self.assertIn("› hello", out)
        self.assertNotIn("phdlab-action", out)
        self.run_cli("--json", "history", "show", s["id"])

    def test_code_library_review_models(self):
        self.assertIn("main", self.run_cli("code", "list"))
        self.run_cli("code", "new", "exp9")
        self.run_cli("code", "open", "exp9")
        with mock.patch("backend.execution.vscode.vscode_cli", return_value="code"), \
                mock.patch("backend.execution.vscode.run_cli", return_value=(0, "")):
            self.assertIn("VS Code", self.run_cli("code", "vscode"))
        self.assertIn("proposals", self.run_cli("code", "sync"))
        self.run_cli("code", "jobs")
        from pdfgen import make_pdf
        pdf = self.tmp / "p.pdf"
        pdf.write_bytes(make_pdf([[(14, "Paper Title")]]))
        txt = self.tmp / "x.txt"
        txt.write_text("x", "utf-8")
        out = self.run_cli("library", "add", str(pdf), str(txt))
        self.assertIn("added", out)
        self.assertIn("skipped", out)
        self.run_cli("library", "list")
        paper = self.tmp / "paper.md"
        paper.write_text("Title\n\n" + "We propose a thing. " * 60, "utf-8")
        rid = self.run_cli("review", "new", str(paper)).split()[1]
        self.assertIn(rid, self.run_cli("review", "list"))
        self.assertIn("issues", self.run_cli("review", "run", rid))
        with mock.patch.object(llm, "stream_agent", side_effect=llm.LLMError("offline")):
            self.assertIn("offline", self.run_cli("review", "run", rid, rc=1))
        self.assertIn("research", self.run_cli("models", "list"))
        with mock.patch("backend.providers.lifecycle.unload_all_local", mock.AsyncMock(return_value={"unloaded": []})):
            self.run_cli("models", "unload", "--force")


class Chat(Base):
    """The terminal research chat: plain mode (scripted input) exercises the same handlers as the interactive TUI."""

    def test_ask(self):
        out = self.run_cli("ask", "/help")
        self.assertIn("Lệnh /", out)
        out = self.run_cli("ask", "tell me something")
        self.assertIn("Answer **bold**.", out)
        self.assertNotIn("phdlab-action", out)
        self.assertIn("Chờ bạn duyệt", out)
        self.assertIn("Done.", out)

    def test_repl_every_command(self):
        sk = self.tmp / "data.csv"
        sk.write_text("a,b\n1,2", "utf-8")
        pdf = self.tmp / "p.pdf"
        from pdfgen import make_pdf
        pdf.write_bytes(make_pdf([[(14, "Paper")]]))
        paper = self.tmp / "paper.md"
        paper.write_text("Title\n\n" + "We propose. " * 80, "utf-8")
        lines = ["", "/help", "/pending", "/accept", "/new", "/rename Chat one", "/sessions", "/model", "/model app:local",
                 "/model auto", "/reasoning high", "/reasoning ultra", "/attach " + str(sk), "/attach nope.txt",
                 "what is in this file?", "/pending", "/accept 1", "hello again", "/accept 9", "/accept x", "/reject all",
                 "/lit vision", "/runs", "/runs all", "/outline set topic Edge ViT", "/outline show",
                 f"/outline attach {paper}", "/outline", "/outline bogus", "/library add " + str(pdf), "/library",
                 "/code", "/code new exp7", "/code open exp7", "/code sync", "/code jobs", "/code nope",
                 "/review", f"/review new {paper}", "/review nope", "/pins", "/providers", "/models", "/config",
                 "/config runs.max_minutes", "/config runs.max_minutes 45", "/config aiws.memory_mode \"suggest\"",
                 "/project", "/project new Second", "/project nope", "/dashboard", "/clear", "/workflow", "/workflow list", "/workflow status", "/workflow nope", "/harness list", "/unknowncmd x", "/quit"]
        with mock.patch("backend.execution.vscode.vscode_cli", return_value="code"), \
                mock.patch("backend.execution.vscode.run_cli", return_value=(0, "")), \
                mock.patch("backend.providers.lifecycle.unload_all_local", mock.AsyncMock(return_value={"unloaded": []})):
            out = self.run_cli(lines=lines + ["/code vscode", "/unload"])
        for part in ("PhD Research Lab", "Kỹ năng nghiên cứu", "cấp độ tư duy: cao", "📎 data.csv", "không thấy file",
                     "mô hình: app:local", "Không có gì chờ duyệt", "không có mục số 9", "dùng /accept", "đề cương cấp",
                     "đã đính kèm", "exp7 đã tạo", "dùng /code", "phiên phản biện", "dùng /review", "runs.max_minutes = 45",
                     "dự án mới: Second", "dùng /project", "Project", "Danh mục Quy trình Nghiên cứu PhD Lab", "dùng /workflow"):
            self.assertIn(part, out, part)

    def test_repl_runs_and_decisions(self):
        s = sessions.create("t")
        r = runs.create("experiment", "e", inputs={"command": "python nope.py"}, session_id=s["id"], risk=2)
        lines = ["/pending", "/run " + r["id"], "/accept 1", "/follow " + r["id"], "/pending", "/accept 1", "/cancel " + r["id"],
                 "/accept all"]
        out = self.run_cli("chat", "--session", s["id"], lines=lines)
        self.assertIn("Run " + r["id"], out)
        s2 = sessions.create("t2")
        r2 = runs.create("experiment", "e", inputs={"command": "python nope.py"}, session_id=s2["id"], risk=2)
        out = self.run_cli("chat", "--session", s2["id"], lines=["/reject 1"])
        self.assertIn("CANCELLED", out)
        from backend.memory import lifecycle
        from backend.agent import memory_modes
        s3 = sessions.get(sessions.create("t3")["id"])
        memory_modes.propose(s3, "finding", "Fact one")
        memory_modes.propose(s3, "finding", "Fact two, different")
        out = self.run_cli("chat", "--session", s3["id"], lines=["/accept 1", "/reject 1"])
        self.assertIn("đã lưu", out)
        self.assertIn("đã bỏ qua", out)
        self.assertEqual(sorted(c["status"] for c in lifecycle.list_candidates()), ["approved", "rejected"])
        self.run_cli("chat", "--session", "as-0000000000", rc=1)
        self.run_cli("chat", "--new", lines=["/pending"])

    def test_cancel_and_interrupt(self):
        s = sessions.create("t")
        r = R.Repl(cli.Ctx(cli.Client("", self.tc), io.StringIO(), False))
        r.sid = s["id"]
        with mock.patch.object(r.c, "get", side_effect=[{"last_seq": 0}, KeyboardInterrupt()]), \
                mock.patch.object(r.c, "post", side_effect=[{"id": "t-1", "status": "running"}, {}]):
            self.assertEqual(r.send("x"), 130)
        self.assertEqual(r.send("/help", timeout=0.01), 0)

    def test_rich_output_completer_and_toolbar(self):
        buf = io.StringIO()
        o = R.Out(buf, True)
        o.line("x", "bold")
        o.md("# Title\n- item")
        o.raw("raw")
        self.assertIn("Title", buf.getvalue())
        x = cli.Ctx(cli.Client("", self.tc), io.StringIO(), False)
        rp = R.Repl(x)
        rp.skills = self.tc.get("/api/skills").json()["skills"]
        from prompt_toolkit.document import Document
        comp = R.Completer(rp)
        names = [c.text for c in comp.get_completions(Document("/li"), None)]
        self.assertIn("/lit ", names)
        self.assertIn("/library ", names)
        self.assertEqual([c.text for c in comp.get_completions(Document("/reasoning h"), None)], ["high"])
        self.assertIn("app:auto", [c.text for c in comp.get_completions(Document("/model app:a"), None)])
        self.assertEqual(list(comp.get_completions(Document("hello"), None)), [])
        self.assertIn("tư duy tự động", rp.toolbar())
        rp.sid = sessions.create("t", settings={"reasoning": "low"})["id"]
        rp.atts = [("a", "b")]
        self.assertIn("tư duy thấp", rp.toolbar())
        self.assertIn("📎 1", rp.toolbar())
        with mock.patch.object(rp.c, "get", side_effect=cli.CLIError(3, "down")):
            self.assertIn("0 chờ duyệt", rp.toolbar())
        rp.o = R.Out(io.StringIO(), True)
        rp.banner()
        self.assertEqual(R.visible("a ``"), "a ")
        self.assertEqual(R.visible("a ```phd"), "a ")
        self.assertEqual(R._brief({"name": "x", "args": {}, "reason": "why"}), "why")
        self.assertFalse(R._isatty(object()))

    def test_live_streaming_in_a_terminal(self):
        class TTY(io.StringIO):
            def isatty(self):
                return True
        out = TTY()
        x = cli.Ctx(cli.Client("", self.tc), out, False)
        with mock.patch("sys.stdin", TTY()):
            rp = R.Repl(x)
        self.assertTrue(rp.tty)
        rp.o.console.is_terminal  # rich detects the terminal through isatty
        rp.sid = sessions.create("t")["id"]
        with mock.patch("rich.console.Console.is_terminal", new_callable=mock.PropertyMock, return_value=True):
            self.assertEqual(rp.send("hello"), 0)
        rp.c_clear("")
        self.assertIn("\033[2J", out.getvalue())
        with mock.patch.object(rp, "_prompt_session", side_effect=RuntimeError("no console")), \
                mock.patch("builtins.input", return_value="typed"):
            self.assertEqual(rp.read(), "typed")
        rp.session = mock.Mock(prompt=mock.Mock(return_value="from prompt"))
        rp.inp = None
        self.assertEqual(rp.read(), "from prompt")
        with mock.patch("prompt_toolkit.PromptSession") as PS:
            rp.session, rp.inp = None, None
            rp.read()
            self.assertTrue(PS.called)



class ZZ(Base):
    def test_every_command_ran(self):
        missing = sorted(f"{g} {n}".strip() for (g, n) in cli.COMMANDS if (g, n) not in PASSED)
        self.assertEqual(missing, [], "commands never run successfully")


if __name__ == "__main__":
    unittest.main()
