"""FQC-COVERAGE-662: project-owned isolated CLI containers (plan preparation, launch policy, owned cleanup).

Docker is replaced by a recording fake so every policy branch is exercised without a daemon; the real container
launch is covered separately by the live CLI sandbox checks.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _env  # noqa: F401
from backend.core import config
from backend.providers import cli_space as W
from backend.providers import isolated_cli as I

IMAGE = "sha256:" + "a" * 64
PROXY = "b" * 64


def image(provider, **override):
    labels = {"phdlab.cli.provider": provider, "phdlab.cli.version": I.RUNTIMES[provider][1],
              "phdlab.cli.adapter.sha256": I.adapter_digest()}
    return {"Id": IMAGE, "Config": {"Labels": {**labels, **override}}}


class FakeDocker:
    def __init__(self, provider="codex", proxy=PROXY, leftovers=""):
        self.provider, self.proxy, self.leftovers, self.calls = provider, proxy, leftovers, []

    def __call__(self, *args, timeout=20):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            return json.dumps([image(self.provider)])
        if args[0] == "run":
            return self.proxy
        if args[:2] == ("ps", "-aq"):
            return self.leftovers
        return ""


class IsolatedCli(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.fake = FakeDocker()
        patcher = mock.patch.object(I, "docker", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_runtime_status_reports_identity_bound_images_only(self):
        self.assertEqual(I.runtime_status("antigravity")["state"], "UNSUPPORTED")
        self.assertEqual(I.runtime_status("unknown")["state"], "BLOCKED")
        self.assertEqual(I.runtime_status("codex"), {"state": "PREPARED", "verified": True, "image": IMAGE,
                                                     "detail": mock.ANY})
        with mock.patch.object(I, "docker", lambda *a, **k: json.dumps([image("codex", **{"phdlab.cli.version": "0"})])):
            self.assertEqual(I.runtime_status("codex")["state"], "BLOCKED")
        with mock.patch.object(I, "docker", side_effect=subprocess.CalledProcessError(1, "docker")):
            self.assertFalse(I.runtime_status("codex")["verified"])

    def test_prepare_refuses_unprepared_or_unknown_runtimes(self):
        self.assertFalse(I.prepare("antigravity")["launched"])
        self.assertEqual(I.prepare("unknown")["state"], "BLOCKED")
        with mock.patch.object(I, "docker", side_effect=OSError("no docker")):
            self.assertIn("prepare_cli_sandbox.py --provider codex", I.prepare("codex")["detail"])

    def test_prepare_writes_a_server_authored_plan_per_provider(self):
        with tempfile.TemporaryDirectory() as codex_home:
            Path(codex_home, "auth.json").write_text("{}", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CODEX_HOME": codex_home}):
                out = I.prepare("codex", login=True, session_id="s-codex")
        plan = json.loads(Path(out["plan"]).read_text(encoding="utf-8"))
        self.assertEqual((out["state"], plan["command"], plan["image"]), ("PREPARED", ["codex", "login", "--device-auth"], IMAGE))
        self.assertTrue(Path(plan["home"], ".codex", "auth.json").is_file(), "only this vendor's sign-in is seeded")
        self.assertTrue(Path(out["cwd"], "AGENTS.md").is_file())

        self.fake.provider = "claude_code"
        plan = json.loads(Path(I.prepare("claude_code", login=True, session_id="s-claude")["plan"]).read_text(encoding="utf-8"))
        self.assertEqual(plan["command"], ["claude", "auth", "login", "--claudeai"])
        settings = json.loads(Path(plan["home"], ".claude", "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings, {"forceLoginMethod": "claudeai"})

        self.fake.provider = "gemini_cli"
        out = I.prepare("gemini_cli", session_id="s-gemini", mcp={"url": "http://127.0.0.1:8765/mcp", "token": "t"})
        plan = json.loads(Path(out["plan"]).read_text(encoding="utf-8"))
        self.assertEqual(plan["mcp"], {"port": 8765, "token": "t"})
        mcp_settings = json.loads(Path(out["cwd"], ".gemini", "settings.json").read_text(encoding="utf-8"))
        self.assertIn("phdlab", mcp_settings["mcpServers"])
        for url in ("https://127.0.0.1/mcp", "http://example.com/mcp", "http://127.0.0.1/other", "http://u@127.0.0.1/mcp"):
            with self.subTest(url), self.assertRaises(W.WorkspaceError):
                I.prepare("gemini_cli", session_id="s-bad", mcp={"url": url, "token": "t"})

    def prepared(self, **plan_override):
        out = I.prepare("codex", session_id="s-run")
        path = Path(out["plan"])
        plan = {**json.loads(path.read_text(encoding="utf-8")), **plan_override}
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path

    def test_run_launches_an_offline_container_behind_the_proxy_and_cleans_up(self):
        path = self.prepared(profile="review", mcp={"port": 8765, "token": "tok"}, timeout_s=30)
        with mock.patch.object(I.subprocess, "call", return_value=0) as call, \
                mock.patch.object(I.subprocess, "run", return_value=mock.Mock(stdout="log", stderr="")):
            self.assertEqual(I.run(path, interactive=False, command=["codex", "exec", "hi"], runtime_owner="c" * 32), 0)
        args = call.call_args.args[0]
        self.assertIn("--network=none", args)
        self.assertTrue(any(a.endswith(",readonly") and "target=/workspace" in a for a in args), "review profile is read-only")
        self.assertEqual(args[-3:], ["codex", "exec", "hi"])
        self.assertEqual(call.call_args.kwargs["timeout"], 30)
        self.assertEqual((path.parent / ".env.proxy").read_text(encoding="utf-8"), "PHDLAB_MCP_PORT=8765\nPHDLAB_MCP_TOKEN=tok\n")
        self.assertEqual((path.parent / "egress-proxy.log").read_text(encoding="utf-8"), "log")
        self.assertIn(("volume", "create", "--label", "phdlab.cli=" + "c" * 32, "phdlab-cli-ipc-" + "c" * 32), self.fake.calls)

    def test_run_refuses_plans_that_break_the_launch_policy(self):
        project = Path(config.data_dir()).resolve()
        cases = {
            "outside": None,
            "mount": {"workspace": str(project)},
            "domains": {"domains": ["evil.example"]},
            "image": {"image": "sha256:" + "f" * 64},
        }
        for name, override in cases.items():
            with self.subTest(name), self.assertRaises(W.WorkspaceError):
                if override is None:
                    with tempfile.TemporaryDirectory() as tmp:
                        outside = Path(tmp) / "plan.json"
                        outside.write_text(self.prepared().read_text(encoding="utf-8"), encoding="utf-8")
                        I.run(outside)
                else:
                    I.run(self.prepared(**override))
        with self.assertRaisesRegex(W.WorkspaceError, "Invalid CLI runtime owner"):
            I.run(self.prepared(), runtime_owner="not-hex")
        with mock.patch.object(I.subprocess, "run"), self.assertRaisesRegex(W.WorkspaceError, "Invalid MCP token"):
            I.run(self.prepared(mcp={"port": 1, "token": "a\nb"}), runtime_owner="d" * 32)
        self.fake.proxy = "not-a-container"
        with mock.patch.object(I.subprocess, "run"), self.assertRaisesRegex(W.WorkspaceError, "Unexpected sidecar identity"):
            I.run(self.prepared(), runtime_owner="e" * 32)

    def test_interactive_runs_have_no_timeout_and_a_tty(self):
        path = self.prepared()
        with mock.patch.object(I.subprocess, "call", return_value=7) as call, \
                mock.patch.object(I.subprocess, "run", side_effect=OSError("logs unavailable")):
            with self.assertRaises(OSError):  # cleanup still runs and its own failure surfaces
                I.run(path, runtime_owner="f" * 32)
        self.assertIn("-it", call.call_args.args[0])
        self.assertIsNone(call.call_args.kwargs["timeout"])

    def test_cleanup_removes_only_owned_resources(self):
        with self.assertRaises(ValueError):
            I.cleanup_owned_runtime("bad")
        owner = "1" * 32
        self.fake.leftovers = "abcdef123456"
        with mock.patch.object(I.subprocess, "run") as run:
            with self.assertRaisesRegex(W.WorkspaceError, "did not complete"):
                I.cleanup_owned_runtime(owner)
        self.assertEqual(run.call_args_list[0].args[0], ["docker", "rm", "-f", "abcdef123456"])
        self.fake.leftovers = "a\nb\nc"
        with self.assertRaisesRegex(W.WorkspaceError, "resource count"):
            I.cleanup_owned_runtime(owner)
        self.fake.leftovers = "NOT-HEX"
        with self.assertRaisesRegex(W.WorkspaceError, "container identity"):
            I.cleanup_owned_runtime(owner)
        self.fake.leftovers = ""
        with mock.patch.object(I.subprocess, "run"):
            I.cleanup_owned_runtime(owner)


if __name__ == "__main__":
    unittest.main()
