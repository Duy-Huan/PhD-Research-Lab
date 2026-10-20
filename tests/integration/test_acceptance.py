"""v3.4 §25 acceptance workflow, end to end through the HTTP API and the MCP endpoint (vendor CLIs replaced by the fake
CLI, everything else real): ChatGPT (Codex) → Antigravity (MCP + agy) → recorded decision → recovered by a later session."""
import _env  # noqa: F401  (must be first)
import unittest
import warnings
from unittest import mock

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402
from backend.gateway import connectors as C, service as GS  # noqa: E402
from backend.memory import cache  # noqa: E402
from mcp.test_research_tools import McpClient  # noqa: E402
from memory_eval import golden  # noqa: E402
from providers.fakes import fake  # noqa: E402

Q = "Should I test SwinIR next?"


class Acceptance(unittest.TestCase):
    def test_workflow(self):
        c = TestClient(app)
        _env.fresh_project("Hyperspectral Image Denoising")                                   # 1-2
        _env.config.save_config({"memory": {"embed_engine": "hashing"}, "mcp": {"token": "", "rate_limit_per_min": 0},
                                 "gateway": {"review_before_external": False}})
        golden.seed()                                                                          # 3: HYPE-002 / EXP-004 / 31.42
        st = c.get("/api/memory/state").json()
        self.assertEqual(st["active_hypotheses"][0]["id"], "HYPE-002")
        self.assertEqual(st["best_results"]["PSNR"]["value"], 31.42)
        with mock.patch.dict(C.CONNECTORS, {p: fake(p) for p in C.CONNECTORS}):
            con = c.post("/api/gateway/providers/codex/connect", json={}).json()           # 4: official sign-in path
            self.assertEqual(con["command"], "codex login")
            r = c.post("/api/gateway/requests", json={"query": Q, "provider": "codex", "role": "experiment_designer",
                                                      "send": True}).json()                 # 5
            GS.REQS[r["id"]]["thread"].join(30)
            req = c.get(f"/api/gateway/requests/{r['id']}").json()
            for rid in ("HYPE-002", "FAIL-001", "EXP-004", "EXP-001"):                        # 6: hypothesis, failures,
                self.assertIn(rid, req["prompt"], rid)                                         #    experiments, baseline
            for fact in ("12 GB", "31.42", "QRNN3D"):                                           #    hardware, evidence
                self.assertIn(fact, req["prompt"], fact)
            self.assertEqual(req["status"], "completed")
            self.assertIn(f"chars={len(req['prompt'])}", req["answer"])                       # 7: only the compiled context
            body = c.get(f"/api/gateway/requests/{r['id']}/stream").text                     # 8: streamed in
            self.assertIn("text_delta", body)

            ag = McpClient(c, name="antigravity")                                              # 9-10: same state via MCP
            s2 = ag.call("research_get_current_state")["structuredContent"]
            self.assertEqual(s2["result"]["active_hypotheses"][0]["id"], "HYPE-002")
            self.assertEqual(s2["provenance"]["context_version"], req["context_version"])
            ev = ag.call("research_get_evidence", {"query": "Swin window attention PSNR"})["structuredContent"]["result"]   # 12
            self.assertIn("EVID-001", [e["id"] for e in ev["evidence"]])
            fl = ag.call("research_get_failures", {"query": "SwinIR OOM"})["structuredContent"]["result"]["failures"]
            self.assertEqual(fl[0]["id"], "FAIL-001")
            ex = ag.call("research_get_experiment", {"id": "EXP-004"})["structuredContent"]["result"]
            self.assertIn(golden.GIT_BEST, ex["provenance"]["commits"])
            r2 = c.post("/api/gateway/requests", json={"query": Q, "provider": "antigravity", "role": "experiment_designer",
                                                       "session_id": req["session_id"], "send": True}).json()   # 11
            GS.REQS[r2["id"]]["thread"].join(30)
            self.assertEqual(c.get(f"/api/gateway/requests/{r2['id']}").json()["prompt"], req["prompt"])

            dec = c.post("/api/research/decisions", json={                                    # 13: the researcher decides
                "text": "Test SwinIR-small (window 8, batch 4) next; SwinIR-large stays excluded on the 12 GB GPU",
                "kind": "direction", "evidence_ids": ["EVID-001", "FAIL-001"], "provider": "codex",
                "session": req["session_id"]}).json()
            self.assertEqual(dec["provider"], "codex")                                         # 14: decision + provenance
            ch = c.get(f"/api/provenance/chain/{dec['id']}").json()
            self.assertIn(golden.GIT_BEST, ch["answers"]["commits"])
            sess = c.get(f"/api/gateway/sessions/{req['session_id']}").json()
            self.assertEqual([x["provider"] for x in sess["requests"]], ["codex", "antigravity"])

        GS.REQS.clear()                                                                        # 15: "restart" + another provider
        cache.clear_all()
        later = McpClient(c, name="claude-code")
        decs = later.call("research_get_decisions")["structuredContent"]["result"]["decisions"]
        self.assertIn(dec["id"], [d["id"] for d in decs])
        st = later.call("research_get_current_state")["structuredContent"]["result"]
        self.assertEqual(st["recent_decisions"][0]["id"], dec["id"])
        ctx = later.call("research_get_context", {"query": "What did we decide about SwinIR?", "role": "director"})
        self.assertIn(dec["id"], ctx["structuredContent"]["result"]["context"])
        self.assertEqual(c.get(f"/api/gateway/requests/{r['id']}").json()["status"], "completed")  # persisted


if __name__ == "__main__":
    unittest.main()
