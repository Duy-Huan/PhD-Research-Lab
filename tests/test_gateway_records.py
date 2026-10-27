"""FQC-COVERAGE-662: gateway durable records after a restart — usage report (tokens, latency, malformed files),
detached Hermes jobs reconciled by RPC without replay, lost CLI processes marked failed, and detached cancel."""
import json
import time
import unittest
from unittest.mock import patch

import _env
from backend.providers import gateway as G
from backend.providers.cli import ProviderError


class Records(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"gw-{self._testMethodName[:30]}", code_project=None)
        self.dir = G._dir("requests")

    def write(self, rid, **record):
        base = {"id": rid, "provider": "codex", "status": "completed", "errors": [], "events": []}
        (self.dir / f"{rid}.json").write_text(json.dumps({**base, **record}), "utf-8")

    def test_usage_report_groups_measured_tokens_and_latency(self):
        self.write("gw-0000000001", executing_model="m1", usage={"input_tokens": 10, "output_tokens": 4}, timings_ms={"total": 100})
        self.write("gw-0000000002", executing_model="m1", usage={"prompt_tokens": 5, "completion_tokens": -1}, timings_ms={"total": 300},
                   status="failed")
        self.write("gw-0000000003", provider="claude_code", usage={}, status="cancelled")
        self.write("gw-0000000004", provider=5)
        self.write("gw-0000000005", usage="lots")
        (self.dir / "gw-0000000006.json").write_text("{broken", "utf-8")
        report = G.usage_report()
        rows = {(r["provider"], r["model"]): r for r in report["providers"]}
        m1 = rows[("codex", "m1")]
        self.assertEqual((m1["requests"], m1["completed"], m1["failed"]), (2, 1, 1))
        self.assertEqual((m1["input_tokens"], m1["output_tokens"], m1["usage_reported"]), (15, 4, 2))
        self.assertEqual(m1["mean_latency_ms"], 200.0)
        claude = rows[("claude_code", "(not reported)")]
        self.assertEqual((claude["cancelled"], claude["input_tokens"], claude["mean_latency_ms"]), (1, None, None))
        self.assertEqual((report["malformed_records"], report["truncated"]), (3, False))
        self.assertTrue(G.usage_report(limit=1)["truncated"])

    def test_detached_hermes_jobs_are_reconciled_without_replay(self):
        self.write("gw-00000000a1", provider="hermes", status="running", runtime_job_id="j1")
        with patch("backend.providers.hermes.rpc", return_value={"status": "completed", "answer": "done", "usage": {"t": 1}, "ended": 5}):
            r = G.get("gw-00000000a1")
        self.assertEqual((r["status"], r["answer"], r["detached_runtime"]), ("completed", "done", True))
        self.write("gw-00000000a2", provider="hermes", status="running", runtime_job_id="j2")
        with patch("backend.providers.hermes.rpc", return_value={"status": "interrupted"}):
            r = G.get("gw-00000000a2")
        self.assertEqual(r["status"], "failed")
        self.assertIn("no automatic replay", r["errors"][-1])
        self.write("gw-00000000a3", provider="hermes", status="running", runtime_job_id="j3")
        with patch("backend.providers.hermes.rpc", side_effect=ProviderError("down", "UNAVAILABLE")):
            r = G.get("gw-00000000a3")
        self.assertEqual((r["status"], r["runtime_job_status"]), ("running", "UNAVAILABLE"),
                         "an unreachable runtime is not evidence that the job ended")
        self.write("gw-00000000a4", status="running")
        r = G.get("gw-00000000a4")
        self.assertEqual(r["status"], "failed")
        self.assertIn("CLI process lost after restart", r["errors"][-1])
        with self.assertRaises(G.GatewayError):
            G.get("gw-00000000ff")

    def test_detached_hermes_job_can_still_be_cancelled(self):
        self.write("gw-00000000b1", provider="hermes", status="running", runtime_job_id="j9", profile="assisted")
        with patch("backend.providers.hermes.rpc", side_effect=[{"status": "running"},
                                                              {"status": "cancelled", "ended": time.time()}]) as rpc:
            out = G.cancel("gw-00000000b1")
        self.assertEqual(out["status"], "cancelled")
        self.assertEqual(rpc.call_args.args[0], "/v1/jobs/j9/cancel")
        self.write("gw-00000000b2", status="completed")
        with self.assertRaisesRegex(G.GatewayError, "Request is completed"):
            G.cancel("gw-00000000b2")


if __name__ == "__main__":
    unittest.main()
