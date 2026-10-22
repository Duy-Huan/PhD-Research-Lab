"""The Primary Research Orchestrator (v5): "/" skills, the intent router, proposals the researcher accepts, the
dashboard, VS Code sync, the outline → long-term memory link, research providers and acceptance evidence."""
import _env  # noqa: F401  (must be first)
import json
import subprocess
import sys
import time
import unittest
from unittest import mock

from backend.agent import AIWSError, acceptance, dashboard, launch, orchestrator as O, outline, runs, sessions as store
from backend.core import config
from backend.execution import code_projects, sandbox, sync
from backend.providers import models as llm, research as RP

SEEN: dict = {}
REAL_APP_COMPLETE = RP.app_complete


async def answer(agent, system, messages, max_tokens=0, temperature=0.3):
    SEEN.update(agent=agent, system=system)
    yield ("delta", "Done.\n")
    yield ("delta", '```phdlab-action\n{"action": "write_section", "args": {"section": "abstract", "text": "We study X."}}\n```\n'
                    '```phdlab-action\n{"action": "update_outline", "args": {"topic": "ViT on edge", "keywords": "a, b"}}\n```\n')
    yield ("meta", {})


def wait_turn(sid, n=400):
    for _ in range(n):
        t = store.get(sid)["turns"][-1]
        if t["status"] not in ("queued", "running"):
            return t
        time.sleep(0.03)
    raise AssertionError("turn stuck")


