"""v4.2 research chat: one conversation surface for the whole project — shared project context (Project adapter),
pinned results (pins.py + /api/pins), the new page at / and the classic tools at /classic."""
import _env  # noqa: F401  (must be first)
import json
import sys
import unittest

from fastapi.testclient import TestClient

from backend.execution import sandbox
from backend.agent import AIWSError, project_context as AD, context as CX, pins, policy as POL, sessions as store
from backend.app import app




class Pins(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("pn-" + self._testMethodName[:30])

    def test_crud_and_verification_rule(self):
        self.assertEqual(pins.list_pins(), [])
        p = pins.add("gap", "  Gap A  ", "body", provenance={"session_id": "as-1", "source_ids": ["ref:x", " ", "ref:y"]})
        self.assertEqual((p["title"], p["status"], p["provenance"]["source_ids"]), ("Gap A", "pinned", ["ref:x", "ref:y"]))
        for bad in (dict(kind="x", title="t"), dict(kind="gap", title=" "), dict(kind="gap", title="t", status="true")):
            with self.assertRaises(AIWSError):
                pins.add(**bad)
        with self.assertRaises(AIWSError):
            pins.add("result", "r", status="verified")                 # no run
        with self.assertRaises(AIWSError):
            pins.add("result", "r", status="verified", provenance={"run_id": "missing-run-1"})
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False, "gpu": False})
        (sandbox.code_dir() / "ok.py").write_text("print('acc=0.9')\n", "utf-8")
        (sandbox.code_dir() / "bad.py").write_text("raise SystemExit(2)\n", "utf-8")
        good = sandbox.run_blocking("python ok.py", 60, "run", "ok")
        bad = sandbox.run_blocking("python bad.py", 60, "run", "bad")
        with self.assertRaises(AIWSError):
            pins.add("result", "r", status="verified", provenance={"run_id": bad.id})
        v = pins.add("result", "acc 0.9", status="verified", provenance={"run_id": good.id})
        self.assertEqual(v["status"], "verified")
        self.assertEqual([x["id"] for x in pins.list_pins(kind="result")], [v["id"]])
        self.assertEqual([x["id"] for x in pins.list_pins(status="pinned")], [p["id"]])
        u = pins.update(p["id"], title="Gap B", body="b2", kind="hypothesis", status="approved", provenance={"message_id": "m-1"})
        self.assertEqual((u["title"], u["kind"], u["status"], u["provenance"]["message_id"], u["provenance"]["session_id"]),
                         ("Gap B", "hypothesis", "approved", "m-1", "as-1"))
        self.assertEqual(pins.update(p["id"], title="   ")["title"], "Gap B")
        self.assertEqual(pins.update(p["id"], body=None)["body"], "b2")
        with self.assertRaises(AIWSError):
            pins.update(p["id"], status="verified")
        self.assertEqual(pins.update(p["id"], status="verified", provenance={"run_id": good.id})["status"], "verified")
        for bad_call in (lambda: pins.update("pin-none", title="x"), lambda: pins.update(p["id"], kind="zzz"), lambda: pins.remove("pin-none")):
            with self.assertRaises(AIWSError):
                bad_call()
        self.assertEqual(pins.remove(p["id"]), {"deleted": p["id"]})
        pins._path().write_text("[]", "utf-8")                          # damaged file → empty list, never a crash
        self.assertEqual(pins.list_pins(), [])

    def test_api(self):
        c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        p = c.post("/api/pins", json={"title": "note 1"}).json()
        self.assertEqual(p["kind"], "note")
        self.assertEqual(c.post("/api/pins", json={"kind": "nope", "title": "x"}).status_code, 400)
        r = c.get("/api/pins").json()
        self.assertEqual((len(r["pins"]), "verified" in r["statuses"], "gap" in r["kinds"]), (1, True, True))
        self.assertEqual(c.put(f"/api/pins/{p['id']}", json={"status": "approved", "ignored": 1}).json()["status"], "approved")
        self.assertEqual(c.put(f"/api/pins/{p['id']}", json={"status": "verified"}).status_code, 400)
        self.assertEqual(c.delete(f"/api/pins/{p['id']}").json(), {"deleted": p["id"]})
        self.assertEqual(c.delete(f"/api/pins/{p['id']}").status_code, 400)




if __name__ == "__main__":
    unittest.main()
