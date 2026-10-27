"""FQC-HERMES-NATIVE-662: one Hermes per project under the owner's agent profile, without work budgets.

Owner decisions (2026-10-27): memory/history/workspace stay per project; the Nous sign-in and a reviewed skill library
are shared (Hermes' own HERMES_SHARED_AUTH_DIR and skills.external_dirs, verified in the pinned image); the agent
profile chooses the workspace mode (workspace_write -> writable) and Hermes always sees the registry meta-tools; no
deadline, iteration or token caps (Hermes' own defaults are unlimited) — liveness replaces the observation deadline;
only the open project's Hermes runs. Docker and the vendor are MOCKED; RPC parsing and files are real.
"""
import importlib.util
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from types import ModuleType
from unittest.mock import patch

import _env
from backend.core import config
from backend.providers import hermes
from backend.providers.cli import ProviderError

spec = importlib.util.spec_from_file_location('phdlab_hermes_service_native', _env.ROOT / 'tools/hermes_runtime/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class Base(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"hermes-native-{self._testMethodName[:28]}")
        self.addCleanup(patch.stopall)


class ProfileAndShared(Base):
    def test_workspace_mode_follows_the_agent_profile(self):
        if not hasattr(hermes, "runtime_profile"):
            raise AssertionError("runtime_profile missing")
        self.assertEqual(hermes.runtime_profile(), "assisted", "default profile has workspace_write")
        config.save_config({"tools": {"client_profiles": {"hermes": {"permissions": ["read", "compute"], "tools": ["*"]}}}})
        self.assertEqual(hermes.runtime_profile(), "review")

    def test_start_shares_login_and_skills_mounts_project_data_and_stops_other_projects(self):
        calls = []
        other = "f" * 24

        def docker(*args, timeout=20):
            calls.append(list(args))
            if args[:2] == ("image", "inspect"):
                return json.dumps([{"Id": "sha256:img", "Config": {"Labels": {
                    "phdlab.runtime": "hermes", "phdlab.rpc.version": str(hermes.PROTOCOL),
                    "phdlab.adapter.sha256": hermes.adapter_digest()}}}])
            if args[0] == "ps":
                return f"c1 {other}\nc2 {hermes._owner(hermes.runtime_profile())}\n"
            return "container-id"
        states = iter([{"ready": False}, {"ready": True, "state": "READY"}])
        with patch.object(hermes, "docker", docker), patch.object(hermes, "status", lambda p: next(states)), \
                patch.object(hermes, "_inspect", return_value={}):
            hermes.start()
        runtime = next(c for c in calls if c[0] == "run" and "phdlab.hermes.role=runtime" in c)
        proxy = next(c for c in calls if c[0] == "run" and "phdlab.hermes.role=proxy" in c)
        joined = " ".join(runtime)
        shared = hermes.shared_root()
        self.assertIn(f"source={(shared / 'auth').resolve()},target=/opt/shared-auth", joined)
        self.assertIn("HERMES_SHARED_AUTH_DIR=/opt/shared-auth", joined)
        self.assertIn(f"source={(shared / 'skills').resolve()},target=/opt/shared-skills,readonly", joined)
        self.assertIn("target=/workspace", joined)
        self.assertNotIn("target=/workspace,readonly", joined, "assisted profile: writable workspace")
        self.assertNotIn("PHDLAB_ALLOWED_DOMAINS", " ".join(proxy), "unused proxy allowlist removed")
        self.assertIn(["stop", "--time", "10", "c1"], calls, "the other project's Hermes is paused")
        self.assertNotIn(["stop", "--time", "10", "c2"], calls)
        cfg = (hermes.folder(hermes.runtime_profile()) / "home" / "config.yaml").read_text("utf-8")
        self.assertIn("/opt/shared-skills", cfg)

    def test_existing_hermes_config_is_never_rewritten(self):
        home = hermes.folder(hermes.runtime_profile()) / "home"
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.yaml").write_text("model: custom\n", "utf-8")
        self.assertFalse(hermes.link_shared_skills(home)["linked"])
        self.assertEqual((home / "config.yaml").read_text("utf-8"), "model: custom\n")

    def test_skill_sharing_copies_one_reviewed_skill_and_refuses_traversal(self):
        skills = hermes.folder(hermes.runtime_profile()) / "home" / "skills" / "lit-review"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: lit-review\n---\nSteps", "utf-8")
        out = hermes.share_skill("lit-review", approved_by="owner")
        self.assertEqual((hermes.shared_root() / "skills" / "lit-review" / "SKILL.md").read_text("utf-8"),
                         "---\nname: lit-review\n---\nSteps")
        self.assertEqual(out["approved_by"], "owner")
        for bad in ("../x", "a/b", "", "missing"):
            with self.subTest(bad=bad), self.assertRaises(ProviderError):
                hermes.share_skill(bad, approved_by="owner")
        with self.assertRaises(ProviderError):
            hermes.share_skill("lit-review", approved_by="")


class SkillsApi(Base):
    def test_skills_listing_and_sharing_through_the_api(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        home = hermes.folder(hermes.runtime_profile()) / "home" / "skills" / "stats-check"
        home.mkdir(parents=True)
        (home / "SKILL.md").write_text("---\nname: stats-check\n---\nSteps", "utf-8")
        with TestClient(app, headers={"X-PhDLab-Client": "ui"}) as client:
            listed = client.get("/api/runtimes/hermes/skills").json()
            self.assertIn("stats-check", listed["shareable"])
            self.assertEqual(client.post("/api/runtimes/hermes/share-skill", json={"skill": "stats-check"}).status_code, 400,
                             "the reviewing owner is required")
            shared = client.post("/api/runtimes/hermes/share-skill", json={"skill": "stats-check", "approved_by": "owner"})
            self.assertEqual(shared.status_code, 200, shared.text)
            listed = client.get("/api/runtimes/hermes/skills").json()
        self.assertIn("stats-check", listed["shared"], "the shared library is app-wide")
        self.assertNotIn("stats-check", listed["shareable"])


class NoBudgets(Base):
    def test_job_has_no_budgets_and_always_includes_the_registry_tools(self):
        sent = []
        config.save_config({"hermes": {"enabled": True, "model": "observed:free"}})

        def rpc(path, body=None, *, profile="review", timeout=40):
            if path == "/v1/jobs":
                sent.append(body)
                return {"status": "completed", "answer": "done"}
            return {"status": "completed", "answer": "done"}
        with patch.object(hermes, "rpc", rpc):
            list(hermes.HermesConnector().stream_message("q", {"cwd": "x", "mcp_url": "http://127.0.0.1:8765/mcp",
                                                              "mcp_token": "t", "mcp_tools": ["research_get_current_state"]}))
        job = sent[0]
        for key in ("deadline_s", "max_iterations", "max_tokens"):
            self.assertNotIn(key, job)
        self.assertTrue({"phdlab_tools_search", "phdlab_tools_describe", "phdlab_tools_call",
                         "research_get_current_state"} <= set(job["mcp"]["tools"]))

    def test_observation_survives_transient_rpc_errors_and_long_jobs(self):
        config.save_config({"hermes": {"enabled": True, "model": "observed:free"}})
        replies = [{"status": "running"}] + [ProviderError("blip")] * 3 + [{"status": "running"}] * 5 + \
            [{"status": "completed", "answer": "finished after a long run"}]

        def rpc(path, body=None, *, profile="review", timeout=40):
            item = replies.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        with patch.object(hermes, "rpc", rpc), patch.object(hermes.time, "sleep", lambda s: None):
            events = list(hermes.HermesConnector().stream_message("q", {"cwd": "x"}))
        self.assertEqual(events[-1]["type"], "request_completed")
        self.assertIn("finished after a long run", json.dumps(events))

    def test_runtime_unreachable_for_long_is_an_error_not_a_hang(self):
        config.save_config({"hermes": {"enabled": True, "model": "observed:free"}})
        clock = {"t": 0.0}

        def rpc(path, body=None, *, profile="review", timeout=40):
            if path == "/v1/jobs":
                return {"status": "running"}
            raise ProviderError("down")

        def sleep(s):
            clock["t"] += 30
        with patch.object(hermes, "rpc", rpc), patch.object(hermes.time, "sleep", sleep), \
                patch.object(hermes.time, "monotonic", lambda: clock["t"]):
            with self.assertRaisesRegex(ProviderError, "not responding"):
                list(hermes.HermesConnector().stream_message("q", {"cwd": "x"}))


class ServiceUnbounded(Base):
    def setUp(self):
        super().setUp()
        patch.object(service, "STATE", config.data_dir() / "rpc-native").start()
        patch.dict(service.ACTIVE, {}, clear=True).start()

    def test_job_without_budgets_is_admitted_and_agent_gets_hermes_defaults(self):
        patch.object(service, "supervise", lambda job: None).start()
        server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        import urllib.request
        body = {"id": "a" * 32, "session": "b" * 32, "model": "observed:free", "prompt": "q", "tools": []}
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/jobs", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 202)
        calls = []
        runtime = ModuleType("run_agent")

        class FixtureAgent:
            def __init__(self, **kwargs):
                calls.append(kwargs)

            def run_conversation(self, **kwargs):
                return {"final_response": "ok", "messages": []}
        runtime.AIAgent = FixtureAgent
        with patch.dict("sys.modules", {"run_agent": runtime}), \
                patch.object(service.Path, "read_bytes", return_value=b"fixture"), \
                patch.object(service, "AGENT_HASH", __import__("hashlib").sha256(b"fixture").hexdigest()), \
                patch.object(service, "catalog", return_value={"models": [{"id": "observed:free", "free": True}]}), \
                patch.object(service, "nous_credentials", return_value={"api_key": "k", "base_url": "https://inference-api.nousresearch.com/v1"}):
            service.run_agent("a" * 32)
        for key in ("max_iterations", "run_budget_seconds", "max_tokens"):
            self.assertNotIn(key, calls[0], "Hermes' own unlimited defaults apply")

    def test_supervisor_waits_for_the_worker_without_a_deadline(self):
        waited = []

        class Proc:
            pid = 1

            def wait(self, timeout=None):
                waited.append(timeout)
                return 0
        job = {"id": "c" * 32, "session": "b" * 32, "status": "running", "model": "m", "prompt": "q"}
        service.save(service.job_path(job["id"]), {**job, "status": "completed"})
        with patch.object(service.subprocess, "Popen", return_value=Proc()):
            service.save(service.job_path(job["id"]), job)
            service.supervise(job)
        self.assertEqual(waited[0], None)


if __name__ == "__main__":
    unittest.main()
