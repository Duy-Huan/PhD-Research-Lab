"""The orchestrator's provider paths: a CLI provider through the gateway (fake vendor CLIs, real connectors, firewall and
MCP grant), manual launch plans, cancellation, input validation, history and artifact settings."""
import _env  # noqa: F401  (must be first)
from contextlib import contextmanager
import time
import unittest
from unittest import mock

from backend.agent import AIWSError, orchestrator as O, sessions as store
from backend.core import config
from backend.providers import cli as C, cli_space as W, gateway as GS, models as llm
from providers.fakes import fake


async def answer(agent, system, messages, max_tokens=0, temperature=0.3):
    yield ("delta", "Plain answer.")
    yield ("meta", {})


def wait(sid, tid=None, n=600):
    for _ in range(n):
        s = store.get(sid)
        t = next(x for x in s["turns"] if x["id"] == tid) if tid else s["turns"][-1]
        if t["status"] not in ("queued", "running"):
            return t
        time.sleep(0.03)
    raise AssertionError("turn stuck")


@contextmanager
def fakes(**modes):
    # This fixture executes a Python protocol peer, not a vendor container.
    # Host Docker availability must neither admit nor deny that fixture.
    runtime={'state':'CONTROLLED_PROTOCOL_FIXTURE','verified':True,
             'detail':'Python subprocess fixture only; not OS isolation or live provider qualification'}
    with mock.patch.dict(C.CONNECTORS, {p: fake(p, modes.get(p, "ok")) for p in ("codex", "claude_code", "antigravity", "gemini_cli")}), \
         mock.patch('backend.providers.isolated_cli.runtime_status',return_value=runtime):
        yield


