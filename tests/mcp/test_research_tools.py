import _env  # noqa: F401  (must be first)
import json
import unittest
import warnings

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from backend import memory as M  # noqa: E402
from backend.app import app  # noqa: E402
from backend.providers import mcp_tools  # noqa: E402
from memory_eval import golden  # noqa: E402

READ = ["research_get_current_state", "research_search_memory", "research_get_hypothesis", "research_get_experiment",
        "research_get_evidence", "research_get_decisions", "research_get_failures", "research_get_context", "research_get_provenance"]
WRITE = ["research_record_observation", "research_record_decision", "research_record_experiment_result"]


class McpClient:
    def __init__(self, c, name="antigravity"):
        self.c, self.n = c, 0
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": name, "version": "1"}})
        self.session = r.headers.get("mcp-session-id")
        assert self.session

    def rpc(self, method, params=None, headers=None):
        self.n += 1
        h = {"Accept": "application/json, text/event-stream", **(headers or {})}
        if getattr(self, "session", None):
            h["Mcp-Session-Id"] = self.session
        return self.c.post("/mcp", json={"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}, headers=h)

    def call(self, name, args=None):
        r = self.rpc("tools/call", {"name": name, "arguments": args or {}}).json()["result"]
        return r


class ResearchTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def setUp(self):
        _env.fresh_project("mcp34")
        _env.config.save_config({"memory": {"embed_engine": "hashing"}, "mcp": {"token": "", "rate_limit_per_min": 0,
                                                                                  "expose_sandbox": True, "allow_writes": True}})
        self.ids = golden.seed()
        self.m = McpClient(self.c)

    def test_tools_list_and_strict_schemas(self):
        tools = {t["name"]: t for t in self.m.rpc("tools/list").json()["result"]["tools"]}
        for n in READ + WRITE:
            self.assertIn(n, tools)
            self.assertFalse(tools[n]["inputSchema"]["additionalProperties"], n)
            self.assertRegex(n, r"^[A-Za-z0-9_-]{1,64}$")  # portable tool names (no dots)
        self.assertIn("sandbox_run_code", tools)
        _env.config.save_config({"mcp": {"expose_sandbox": False, "allow_writes": False}})
        names = {t["name"] for t in self.m.rpc("tools/list").json()["result"]["tools"]}
        self.assertNotIn("sandbox_run_code", names)
        self.assertNotIn("research_record_decision", names)
        r = self.m.call("research_record_decision", {"text": "do it"})
        self.assertTrue(r["isError"])
        r = self.m.call("sandbox_manage_files", {"action": "list"})
        self.assertTrue(r["isError"])

    def test_read_tools_return_structured_results_with_provenance(self):
        st = self.m.call("research_get_current_state")["structuredContent"]
        self.assertEqual(st["result"]["active_hypotheses"][0]["id"], "HYPE-002")
        self.assertIn("context_version", st["provenance"])
        hits = self.m.call("research_search_memory", {"query": "What configuration caused the OOM?"})["structuredContent"]["result"]["hits"]
        self.assertEqual(hits[0]["id"], "FAIL-001")
        self.assertTrue(hits[0]["why"])
        exp = self.m.call("research_get_experiment", {"id": "EXP-004"})["structuredContent"]["result"]
        self.assertIn(golden.GIT_BEST, exp["provenance"]["commits"])
        self.assertEqual(exp["evidence"][0]["id"], "EVID-001")
        hyp = self.m.call("research_get_hypothesis", {"id": "HYPE-002"})["structuredContent"]["result"]
        self.assertEqual({e["id"] for e in hyp["experiments"]}, {"EXP-003", "EXP-004"})
        ev = self.m.call("research_get_evidence", {"claim_id": "CLM-001"})["structuredContent"]["result"]
        self.assertEqual(ev["evidence"][0]["metric"]["value"], 31.42)
        fl = self.m.call("research_get_failures", {"model": "SwinIR"})["structuredContent"]["result"]["failures"]
        self.assertEqual(fl[0]["id"], "FAIL-001")
        dec = self.m.call("research_get_decisions")["structuredContent"]["result"]["decisions"]
        self.assertEqual(len(dec), 2)
        ctx = self.m.call("research_get_context", {"query": "Should we use Swin Transformer?", "role": "experiment_designer", "trace": True})
        body = ctx["structuredContent"]["result"]
        self.assertIn("### RESEARCH STATE", body["context"])
        self.assertIn("CONTEXT TRACE", body["trace"])
        pv = self.m.call("research_get_provenance", {"id": "EVID-001"})["structuredContent"]["result"]
        self.assertIn("EXP-004", pv["answers"]["where_from"])
        text = json.loads(self.m.call("research_get_current_state")["content"][0]["text"])
        self.assertIn("result", text)

    def test_dotted_alias(self):
        r = self.m.call("research.get_current_state")
        self.assertFalse(r.get("isError"))

    def test_input_validation(self):
        for name, args in [("research_get_experiment", {"id": "../../etc/passwd"}), ("research_get_experiment", {}),
                           ("research_search_memory", {"query": "x", "sql": "DROP TABLE"}),
                           ("research_search_memory", {"query": "x", "k": 10 ** 6}),
                           ("research_record_decision", {"text": "x" * 5000}),
                           ("research_record_observation", {"text": "abc", "metric": {"name": "PSNR", "value": "high"}}),
                           ("research_get_hypothesis", {"id": "HYPE-999"})]:
            r = self.m.call(name, args)
            self.assertTrue(r["isError"], (name, args))
        self.assertEqual(self.m.rpc("bogus/method").json()["error"]["code"], -32601)

    def test_writes_are_candidates_with_client_provenance(self):
        n0 = len(M.load()["decisions"])
        r = self.m.call("research_record_decision", {"text": "Adopt SwinIR-small window 8 as the CAVE baseline",
                                                      "evidence_ids": ["EVID-001"]})["structuredContent"]["result"]
        cand = r["candidate"]
        self.assertEqual(cand["status"], "pending")
        self.assertEqual(cand["origin"]["provider"], "antigravity")
        self.assertEqual(cand["origin"]["session"], self.m.session)
        self.assertEqual(len(M.load()["decisions"]), n0)  # not memory until approved
        r = self.m.call("research_record_experiment_result", {"experiment_id": "EXP-777", "text": "made up"})
        self.assertTrue(r["isError"])


    def test_secrets_are_redacted_in_results(self):
        research_note = "API key for the cluster: sk-abcdefghijklmnopqrstuvwxyz123456"
        from backend.memory import research
        research.add_failure("Cluster login failed", reason=research_note)
        out = self.m.call("research_get_failures", {"query": "cluster login"})["content"][0]["text"]
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", out)
        self.assertIn("[REDACTED]", out)

    def test_schema_validator(self):
        with self.assertRaises(mcp_tools.ToolInputError):
            mcp_tools.validate(mcp_tools.BY_NAME["research_search_memory"]["inputSchema"], {"query": 5})
        with self.assertRaises(mcp_tools.ToolInputError):
            mcp_tools.validate(mcp_tools.BY_NAME["research_get_decisions"]["inputSchema"], {"include_superseded": "yes"})

    def test_audit_has_no_argument_values(self):
        self.m.call("research_search_memory", {"query": "very secret query text"})
        log = (_env.config.data_dir() / "gateway" / "mcp_audit.jsonl").read_text("utf-8")
        self.assertIn("research_search_memory", log)
        self.assertNotIn("very secret query text", log)


if __name__ == "__main__":
    unittest.main()