class Base(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("ag-" + self._testMethodName[:28])
        config.save_config({"runs": {"web_search": False}})
        provider_for = launch.provider_for
        for p in (mock.patch.object(llm, "stream_agent", answer),
                  mock.patch.object(launch, "provider_for", side_effect=lambda skill: "app" if skill["provider"] == "feynman" else provider_for(skill)),
                  mock.patch.object(RP, "app_complete", return_value="lit text (Doe, 2020)")):
            p.start()
            self.addCleanup(p.stop)
        self.s = store.create("t")

    def msgs(self):
        return [m for m in store.get(self.s["id"])["messages"] if m["role"] == "assistant"]


class Skills(Base):
    def test_help_status_and_unknown(self):
        O.start(self.s["id"], "/help")
        self.assertIn("**Lệnh /**", self.msgs()[-1]["content"])
        O.start(self.s["id"], "/status")
        self.assertIn("**Dự án:**", self.msgs()[-1]["content"])
        O.start(self.s["id"], "/nope")
        self.assertIn("Unknown command", self.msgs()[-1]["content"])
        self.assertEqual(store.get(self.s["id"])["turns"][-1]["status"], "completed")

    def test_run_skill_starts_a_run_and_errors_are_answers(self):
        O.start(self.s["id"], "/lit vision transformers")
        m = self.msgs()[-1]
        self.assertTrue(m["run_id"].startswith("RR-"))
        self.assertEqual(runs.wait(m["run_id"], 30)["status"], "COMPLETED")
        O.start(self.s["id"], "/run")
        self.assertIn("/run needs a command", self.msgs()[-1]["content"])
        O.start(self.s["id"], "/idea tiny mlp")
        r = runs.get(self.msgs()[-1]["run_id"])
        self.assertEqual(r["status"], "APPROVAL_PENDING")
        self.assertIn("Chấp nhận", self.msgs()[-1]["content"])

    def test_chat_skill_instructions_and_agent(self):
        O.start(self.s["id"], "/write abstract, formal tone")
        wait_turn(self.s["id"])
        self.assertIn("# Skill /write", SEEN["system"])
        self.assertEqual(SEEN["agent"], "research")
        aps = [a for a in store.get(self.s["id"])["approvals"] if a["kind"] == "action"]
        names = sorted(a["name"] for a in aps)
        self.assertEqual(names, ["update_outline", "write_section"])
        for a in aps:
            O.decide(self.s["id"], a["id"], "approve")
        from backend.paper.writer import load_project
        self.assertEqual(load_project()["sections"]["abstract"], "We study X.")
        o = outline.get()
        self.assertEqual((o["topic"], o["keywords"]), ("ViT on edge", ["a", "b"]))
        from backend.memory import load
        self.assertEqual(load()["tier3"]["goals"], ["ViT on edge"])
        O.start(self.s["id"], "/review")  # reviewer agent skill runs in the background
        self.assertTrue(self.msgs()[-1].get("run_id"))
        O.start(self.s["id"], "/gap please")
        wait_turn(self.s["id"])
        self.assertIn("# Skill /gap", SEEN["system"])
        with mock.patch("backend.agent.skills.get", side_effect=AIWSError("gone")):
            self.assertEqual(O._skill_block("x"), "")
            self.assertEqual(O._agent({"skill": "x"}), "research")
        self.assertEqual(O._agent({"skill": "verify"}), "reviewer")

    def test_write_section_keeps_the_previous_version(self):
        from backend.agent import project_context as PC
        PC.execute("write_section", {"section": "experiments", "text": "v1", "title": "Paper"}, self.s)
        r = PC.execute("write_section", {"section": "experiments", "text": "v2"}, self.s)
        self.assertTrue(r["previous_kept"])
        from backend.paper.writer import load_project
        p = load_project()
        self.assertEqual(p["title"], "Paper")
        self.assertTrue(p["section_history"]["experiments"][0].endswith("v1"))
        pin = PC.execute("pin_result", {"kind": "result", "title": "acc", "research_run": "RR-12345678"}, self.s)
        self.assertTrue(pin["pin"])


class Intents(Base):
    def test_router(self):
        for text, skill in (("chạy thử ý tưởng dùng MLP", "idea"), ("tìm tài liệu về pruning", "lit"),
                            ("viết phần results theo văn phong IEEE", "write"), ("research gap là gì", "gap"),
                            ("đề xuất giả thuyết", "hypothesis"), ("biên dịch latex", "latex"),
                            ("phản biện bài báo này", "review"), ("kiểm chứng kết quả", "verify"),
                            ("đề cương của mình", "outline"), ("tiến độ thế nào", "status"),
                            ("chạy lệnh python train.py", "run")):
            with self.subTest(text):
                self.assertEqual(launch.route(text)["skill"], skill)
        self.assertIsNone(launch.route("xin chào"))
        self.assertIsNone(launch.route("/lit x"))
        with mock.patch("backend.agent.skills.get", side_effect=AIWSError("x")):
            self.assertIsNone(launch.route("tìm tài liệu về pruning"))

    def test_inputs_and_help(self):
        sk = {"pipeline": "experiment"}
        self.assertEqual(launch.inputs_for(sk, "python t.py --gpu"), {"command": "python t.py", "gpu": True})
        self.assertEqual(launch.inputs_for({"pipeline": "review"}, "draft.md"), {"path": "draft.md"})
        self.assertEqual(launch.inputs_for({"pipeline": "verify"}, "x" * 50), {"text": "x" * 50})
        self.assertEqual(launch.inputs_for({"pipeline": "verify"}, ""), {})
        self.assertEqual(launch.inputs_for({"pipeline": "latex"}, "a"), {"text": "a"})
        self.assertEqual(launch.inputs_for({"pipeline": "code"}, "a"), {"task": "a"})
        config.save_config({"research_providers": {"coding_default": "codex"}})
        self.assertEqual(launch.provider_for({"provider": "coding"}), "codex")
        with self.assertRaisesRegex(AIWSError, "answers in the chat"):
            launch.from_skill("gap", "x")
        self.assertIn("**Thí nghiệm**", launch.help_text())

    def test_auto_started_read_only_run_and_proposed_risky_run(self):
        O.start(self.s["id"], "tìm tài liệu về token pruning")
        self.assertTrue(self.msgs()[-1]["run_id"])
        O.start(self.s["id"], "chạy thử ý tưởng dùng MLP nhỏ")
        ap = next(a for a in store.get(self.s["id"])["approvals"] if a["name"] == "start_run")
        r = O.decide(self.s["id"], ap["id"], "approve")
        self.assertEqual(runs.get(r["result"]["run"])["approval"]["status"], "approved")
        runs.cancel(r["result"]["run"])

    def test_chat_intent_uses_the_skill(self):
        O.start(self.s["id"], "đề xuất giả thuyết cho hướng này")
        wait_turn(self.s["id"])
        self.assertIn("# Skill /hypothesis", SEEN["system"])


class Dashboard(Base):
    def test_status_pending_and_text(self):
        d = dashboard.status()
        self.assertEqual((d["status"], d["goal"]), ("idle", ""))
        self.assertIn("chưa có", dashboard.status_text())
        outline.update({"keywords": "a, b"})
        self.assertEqual(dashboard.status()["goal"], "Từ khoá: a, b")
        outline.update({"topic": "Edge ViT"})
        r = runs.create("experiment", "e", inputs={"command": "python x.py"}, session_id=self.s["id"], risk=2)
        O.start(self.s["id"], "chạy thử ý tưởng MLP")
        from backend.memory import lifecycle
        lifecycle.propose("claim", {"text": "A finding"}, origin="provider")
        from backend.agent import pins
        pins.add("note", "pinned thing", "body")
        d = dashboard.status(advanced=True)
        kinds = {p["kind"] for p in d["pending"]}
        self.assertEqual(kinds, {"run", "approval", "memory"})
        self.assertEqual((d["status"], d["goal"]), ("waiting approval", "Edge ViT"))
        self.assertIn("resources", d)
        txt = dashboard.status_text()
        self.assertIn("Cần bạn duyệt", txt)
        self.assertIn("pinned thing", txt)
        runs.approve(r["id"])
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False})
        (sandbox.code_dir() / "x.py").write_text("import time; time.sleep(5)", "utf-8")
        end = time.time() + 10
        while time.time() < end and not dashboard.status()["current"]:
            time.sleep(0.05)
        self.assertIn("Đang chạy", dashboard.status_text())
        runs.cancel(r["id"])

    def test_failures_are_tolerated(self):
        with mock.patch("backend.memory.lifecycle.list_candidates", side_effect=RuntimeError("x")), \
                mock.patch("backend.memory.state.current", side_effect=RuntimeError("x")), \
                mock.patch("backend.execution.resources.gpus", side_effect=RuntimeError("x")), \
                mock.patch("backend.execution.resources.loaded_local_models", side_effect=RuntimeError("x")):
            d = dashboard.status(advanced=True)
        self.assertEqual((d["gpus"], d["local_models"], d["goal"]), ([], {}, ""))


