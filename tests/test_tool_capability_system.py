"""FQC-NATIVE-TOOLS-660: native tool capability system.

Tiers: registry/runtime/proposal cases execute REAL subprocesses, a REAL loopback MCP HTTP server and real files in a
disposable PHDLAB_DATA_DIR. The agent-loop cases drive the loop with an explicitly MOCKED scripted model (a fixture
standing in for model decisions): they prove the loop imposes no tool choice and enforces boundaries, NOT that any
real model makes good choices. Real-model acceptance is the separate tools/tool_agent_acceptance.py qualification.
"""
import json
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import _env

try:
    from backend.tools import agent_loop, proposals, registry as R, schema as S
    from backend.tools.adapters import Cli, Container
    from backend.tools.runtime import Grant, Runtime, provenance, runs_root, verify_provenance
    from backend.tools.spec import ToolError, ToolSpec, satisfies
    MISSING = None
except ImportError as missing:  # RED before implementation: every case fails on its own, with the same case id
    MISSING = missing
    Cli = Container = type("Missing", (), {})


def require_feature():
    if MISSING is not None:
        raise MISSING

STATS = '''import json, sys, statistics
a = json.load(sys.stdin)
xs = a["values"]
print("computing", file=sys.stderr, flush=True)
if a.get("fail"):
    sys.exit(3)
print(json.dumps({"mean": statistics.fmean(xs), "n": len(xs)}))
'''
SLOW = 'import time, json, sys\njson.load(sys.stdin)\ntime.sleep(30)\nprint("{}")\n'


def manifest(tool_id, version="1.0.0", **extra):
    base = {"id": tool_id, "version": version, "kind": "python", "description": f"{tool_id} fixture tool",
            "capabilities": ["statistics"], "permissions": ["compute"], "execution": {"entry": "tool.py"},
            "input_schema": {"type": "object", "required": ["values"], "additionalProperties": False,
                             "properties": {"values": {"type": "array", "items": {"type": "number"}, "minItems": 1},
                                            "fail": {"type": "boolean"}}},
            "output_schema": {"type": "object", "required": ["mean", "n"]}}
    base.update(extra)
    return base


def install(tool_id, version="1.0.0", code=STATS, activate=True, **extra):
    folder = R.tools_root() / tool_id / version
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tool.json").write_text(json.dumps(manifest(tool_id, version, **extra)), "utf-8")
    (folder / "tool.py").write_text(code, "utf-8")
    if activate:
        (folder.parent / "active.json").write_text(json.dumps({"version": version}), "utf-8")
    return folder


class Base(unittest.TestCase):
    def setUp(self):
        require_feature()
        _env.isolate_config(self)
        _env.fresh_project(f"tools-{self._testMethodName[:40]}")
        R._probe_cache.clear()
        self.rt = Runtime(R.Registry(), workers=2)
        self.addCleanup(self.rt.pool.shutdown, wait=True)

    def grant(self, **kw):
        base = dict(principal="test", tools=["*"], permissions=["read", "compute", "process", "workspace_write"],
                    allow_mutation=True, max_calls=20, max_wall_s=120)
        base.update(kw)
        return Grant(**base)

    def run_loop(self, model, grant=None, **kw):
        return agent_loop.run("Estimate the central tendency of 3, 5, 10", model, grant or self.grant(),
                              registry=self.rt.registry, runtime=self.rt, **kw)


class SchemaAndSpec(unittest.TestCase):
    def setUp(self):
        require_feature()

    def test_validation_reports_paths_and_rejects_unknown_keywords(self):
        schema = {"type": "object", "required": ["a"], "additionalProperties": False,
                  "properties": {"a": {"type": "integer", "minimum": 1}, "b": {"type": "array", "maxItems": 1}}}
        self.assertEqual(S.validate({"a": 2}, schema), [])
        errors = S.validate({"a": 0, "b": [1, 2], "c": 1}, schema)
        self.assertTrue(any("$.a" in e for e in errors) and any("$.b" in e for e in errors) and any("$.c" in e for e in errors))
        self.assertEqual(S.validate({"a": True}, schema)[0], "$.a: expected integer, got bool")
        self.assertIn("unsupported keyword", S.schema_errors({"type": "object", "patternProperties": {}})[0])
        with self.assertRaises(ValueError):
            ToolSpec(id="x", description="d", kind="cli", input_schema={"type": "object", "if": {}})

    def test_pydantic_refs_and_anyof_are_validated(self):
        from backend.agent.capabilities import Compare
        schema = Compare.model_json_schema()
        self.assertEqual(S.schema_errors(schema), [])
        self.assertEqual(S.validate({"paper_ids": ["a"], "question": "q"}, schema), [])
        self.assertTrue(S.validate({"paper_ids": "a"}, schema))

    def test_versions_and_constraints(self):
        self.assertTrue(satisfies("1.4.0", "^1.2"))
        self.assertFalse(satisfies("2.0.0", "^1.2"))
        self.assertTrue(satisfies("1.0.1", ">=1.0.0"))
        self.assertFalse(satisfies("1.0.0", "1.0.1"))
        with self.assertRaises(ValueError):
            ToolSpec(id="x", version="1.0", description="d", kind="cli")
        with self.assertRaises(ValueError):
            ToolSpec(id="x", description="d", kind="cli", permissions=["root"])


