"""FQC-CLAUDE-SIGNIN-663: the container's Claude Code uses the researcher's existing Claude subscription sign-in.

Live finding (2026-10-28): readiness said CONNECTED from the host's `claude auth status`, but the container home had no
credentials, so every CLI turn failed with "Not logged in". The fix seeds the host's current access token, without the
refresh token (the container can never rotate, and so sign out, the host's sign-in), and readiness reports CONNECTED
only when the container can actually sign in."""
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _env
from backend.core import config
from backend.providers import cli as C
from backend.providers import cli_space as W
from backend.providers import isolated_cli as I

HOST = {"claudeAiOauth": {"accessToken": "sk-ant-oat01-test", "refreshToken": "sk-ant-ort01-secret",
                          "expiresAt": 0, "refreshTokenExpiresAt": 0, "scopes": ["user:inference"],
                          "subscriptionType": "max"}, "organizationUuid": "org-test"}


class ClaudeSignIn(unittest.TestCase):
    def setUp(self):
        self.config = Path(tempfile.mkdtemp(prefix="claude-config-"))
        self.home = W.safe_path(W.root(), "claude_code", "runtime-home")  # the home readiness inspects (test data dir)
        shutil.rmtree(self.home, ignore_errors=True)
        self.home.mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def host(self, expires_in_s: float = 3600, **oauth):
        data = json.loads(json.dumps(HOST))
        data["claudeAiOauth"].update(expiresAt=int((time.time() + expires_in_s) * 1000), **oauth)
        path = self.config / ".credentials.json"
        path.write_text(json.dumps(data), "utf-8")
        return path

    def seeded(self):
        return json.loads((self.home / ".claude" / ".credentials.json").read_text("utf-8"))

    def test_seed_copies_the_access_token_without_the_refresh_token(self):
        host = self.host()
        before = host.read_bytes()
        self.assertTrue(I.seed_claude_sign_in(self.home))
        oauth = self.seeded()["claudeAiOauth"]
        self.assertEqual(oauth["accessToken"], "sk-ant-oat01-test")
        self.assertNotIn("refreshToken", oauth)
        self.assertNotIn("refreshTokenExpiresAt", oauth)
        self.assertEqual(host.read_bytes(), before, "the host sign-in is never modified")

    def test_seed_follows_the_hosts_current_token(self):
        self.host()
        I.seed_claude_sign_in(self.home)
        self.host(accessToken="sk-ant-oat01-renewed")
        I.seed_claude_sign_in(self.home)
        self.assertEqual(self.seeded()["claudeAiOauth"]["accessToken"], "sk-ant-oat01-renewed")

    def test_unchanged_token_is_not_rewritten(self):
        self.host()
        I.seed_claude_sign_in(self.home)
        target = self.home / ".claude" / ".credentials.json"
        os.utime(target, (1, 1))
        I.seed_claude_sign_in(self.home)
        self.assertEqual(target.stat().st_mtime, 1)

    def test_a_sign_in_made_inside_the_runtime_is_kept(self):
        self.host()
        own = {"claudeAiOauth": {"accessToken": "sk-ant-oat01-own", "refreshToken": "sk-ant-ort01-own"}}
        target = self.home / ".claude" / ".credentials.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(own), "utf-8")
        I.seed_claude_sign_in(self.home)
        self.assertEqual(self.seeded(), own)
        self.assertEqual(self.state()[0], "CONNECTED", "readiness counts the runtime's own sign-in")

    def test_missing_or_malformed_host_sign_in_seeds_nothing(self):
        self.assertFalse(I.seed_claude_sign_in(self.home))
        for text in ("not json", "[]", json.dumps({"claudeAiOauth": {"refreshToken": "x"}})):
            (self.config / ".credentials.json").write_text(text, "utf-8")
            with self.subTest(text=text):
                self.assertFalse(I.seed_claude_sign_in(self.home))
        self.assertFalse((self.home / ".claude" / ".credentials.json").exists())

    def test_prepare_seeds_the_container_home(self):
        self.host()
        with mock.patch.object(I, "docker", lambda *a, **k: json.dumps([{"Id": "sha256:" + "a" * 64, "Config": {"Labels": {
                "phdlab.cli.provider": "claude_code", "phdlab.cli.version": I.RUNTIMES["claude_code"][1],
                "phdlab.cli.adapter.sha256": I.adapter_digest()}}}])):
            plan = json.loads(Path(I.prepare("claude_code", session_id="s-claude")["plan"]).read_text("utf-8"))
        oauth = json.loads(Path(plan["home"], ".claude", ".credentials.json").read_text("utf-8"))["claudeAiOauth"]
        self.assertEqual(oauth["accessToken"], "sk-ant-oat01-test")
        self.assertNotIn("refreshToken", oauth)

    def state(self, logged_in=True):
        probe = {"ok": True, "bin": "claude", "auth_code": 0,
                 "auth": {"loggedIn": logged_in, "authMethod": "claude.ai", "apiProvider": "firstParty"}}
        with mock.patch.object(C, "run_cli", side_effect=AssertionError("readiness must not start the CLI")):
            return C.ClaudeCodeConnector().auth_state(probe)

    def test_connected_only_when_the_container_can_sign_in(self):
        self.host()
        self.assertEqual(self.state()[0], "CONNECTED")
        self.host(expires_in_s=-60)
        state, detail = self.state()
        self.assertEqual(state, "AUTH_EXPIRED")
        self.assertIn("Claude Code", detail)
        (self.config / ".credentials.json").unlink()
        state, detail = self.state()
        self.assertEqual(state, "AUTH_EXPIRED", "a host sign-in that cannot be shared (e.g. a keychain) is not CONNECTED")
        self.assertIn("/login", detail)


