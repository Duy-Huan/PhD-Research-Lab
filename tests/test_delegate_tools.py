"""FQC-DELEGATE-TOOLS-662: Codex CLI and Claude Code as delegate tools in the registry.

The agent can hand a coding sub-task to an installed CLI agent the researcher signed in to; the call goes through the
existing durable gateway (isolated workspace, scoped MCP grant, provenance) and returns its real output files.
Antigravity and Gemini CLI are never delegates (their terms forbid third-party driving). Vendor transport is MOCKED.
"""
import unittest
from unittest.mock import patch

import _env

try:
    from backend.tools import delegate_tools
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        _env.fresh_project(f"delegate-{self._testMethodName[:30]}")

    def runtime(self):
        from backend.tools import registry as R
        from backend.tools.runtime import Runtime
        rt = Runtime(R.Registry(), workers=1)
        self.addCleanup(rt.pool.shutdown, wait=True)
        return rt


def fixture_connector():
    from backend.providers import cli
    from pathlib import Path

    class Fixture(cli.ProviderConnector):
        provider_id, label = "codex", "Controlled delegate fixture"

        def health(self, fresh=False):
            return {"state": "CONNECTED", "detail": "Mocked vendor boundary"}

        def capabilities(self):
            return {"send": True, "cancel": True}

        def cancel(self, rid):
            return {"cancelled": True}

        def stream_message(self, message, context):
            (Path(context["cwd"]) / "result.py").write_text("observed = 42", "utf-8")
            yield {"type": "text_delta", "text": "Wrote result.py"}
            yield {"type": "request_completed", "exit_code": 0}
    return Fixture()


class DelegateTools(Base):
    def test_only_terms_compatible_cli_agents_are_delegates(self):
        from backend.tools import registry as R
        ids = {t["id"] for t in R.Registry().listing()["tools"]}
        self.assertIn("delegate.codex", ids)
        self.assertIn("delegate.claude_code", ids)
        self.assertNotIn("delegate.antigravity", ids)
        self.assertNotIn("delegate.gemini_cli", ids)

    def test_delegation_runs_through_the_gateway_and_returns_real_files(self):
        from backend.core import config
        from backend.providers import cli
        from backend.tools.profiles import agent_grant
        rt = self.runtime()
        with patch.dict(cli.CONNECTORS, {"codex": fixture_connector()}):
            job = rt.run("delegate.codex", {"task": "Write result.py with observed = 42"}, agent_grant("session:t"))
        self.assertEqual(job["status"], "succeeded", job.get("error"))
        self.assertEqual(job["result"]["files"], ["result.py"])
        out = config.data_dir() / job["result"]["output_dir"]
        self.assertEqual((out / "result.py").read_text("utf-8"), "observed = 42")
        self.assertTrue(job["result"]["gateway_request_id"].startswith("gw-"))

    def test_delegation_needs_compute_and_workspace_write(self):
        from backend.tools.runtime import Grant
        rt = self.runtime()
        job = rt.run("delegate.codex", {"task": "x"}, Grant(principal="t", permissions=["read", "compute"]))
        self.assertEqual(job["status"], "denied")

    def test_unavailable_cli_is_reported_not_faked(self):
        from backend.tools import registry as R
        reg = R.Registry()
        with patch.dict(R._probe_cache, clear=True), patch.object(delegate_tools, "_health", return_value={"state": "NOT_INSTALLED", "detail": "codex not found"}):
            state = reg.probe(reg.resolve("delegate.codex"))
        self.assertFalse(state["available"])
        self.assertIn("codex not found", state["reason"])


if __name__ == "__main__":
    unittest.main()
