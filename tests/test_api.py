"""Every HTTP route of the v5 API (backend/api/*) through the real app: the browser UI and the CLI use exactly these."""
import _env  # noqa: F401  (must be first)
import io
import json
import sys
import threading
import time
import unittest
import zipfile
from unittest import mock

from fastapi.testclient import TestClient

from backend.agent import runs, sessions
from backend.app import app
from backend.core import bus, config
from backend.execution import sandbox
from backend.providers import models as llm, research as RP
from pdfgen import make_pdf


async def fake_stream(agent, system, messages, max_tokens=0, temperature=0.3):
    yield ("delta", "Answer.\n")
    yield ("meta", {"text": "Answer.\n**Recommendation:** Accept\n**Decision:** Accept\n"
                            '{"issues": [{"id": "I1", "severity": "major", "title": "Baseline", "quote": "We", "problem": "p", "fix": "f"}]}\n'
                            "<<<ORIGINAL\nWe\n>>>\n<<<REVISED\nWe now\n>>>",
                    "engine": "fake", "note": ""})


async def fake_connection(*args, **kwargs):
    yield "OK"


async def failed_connection(*args, **kwargs):
    raise llm.LLMError("no key")
    yield  # keep the same async-generator contract as the actual streaming adapter


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        cls.c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("api-" + self._testMethodName[:28])
        # This API state-transition fixture requires an unavailable preferred
        # provider. Never probe a developer's installed Feynman CLI/auth here.
        config.save_config({"runs": {"web_search": False},
                            "research_providers": {"feynman_enabled": False}})
        for p in (mock.patch.object(llm, "stream_agent", fake_stream),
                  mock.patch.object(RP, "app_complete", return_value="text (Doe, 2020)")):
            p.start()
            self.addCleanup(p.stop)
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False,
                               "gpu": False})

    def ok(self, method, url, **kw):
        r = self.c.request(method, url, **kw)
        self.assertLess(r.status_code, 300, f"{method} {url} → {r.status_code} {r.text[:300]}")
        return r.json() if "json" in r.headers.get("content-type", "") else r

    def bad(self, method, url, code=400, **kw):
        r = self.c.request(method, url, **kw)
        self.assertEqual(r.status_code, code, f"{method} {url} → {r.status_code} {r.text[:300]}")
        return r

    def wait_chat(self, sid, timeout=30):
        """A cold context/compiler import may exceed six seconds; wait for the actual terminal state."""
        deadline = time.monotonic() + timeout
        while True:
            turn = sessions.get(sid)["turns"][-1]
            if turn["status"] in ("completed", "failed", "cancelled"):
                self.assertEqual(turn["status"], "completed", turn.get("error"))
                return turn
            if time.monotonic() >= deadline:
                self.fail(f"Chat did not complete within {timeout}s: {turn['status']} / {turn.get('error')}")
            time.sleep(0.03)

    # ------------------------------------------------------------------ system
    def test_system(self):
        self.assertEqual(self.ok("GET", "/api/version")["version"], config.APP_VERSION)
        self.assertIn("runs", self.ok("GET", "/api/config"))
        self.assertEqual(self.ok("POST", "/api/config", json={"runs": {"max_minutes": 30}})["runs"]["max_minutes"], 30)
        m = self.ok("GET", "/api/models")
        self.assertIn("research", m["agents"])
        self.assertTrue(any(p["id"] == "app:auto" and p["reasoning"] for p in m["providers"]))
        self.bad("POST", "/api/models/test", json={"provider": "nope"})
        with mock.patch("backend.providers.models._stream_engine", fake_connection):
            self.assertTrue(self.ok("POST", "/api/models/test", json={"provider": "anthropic"})["ok"])
        with mock.patch("backend.providers.models.list_provider_models", mock.AsyncMock(return_value=["a"])):
            self.assertEqual(self.ok("POST", "/api/models/list", json={"provider": "openai"})["models"], ["a"])
        with mock.patch("backend.providers.local.lmstudio_status", mock.AsyncMock(return_value={"online": False})), \
                mock.patch("backend.providers.local.ollama_status", mock.AsyncMock(return_value={"online": False})):
            self.assertIn("lifecycle", self.ok("GET", "/api/models/local"))
        with mock.patch("backend.providers.lifecycle.unload_all_local", mock.AsyncMock(return_value={"unloaded": []})):
            self.ok("POST", "/api/models/unload", json={})
        with mock.patch("backend.providers.lifecycle.unload", mock.AsyncMock(return_value={"unloaded": ["m"]})):
            self.ok("POST", "/api/models/unload", json={"engine": "ollama", "model": "m"})
        self.bad("POST", "/api/models/unload", json={"engine": "tpu"})
        with mock.patch.object(RP, "describe_all", return_value=[{"id": "app"}]):
            self.assertEqual(self.ok("GET", "/api/providers?fresh=1")["providers"], [{"id": "app"}])
        with mock.patch("backend.providers.native.launch_provider", return_value={'launched': True, 'command': ['feynman', 'model', 'login']}) as launch:
            self.assertEqual(self.ok("POST", "/api/providers/feynman/connect")["command"], 'feynman model login')
            self.assertEqual(launch.call_args.args, ('feynman', True))
        self.bad("POST", "/api/providers/nope/connect")
        from backend.providers import cli as C
        with mock.patch("backend.providers.native.launch_provider", return_value={'launched': True}):
            self.assertEqual(self.ok("POST", "/api/providers/codex/connect")["provider"], "codex")
        self.assertEqual(self.ok("GET", "/api/dashboard")["status"], "idle")
        self.assertIn("resources", self.ok("GET", "/api/dashboard?advanced=1"))
        bus.publish("test.event", x=1)
        self.assertTrue(self.ok("GET", "/api/events?after=0")["events"])
        with self.c.stream("GET", "/api/events/stream?timeout=1") as r:
            self.assertIn('"hello"', next(r.iter_lines()))
        self.assertEqual(self.c.get("/").status_code, 200)
        self.assertIn("/dist/assets/react-", self.c.get("/").text)
        self.assertEqual(self.c.get("/favicon.ico").status_code, 200)
        self.assertEqual(self.c.get("/assets/app.css").headers["cache-control"], "no-cache, must-revalidate")

    def test_security_middlewares(self):
        self.assertEqual(self.c.get("/api/version", headers={"host": "evil.example"}).status_code, 421)
        self.assertEqual(self.c.get("/api/version", headers={"host": "[::1]:8765"}).status_code, 200)
        self.assertEqual(self.c.post("/api/config", json={}, headers={"origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.c.post("/api/config", json={}, headers={"origin": "http://[bad"}).status_code, 403)
        self.assertEqual(self.c.post("/api/config", json={}, headers={"origin": "http://localhost:8765"}).status_code, 200)
        from backend.execution import code_projects
        code_projects.close()
        r = self.c.post("/api/code/vscode")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "NO_CODE_PROJECT"))
        with mock.patch("backend.providers.models._stream_engine", failed_connection):
            self.assertEqual(self.c.post("/api/models/test", json={"provider": "openai"}).status_code, 502)

    # ------------------------------------------------------------------ projects + outline + files
    def test_projects_outline_files(self):
        p = self.ok("POST", "/api/projects", json={"name": "Proj A", "outline": {"topic": "Edge ViT"}})
        self.assertEqual(self.ok("GET", "/api/outline")["topic"], "Edge ViT")
        self.assertTrue(any(x["name"] == "Proj A" for x in self.ok("GET", "/api/projects")["projects"]))
        self.ok("PUT", "/api/projects/rename", json={"data_dir": p["data_dir"], "name": "Proj B"})
        self.ok("POST", "/api/projects/activate", json={"data_dir": p["data_dir"]})
        self.ok("POST", "/api/projects/open", json={"data_dir": p["data_dir"]})
        self.bad("POST", "/api/projects/open", json={"data_dir": "Z:/nope/never"})
        with mock.patch("os.startfile", create=True):
            self.assertTrue(self.ok("POST", "/api/projects/reveal")["path"])
        o = self.ok("PUT", "/api/outline", json={"keywords": "a, b", "reason": "x"})
        self.assertEqual(o["level"], 2)
        self.ok("PUT", "/api/outline", json={"topic": "T2"})
        self.assertEqual(self.ok("POST", "/api/outline/restore", json={"index": -1})["topic"], "Edge ViT")
        self.bad("PUT", "/api/outline", json={})
        a = self.ok("POST", "/api/outline/attach", files={"file": ("prop.md", b"# Proposal", "text/markdown")})
        self.assertIn("Proposal", self.ok("GET", f"/api/outline/attach/{a['id']}")["text"])
        self.ok("DELETE", f"/api/outline/attach/{a['id']}")
        self.bad("POST", "/api/outline/attach", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
        (config.data_dir() / "notes.md").write_text("# hi", "utf-8")
        r = self.ok("GET", "/api/files?path=notes.md")
        self.assertIn("text/plain", r.headers["content-type"])
        self.assertIn("attachment", self.ok("GET", "/api/files?path=notes.md&download=1").headers["content-disposition"])
        self.bad("GET", "/api/files?path=../../etc/passwd", 404)
        self.ok("POST", "/api/projects/forget", json={"data_dir": p["data_dir"]})

    # ------------------------------------------------------------------ chat
    def test_chat(self):
        s = self.ok("POST", "/api/chat/sessions", json={"title": "T", "settings": {"reasoning": "high"}})
        sid = s["id"]
        self.assertEqual(self.ok("GET", "/api/chat/sessions")["sessions"][0]["id"], sid)
        att = self.ok("POST", "/api/chat/attachments", files={"file": ("data.csv", b"a,b\n1,2", "text/csv")})
        t = self.ok("POST", f"/api/chat/sessions/{sid}/turns", json={"text": "what is in the file?",
                                                                       "overrides": {"sources": [f"att:{att['id']}"]}})
        self.wait_chat(sid)
        g = self.ok("GET", f"/api/chat/sessions/{sid}")
        self.assertEqual(g["turns"][-1]["status"], "completed", g["turns"][-1])
        self.assertGreater(g["last_seq"], 0)
        self.assertTrue(any(x["id"] == f"att:{att['id']}" for x in self.ok("GET", f"/api/chat/sessions/{sid}/turns/{t['id']}/context")["sources"]))
        self.assertTrue(self.ok("GET", f"/api/chat/sessions/{sid}/events?after=0")["events"])
        with self.c.stream("GET", f"/api/chat/sessions/{sid}/stream?after=0&timeout=1") as r:
            lines = [l for l in r.iter_lines() if l.startswith("data:")]
        self.assertIn("stream.timeout", lines[-1])
        self.assertEqual(self.ok("GET", f"/api/chat/sessions/{sid}/effective")["effective"]["reasoning"]["value"], "high")
        self.ok("PUT", f"/api/chat/sessions/{sid}", json={"title": "New", "settings": {"provider": "app:local"}})
        self.ok("PUT", f"/api/chat/sessions/{sid}", json={"settings_reset": ["provider"]})
        self.assertEqual(self.ok("GET", f"/api/chat/sessions/{sid}")["title"], "New")
        self.bad("PUT", f"/api/chat/sessions/{sid}", json={"settings": {"reasoning": "max"}})
        self.ok("POST", f"/api/chat/sessions/{sid}/retry", json={})
        self.wait_chat(sid)
        tid = sessions.get(sid)["turns"][-1]["id"]
        self.bad("POST", f"/api/chat/sessions/{sid}/turns/{tid}/cancel")
        self.bad("POST", f"/api/chat/sessions/{sid}/turns/{tid}/launch")
        msg = next(m for m in sessions.get(sid)["messages"] if m["role"] == "assistant")
        c = self.ok("POST", f"/api/chat/sessions/{sid}/memory", json={"message_id": msg["id"], "type": "finding", "content": "X holds",
                                                                    "save": True})
        self.assertEqual(c["status"], "approved")
        self.assertEqual(self.ok("GET", f"/api/chat/sessions/{sid}")["memory_items"][-1]["status"], "approved")
        f = self.ok("POST", f"/api/chat/sessions/{sid}/fork", json={})
        self.ok("PUT", f"/api/chat/sessions/{f['id']}", json={"archived": True})
        self.assertTrue(self.ok("GET", "/api/chat/sessions?archived=1")["sessions"])
        self.bad("DELETE", f"/api/chat/sessions/{sid}?confirm=no")
        self.ok("DELETE", f"/api/chat/sessions/{sid}?confirm={sid}")
        self.bad("GET", "/api/chat/sessions/as-0000000000")

    def test_approvals_and_artifacts(self):
        s = sessions.create("t")
        from backend.agent import artifacts, orchestrator
        async def propose(agent,system,messages,**kwargs):
            yield ('delta','```phdlab-action\n'+json.dumps({'action':'start_run','args':{
                'skill':'idea','input':'MLP fixture'}})+'\n```')
        with mock.patch.object(llm,'stream_agent',propose):
            orchestrator.start(s["id"], "chạy thử ý tưởng MLP")
            self.wait_chat(s['id'])
        ap = next(a for a in sessions.get(s["id"])["approvals"] if a["name"] == "start_run")
        self.bad("POST", f"/api/chat/sessions/{s['id']}/approvals/{ap['id']}", json={"decision": "maybe"})
        self.assertEqual(self.ok("POST", f"/api/chat/sessions/{s['id']}/approvals/{ap['id']}", json={"decision": "reject"})["status"],
                         "rejected")
        art = artifacts.register(s["id"], "", "src/new.py", b"print(1)\n", "test")
        aid = art["id"]
        self.assertEqual(self.ok("GET", f"/api/chat/sessions/{s['id']}/artifacts/{aid}")["path"], "src/new.py")
        d = self.ok("GET", f"/api/chat/sessions/{s['id']}/artifacts/{aid}/diff")
        self.assertIn("+print(1)", d["diff"])
        self.assertEqual(self.ok("GET", f"/api/chat/sessions/{s['id']}/artifacts/{aid}/download").content, b"print(1)\n")
        self.ok("POST", f"/api/chat/sessions/{s['id']}/artifacts/{aid}/apply", json={"target": "src/new.py", "expected_sha": ""})
        art2 = artifacts.register(s["id"], "", "src/b.py", b"x", "test")
        self.ok("POST", f"/api/chat/sessions/{s['id']}/artifacts/{art2['id']}/reject", json={"reason": "no"})

    def test_skills(self):
        self.assertTrue(self.ok("GET", "/api/skills")["skills"])
        self.assertEqual(self.ok("GET", "/api/skills/lit")["name"], "lit")
        self.bad("GET", "/api/skills/nope")
        text = "---\nname: mine\ndescription: my skill\n---\nDo it.\n"
        self.assertEqual(self.ok("POST", "/api/skills", json={"text": text})["origin"], "project")
        self.ok("DELETE", "/api/skills/mine")
        self.bad("DELETE", "/api/skills/lit")

    # ------------------------------------------------------------------ runs + memory + pins
    def test_runs_and_memory(self):
        s = sessions.create("t")
        r = self.ok("POST", "/api/runs", json={"skill": "lit", "input": "vit", "session_id": s["id"]})
        self.assertEqual(runs.wait(r["id"], 30)["status"], "NEEDS_USER_ACTION")
        self.ok("POST", f"/api/runs/{r['id']}/provider", json={"step": "S1", "provider": "app"})
        self.ok("POST", f"/api/runs/{r['id']}/resume", json={"accept": False})
        self.assertEqual(runs.wait(r["id"], 30)["status"], "COMPLETED")
        self.assertTrue(self.ok("GET", "/api/runs")["runs"])
        self.assertEqual(self.ok("GET", f"/api/runs/{r['id']}")["id"], r["id"])
        self.assertTrue(self.ok("GET", f"/api/runs/{r['id']}/events")["events"])
        with self.c.stream("GET", f"/api/runs/{r['id']}/stream?after=0&timeout=1") as st:
            self.assertTrue(any(l.startswith("data:") for l in st.iter_lines()))
        e = self.ok("POST", "/api/runs", json={"skill": "run", "input": "python nope.py"})
        self.bad("POST", f"/api/runs/{e['id']}/resume", json={})
        self.ok("POST", f"/api/runs/{e['id']}/provider", json={"step": "S1", "provider": "docker"})
        self.ok("POST", f"/api/runs/{e['id']}/approve")
        self.assertEqual(runs.wait(e["id"], 30)["status"], "NEEDS_USER_ACTION")
        self.ok("POST", f"/api/runs/{e['id']}/resume", json={"accept": False, "patch": {"command": "python nope2.py"}})
        runs.wait(e["id"], 30)
        self.ok("POST", f"/api/runs/{e['id']}/cancel")
        self.bad("POST", "/api/runs", json={"skill": "gap", "input": "x"})
        self.bad("GET", "/api/runs/RR-00000000")
        self.assertIn("criteria", self.ok("GET", "/api/acceptance"))
        from backend.memory import lifecycle
        c = lifecycle.propose("claim", {"text": "Claim A"}, origin="provider")
        self.assertTrue(self.ok("GET", "/api/memory/candidates")["candidates"])
        self.ok("POST", f"/api/memory/candidates/{c['id']}/approve", json={})
        c2 = lifecycle.propose("claim", {"text": "Claim B something else"}, origin="provider")
        self.ok("POST", f"/api/memory/candidates/{c2['id']}/reject", json={"reason": "no"})
        self.assertIn("decisions", self.ok("GET", "/api/research"))
        self.assertEqual(self.ok("PUT", "/api/memory/sensitivity", json={"id": "FAIL-001", "level": "RESTRICTED"})["sensitivity"],
                         "RESTRICTED")
        self.bad("PUT", "/api/memory/sensitivity", json={"id": "x", "level": "TOP"})
        pin = self.ok("POST", "/api/pins", json={"kind": "note", "title": "P", "body": "b"})
        self.assertTrue(self.ok("GET", "/api/pins")["pins"])
        self.ok("PUT", f"/api/pins/{pin['id']}", json={"status": "approved"})
        self.ok("DELETE", f"/api/pins/{pin['id']}")

    # ------------------------------------------------------------------ code / jobs / library / paper / review / mcp
    def test_code_and_jobs(self):
        self.assertTrue(self.ok("GET", "/api/code")["projects"])
        self.ok("POST", "/api/code", json={"name": "exp2", "git": False, "seed": False})
        self.ok("POST", "/api/code/open", json={"name": "exp2"})
        self.assertIn("project", self.ok("GET", "/api/code/environment"))
        with mock.patch("backend.execution.vscode.vscode_cli", return_value=None):
            self.bad("POST", "/api/code/vscode")
        with mock.patch("backend.execution.vscode.vscode_cli", return_value="code"), \
                mock.patch("backend.execution.vscode.run_cli", return_value=(0, "")):
            self.assertTrue(self.ok("POST", "/api/code/vscode")["launched"])
        s = sessions.create("t")
        self.assertIn("proposals", self.ok("POST", "/api/code/sync", json={"session_id": s["id"]}))
        self.assertIn("changes", self.ok("GET", "/api/code/scan"))
        (sandbox.code_dir() / "t.py").write_text("import time\nprint('a', flush=True)\ntime.sleep(20)\n", "utf-8")
        job = sandbox.start_job("python t.py", "run", "t", extra_env={"CUDA_VISIBLE_DEVICES": ""})
        time.sleep(0.5)
        threading.Thread(target=lambda: (time.sleep(0.3), self.ok("POST", f"/api/jobs/{job.id}/stop")), daemon=True).start()
        with self.c.stream("GET", f"/api/jobs/{job.id}/stream") as resp:
            lines = [l for l in resp.iter_lines() if l.startswith("data:")]
            first = next(l for l in lines if '"type": "line"' in l or '"type":"line"' in l)
            self.assertIn("line", first)
        end = time.time() + 15
        while job.status == "running" and time.time() < end:
            time.sleep(0.1)
        with self.c.stream("GET", f"/api/jobs/{job.id}/stream?after=999999") as r:
            self.assertIn('"end"', [l for l in r.iter_lines() if l.startswith("data:")][-1])
        self.assertTrue(self.ok("GET", "/api/jobs")["jobs"])
        self.assertEqual(self.ok("GET", f"/api/jobs/{job.id}")["id"], job.id)
        self.ok("GET", f"/api/jobs/{job.id}/file?path=stdout.log")
        self.bad("GET", f"/api/jobs/{job.id}/file?path=../../x", 404)
        self.bad("GET", "/api/jobs/x!/file?path=a", 400)
        self.bad("GET", "/api/jobs/nojob00001/stream", 404)
        self.bad("POST", "/api/jobs/nojob00001/stop")
        self.ok("POST", "/api/code/close")
        self.ok("POST", "/api/code/open", json={"name": "exp2"})
        self.ok("POST", "/api/code/delete", json={"name": "exp2", "confirm": "exp2"})

    def test_library_and_paper(self):
        pdf = make_pdf([[(16, "A Paper About Pruning"), (10, "J. Smith")]])
        r = self.ok("POST", "/api/library/upload", files=[("files", ("p.pdf", pdf, "application/pdf")),
                                                         ("files", ("x.txt", b"no", "text/plain"))])
        name = r["saved"][0]
        self.assertRegex(name, r"^nd_Unknown_A-Paper-About-Pruning_[a-f0-9]{12}\.pdf$")
        self.assertEqual(r["skipped"], ["x.txt"])
        self.assertEqual(len(self.ok("GET", "/api/library")["references"]), 1)
        self.ok("PUT", f"/api/library/{name}", json={"title": "T", "authors": "A; B", "include": False, "key": "k1", "year": "2024"})
        self.bad("PUT", "/api/library/none.pdf", json={})
        with mock.patch("backend.providers.models.call_agent", mock.AsyncMock(return_value={"text": '{"title": "Better"}', "engine": "x"})):
            self.assertEqual(self.ok("POST", "/api/library/refine", json={"file": name})["entry"]["title"], "Better")
        with mock.patch("backend.providers.models.call_agent", mock.AsyncMock(return_value={"text": "nope", "engine": "x"})):
            self.bad("POST", "/api/library/refine", json={"file": name}, code=502)
        self.bad("POST", "/api/library/refine", json={"file": "none.pdf"}, code=404)
        with mock.patch("backend.api.library.first_pages_text", return_value=""):
            self.bad("POST", "/api/library/refine", json={"file": name}, code=422)
        self.assertIn("references.bib", self.ok("GET", "/api/library/bib").text)
        self.assertEqual(self.c.get(f"/api/library/file/{name}").status_code, 200)
        self.bad("GET", "/api/library/file/none.pdf", 404)
        self.ok("DELETE", f"/api/library/{name}")
        p = self.ok("GET", "/api/paper")
        self.assertFalse(p["pdf"])
        self.ok("PUT", "/api/paper", json={"title": "My paper", "venue": "CVPR"})
        self.ok("PUT", "/api/paper/section", json={"section": "abstract", "text": "v1"})
        self.ok("PUT", "/api/paper/section", json={"section": "abstract", "text": "v2"})
        self.assertEqual(next(x for x in self.ok("GET", "/api/paper")["sections"] if x["id"] == "abstract")["versions"], 1)
        self.bad("PUT", "/api/paper/section", json={"section": "nope", "text": "x"})
        from backend.paper import latex as LB
        eng_info = self.ok("GET", "/api/paper/engines")
        self.assertIn("available", eng_info)
        self.assertIn("online", eng_info)
        eng_after = self.ok("POST", "/api/paper/engines/online", json={"enabled": True})
        self.assertTrue(eng_after["online"])
        self.ok("POST", "/api/paper/engines/online", json={"enabled": False})
        tex_raw = self.ok("GET", "/api/paper/tex").text
        self.assertIn("documentclass", tex_raw)
        with mock.patch.object(LB, "compile_pdf", side_effect=LB.NoEngine()):
            self.bad("POST", "/api/paper/compile", json={}, code=424)
        with mock.patch.object(LB, "compile_pdf", side_effect=RuntimeError("busy")):
            self.bad("POST", "/api/paper/compile", json={})
        with mock.patch.object(LB, "compile_pdf", return_value={"ok": True}):
            self.assertTrue(self.ok("POST", "/api/paper/compile", json={})["ok"])
            self.assertTrue(self.ok("POST", "/api/paper/compile", json={"engine": "local"})["ok"])
            self.assertTrue(self.ok("POST", "/api/paper/compile", json={"engine": "online"})["ok"])
        self.bad("GET", "/api/paper/pdf", 404)
        (LB.build_dir() / "main.pdf").write_bytes(b"%PDF-1.4")
        (LB.build_dir() / "build.log").write_text("log", "utf-8")
        self.assertEqual(self.c.get("/api/paper/pdf?download=1").status_code, 200)
        self.assertEqual(self.ok("GET", "/api/paper/log").text, "log")
        with zipfile.ZipFile(io.BytesIO(self.ok("GET", "/api/paper/latex.zip").content)) as z:
            self.assertIn("main.tex", z.namelist())

    def test_review(self):
        text = ("Title of the manuscript\n\nWe propose a method. " * 60).encode()
        r = self.ok("POST", "/api/review/upload", files={"file": ("paper.md", text, "text/markdown")})
        rid = r["meta"]["id"]
        self.assertEqual(self.ok("GET", "/api/review")["reviews"][0]["id"], rid)
        self.ok("PUT", f"/api/review/{rid}/settings", json={"venue": {"type": "journal", "quartile": "Q1"}, "n_reviewers": 1})
        self.assertIn("method", self.ok("GET", f"/api/review/{rid}/text").text)
        self.assertEqual(self.c.get(f"/api/review/{rid}/original").status_code, 200)
        self.bad("POST", f"/api/review/{rid}/stage", json={"stage": "meta"})
        self.bad("POST", f"/api/review/{rid}/stage", json={"stage": "reviewer", "idx": 9})

        def stage(body, path="stage"):
            with self.c.stream("POST", f"/api/review/{rid}/{path}", json=body) as st:
                evs = [json.loads(l[6:]) for l in st.iter_lines() if l.startswith("data:")]
            return evs[-1]
        self.assertEqual(stage({"stage": "reviewer", "idx": 1, "fresh": True})["type"], "done")
        self.assertEqual(stage({"stage": "meta"})["type"], "done")
        self.assertEqual(stage({"stage": "issues"})["type"], "done")
        self.assertEqual(stage({"stage": "response"})["type"], "done")
        self.bad("POST", f"/api/review/{rid}/stage", json={"stage": "nope"})
        st = self.ok("GET", f"/api/review/{rid}")["state"]
        iid = st["issues"][0]["id"]
        self.assertEqual(stage({"issue_id": iid}, "fix")["type"], "done")
        self.bad("POST", f"/api/review/{rid}/fix", json={"issue_id": "none"}, code=404)
        self.ok("PUT", f"/api/review/{rid}/issue/{iid}", json={"status": "done", "fix_status": "accepted", "revised": "We now"})
        self.bad("POST", f"/api/review/{rid}/source", files={"file": ("x.md", b"x", "text/plain")})
        self.ok("POST", f"/api/review/{rid}/source", files={"file": ("main.tex", b"We propose. We", "application/x-tex")})
        self.assertIn("applied", self.ok("POST", f"/api/review/{rid}/apply", json={}))
        for kind in ("report", "fixes", "response", "source"):
            self.assertEqual(self.c.get(f"/api/review/{rid}/download/{kind}").status_code, 200, kind)
        self.bad("GET", f"/api/review/{rid}/download/nope", 404)
        with mock.patch.object(llm, "stream_agent", side_effect=llm.LLMError("offline")):
            self.assertEqual(stage({"stage": "meta"})["type"], "error")
        self.ok("DELETE", f"/api/review/{rid}")
        rid2 = self.ok("POST", "/api/review/upload", files={"file": ("p.md", text, "text/markdown")})["meta"]["id"]
        self.bad("GET", f"/api/review/{rid2}/download/response", 404)
        self.bad("GET", f"/api/review/{rid2}/download/source", 404)
        self.bad("POST", "/api/review/upload", files={"file": ("p.exe", b"MZ", "application/x")})

    def test_mcp(self):
        self.assertEqual(self.c.get("/mcp").status_code, 405)
        r = self.c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIn(r.status_code, (200, 401, 403))
        self.assertEqual(self.c.post("/mcp", content=b"{bad", headers={"content-type": "application/json"}).status_code, 400)
        self.assertEqual(self.c.post("/mcp", json=5).status_code, 400)
        r = self.c.post("/mcp", json=[{"jsonrpc": "2.0", "method": "notifications/initialized"}])
        self.assertEqual(r.status_code, 202)
        from backend.agent import mcp_policy
        tok = mcp_policy.issue("as-0000000001", ["web_search"])
        r = self.c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers={"authorization": f"Bearer {tok}"})
        self.assertEqual([t["name"] for t in r.json()["result"]["tools"]], ["web_search"])
        r = self.c.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}}, headers={"authorization": f"Bearer {tok}"})
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
