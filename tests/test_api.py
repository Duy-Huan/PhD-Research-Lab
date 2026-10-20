import _env  # noqa: F401  (must be first)
import unittest
import warnings

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402
from test_provenance_critic import tiny_png  # noqa: E402


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)  # no context manager → the background memory worker is not started
        _env.fresh_project("api")

    def test_host_check_blocks_dns_rebinding(self):
        self.assertEqual(self.c.get("/api/version", headers={"host": "attacker.example"}).status_code, 421)
        self.assertEqual(self.c.get("/api/version", headers={"host": "127.0.0.1:8765"}).status_code, 200)
        self.assertEqual(self.c.get("/api/version", headers={"host": "[::1]:8765"}).status_code, 200)
        self.assertEqual(self.c.post("/api/sandbox/run", json={"cmd": "echo x"}, headers={"host": "evil.test"}).status_code, 421)

    def test_existing_endpoints_still_work(self):
        for p in ("/api/version", "/api/config", "/api/projects", "/api/memory/status", "/api/context/graph",
                  "/api/decisions", "/api/results", "/api/paper/project", "/api/sandbox/runs", "/api/tool/output/lit2plan", "/"):
            self.assertEqual(self.c.get(p).status_code, 200, p)
        self.assertEqual(self.c.get("/api/version").json()["version"], "3.2.0")

    def test_new_read_endpoints(self):
        for p in ("/api/dashboard", "/api/memory/v2/compile?q=test", "/api/memory/v2/plan", "/api/research", "/api/research/timeline",
                  "/api/knowledge", "/api/memory/pages", "/api/resources/policy", "/api/connectors", "/api/workspace/environment/options",
                  "/api/experiments/backends", "/api/codex/runs"):
            self.assertEqual(self.c.get(p).status_code, 200, p)

    def test_research_crud_and_graph(self):
        h = self.c.post("/api/research/hypotheses", json={"text": "Attention helps"}).json()
        self.assertTrue(h["id"].startswith("HYPE-"))
        e = self.c.post("/api/research/experiments", json={"title": "exp", "hypothesis_id": h["id"], "verdict": "supports"}).json()
        self.assertEqual(self.c.post("/api/research/experiments", json={"hypothesis_id": "HYPE-999"}).status_code, 400)
        g = self.c.get("/api/context/graph").json()
        self.assertTrue(any(x["from"] == e["id"] and x.get("research") for x in g["edges"]))
        hits = self.c.post("/api/memory/v2/search", json={"q": "attention"}).json()["hits"]
        self.assertTrue(any(x["id"] == h["id"] for x in hits))
        self.assertEqual(self.c.delete(f"/api/research/{e['id']}").status_code, 200)
        self.assertEqual(self.c.delete("/api/research/EXP-999").status_code, 404)

    def test_provenance_inspect_and_critic(self):
        from backend import provenance as P
        sealed = P.png_write(tiny_png(), P.record("20260101-000000-0000", {"git": {"sha": "c" * 40}}))
        r = self.c.post("/api/provenance/inspect", files={"file": ("loss.png", sealed, "image/png")}).json()
        self.assertEqual(r["embedded"]["git_sha"], "c" * 40)
        self.assertIn("run_error", r)  # the run is not in this project → said honestly, not invented
        r = self.c.post("/api/critic/check", json={"text": "\\begin{figure}\nno end\n"}).json()
        self.assertTrue(any("never closed" in i["message"] for i in r["issues"]))

    def test_validation_errors(self):
        self.assertEqual(self.c.post("/api/experiments/clearml/sync", json={"run_id": "../x"}).status_code, 400)
        self.assertEqual(self.c.get("/api/experiments/clearml/notanid").status_code, 400)
        self.assertEqual(self.c.post("/api/workspace/open", json={"target": "C:/"}).status_code, 409)
        self.assertEqual(self.c.get("/api/memory/pages/../../secret").status_code, 404)

    def test_versions_are_consistent(self):
        import re
        from backend.config import APP_VERSION
        root = _env.ROOT
        start = re.search(r'APP_VERSION = "([^"]+)"', (root / "start.py").read_text("utf-8")).group(1)
        page = re.search(r"const PAGE_V = '([^']+)'", (root / "frontend" / "index.html").read_text("utf-8")).group(1)
        self.assertEqual({APP_VERSION, start, page}, {APP_VERSION})

    def test_launcher_required_files_exist(self):
        import re
        src = (_env.ROOT / "start.py").read_text("utf-8")
        files = re.findall(r'"((?:backend|frontend)/[^"]+)"', src[src.index("REQUIRED_FILES"):src.index("UPGRADE_HELP")])
        self.assertTrue(files)
        self.assertEqual([f for f in files if not (_env.ROOT / f).is_file()], [])

    def test_clearml_secret_never_returned(self):
        self.c.post("/api/config", json={"clearml": {"secret_key": "TOPSECRETVALUE123"}})
        self.assertNotIn("TOPSECRETVALUE123", self.c.get("/api/config").text)
        self.c.post("/api/config", json={"clearml": {"secret_key": ""}})


if __name__ == "__main__":
    unittest.main()
