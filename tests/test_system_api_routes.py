"""FQC-COVERAGE-662: system API routes (models, Hermes runtime actions, provider sign-in, sync, folder browsing).

Real FastAPI app and request validation; provider processes, vendor CLIs and the native folder dialog are replaced
at their module boundary so no external program or network is started.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _env  # noqa: F401
from fastapi.testclient import TestClient

from backend.app import app
from backend.core import config
from backend.providers import cli, hermes


class SystemApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        cls.c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)

    def test_model_connections_codex_catalog_and_usage(self):
        with mock.patch("backend.providers.connections.status", return_value=[{"id": "x"}]):
            self.assertEqual(self.c.get("/api/models/connections").json(), {"connections": [{"id": "x"}]})
        with mock.patch("backend.providers.app_server.model_catalog", return_value=["gpt-5.4"]):
            out = self.c.post("/api/models/cli/codex").json()
        self.assertEqual(out, {"models": ["gpt-5.4"], "entitlement_verified": False})
        gateway = config.load_config()["gateway"]
        self.assertEqual(gateway["cli_models"]["codex"], ["gpt-5.4"])
        self.assertEqual(gateway["cli_catalogs"]["codex"]["origin"], "installed-cli-catalog")
        with mock.patch("backend.providers.gateway.usage_report", return_value={"calls": 3}):
            self.assertEqual(self.c.get("/api/models/usage").json(), {"calls": 3})

    def test_hermes_runtime_actions(self):
        calls = []

        def rec(name, value):
            def fn(*args, **kwargs):
                calls.append((name, args))
                return value
            return fn

        connector = mock.Mock()
        connector.return_value.connect = rec("connect", {"connected": True})
        with mock.patch.multiple(hermes, refresh_models=rec("models", {"models": []}), start=rec("start", {"state": "RUNNING"}),
                                 stop=rec("stop", {"state": "STOPPED"}), rpc=rec("rpc", {"id": "j1"}),
                                 status=rec("status", {"state": "STOPPED"}), HermesConnector=connector):
            self.assertEqual(self.c.post("/api/runtimes/hermes/models", json={}).json(), {"models": []})
            self.assertEqual(self.c.post("/api/runtimes/hermes/start", json={"profile": "review"}).json(), {"state": "RUNNING"})
            self.assertTrue(config.load_config()["hermes"]["enabled"])
            self.assertEqual(self.c.post("/api/runtimes/hermes/stop", json={}).json(), {"state": "STOPPED"})
            self.assertEqual(self.c.post("/api/runtimes/hermes/connect", json={}).json(), {"connected": True})
            self.assertEqual(self.c.get("/api/runtimes/hermes/jobs/j1").json(), {"id": "j1"})
            self.assertEqual(self.c.get("/api/runtimes/hermes?profile=review").json(), {"state": "STOPPED"})
            self.assertEqual(self.c.post("/api/runtimes/hermes/explode", json={}).status_code, 404)
            self.assertEqual(self.c.post("/api/runtimes/hermes/start", json={"profile": "root"}).status_code, 400)
            self.assertEqual(self.c.post("/api/runtimes/hermes/start", json={"extra": 1}).status_code, 400)
            self.assertEqual(self.c.post("/api/runtimes/hermes/share-skill", json={"skill": "x", "other": 1}).status_code, 400)
        self.assertEqual(calls[1], ("start", ("review",)))
        self.assertEqual(calls[4], ("rpc", ("/v1/jobs/j1",)))

    def test_provider_auth_status(self):
        unknown = self.c.get("/api/providers/cli:nothing/auth-status").json()
        self.assertEqual((unknown["state"], unknown["ready"]), ("UNKNOWN", False))
        with mock.patch.object(cli.CONNECTORS["codex"], "health", return_value={"state": "CONNECTED", "detail": "ok"}):
            ready = self.c.get("/api/providers/cli:codex/auth-status").json()
        self.assertEqual((ready["state"], ready["ready"], ready["web_url"]), ("CONNECTED", True, "https://chatgpt.com"))

    def test_provider_connect_and_launch_use_the_installed_cli_only(self):
        launched = {"launched": True, "command": ["codex", "login"], "detail": "opened"}
        with mock.patch("backend.providers.native.launch_provider", return_value=launched) as launch:
            out = self.c.post("/api/providers/cli:codex/connect", json={}).json()
            self.assertEqual((out["command"], out["argv"], out["opened_web"]), ("codex login", ["codex", "login"], False))
            self.assertEqual(launch.call_args.args, ("codex", True))
            self.c.post("/api/providers/codex/connect", json={"mode": "app"})
            self.assertEqual(launch.call_args.args, ("codex",))
            self.c.post("/api/providers/phdlab/connect", json={})
            self.assertEqual(launch.call_args.args, ("phdlab",))
            out = self.c.post("/api/providers/cli:codex/launch").json()
            self.assertEqual((out["ok"], out["clean_id"], out["message"]), (True, "codex", "opened"))
        self.assertEqual(self.c.post("/api/providers/nope/connect", json={}).status_code, 400)
        self.assertEqual(self.c.post("/api/providers/codex/connect", json={"mode": "fax"}).status_code, 400)
        self.assertEqual(self.c.post("/api/providers/nope/launch").status_code, 404)
        with mock.patch("backend.providers.native.launch_provider", return_value={"launched": False, "detail": "missing"}):
            self.assertEqual(self.c.post("/api/providers/codex/connect", json={}).json()["detail"], "missing")
            self.assertEqual(self.c.post("/api/providers/codex/launch").status_code, 503)

    def test_provider_sync_reports_workspace_changes(self):
        self.assertEqual(self.c.post("/api/providers/feynman/sync").status_code, 410)
        from backend.knowledge import research_store as S
        S.save_topic(S.TopicInput(title="Sync topic"))
        workspaces = [{"id": "w1", "engine": "phdlab"}, {"id": "w2", "engine": "other"}]
        with mock.patch("backend.research_engines.workspaces.list_workspaces", return_value=workspaces), \
                mock.patch("backend.research_engines.workspaces.sync", return_value={"changed": 2, "observed": 5}):
            out = self.c.post("/api/providers/cli:codex/sync").json()
            self.assertEqual((out["workspaces_synced"], out["total_changed"], out["total_observed"]), (1, 2, 5))
            fallback = self.c.post("/api/providers/unlisted/sync").json()
            self.assertEqual(fallback["workspaces_synced"], 2, "no engine match falls back to the latest workspaces")

    def test_folder_picker_browse_and_mkdir(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout="D:\\Research\n")):
            self.assertEqual(self.c.post("/api/system/pick-folder", json={"title": "x"}).json(),
                             {"path": "D:\\Research", "canceled": False, "ok": True})
        with mock.patch("subprocess.run", side_effect=OSError("no display")):
            out = self.c.post("/api/system/pick-folder", json={}).json()
        self.assertEqual((out["ok"], out["canceled"], out["error"]), (False, True, "no display"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "b").mkdir()
            (Path(tmp) / ".a").mkdir()
            (Path(tmp) / "file.txt").write_text("x", encoding="utf-8")
            listing = self.c.get("/api/system/fs-browse", params={"path": tmp}).json()
            self.assertEqual([d["name"] for d in listing["directories"]], ["b", ".a"], "visible folders first, files hidden")
            self.assertEqual(Path(listing["parent"]), Path(tmp).resolve().parent)
            self.assertTrue(listing["drives"])
            made = self.c.post("/api/system/fs-mkdir", json={"path": str(Path(tmp) / "new" / "deep")}).json()
            self.assertTrue(Path(made["path"]).is_dir())
        fallback = self.c.get("/api/system/fs-browse", params={"path": str(Path(tmp) / "gone")}).json()
        self.assertEqual(Path(fallback["current"]), config.ROOT.resolve())
        self.assertEqual(Path(self.c.get("/api/system/fs-browse").json()["current"]), config.ROOT.resolve())
        self.assertEqual(self.c.post("/api/system/fs-mkdir", json={"path": " "}).status_code, 400)

    def test_events_listing_and_stream_hello(self):
        from backend.core import bus
        bus.publish("coverage.probe", n=1)
        events = self.c.get("/api/events", params={"after": 0, "limit": 5000}).json()
        self.assertTrue(events)
        with self.c.stream("GET", "/api/events/stream", params={"timeout": 1, "after": bus.last()}) as response:
            first = next(response.iter_lines())
        self.assertEqual(json.loads(first.removeprefix("data: "))["type"], "hello")


if __name__ == "__main__":
    unittest.main()