class RegistryDiscovery(Base):
    def test_builtin_tools_are_registered_with_schemas_permissions_and_lazy_summaries(self):
        listing = R.REGISTRY.listing()
        ids = {t["id"] for t in listing["tools"]}
        self.assertTrue({"research_search_memory", "web_search", "sandbox_run_code"} <= ids)
        entry = next(t for t in listing["tools"] if t["id"] == "sandbox_run_code")
        self.assertNotIn("input_schema", entry, "listing returns summaries; schemas load lazily via describe")
        self.assertEqual(entry["permissions"], ["compute", "process", "workspace_write"])
        full = R.REGISTRY.describe("research_search_memory")
        self.assertIn("query", full["input_schema"]["properties"])
        self.assertEqual(len(full["digest"]), 64)

    def test_new_manifest_is_discovered_at_runtime_and_ranked_by_capability_search(self):
        self.assertFalse(R.REGISTRY.search("arithmetic mean statistics"))
        install("stats_mean")
        found = R.REGISTRY.search("arithmetic mean statistics")
        self.assertEqual(found[0]["id"], "stats_mean")
        self.assertTrue(found[0]["available"])
        self.assertEqual([t["id"] for t in R.REGISTRY.search("", capability="statistics")], ["stats_mean"])
        self.assertFalse(R.REGISTRY.search("mean", permissions=["read"]), "permission filter excludes compute tools")

    def test_versions_active_pointer_and_compatibility(self):
        install("stats_mean", "1.0.0")
        install("stats_mean", "1.1.0", activate=False)
        self.assertEqual(R.REGISTRY.resolve("stats_mean").version, "1.0.0", "active pointer wins over newest")
        self.assertEqual(R.REGISTRY.resolve("stats_mean", "^1.1").version, "1.1.0")
        install("stats_future", requires_app=">=99.0.0")
        with self.assertRaises(ToolError) as e:
            R.REGISTRY.resolve("stats_future")
        self.assertEqual(e.exception.code, "incompatible_version")
        with self.assertRaises(ToolError) as e:
            R.REGISTRY.resolve("stats_mean", "^3")
        self.assertEqual(e.exception.code, "incompatible_version")

    def test_unknown_tool_error_suggests_similar_tools(self):
        install("stats_mean")
        with self.assertRaises(ToolError) as e:
            R.REGISTRY.resolve("stats_median")
        self.assertEqual(e.exception.code, "not_found")
        self.assertIn("stats_mean", e.exception.hint)

    def test_manifests_cannot_be_native_override_builtin_or_inject_host_paths(self):
        folder = install("evil_native", kind="native", execution={"callable": "backend.core.config:save_config"})
        listing = R.REGISTRY.listing()
        self.assertNotIn("evil_native", {t["id"] for t in listing["tools"]})
        self.assertTrue(any("native" in p["error"] for p in listing["invalid_manifests"]))
        install("web_search")
        self.assertEqual(R.REGISTRY.resolve("web_search").kind, "native", "builtin ids are reserved")
        sneaky = install("sneaky", execution={"entry": "tool.py", "home": "C:/", "python": "C:/evil.exe"})
        spec = R.REGISTRY.resolve("sneaky")
        self.assertEqual(spec.execution["home"], str(sneaky.resolve()))
        self.assertNotIn("python", spec.execution)
        self.assertTrue(folder.exists())

    def test_unavailable_cli_tool_is_detected_and_reported(self):
        folder = R.tools_root() / "missing_cli" / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.json").write_text(json.dumps({"id": "missing_cli", "kind": "cli", "description": "absent",
                                                      "execution": {"binary": "phdlab-definitely-not-installed"}}))
        entry = next(t for t in R.REGISTRY.listing()["tools"] if t["id"] == "missing_cli")
        self.assertFalse(entry["available"])
        self.assertIn("not installed", entry["unavailable_reason"])
        self.assertNotIn("missing_cli", {t["id"] for t in R.REGISTRY.listing(include_unavailable=False)["tools"]})