class Sync(Base):
    def test_scan_and_proposals(self):
        root = code_projects.active_dir()
        subprocess.run(["git", "init", "-q"], cwd=root)
        (root / "train.py").write_text("print(1)", "utf-8")
        (root / "outputs").mkdir(exist_ok=True)
        (root / "outputs" / "metrics.json").write_text(json.dumps({"acc": 0.9, "name": "x"}), "utf-8")
        (root / "outputs" / "bad_metrics.json").write_text("{", "utf-8")
        (root / "metrics_list.json").write_text("[1, 2]", "utf-8")
        (root / "outputs" / "fig.png").write_bytes(b"png")
        sc = sync.scan()
        self.assertEqual(sc["metrics"][0]["metrics"], {"acc": 0.9})
        self.assertIn("outputs/fig.png", sc["figures"])
        self.assertTrue(any(f["path"] == "train.py" for f in sc["changes"]))
        out = sync.propose(self.s["id"])
        self.assertEqual(out["proposals"], 2)
        aps = store.get(self.s["id"])["approvals"]
        commit = next(a for a in aps if a["name"] == "commit_code")
        r = O.decide(self.s["id"], commit["id"], "approve")
        self.assertEqual(r["status"], "executed")
        self.assertTrue(r["result"]["commit"])
        again = sync.propose(self.s["id"])  # nothing new since the last sync
        self.assertEqual(again["proposals"], 0)
        self.assertIn("Không có gì mới", self.msgs()[-1]["content"])

    def test_scan_without_git(self):
        with mock.patch("backend.execution.gitops.status", side_effect=RuntimeError("no git")):
            self.assertFalse(sync.scan()["repo"])
        sync._state_file().write_text("{bad", "utf-8")
        self.assertEqual(sync.last_sync(), 0.0)