class Orchestrator(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("orc-" + self._testMethodName[:24])
        config.save_config({"runs": {"web_search": False}, "aiws": {"mcp_auto": False}})
        p = mock.patch.object(llm, "stream_agent", answer)
        p.start()
        self.addCleanup(p.stop)
        C._last_error.clear()
        self.s = store.create("t")
        self.sid = self.s["id"]

    def cli(self, name, **settings):
        store.update(self.sid, lambda x: x["settings"].update(provider="cli:" + name, **settings))

    def test_protocol_fixture_does_not_require_or_certify_a_vendor_container(self):
        from backend.providers import registry
        blocked={'state':'UNAVAILABLE','verified':False,'detail':'Controlled absent host runtime'}
        self.cli('codex')
        with mock.patch('backend.providers.isolated_cli.runtime_status',return_value=blocked):
            with fakes():
                turn=wait(self.sid,O.start(self.sid,'Controlled Python protocol, not live inference')['id'])
                self.assertEqual(turn['status'],'completed',turn.get('error'))
            # The test-owned transport must not relax production readiness.
            with mock.patch.dict(C.CONNECTORS,{'codex':fake('codex')}):
                self.assertFalse(registry.describe('cli:codex')['available'])

    def test_cli_provider_answer_tools_usage_and_workspace(self):
        self.cli("claude_code")
        with fakes():
            t = O.start(self.sid, "What next for HYPE-002?", base_url="http://127.0.0.1:8765")
            t = wait(self.sid, t["id"])
        self.assertEqual(t["status"], "completed", t.get("error"))
        s = store.get(self.sid)
        self.assertTrue(s["gateway_session"].startswith("gs-"))
        msg = [m for m in s["messages"] if m["role"] == "assistant"][-1]
        self.assertIn("keys=none", msg["content"])  # the CLI never sees an API key
        types = [e["type"] for e in store.events(self.sid, 0)]
        for ty in ("message.delta", "tool.started", "tool.completed"):
            self.assertIn(ty, types)
        self.assertTrue(t["gateway_request"].startswith("gw-"))

    def test_cli_provider_errors_and_refusals(self):
        self.cli("codex")
        with fakes(codex="auth"):
            t = wait(self.sid, O.start(self.sid, "q")["id"])
        self.assertEqual(t["status"], "failed")
        self.assertIn("Authentication", t["error"])
        C._last_error.clear()
        # the security profile cannot be enforced → refused before anything starts
        with fakes(), mock.patch.object(W, "check_profile", side_effect=W.WorkspaceError("weaker isolation")):
            t = wait(self.sid, O.start(self.sid, "q2")["id"])
        self.assertEqual((t["status"], t["error"]), ("failed", "weaker isolation"))
        with fakes(), mock.patch.object(GS, "prepare", side_effect=GS.GatewayError("gateway off")):
            t = wait(self.sid, O.start(self.sid, "q3")["id"])
        self.assertEqual(t["error"], "gateway off")

    def test_cli_partial_answer_keeps_the_text_with_the_error(self):
        self.cli("gemini_cli")

        def stream(self_, message, ctx):
            yield {"type": "text_delta", "text": "half an answer", "ts": 0}
            yield {"type": "status", "state": "usage", "usage": {"in": 1}, "ts": 0}
            yield {"type": "status", "state": "other", "ts": 0}
            yield {"type": "tool_call", "name": "web_search", "detail": "q", "ts": 0}
            yield {"type": "tool_result", "name": "web_search", "is_error": True, "ts": 0}
            yield {"type": "unknown", "ts": 0}
            yield {"type": "error", "message": "connection dropped", "ts": 0}
        with fakes(), mock.patch.object(type(fake("gemini_cli")).__mro__[1], "stream_message", stream):
            t = wait(self.sid, O.start(self.sid, "q")["id"])
        self.assertEqual(t["status"], "completed")
        self.assertEqual(t["error"], "connection dropped")
        m = [x for x in store.get(self.sid)["messages"] if x["role"] == "assistant"][-1]
        self.assertEqual((m["content"], m["status"]), ("half an answer", "partial"))
        types = [e["type"] for e in store.events(self.sid, 0)]
        self.assertIn("usage.updated", types)
        self.assertIn("tool.failed", types)

    def test_manual_mode_plan_for_cli_and_http_then_launch_and_cancel(self):
        self.cli("codex", operating_mode="manual")
        with fakes():
            t = wait(self.sid, O.start(self.sid, "plan me")["id"])
            self.assertEqual(t["status"], "awaiting_launch")
            plan = O.launch_plan(self.sid, t["id"])
            self.assertEqual(plan["transport"], "cli")
            self.assertTrue(plan["command"])
            self.assertIn("<new gateway session>", plan["cwd"])
            with mock.patch.object(type(C.CONNECTORS["codex"]), "binary", return_value=None):
                self.assertEqual(O.launch_plan(self.sid, t["id"])["command"], [])
            O.launch(self.sid, t["id"], edited_context="only this, key sk-abcdefghijklmnopqrst123")
            t = wait(self.sid, t["id"])
        self.assertEqual(t["status"], "completed", t.get("error"))
        self.assertTrue(t["context_edited"])
        with self.assertRaises(AIWSError):
            O.launch(self.sid, t["id"])
        store.update(self.sid, lambda x: x["settings"].update(provider="app:local"))
        t2 = wait(self.sid, O.start(self.sid, "http plan")["id"])
        self.assertEqual(O.launch_plan(self.sid, t2["id"])["endpoint"], "local model server")
        O.cancel(self.sid, t2["id"])
        self.assertEqual(store.get(self.sid)["turns"][-1]["status"], "cancelled")

    def test_cancel_a_running_cli_turn(self):
        self.cli("codex")
        real, calls = GS.cancel, []

        def flaky(rid):  # the first two cancel requests race with the request finishing / starting
            calls.append(rid)
            if len(calls) <= 2:
                raise GS.GatewayError("Request is ready")
            return real(rid)
        with fakes(codex="slow"), mock.patch.object(GS, "cancel", flaky):
            t = O.start(self.sid, "long job")
            for _ in range(200):
                if (store.get(self.sid)["turns"][-1].get("gateway_request")):
                    break
                time.sleep(0.03)
            O.cancel(self.sid, t["id"])
            t = wait(self.sid, t["id"])
        self.assertEqual(t["status"], "cancelled")
        # a gateway that already forgot the request is tolerated
        O._running["t-fake"] = {"cancel": mock.Mock(), "rid": "gw-0000000000"}
        store.update(self.sid, lambda x: x["turns"].append({"id": "t-fake", "status": "running"}))
        O.cancel(self.sid, "t-fake")
        O._running.pop("t-fake", None)

    def test_input_validation(self):
        with self.assertRaises(AIWSError):
            O.start(self.sid, "   ")
        with self.assertRaises(AIWSError):
            O.retry(self.sid)
        store.update(self.sid, lambda x: x["turns"].append({"id": "t-busy", "status": "running"}))
        O._running['t-busy'] = {'cancel': mock.Mock(), 'rid': ''}
        with self.assertRaises(AIWSError):
            O.start(self.sid, "again")
        O._running.pop('t-busy', None)
        store.update(self.sid, lambda x: x["turns"].pop())
        with self.assertRaises(AIWSError):
            O.start(self.sid, "x", replace_from="m-missing")
        store.update(self.sid, lambda x: x.update(archived=True))
        with self.assertRaises(AIWSError):
            O.start(self.sid, "archived")

    def test_decisions_validation_edits_and_failures(self):
        ap = {"id": "ap-1", "turn_id": "t-x", "kind": "action", "name": "add_note", "args": {"text": "n"}, "status": "pending", "created": 1}
        store.update(self.sid, lambda x: x["approvals"].append(dict(ap)))
        with self.assertRaises(AIWSError):
            O.decide(self.sid, "ap-1", "maybe")
        with self.assertRaises(AIWSError):
            O.decide(self.sid, "ap-none", "approve")
        with self.assertRaises(ValueError):
            O.decide(self.sid, "ap-1", "approve", edits={"nope": 1, "text": ""})
        with mock.patch.object(O.adapters, "execute", side_effect=RuntimeError("disk full")):
            out = O.decide(self.sid, "ap-1", "approve", edits={"text": "edited"})
        self.assertEqual(out["status"], "failed")
        self.assertIn("disk full", out["result"]["error"])
        self.assertTrue(out["edited"])
        with self.assertRaises(AIWSError):
            O.decide(self.sid, "ap-1", "approve")

    def test_history_off_no_artifacts_no_summary_and_provider_notes(self):
        store.update(self.sid, lambda x: x["settings"].update(keep_history=False, collect_artifacts=False, summaries=False,
                                                              reasoning="high", provider="app:local"))
        async def local_stream(cfg, engine, system, messages, *args):
            self.assertEqual(engine, "local")
            self.assertEqual(messages[-1]["content"], "secret question")
            yield "Plain answer."
        # Explicit providers use _stream_engine directly; mocking stream_agent only isolates the auto-router path.
        with mock.patch.object(llm, "_stream_engine", local_stream):
            t = wait(self.sid, O.start(self.sid, "secret question")["id"])
        self.assertEqual(t["status"], "completed", t.get("error"))
        s = store.get(self.sid)
        a = [m for m in s["messages"] if m["role"] == "assistant"][-1]
        self.assertTrue(a["not_retained"])
        self.assertEqual(s.get("summary", ""), "")
        self.assertTrue(any(e["type"] == "status.updated" for e in store.events(self.sid, 0)) or t["notes"] == [])


if __name__ == "__main__":
    unittest.main()
