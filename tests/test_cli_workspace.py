"""v4.1 Secure CLI space (Firewall spec §5, M1 exit criteria): session workspaces, path safety, environment allowlist,
fail-closed security profiles, read-only context manifests, time limit + process-tree cleanup, gateway integration."""
import _env  # noqa: F401  (must be first)
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.core import config
from backend.providers import lifecycle as LC
from backend.providers import cli as C, gateway as GS, cli_space as W
from providers.fakes import FAKE, FMT, fake


class Paths(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())

    def test_safe_join_and_traversal(self):
        self.assertEqual(W.safe_path(self.base, "a", "b.txt"), (self.base / "a" / "b.txt").resolve())
        for bad in ("..", "../x", "a/../../x", "C:\\Windows", "/etc/passwd", "\\\\server\\share", "", ".", "a\x00b"):
            with self.assertRaises(W.WorkspaceError, msg=bad):
                W.safe_path(self.base, bad)

    def test_symlink_escape_is_refused(self):
        outside = Path(tempfile.mkdtemp())
        link = self.base / "link"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks need developer mode / admin on Windows")
        with self.assertRaises(W.WorkspaceError):
            W.safe_path(self.base, "link", "x.txt")

    def test_inner_symlink_is_allowed(self):
        (self.base / "real").mkdir()
        try:
            os.symlink(self.base / "real", self.base / "alias", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks need developer mode / admin on Windows")
        self.assertTrue(str(W.safe_path(self.base, "alias", "f")).startswith(str(self.base.resolve())))

    def test_symlink_checks_without_os_symlinks(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        inside = (self.base / "real").resolve()
        real_resolve = Path.resolve

        def fake_resolve(p, *a, **k):
            if p.name == "evil":
                return outside
            if p.name == "alias":
                return inside
            return real_resolve(p, *a, **k)
        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda p: p.name in ("evil", "alias")), \
                mock.patch.object(Path, "resolve", autospec=True, side_effect=fake_resolve):
            with self.assertRaises(W.WorkspaceError):
                W.safe_path(self.base, "evil", "f.txt")  # the file path looks inside, its parent link is not
            self.assertTrue(str(W.safe_path(self.base, "alias", "f")).startswith(str(self.base.resolve())))

    def test_resolved_escape(self):
        with mock.patch.object(Path, "resolve", autospec=True, side_effect=lambda p: Path("Z:/elsewhere") if p.name == "x" else Path(os.path.abspath(p))):
            with self.assertRaises(W.WorkspaceError):
                W.safe_path(self.base, "x")


class Sessions(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("cli-space")
        config.save_config({"gateway": {"cli_space_dir": ""}})

    def test_layout_meta_and_reopen(self):
        s = W.open_session("codex", "gs-0000aaaa", "review")
        for sub in W.SUBDIRS:
            self.assertTrue(Path(s[sub]).is_dir(), sub)
        self.assertEqual(Path(s["cwd"]).name, "workspace")
        root = W.root()
        self.assertEqual(Path(s["dir"]).parent.parent.parent, root)
        self.assertNotEqual(Path(s["cwd"]).resolve(), config.ROOT.resolve())
        meta = json.loads((Path(s["dir"]) / "session.json").read_text("utf-8"))
        self.assertEqual(meta["isolation"]["level"], "os-sandbox")
        (Path(s["dir"]) / "session.json").write_text("{broken", "utf-8")
        s2 = W.open_session("codex", "gs-0000aaaa", "assisted")
        self.assertEqual(s2["meta"]["profile"], "assisted")
        self.assertNotIn("api_key", json.dumps(s2["meta"]).lower())

    def test_invalid_ids_and_forbidden_roots(self):
        with self.assertRaises(W.WorkspaceError):
            W.open_session("Codex!", "gs-1")
        with self.assertRaises(W.WorkspaceError):
            W.open_session("codex", "../x")
        target = W.root() / "codex" / "sessions" / "gs-forbid1"
        with mock.patch.object(W, "_forbidden_roots", return_value=[target.resolve()]):
            with self.assertRaises(W.WorkspaceError):
                W.open_session("codex", "gs-forbid1")

    def test_custom_root(self):
        d = tempfile.mkdtemp()
        config.save_config({"gateway": {"cli_space_dir": d}})
        with self.assertRaises(W.WorkspaceError):
            W.root()
        dedicated = config.data_dir() / 'approved-cli'
        config.save_config({'gateway': {'cli_space_dir': str(dedicated)}})
        self.assertEqual(W.root(), dedicated.resolve())
        config.save_config({"gateway": {"cli_space_dir": ""}})

    def test_context_is_staged_read_only_with_hashes(self):
        s = W.open_session("claude_code", "gs-0000bbbb")
        man = W.stage_context(s, "gw-0123456789", "PROMPT TEXT", {"included_ids": ["HYPE-001"]})
        self.assertEqual(len(man["prompt_sha256"]), 64)
        pf = Path(s["context"]) / "gw-0123456789.prompt.md"
        self.assertFalse(os.stat(pf).st_mode & stat.S_IWRITE)
        with self.assertRaises(PermissionError):
            pf.write_text("overwrite", "utf-8")
        W.stage_context(s, "gw-0123456789", "NEW", {})  # restaging the same request is allowed
        self.assertEqual(pf.read_text("utf-8"), "NEW")
        with self.assertRaises(W.WorkspaceError):
            W.stage_context(s, "../evil", "x", {})

    def test_output_and_redacted_logs(self):
        s = W.open_session("codex", "gs-0000cccc")
        W.write_output(s, "gw-0000000001", "answer", ["token sk-ant-abcdefghijklmnopqrstuvwx leaked"])
        self.assertEqual((Path(s["output"]) / "gw-0000000001.md").read_text("utf-8"), "answer")
        log = (Path(s["logs"]) / "stderr.log").read_text("utf-8")
        self.assertNotIn("abcdefghijklmnopqrstuvwx", log)

    def test_list_and_prune(self):
        W.open_session("gemini_cli", "gs-0000dddd")
        old = W.open_session("gemini_cli", "gs-0000eeee")
        W.stage_context(old, "gw-0000000002", "x", {})
        m = Path(old["dir"]) / "session.json"
        d = json.loads(m.read_text("utf-8"))
        d["updated"] = time.time() - 40 * 86400
        m.write_text(json.dumps(d), "utf-8")
        (W.root() / "gemini_cli" / "sessions" / "gs-bad" ).mkdir(parents=True, exist_ok=True)
        (W.root() / "gemini_cli" / "sessions" / "gs-bad" / "session.json").write_text("{", "utf-8")
        ids = [x["session_id"] for x in W.sessions()]
        self.assertIn("gs-0000dddd", ids)
        self.assertEqual(W.prune(), 0) if W._pruned["t"] > time.time() - 600 else None  # throttled
        self.assertGreaterEqual(W.prune(force=True), 1)
        self.assertFalse(Path(old["dir"]).exists())
        config.save_config({"gateway": {"cli_max_sessions": 1}})
        W.open_session("gemini_cli", "gs-0000ffff")
        W.prune(force=True)
        self.assertLessEqual(len(W.sessions()), 1)
        config.save_config({"gateway": {"cli_max_sessions": 300}})


class Profiles(unittest.TestCase):
    def test_fail_closed(self):
        self.assertTrue(W.check_profile("codex", "assisted")["enforced"])
        with self.assertRaises(W.WorkspaceError):
            W.check_profile("codex", "root-access")
        with self.assertRaises(W.WorkspaceError):
            W.check_profile("gemini_cli", "assisted")  # not supported → refused, never silently weaker
        with self.assertRaises(W.WorkspaceError):
            W.check_profile("claude_code", "assisted")  # weaker → needs consent
        iso = W.check_profile("claude_code", "assisted", allow_weaker=True)
        self.assertTrue(iso["consented_weaker"])
        self.assertEqual(W.isolation("nope", "review")["level"], "none")

    def test_env_allowlist(self):
        base = {"PATH": "p", "SYSTEMROOT": "s", "AWS_SECRET_ACCESS_KEY": "x", "GITHUB_TOKEN": "t", "ANTHROPIC_API_KEY": "a",
                "MY_RANDOM_VAR": "r", "HOME": "h", "APPDATA": "ad"}
        env = W.minimal_env(base=base)
        self.assertEqual(set(env), {"PATH", "SYSTEMROOT", "HOME", "APPDATA", "NO_COLOR"})
        self.assertIn("ANTHROPIC_API_KEY", W.minimal_env({"ANTHROPIC_API_KEY"}, base))

    def test_argv_follows_the_profile(self):
        cx = fake("codex")
        a = C.CodexConnector.argv(cx, {"profile": "assisted"})
        self.assertEqual(a[a.index("--sandbox") + 1], "workspace-write")
        a = C.CodexConnector.argv(cx, {})
        self.assertEqual(a[a.index("--sandbox") + 1], "read-only")
        a = C.CodexConnector.argv(cx, {"profile": "assisted", "resume_session": "th-123456"})
        self.assertIn("sandbox_mode=workspace-write", a)
        cl = fake("claude_code")
        a = C.ClaudeCodeConnector.argv(cl, {})
        self.assertIn("Write", a[a.index("--disallowedTools") + 1])
        a = C.ClaudeCodeConnector.argv(cl, {"profile": "assisted"})
        self.assertEqual(a[a.index("--permission-mode") + 1], "acceptEdits")
        self.assertTrue(C.CodexConnector.supports_resume and C.GeminiCliConnector.supports_resume)
        gm = fake("gemini_cli")
        self.assertIn("--resume", C.GeminiCliConnector.argv(gm, {"resume_session": "session-123456"}))


class Launch(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("cli-launch")


    def test_two_sessions_two_workspaces(self):
        a = W.open_session("codex", "gs-sessA001")
        b = W.open_session("codex", "gs-sessB001")
        self.assertNotEqual(a["cwd"], b["cwd"])
        self.assertNotEqual(a["logs"], b["logs"])

    def test_foreign_cwd_is_refused(self):
        with self.assertRaises(C.ProviderError):
            list(fake("codex").stream_message("q", {"cwd": tempfile.mkdtemp()}))

    def test_unsupported_profile_is_refused_before_launch(self):
        with self.assertRaises(C.ProviderError):
            list(fake("gemini_cli").stream_message("q", {"profile": "assisted"}))

    def test_time_limit_kills_the_process_tree(self):
        evs = list(fake("gemini_cli", "slow").stream_message("q", {"timeout_s": 1}))
        err = [e for e in evs if e["type"] == "error"]
        self.assertTrue(err and "time limit" in err[0]["message"])
        self.assertEqual(evs[-1]["type"], "request_completed")
        self.assertEqual(C._procs, {})

    def test_consumer_abort_kills_the_process(self):
        gen = fake("gemini_cli", "slow").stream_message("q", {"request_id": "req-abort0001"})
        next(gen)  # request_started
        proc = C._procs["req-abort0001"]
        gen.close()  # client went away
        self.assertIsNotNone(proc.poll())
        self.assertNotIn("req-abort0001", C._procs)
        C.kill_tree(proc)  # already dead: no error


class GatewayIntegration(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("cli-gw")
        LC.reset()
        config.save_config({"gateway": {"cli_profile": "review"}, "lifecycle": {"cli": "idle_unload"}})

    def tearDown(self):
        LC.reset()

    def _fake_conn(self, pid="claude_code"):
        f = fake(pid)
        return mock.patch.dict(C.CONNECTORS, {pid: f})

    def test_prepare_refuses_weaker_profile_without_consent(self):
        with self._fake_conn():
            with self.assertRaises(GS.GatewayError):
                GS.prepare("question", "claude_code", profile="assisted")
            r = GS.prepare("question", "claude_code", profile="assisted", allow_weaker=True)
        self.assertTrue(r["isolation"]["consented_weaker"])




if __name__ == "__main__":
    unittest.main()
