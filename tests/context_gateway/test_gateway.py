import _env  # noqa: F401  (must be first)
import json
import unittest
from unittest import mock

from backend.providers import cli as C, gateway as GS
from backend.providers.context_packet import SCHEMA_VERSION, canonical_packet, provider_context
from backend.providers.privacy import allowed_classes, sanitize, set_sensitivity
from memory_eval import golden
from providers.fakes import fake

Q = "Should I test SwinIR next?"


def fakes(**modes):
    return mock.patch.dict(C.CONNECTORS, {p: fake(p, modes.get(p, "ok")) for p in ("codex", "claude_code", "antigravity", "gemini_cli")})


def send(rid):
    GS.send(rid)
    GS.REQS[rid]["thread"].join(20)


class Gateway(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("gw34")
        _env.config.save_config({"memory": {"embed_engine": "hashing"},
                                 "gateway": {"allow_internal": True, "allow_sensitive": False}})
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
        sid = ""
        with fakes():
            for p in ("codex", "claude_code", "antigravity"):
                r = GS.prepare(Q, p, role="experiment_designer", session_id=sid)
                sid = r["session_id"]
                self.assertEqual(r["prompt"], a["prompt"])
                send(r["id"])
                full = GS.get(r["id"])
                self.assertEqual(full["status"], "completed", full["errors"])
                self.assertIn("hyp=True", full["answer"])

    def test_sensitivity_enforced_before_sending(self):
        set_sensitivity("FAIL-001", "RESTRICTED")
        with fakes():
            r = GS.prepare(Q, "claude_code", role="experiment_designer")
            self.assertIn("FAIL-001", r["blocked"])
            self.assertNotIn("FAIL-001", r["prompt"])
            send(r["id"])
            self.assertIn("restricted=False", GS.get(r["id"])["answer"])

    def test_cancel_before_sending_and_bad_ids(self):
        with fakes():
            r = GS.prepare(Q, "codex")
            self.assertEqual(r["status"], "ready")
            self.assertEqual(GS.events(r["id"])["events"], [])  # nothing left the machine yet
            self.assertEqual(GS.cancel(r["id"])["status"], "cancelled")
            with self.assertRaises(GS.GatewayError):
                GS.send(r["id"])
            with self.assertRaises(GS.GatewayError):
                GS.cancel(r["id"])
        for bad in ("nope", "gw-0000000000"):
            with self.assertRaises(GS.GatewayError):
                GS.get(bad)
        with self.assertRaises(GS.GatewayError):
            GS.prepare("  ", "codex")

    def test_no_automatic_fallback(self):
        with fakes(codex="auth"):
            r = GS.prepare(Q, "codex")
            send(r["id"])
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

    def test_audit_has_metadata_only(self):
        with fakes():
            r = GS.prepare("my unpublished idea about spectral priors", "gemini_cli")
            send(r["id"])
        raw = (_env.config.data_dir() / "gateway" / "audit.jsonl").read_text("utf-8")
        self.assertEqual([json.loads(x)["event"] for x in raw.splitlines()[-2:]], ["prepared", "completed"])
        self.assertNotIn("unpublished idea", raw)
        self.assertNotIn("Objective", raw)

    def test_sanitize(self):
        # The firewall is opt-in since 6.6.3 (FQC-SOURCE-POLICY-663); this checks it when the researcher enables it.
        t, notes = sanitize("key sk-abcdefghijklmnop1234 and\n```python\nsecret_code()\n```", {"gateway": {"block_source_code": True}})
        self.assertNotIn("secret_code", t)
        self.assertNotIn("sk-abcdefghijklmnop1234", t)
        self.assertEqual(set(notes), {"credentials redacted", "source code withheld"})



if __name__ == "__main__":
    unittest.main()