class RuntimeExecution(Base):
    def test_python_tool_executes_streams_observations_and_records_provenance(self):
        install("stats_mean")
        job = self.rt.run("stats_mean", {"values": [1, 2, 3, 6]}, self.grant())
        self.assertEqual(job["status"], "succeeded", job["error"])
        self.assertEqual(job["result"], {"mean": 3.0, "n": 4})
        self.assertIn("computing", [o["text"] for o in job["observations"]])
        rows = provenance(job["id"])
        self.assertEqual(rows[-1]["status"], "succeeded")
        self.assertEqual(rows[-1]["version"], "1.0.0")
        self.assertEqual(len(rows[-1]["spec_digest"]), 64)
        self.assertTrue(verify_provenance()["valid"])
        self.assertTrue((runs_root() / job["id"] / "job.json").is_file())

    def test_invalid_arguments_fail_before_execution_with_actionable_paths(self):
        install("stats_mean")
        job = self.rt.run("stats_mean", {"values": []}, self.grant())
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"]["code"], "invalid_input")
        self.assertIn("$.values", json.dumps(job["error"]["details"]))
        self.assertEqual(job["attempts"], [], "nothing executed")

    def test_execution_failure_is_structured_and_not_reported_as_success(self):
        install("stats_mean")
        job = self.rt.run("stats_mean", {"values": [1], "fail": True}, self.grant())
        self.assertEqual((job["status"], job["error"]["code"]), ("failed", "execution_failed"))
        self.assertIsNone(job["result"])

    def test_output_schema_violation_is_rejected(self):
        install("stats_bad", code='import json,sys\njson.load(sys.stdin)\nprint(json.dumps({"mean": 1}))\n')
        job = self.rt.run("stats_bad", {"values": [1]}, self.grant())
        self.assertEqual(job["error"]["code"], "invalid_output")

    def test_timeout_kills_process_and_cancellation_stops_async_job(self):
        install("slow", code=SLOW, budget={"timeout_s": 1})
        t0 = time.monotonic()
        job = self.rt.run("slow", {"values": [1]}, self.grant())
        self.assertEqual((job["status"], job["error"]["code"]), ("timed_out", "timeout"))
        self.assertLess(time.monotonic() - t0, 15)
        install("slow2", code=SLOW, budget={"timeout_s": 60})
        queued = self.rt.submit("slow2", {"values": [1]}, self.grant())
        deadline = time.monotonic() + 10
        while self.rt.get(queued["id"])["status"] != "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        self.rt.cancel(queued["id"])
        final = self.rt.wait(queued["id"], timeout=20)
        self.assertEqual(final["status"], "cancelled")

    def test_retry_only_for_retryable_idempotent_failures(self):
        install("flaky", code=SLOW, budget={"timeout_s": 0.5}, max_retries=1)
        job = self.rt.run("flaky", {"values": [1]}, self.grant())
        self.assertEqual(len(job["attempts"]), 2)
        install("flaky_mut", code=SLOW, budget={"timeout_s": 0.5}, max_retries=1, idempotent=False)
        self.assertEqual(len(self.rt.run("flaky_mut", {"values": [1]}, self.grant())["attempts"]), 1)

    def test_permissions_allowlist_mutation_and_budgets_are_enforced_and_traced(self):
        install("stats_mean")
        denied = self.rt.run("stats_mean", {"values": [1]}, self.grant(permissions=["read"]))
        self.assertEqual((denied["status"], denied["error"]["code"]), ("denied", "permission_denied"))
        self.assertEqual(self.rt.run("stats_mean", {"values": [1]}, self.grant(tools=["research_*"]))["status"], "denied")
        install("writer", mutates=True)
        self.assertEqual(self.rt.run("writer", {"values": [1]}, self.grant(allow_mutation=False))["status"], "denied")
        g = self.grant(max_calls=1)
        self.assertEqual(self.rt.run("stats_mean", {"values": [1]}, g)["status"], "succeeded")
        over = self.rt.run("stats_mean", {"values": [1]}, g)
        self.assertEqual(over["error"]["code"], "budget_exceeded")
        expired = self.rt.run("stats_mean", {"values": [1]}, self.grant(expires_at=time.time() - 1))
        self.assertEqual(expired["status"], "denied")
        statuses = [r["status"] for r in provenance()]
        self.assertGreaterEqual(statuses.count("denied"), 4, "denied attempts are traceable too")

    def test_output_budget_and_provenance_tamper_detection(self):
        install("big", code='import json,sys\njson.load(sys.stdin)\nprint(json.dumps({"mean": 1, "n": 1, "x": "y" * 50000}))\n',
                budget={"max_output_bytes": 1000})
        self.assertEqual(self.rt.run("big", {"values": [1]}, self.grant())["error"]["code"], "budget_exceeded")
        install("stats_mean")
        self.rt.run("stats_mean", {"values": [2]}, self.grant())
        path = runs_root() / "provenance.jsonl"
        lines = path.read_text("utf-8").splitlines()
        row = json.loads(lines[0])
        row["status"] = "succeeded"
        path.write_text("\n".join([json.dumps(row)] + lines[1:]) + "\n", "utf-8")
        self.assertFalse(verify_provenance()["valid"])

    def test_replay_reproduces_deterministic_result(self):
        install("stats_mean")
        job = self.rt.run("stats_mean", {"values": [1, 2]}, self.grant())
        rep = self.rt.replay(job["id"], self.grant())
        self.assertTrue(rep["result_identical"])
        self.assertEqual(provenance(rep["replay"])[-1]["parent"], job["id"])

    def test_cli_tool_runs_without_shell_and_blocks_option_injection(self):
        folder = R.tools_root() / "echo_cli" / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.json").write_text(json.dumps({
            "id": "echo_cli", "kind": "cli", "description": "echo via python", "permissions": ["process"],
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "execution": {"binary": sys.executable, "args": ["-I", "-c", "import sys,json;print(json.dumps({'got':sys.argv[1]}))", "{text}"],
                          "output": "json"}}))
        ok = self.rt.run("echo_cli", {"text": "a & b | c"}, self.grant())
        self.assertEqual(ok["result"], {"got": "a & b | c"}, ok["error"])
        bad = self.rt.run("echo_cli", {"text": "--evil"}, self.grant())
        self.assertEqual(bad["error"]["code"], "invalid_input")
        with self.assertRaises(ToolError):
            Cli.argv(["{missing}"], {})

    def test_native_builtin_tool_executes_through_unified_runtime(self):
        job = self.rt.run("research_get_current_state", {}, self.grant(permissions=["read"], allow_mutation=False))
        self.assertEqual(job["status"], "succeeded", job["error"])
        self.assertIn("text", job["result"])
        self.assertEqual(job["kind"], "native")


