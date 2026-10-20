import _env  # noqa: F401  (must be first)
import unittest
from unittest import mock

from backend.gateway import connectors as C, service as GS
from backend.gateway.context import SCHEMA_VERSION, canonical_packet, provider_context
from backend.gateway.policy import allowed_classes, sanitize, set_sensitivity
from memory_eval import golden
from providers.fakes import fake

Q = "Should I test SwinIR next?"


def fakes(**modes):
    return mock.patch.dict(C.CONNECTORS, {p: fake(p, modes.get(p, "ok")) for p in ("codex", "claude_code", "antigravity", "gemini_cli")})


class Gateway(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("gw34")
        _env.config.save_config({"memory": {"embed_engine": "hashing"},
                                 "gateway": {"review_before_external": False, "allow_internal": True, "allow_sensitive": False}})
        golden.seed()
        C._last_error.clear()

    def test_canonical_packet_schema(self):
        p = canonical_packet(Q, role="experiment_designer", allowed=allowed_classes())
        self.assertEqual(p["schema_version"], SCHEMA_VERSION)
        for k in ("project_id", "objective", "active_hypothesis", "active_experiment", "constraints", "recent_decisions",
                  "relevant_evidence", "known_failures", "artifacts", "provenance", "retrieval_trace"):
            self.assertIn(k, p)
        self.assertEqual(p["active_hypothesis"]["id"], "HYPE-002")
        self.assertIn("FAIL-001", [f["id"] for f in p["known_failures"]])
        self.assertTrue(any(golden.GIT_BEST in x["commits"] for x in p["provenance"]))

    def test_same_context_for_every_provider(self):
        a = provider_context(Q, "codex", role="experiment_designer")
        b = provider_context(Q, "antigravity", role="experiment_designer")
        self.assertEqual(a["prompt"], b["prompt"])
        with fakes():
            out = GS.compare(Q, ["codex", "claude_code", "antigravity"], role="experiment_designer")
            self.assertTrue(out["same_context"])
            for r in out["requests"]:
                GS.REQS[r["id"]]["thread"].join(20)
                full = GS.get(r["id"])
                self.assertEqual(full["status"], "completed", full["errors"])
                self.assertIn("hyp=True", full["answer"])
            sess = GS.get_session(out["session_id"])
            self.assertEqual({x["provider"] for x in sess["requests"]}, {"codex", "claude_code", "antigravity"})

    def test_sensitivity_enforced_before_sending(self):
        set_sensitivity("FAIL-001", "RESTRICTED")
        with fakes():
            r = GS.prepare(Q, "claude_code", role="experiment_designer")
            self.assertIn("FAIL-001", r["blocked"])
            self.assertNotIn("FAIL-001", r["prompt"])
            GS.send(r["id"], wait=True)
            self.assertIn("restricted=False", GS.get(r["id"])["answer"])

    def test_review_mode_holds_and_allows_edit(self):
        _env.config.save_config({"gateway": {"review_before_external": True}})
        with fakes():
            r = GS.prepare(Q, "codex")
            self.assertEqual(r["status"], "review")
            self.assertEqual(GS.events(r["id"])["events"], [])  # nothing left the machine
            out = GS.send(r["id"], edited_prompt="Only this: is HYPE-002 still open? token sk-abcdefghijklmnopqrstu123", wait=True)
            self.assertTrue(out["edited"])
            full = GS.get(r["id"])
            self.assertEqual(full["status"], "completed")
            self.assertNotIn("sk-abcdefghijklmnopqrstu123", full["prompt"])
            r2 = GS.prepare(Q, "codex")
            self.assertEqual(GS.cancel(r2["id"])["status"], "cancelled")

    def test_no_automatic_fallback(self):
        with fakes(codex="auth"):
            r = GS.prepare(Q, "codex")
            GS.send(r["id"], wait=True)
            self.assertEqual(GS.get(r["id"])["status"], "failed")
            r2 = GS.prepare(Q, "codex")
            out = GS.send(r2["id"])  # now known AUTH_EXPIRED → refused up-front, alternatives offered, nothing sent
            self.assertEqual(out["status"], "failed")
            self.assertEqual(out["health_state"], "AUTH_EXPIRED")
            self.assertIn("claude_code", out["alternatives"])
            self.assertEqual(GS.events(r2["id"])["events"], [])
        C._last_error.clear()

    def test_unsupported_send_is_explicit(self):
        class McpOnly(C.AntigravityConnector):
            def capabilities(self):
                return {**super().capabilities(), "send": C.NOT_SUPPORTED}
        with mock.patch.dict(C.CONNECTORS, {"antigravity": McpOnly()}):
            with self.assertRaises(GS.GatewayError):
                GS.prepare(Q, "antigravity")

    def test_write_back_is_candidate_with_provenance(self):
        from backend import memory as M
        from backend.memory import lifecycle
        with fakes():
            r = GS.prepare(Q, "claude_code")
            GS.send(r["id"], wait=True)
            c = GS.propose(r["id"], "decision", "Test SwinIR-small with window 8 next, batch 4")
            self.assertEqual(c["status"], "pending")
            self.assertEqual(c["origin"]["provider"], "claude_code")
            self.assertEqual(c["origin"]["request_id"], r["id"])
            n = len(M.load()["decisions"])
            lifecycle.approve(c["id"])
            self.assertEqual(len(M.load()["decisions"]), n + 1)

    def test_audit_has_metadata_only(self):
        with fakes():
            r = GS.prepare("my unpublished idea about spectral priors", "gemini_cli")
            GS.send(r["id"], wait=True)
        log = GS.read_audit()
        self.assertEqual([e["event"] for e in log[-2:]], ["prepared", "completed"])
        raw = (_env.config.data_dir() / "gateway" / "audit.jsonl").read_text("utf-8")
        self.assertNotIn("unpublished idea", raw)
        self.assertNotIn("Objective", raw)

    def test_sanitize(self):
        t, notes = sanitize("key sk-abcdefghijklmnop1234 and\n```python\nsecret_code()\n```")
        self.assertNotIn("secret_code", t)
        self.assertNotIn("sk-abcdefghijklmnop1234", t)
        self.assertEqual(set(notes), {"credentials redacted", "source code withheld"})

    def test_streaming_events_endpoint(self):
        import warnings
        warnings.filterwarnings("ignore")
        from fastapi.testclient import TestClient
        from backend.app import app
        c = TestClient(app)
        with fakes():
            r = c.post("/api/gateway/requests", json={"query": Q, "provider": "antigravity", "send": True}).json()
            GS.REQS[r["id"]]["thread"].join(20)
            body = c.get(f"/api/gateway/requests/{r['id']}/stream").text
            self.assertIn('"type": "request_started"', body)
            self.assertIn('"type": "text_delta"', body)
            self.assertIn("event: end", body)
            self.assertEqual(c.get("/api/gateway/requests/gw-nothere123").status_code, 404)
            prov = c.get("/api/gateway/providers").json()
            self.assertFalse(prov["chatgpt_web"]["supported"])


if __name__ == "__main__":
    unittest.main()