class Providers(Base):
    def test_describe_and_pick(self):
        RP._health.clear()
        with mock.patch("backend.execution.tools.which", return_value=None):
            self.assertEqual(RP.describe("feynman", fresh=True)["state"], "UNAVAILABLE")
        with mock.patch("backend.execution.tools.which", return_value="feynman"), \
                mock.patch("backend.execution.tools.run_cli", return_value=(0, "\x1b[1mModel: anthropic/x\nModel valid: yes")):
            self.assertEqual(RP.describe("feynman", fresh=True)["detail"], "model anthropic/x")
        with mock.patch("backend.execution.tools.which", return_value="feynman"), \
                mock.patch("backend.execution.tools.run_cli", return_value=(0, "Model valid: no")):
            d = RP.describe("feynman", fresh=True)
            self.assertEqual(d["state"], "NOT_CONFIGURED")
            config.save_config({"research_providers": {"feynman_share_app_key": True},
                                "providers": {"anthropic": {"api_key": "sk-ant-x"}, "openai": {"api_key": "sk-o"}}})
            self.assertEqual(RP.describe("feynman", fresh=True)["state"], "READY")
            self.assertEqual(set(RP._shared_key(config.load_config())), {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"})
        config.save_config({"research_providers": {"feynman_enabled": False}})
        self.assertEqual(RP.describe("feynman", fresh=True)["state"], "DISABLED")
        self.assertEqual(RP.describe("feynman")["state"], "DISABLED")  # cached
        with self.assertRaises(RP.ProviderUnavailable):
            RP.describe("nope")
        with mock.patch.object(RP, "_coding_health", side_effect=RuntimeError("boom")):
            self.assertEqual(RP.describe("codex", fresh=True)["state"], "ERROR")
        states = {p["id"]: p["state"] for p in RP.describe_all(fresh=True)}
        self.assertEqual(states["app"], "READY")
        self.assertEqual(states["python"], "READY")
        self.assertEqual(RP.pick("app"), ("app", ""))
        self.assertEqual(RP.pick("feynman")[0], "app")
        with mock.patch.object(RP, "describe", return_value={"ready": True}):
            self.assertEqual(RP.pick("coding"), ("codex", "") if config.load_config()["research_providers"]["coding_default"] == "codex"
                             else ("claude_code", ""))
        self.assertTrue(RP.needs_linux("apt-get install libgl1"))
        self.assertFalse(RP.needs_linux("python train.py"))
        self.assertEqual(RP.strip_ansi("\x1b[31mred\x1b[0m\r"), "red")

    def test_exec_health(self):
        cfg = config.load_config()
        with mock.patch("backend.execution.sandbox.docker_exe", return_value=None):
            self.assertEqual(RP._exec_health("docker", cfg)["state"], "UNAVAILABLE")
        with mock.patch("backend.execution.sandbox.docker_exe", return_value="docker"), \
                mock.patch("backend.execution.sandbox.docker_running", return_value=False):
            self.assertEqual(RP._exec_health("docker", cfg)["state"], "STOPPED")
        with mock.patch("backend.execution.sandbox.docker_exe", return_value="docker"), \
                mock.patch("backend.execution.sandbox.docker_running", return_value=True):
            self.assertEqual(RP._exec_health("docker", cfg)["state"], "READY")
        self.assertEqual(RP._exec_health("clearml", cfg)["state"], "READY")
        with mock.patch("backend.paper.latex.engines", return_value={"tectonic": "t"}):
            self.assertEqual(RP._exec_health("latex", cfg)["state"], "READY")
        with mock.patch("backend.paper.latex.engines", return_value={}):
            self.assertEqual(RP._exec_health("latex", cfg)["state"], "UNAVAILABLE")

    def test_run_feynman_with_a_fake_cli(self):
        fake = config.data_dir() / "feynman_fake.py"
        fake.write_text("import sys,pathlib\npathlib.Path('brief.md').write_text('# brief')\nprint('\\x1b[1mdone\\x1b[0m', sys.argv[1:])\n"
                        "sys.exit(3 if any('fail' in a for a in sys.argv) else 0)\n", "utf-8")
        ready = {"ready": True, "state": "READY", "detail": ""}
        with mock.patch.object(RP, "describe", return_value=ready), \
                mock.patch("backend.execution.tools.node_argv", return_value=[sys.executable, str(fake)]):
            out = RP.run_feynman("task-001", "lit", "topic", "ctx", config.data_dir() / "out")
            self.assertIn("done", out["text"])
            self.assertEqual(out["files"], ["brief.md"])
            with self.assertRaisesRegex(RP.ProviderUnavailable, "exit 3"):
                RP.run_feynman("task-002", "", "fail", "ctx", config.data_dir() / "out2")
            with self.assertRaisesRegex(RP.ProviderUnavailable, "not allowed"):
                RP.run_feynman("task-003", "autoresearch", "x", "", config.data_dir() / "o")
            slow = config.data_dir() / "slow.py"
            slow.write_text("import time; time.sleep(30)", "utf-8")
        with mock.patch.object(RP, "describe", return_value=ready), \
                mock.patch("backend.execution.tools.node_argv", return_value=[sys.executable, str(slow)]):
            with self.assertRaisesRegex(RP.ProviderUnavailable, "time limit"):
                RP.run_feynman("task-004", "", "x", "", config.data_dir() / "o4", timeout_s=0.5)
            with self.assertRaisesRegex(RP.ProviderUnavailable, "cancelled"):
                RP.run_feynman("task-005", "", "x", "", config.data_dir() / "o5", cancelled=lambda: True)
        with mock.patch.object(RP, "describe", return_value={"ready": False, "state": "NOT_CONFIGURED", "detail": "d"}):
            with self.assertRaises(RP.ProviderUnavailable):
                RP.run_feynman("task-006", "", "x", "", config.data_dir() / "o6")

    def test_run_coding_with_a_fake_connector(self):
        from providers.fakes import fake
        from backend.providers import cli as C
        conn = fake("codex")
        with mock.patch.dict(C.CONNECTORS, {"codex": conn}):
            out = RP.run_coding("code-001", "codex", "write code", "ctx", config.data_dir() / "c1")
            self.assertTrue(out["text"])
            with self.assertRaises(RP.ProviderUnavailable):
                RP.run_coding("code-002", "feynman", "x", "", config.data_dir() / "c2")
            with mock.patch.object(conn, "stream_message", side_effect=C.ProviderError("down")):
                with self.assertRaisesRegex(RP.ProviderUnavailable, "down"):
                    RP.run_coding("code-003", "codex", "x", "", config.data_dir() / "c3")
            with mock.patch.object(conn, "stream_message", return_value=iter([{"type": "error", "message": "quota"}])):
                with self.assertRaisesRegex(RP.ProviderUnavailable, "quota"):
                    RP.run_coding("code-004", "codex", "x", "", config.data_dir() / "c4")
        with mock.patch("backend.providers.cli_space.check_profile", side_effect=__import__("backend.providers.cli_space",
                                                                                            fromlist=["x"]).WorkspaceError("no")):
            with self.assertRaises(RP.ProviderUnavailable):
                RP.run_coding("code-005", "gemini_cli", "x", "", config.data_dir() / "c5")

    def test_app_complete(self):
        with mock.patch("backend.providers.models.call_agent", mock.AsyncMock(return_value={"text": " hi "})):
            self.assertEqual(REAL_APP_COMPLETE("research", "s", "u"), "hi")


class Acceptance(Base):
    def test_evaluate_and_gaps(self):
        p = acceptance.report_path()
        backup = p.read_text("utf-8") if p.exists() else None
        self.addCleanup(lambda: p.write_text(backup, "utf-8") if backup is not None else p.unlink(missing_ok=True))
        p.unlink(missing_ok=True)
        ev = acceptance.evaluate()
        self.assertEqual({c["verdict"] for c in ev["criteria"]}, {"NOT VERIFIED"})
        ev = acceptance.evaluate(simulation={"id": "RR-1"})
        self.assertIn("SIMULATED", {c["verdict"] for c in ev["criteria"]})
        acceptance.write_report({"evidence": {"tests": [{"id": "a", "status": "passed"}]},
                                 "permissions_resources": {"tests": [{"id": "b", "status": "failed"}]}})
        v = {c["key"]: c["verdict"] for c in acceptance.evaluate()["criteria"]}
        self.assertEqual((v["evidence"], v["permissions_resources"]), ("PASS", "FAIL"))
        self.assertTrue(any("dataset" in g for g in acceptance.gaps()))
        p.write_text("{bad", "utf-8")
        self.assertEqual(acceptance.load_report(), {})


if __name__ == "__main__":
    unittest.main()