class FakeMcp(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeMcp.calls.append(body["method"])
        if "id" not in body:
            self.send_response(202)
            self.end_headers()
            return
        result = {"initialize": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}},
                  "tools/list": {"tools": [{"name": "Unit-Convert", "description": "Convert units", "annotations": {"readOnlyHint": True},
                                            "inputSchema": {"type": "object", "required": ["celsius"],
                                                            "properties": {"celsius": {"type": "number"}}}}]}}.get(body["method"])
        if body["method"] == "tools/call":
            c = body["params"]["arguments"]["celsius"]
            result = {"content": [{"type": "text", "text": str(c * 9 / 5 + 32)}], "structuredContent": {"fahrenheit": c * 9 / 5 + 32}}
        raw = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ExternalMcpAdapter(Base):
    def test_real_loopback_mcp_server_tools_are_discovered_and_called(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMcp)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        R.add_mcp_server("units", f"http://127.0.0.1:{server.server_address[1]}/mcp")
        found = R.discover_mcp("units")
        self.assertEqual(found["imported"], ["mcp.units.unit_convert"])
        spec = R.REGISTRY.resolve("mcp.units.unit_convert")
        self.assertFalse(spec.mutates)
        job = self.rt.run("mcp.units.unit_convert", {"celsius": 100}, self.grant(permissions=["network"]))
        self.assertEqual(job["result"]["structured"], {"fahrenheit": 212.0}, job["error"])
        self.assertIn("tools/call", FakeMcp.calls)
        self.assertEqual(self.rt.run("mcp.units.unit_convert", {"celsius": 1}, self.grant(permissions=["read"]))["status"], "denied")
        with self.assertRaises(ToolError):
            R.add_mcp_server("remote", "http://example.com/mcp")