LONG = "sk-ant-oat01-" + "L" * 90


class LongLivedToken(unittest.TestCase):
    """A `claude setup-token` token (about a year) keeps the container signed in without the host's short token."""

    def setUp(self):
        _env.isolate_config(self)
        self.config = Path(tempfile.mkdtemp(prefix="claude-config-"))
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.image = lambda *a, **k: json.dumps([{"Id": "sha256:" + "a" * 64, "Config": {"Labels": {
            "phdlab.cli.provider": "claude_code", "phdlab.cli.version": I.RUNTIMES["claude_code"][1],
            "phdlab.cli.adapter.sha256": I.adapter_digest()}}}]) if a[:2] == ("image", "inspect") else ("c" * 64 if a[0] == "run" else "")

    def test_the_token_is_stored_as_a_secret_and_validated(self):
        config.save_config({"gateway": {"claude_code_oauth_token": f"  {LONG}  "}})
        self.assertEqual(config.load_config()["gateway"]["claude_code_oauth_token"], LONG)
        public = config.public_config(config.load_config())["gateway"]
        self.assertTrue(public["has_claude_code_oauth_token"])
        self.assertNotIn("L" * 20, json.dumps(public))
        config.save_config({"gateway": {"claude_code_oauth_token": public["claude_code_oauth_token"]}})
        self.assertEqual(config.load_config()["gateway"]["claude_code_oauth_token"], LONG, "a masked value keeps the stored token")
        for bad in ("sk-ant-api03-" + "x" * 40, "sk-ant-oat01-ab\nc" + "x" * 40, "hello"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config.save_config({"gateway": {"claude_code_oauth_token": bad}})
        config.save_config({"gateway": {"claude_code_oauth_token": ""}})
        self.assertEqual(config.load_config()["gateway"]["claude_code_oauth_token"], "", "the token can be removed")

    def test_the_container_receives_the_token_through_a_removed_env_file(self):
        config.save_config({"gateway": {"claude_code_oauth_token": LONG}})
        seen = {}

        def call(args, timeout=None):
            path = Path(args[args.index("--env-file") + 1])
            seen.update(args=args, path=path, text=path.read_text("utf-8"))
            return 0

        with mock.patch.object(I, "docker", self.image):
            plan = Path(I.prepare("claude_code", session_id="s-long")["plan"])
            with mock.patch.object(I.subprocess, "call", side_effect=call), \
                    mock.patch.object(I.subprocess, "run", return_value=mock.Mock(stdout="", stderr="")):
                I.run(plan, interactive=False, command=["claude", "-p", "hi"], runtime_owner="a" * 32)
        self.assertEqual(seen["text"], f"CLAUDE_CODE_OAUTH_TOKEN={LONG}\n")
        self.assertNotIn(LONG, " ".join(seen["args"]), "never on the command line")
        self.assertNotIn(LONG, plan.read_text("utf-8"), "never in the plan file")
        self.assertFalse(seen["path"].exists(), "the env file is removed after the run")
        self.assertFalse(Path(json.loads(plan.read_text("utf-8"))["home"], ".claude", ".credentials.json").exists(),
                         "the host's short token is not seeded when a long-lived token is set")

    def test_the_launcher_process_gets_the_token_from_its_parent_not_from_config(self):
        # Live finding: turns run run() in tools/run_cli_container.py, started with a minimal environment that has no
        # PHDLAB_DATA_DIR, so reading the configuration there found no token and Claude said "Not logged in".
        config.save_config({"gateway": {"claude_code_oauth_token": LONG}})
        env = C.ClaudeCodeConnector().env()
        self.assertEqual(env.get("CLAUDE_CODE_OAUTH_TOKEN"), LONG, "the launcher process inherits the token")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", C.CodexConnector().env())
        with mock.patch.object(I, "docker", self.image):
            plan = Path(I.prepare("claude_code", session_id="s-child")["plan"])
        config.save_config({"gateway": {"claude_code_oauth_token": ""}})  # what the child process sees
        seen = {}

        def call(args, timeout=None):
            seen["text"] = Path(args[args.index("--env-file") + 1]).read_text("utf-8")
            return 0

        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": LONG}), mock.patch.object(I, "docker", self.image), \
                mock.patch.object(I.subprocess, "call", side_effect=call), \
                mock.patch.object(I.subprocess, "run", return_value=mock.Mock(stdout="", stderr="")):
            I.run(plan, interactive=False, command=["claude", "-p", "hi"], runtime_owner="d" * 32)
        self.assertEqual(seen.get("text"), f"CLAUDE_CODE_OAUTH_TOKEN={LONG}\n")
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x\nINJECT=1"}), \
                mock.patch.object(I, "docker", self.image), mock.patch.object(I.subprocess, "call", return_value=0) as bad, \
                mock.patch.object(I.subprocess, "run", return_value=mock.Mock(stdout="", stderr="")):
            I.run(plan, interactive=False, command=["claude", "-p", "hi"], runtime_owner="e" * 32)
        self.assertNotIn("--env-file", bad.call_args.args[0], "a malformed inherited token is ignored")

    def test_codex_runs_never_receive_the_claude_token(self):
        config.save_config({"gateway": {"claude_code_oauth_token": LONG}})
        image = lambda *a, **k: json.dumps([{"Id": "sha256:" + "a" * 64, "Config": {"Labels": {
            "phdlab.cli.provider": "codex", "phdlab.cli.version": I.RUNTIMES["codex"][1],
            "phdlab.cli.adapter.sha256": I.adapter_digest()}}}]) if a[:2] == ("image", "inspect") else ("c" * 64 if a[0] == "run" else "")
        with mock.patch.object(I, "docker", image):
            plan = Path(I.prepare("codex", session_id="s-codex")["plan"])
            with mock.patch.object(I.subprocess, "call", return_value=0) as call, \
                    mock.patch.object(I.subprocess, "run", return_value=mock.Mock(stdout="", stderr="")):
                I.run(plan, interactive=False, command=["codex", "exec", "hi"], runtime_owner="b" * 32)
        self.assertNotIn("--env-file", call.call_args.args[0])

    def test_readiness_is_connected_with_a_long_lived_token(self):
        config.save_config({"gateway": {"claude_code_oauth_token": LONG}})
        probe = {"ok": True, "bin": "claude", "auth_code": 0, "auth": {"loggedIn": False}}
        state, detail = C.ClaudeCodeConnector().auth_state(probe)
        self.assertEqual(state, "CONNECTED")
        self.assertIn("long-lived", detail)


if __name__ == "__main__":
    unittest.main()