class ContainerAdapter(Base):
    def test_container_is_unavailable_without_docker_and_isolated_when_run(self):
        spec = ToolSpec(id="c", description="c", kind="container", execution={"image": "python:3.12-slim", "command": ["python"]})
        with patch("backend.execution.sandbox.docker_exe", return_value=None):
            self.assertFalse(Container.probe(spec)["available"])
        seen = {}

        def fake_run(argv, ctx, **kw):  # MOCKED process boundary: inspects the docker invocation only
            seen["argv"] = argv
            return {"exit_code": 0, "stdout": '{"ok": true}', "stderr": ""}
        ctx = type("Ctx", (), {"workdir": runs_root(), "job_id": "tj-test"})()
        with patch.object(Container, "probe", return_value={"available": True, "reason": ""}), \
                patch("backend.tools.adapters.run_process", fake_run), \
                patch("backend.execution.sandbox.docker_exe", return_value="docker"), \
                patch("backend.execution.sandbox.docker", return_value=(0, "")):
            self.assertEqual(Container.execute(spec, {}, ctx), {"ok": True})
        argv = seen["argv"]
        for flag in ("--read-only", "--cap-drop", "no-new-privileges"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--network") + 1], "none")


class ScriptedModel:
    """MOCKED model: replays decisions given by the test; records what the loop showed it."""

    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    def __call__(self, system, messages):
        self.seen.append((system, [dict(m) for m in messages]))
        reply = self.replies.pop(0)
        return reply(messages) if callable(reply) else reply


def act(**action):
    return "```phdlab-tool\n" + json.dumps(action) + "\n```"


class AgentLoop(Base):

    def test_loop_has_no_tool_specific_logic_or_keyword_forcing(self):
        import inspect
        control = inspect.getsource(agent_loop.run) + inspect.getsource(agent_loop.parse)
        for name in ("research_", "sandbox_", "web_search", "stats", "experiment", "re.search(", "keyword"):
            self.assertNotIn(name, control, "the loop must not route by tool name or by keywords in the goal")
        model = ScriptedModel("I can answer directly: about 6.")
        out = self.run_loop(model)
        self.assertEqual((out["status"], out["jobs"]), ("completed", []), "no tool is pre-selected or forced")

    def test_agent_discovers_previously_unknown_tool_then_selects_and_uses_it(self):
        def discover(messages):
            install("stats_mean")  # the tool appears AFTER the task started
            return act(action="search", query="mean of numbers")
        model = ScriptedModel(discover, act(action="describe", tool="stats_mean"),
                              lambda m: act(action="call", tool="stats_mean", args={"values": [3, 5, 10]}),
                              lambda m: act(action="final", answer="Mean is 6.0", evidence_jobs=[json.loads(
                                  m[-1]["content"].split("\n", 1)[1])["job"]]))
        out = self.run_loop(model)
        self.assertNotIn("stats_mean", model.seen[0][0], "unknown at start")
        self.assertIn("stats_mean", model.seen[1][1][-1]["content"], "found by agent-initiated search")
        self.assertEqual(out["status"], "completed")
        self.assertEqual(len(out["verified_evidence"]), 1)
        self.assertEqual(out["unsupported_claims"], [])

    def test_agent_recovers_from_failure_and_switches_tool_when_result_inadequate(self):
        install("stats_mean")
        install("stats_alt")
        model = ScriptedModel(act(action="call", tool="stats_mean", args={"values": "3,5,10"}),
                              act(action="call", tool="stats_mean", args={"values": [3, 5, 10], "fail": True}),
                              act(action="call", tool="stats_alt", args={"values": [3, 5, 10]}),
                              lambda m: act(action="final", answer="6.0", evidence_jobs=[json.loads(
                                  m[-1]["content"].split("\n", 1)[1])["job"]]))
        out = self.run_loop(model)
        codes = [j["error"]["code"] if j["error"] else j["status"] for j in out["jobs"]]
        self.assertEqual(codes, ["invalid_input", "execution_failed", "succeeded"])
        self.assertIn("hint", model.seen[1][1][-1]["content"], "structured error with hint fed back to the agent")
        self.assertEqual(out["status"], "completed")

    def test_agent_composes_multiple_tools_for_a_new_task(self):
        install("stats_mean")
        folder = R.tools_root() / "scale" / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.json").write_text(json.dumps({**manifest("scale"), "output_schema": {}, "input_schema": {
            "type": "object", "properties": {"values": {"type": "array"}, "factor": {"type": "number"}}}}))
        (folder / "tool.py").write_text('import json,sys\na=json.load(sys.stdin)\nprint(json.dumps({"values":[x*a["factor"] for x in a["values"]]}))\n')

        def chain(messages):
            scaled = json.loads(messages[-1]["content"].split("\n", 1)[1])["result"]["values"]
            return act(action="call", tool="stats_mean", args={"values": scaled})
        model = ScriptedModel(act(action="call", tool="scale", args={"values": [1, 2, 3], "factor": 10}), chain,
                              act(action="final", answer="20.0"))
        out = self.run_loop(model)
        self.assertEqual(out["jobs"][1]["result"]["mean"], 20.0)

    def test_authorization_boundary_cannot_be_widened_by_model_and_claims_are_verified(self):
        install("stats_mean")
        read_only = self.grant(tools=["research_*"], permissions=["read"], allow_mutation=False)
        model = ScriptedModel(act(action="call", tool="stats_mean", args={"values": [1]}),
                              act(action="final", answer="We ran the experiment: mean 1.", evidence_jobs=["tj-" + "0" * 20]))
        out = self.run_loop(model, grant=read_only)
        self.assertEqual(out["jobs"][0]["status"], "denied")
        self.assertIn("tj-" + "0" * 20, out["unsupported_claims"])
        self.assertIn("execution claimed without a cited succeeded job", out["unsupported_claims"])
        self.assertIn("[not granted]", model.seen[0][0])

    def test_protocol_errors_step_limit_and_cancellation_are_bounded(self):
        model = ScriptedModel(*["```phdlab-tool\nnot json\n```"] * 3)
        out = self.run_loop(model, max_steps=3)
        self.assertEqual(out["status"], "step_limit")
        self.assertEqual([s.get("error") for s in out["steps"]], ["invalid_input"] * 3)
        self.assertEqual(self.run_loop(ScriptedModel(), cancelled=lambda: True)["status"], "cancelled")

    def test_relabelled_json_fence_is_an_action_but_ordinary_json_is_an_answer(self):
        """Regression from the live spark diagnostic: a ```json action fence was taken as the final answer."""
        install("stats_mean")
        model = ScriptedModel('```json\n{"action": "call", "tool": "stats_mean", "args": {"values": [3, 5, 10]}}\n```',
                              'Result:\n```json\n{"mean": 6.0}\n```')
        out = self.run_loop(model)
        self.assertEqual(out["jobs"][0]["status"], "succeeded")
        self.assertEqual(out["status"], "completed")
        self.assertIn('"mean": 6.0', out["answer"])

    def test_empty_or_truncated_reply_is_not_accepted_as_a_final_answer(self):
        """Regression from the live spark diagnostic: a token-limit truncation was taken as the answer."""
        model = ScriptedModel("", "\n\n% [WARNING: output truncated at max_tokens]", "The mean is about 6.")
        out = self.run_loop(model)
        self.assertEqual([s.get("error") for s in out["steps"][:2]], ["invalid_input", "invalid_input"])
        self.assertIn("truncated", model.seen[2][1][-1]["content"])
        self.assertEqual((out["status"], out["answer"]), ("completed", "The mean is about 6."))


class Proposals(Base):
    def propose_mean(self, version="1.0.0", code=STATS):
        return proposals.propose(manifest("agent_mean", version, examples=[{"args": {"values": [2, 4]}, "expect": {"mean": 3.0}}]),
                                 {"tool.py": code}, proposer="agent:test")

    def test_propose_validate_promote_rollback_lifecycle(self):
        self.assertEqual(self.propose_mean()["status"], "proposed")
        self.assertNotIn("agent_mean", {t["id"] for t in R.REGISTRY.listing()["tools"]}, "proposal is not active")
        _env.config.save_config({"tools": {"allow_host_validation": True}})
        with patch("backend.tools.adapters.Container.probe", return_value={"available": False, "reason": "test"}):
            report = proposals.validate("agent_mean", "1.0.0", runtime=self.rt)
        self.assertEqual(report["status"], "PASS", report)
        with self.assertRaises(ToolError):
            proposals.promote("agent_mean", "1.0.0", "agent:self")
        self.assertEqual(proposals.promote("agent_mean", "1.0.0", "owner")["status"], "active")
        self.assertEqual(self.rt.run("agent_mean", {"values": [1, 3]}, self.grant())["result"]["mean"], 2.0)
        self.propose_mean("1.1.0", STATS.replace("statistics.fmean(xs)", "max(xs)"))
        with patch("backend.tools.adapters.Container.probe", return_value={"available": False, "reason": "test"}):
            self.assertEqual(proposals.validate("agent_mean", "1.1.0", runtime=self.rt)["status"], "FAIL")
        with self.assertRaises(ToolError):
            proposals.promote("agent_mean", "1.1.0", "owner")
        self.assertEqual(proposals.rollback("agent_mean", "1.0.0", "owner")["active"], "1.0.0")

    def test_validation_blocked_without_container_and_tamper_after_validation_rejected(self):
        self.propose_mean()
        with patch("backend.tools.adapters.Container.probe", return_value={"available": False, "reason": "test"}):
            self.assertEqual(proposals.validate("agent_mean", "1.0.0", runtime=self.rt)["status"], "BLOCKED")
        _env.config.save_config({"tools": {"allow_host_validation": True}})
        with patch("backend.tools.adapters.Container.probe", return_value={"available": False, "reason": "test"}):
            self.assertEqual(proposals.validate("agent_mean", "1.0.0", runtime=self.rt)["status"], "PASS")
        folder = R.tools_root() / "_proposals" / "agent_mean" / "1.0.0"
        (folder / "tool.py").write_text(STATS + "\nimport os\n", "utf-8")
        with self.assertRaises(ToolError):
            proposals.promote("agent_mean", "1.0.0", "owner")

    def test_agent_proposes_and_validates_from_its_loop_without_escalation_or_promotion(self):
        _env.config.save_config({"tools": {"allow_host_validation": True}})
        good = manifest("agent_mean", examples=[{"args": {"values": [2, 4]}, "expect": {"mean": 3.0}}])
        greedy = manifest("agent_net", permissions=["compute", "network"], examples=[{"args": {"values": [1]}, "expect": {}}])
        model = ScriptedModel(act(action="propose_tool", manifest=good, files={"tool.py": STATS}),
                              act(action="validate_tool", tool="agent_mean", version="1.0.0"),
                              act(action="propose_tool", manifest=greedy, files={"tool.py": STATS}),
                              act(action="validate_tool", tool="agent_net", version="1.0.0"),
                              act(action="final", answer="Proposed agent_mean; awaiting promotion."))
        with patch("backend.tools.adapters.Container.probe", return_value={"available": False, "reason": "test"}):
            out = self.run_loop(model, grant=self.grant(permissions=["compute", "workspace_write"]))
        self.assertIn("propose_tool", model.seen[0][0], "proposal protocol offered only to grants that may write")
        observations = [json.loads(m["content"].split("\n", 1)[1]) for m in model.seen[-1][1] if m["content"].startswith("OBSERVATION")]
        self.assertEqual([o.get("status") for o in observations], ["proposed", "PASS", "proposed", "BLOCKED"])
        self.assertEqual(observations[3]["error"]["code"], "permission_denied", "validation cannot exceed the proposer's grant")
        self.assertNotIn("agent_mean", {t["id"] for t in R.REGISTRY.listing()["tools"]}, "agents never promote")
        read_only = ScriptedModel(act(action="propose_tool", manifest=good, files={}), act(action="final", answer="no"))
        out = self.run_loop(read_only, grant=self.grant(permissions=["read"]))
        self.assertEqual(out["steps"][0]["error"], "permission_denied")
        self.assertNotIn("propose_tool", read_only.seen[0][0])

    def test_proposal_rejects_native_reserved_and_path_escape(self):
        for bad, files in ((manifest("x", kind="native"), {}), (manifest("web_search"), {}),
                           (manifest("ok_tool"), {"../escape.py": "x"})):
            with self.assertRaises(ToolError):
                proposals.propose(bad, files)


class ChatAgentMode(Base):
    """MOCKED model inside the REAL orchestrator/session/runtime path."""

    def test_agent_mode_replaces_keyword_preselection_and_keeps_session_allowlist(self):
        from backend.agent import orchestrator, sessions
        s = sessions.create("Agent tools", settings={
            "provider": "app:local", "tool_mode": "agent", "mcp_tools": ["research_get_current_state"],
            "summaries": False, "collect_artifacts": False, "memory_mode": "off"})
        with patch.object(orchestrator, "_spawn"):
            turn = orchestrator.start(s["id"], "tìm trên internet bài mới nhất về pruning")
        replies = iter([act(action="call", tool="research_get_current_state", args={}),
                        act(action="call", tool="web_search", args={"query": "pruning"}),
                        "Read the project state; web search is not permitted in this session."])
        with patch.object(orchestrator.providers, "describe", return_value={"available": True, "label": "x", "state": "ok", "detail": ""}), \
                patch.object(orchestrator, "_model_text", side_effect=lambda *a, **k: (next(replies), "")), \
                patch.object(orchestrator.mcp_policy, "propose", side_effect=AssertionError("keyword tool forcing")) as keyword:
            orchestrator.run(s["id"], turn["id"], "start")
        keyword.assert_not_called()
        saved = sessions.get(s["id"])
        loop = next(x for x in saved["turns"] if x["id"] == turn["id"])["tool_loop"]
        from backend.tools.runtime import RUNTIME
        statuses = [RUNTIME.get(j)["status"] for j in loop["jobs"]]
        self.assertEqual(statuses, ["succeeded", "denied"], "allowlisted tool ran; web_search stayed outside the grant")
        self.assertEqual(loop["status"], "completed")
        self.assertIn("not permitted", saved["messages"][-1]["content"])

    def test_agent_mode_is_the_default_and_legacy_remains_selectable(self):
        # v6.6.2 owner decision: tool_mode defaults to "agent"; "legacy" stays a per-session fallback.
        from backend.agent import policy, sessions
        s = sessions.create("Default", settings={"provider": "app:local"})
        self.assertEqual(policy.values(policy.effective(sessions.get(s["id"])))["tool_mode"], "agent")
        legacy = sessions.create("Legacy", settings={"provider": "app:local", "tool_mode": "legacy"})
        self.assertEqual(policy.values(policy.effective(sessions.get(legacy["id"])))["tool_mode"], "legacy")


class McpRegistryBridge(Base):
    """External agent clients (e.g. Antigravity as MCP client) reach the registry through /mcp JSON-RPC."""

    def rpc(self, method, params=None, meta=None):
        from backend.providers import mcp_server
        return mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}, "mcp-test", meta)

    def call(self, name, args, meta=None):
        res = self.rpc("tools/call", {"name": name, "arguments": args}, meta)["result"]
        return res, res.get("structuredContent") or {}

    def test_external_client_discovers_and_runs_registry_tools_within_owner_permissions(self):
        install("stats_mean")
        install("writer", mutates=True)
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertTrue({"phdlab_tools_search", "phdlab_tools_describe", "phdlab_tools_call"} <= names)
        _, found = self.call("phdlab_tools_search", {"query": "mean statistics"})
        self.assertEqual(found["results"][0]["id"], "stats_mean")
        _, schema = self.call("phdlab_tools_describe", {"tool": "stats_mean"})
        self.assertIn("values", schema["input_schema"]["properties"])
        res, ran = self.call("phdlab_tools_call", {"tool": "stats_mean", "args": {"values": [2, 4]}})
        self.assertEqual((ran["status"], ran["result"]["mean"]), ("succeeded", 3.0))
        self.assertFalse(res.get("isError"))
        self.assertTrue(provenance(ran["job"])[-1]["principal"].startswith("mcp:"))
        res, denied = self.call("phdlab_tools_call", {"tool": "writer", "args": {"values": [1]}})
        self.assertEqual((denied["status"], res.get("isError")), ("denied", True), "MCP clients never mutate by default")
        _, loop = self.call("phdlab_tools_call", {"tool": "phdlab_tools_call", "args": {}})
        self.assertEqual(loop["error"]["code"], "not_found", "meta-tools are not registry entries")

    def test_ephemeral_session_grant_and_owner_switch_keep_the_boundary(self):
        meta = {"grant": {"tools": ["research_get_current_state"], "session_id": "s", "expires": time.time() + 60}}
        listed = {t["name"] for t in self.rpc("tools/list", meta=meta)["result"]["tools"]}
        self.assertEqual(listed, {"research_get_current_state"})
        res, _ = self.call("phdlab_tools_call", {"tool": "research_get_current_state", "args": {}}, meta)
        self.assertTrue(res.get("isError"), "bridge tools are outside a chat session's grant")
        _env.config.save_config({"tools": {"mcp_registry": False}})
        self.assertFalse({"phdlab_tools_search"} & {t["name"] for t in self.rpc("tools/list")["result"]["tools"]})
        self.assertTrue(self.call("phdlab_tools_search", {"query": "x"})[0].get("isError"))


class ToolsApi(Base):
    def test_http_discovery_invocation_job_and_provenance_routes(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        install("stats_mean")
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/tools/search", params={"q": "mean statistics"}).json()["results"][0]["id"], "stats_mean")
            self.assertIn("input_schema", client.get("/api/tools/stats_mean").json())
            ok = client.post("/api/tools/stats_mean/invoke", json={"args": {"values": [4, 8]}, "permissions": ["compute"]})
            self.assertEqual(ok.json()["result"]["mean"], 6.0, ok.text)
            self.assertEqual(client.get(f"/api/tools/jobs/{ok.json()['id']}").json()["status"], "succeeded")
            denied = client.post("/api/tools/stats_mean/invoke", json={"args": {"values": [4]}})
            self.assertEqual(denied.json()["status"], "denied")
            self.assertEqual(client.get("/api/tools/nope").status_code, 404)
            self.assertTrue(client.get("/api/tools/provenance/verify").json()["valid"])


if __name__ == "__main__":
    unittest.main()
