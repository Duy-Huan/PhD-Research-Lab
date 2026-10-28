"""FQC-COVERAGE-662: settings load/save rules and the project list, on the real config file of a throw-away data folder.

Covers value coercion, section validation (Hermes, tool pool and profiles, MCP agent), recovery from damaged or legacy
settings files, secret masking, and project registration (open, activate, rename, forget).
"""
import json
import tempfile
import unittest
from pathlib import Path

import _env  # noqa: F401
from backend.core import config as C


class Coercion(unittest.TestCase):
    def test_values_take_the_type_of_their_default(self):
        self.assertIs(C._coerce(False, "yes"), True)
        self.assertIs(C._coerce(True, "off"), False)
        self.assertEqual(C._coerce(3, "7.9"), 7)
        self.assertEqual(C._coerce(3, "-2"), 0)
        self.assertEqual(C._coerce(3, "many"), 3)
        self.assertEqual(C._coerce(1.5, "-1"), 0.0)
        self.assertEqual(C._coerce({"a": 1}, [1]), {"a": 1})
        self.assertEqual(C._coerce({}, {"b": 2}), {"b": 2})
        self.assertEqual(C._coerce([1], "x"), [1])
        self.assertEqual(C._coerce([], (1, 2)), [])
        self.assertEqual(C._coerce("", None), "")
        self.assertEqual(len(C._coerce("", "x" * 3000)), 2000)
        self.assertFalse(C._valid_mode(5))
        self.assertTrue(C._valid_mode("runtime:hermes"))

    def test_masking_hides_secrets_but_reports_presence(self):
        self.assertEqual(C.mask(""), "")
        self.assertEqual(C.mask("short"), "•" * 8)
        self.assertEqual(C.mask("sk-abcdefghijklmnop"), "sk-abc" + "•" * 8 + "mnop")


class SaveAndLoad(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)

    def write_raw(self, payload):
        C.CONFIG_PATH.write_text(payload if isinstance(payload, str) else json.dumps(payload), "utf-8")

    def test_hermes_limits_are_clamped_and_zero_means_no_limit(self):
        cfg = C.save_config({"hermes": {"deadline_s": 1, "max_iterations": 999, "max_tokens": 0, "model": "nous/hermes-4"}})
        self.assertEqual((cfg["hermes"]["deadline_s"], cfg["hermes"]["max_iterations"], cfg["hermes"]["max_tokens"]),
                         (5, 50, 0))
        self.assertTrue(cfg["hermes"]["free_only"])
        with self.assertRaisesRegex(ValueError, "Invalid Hermes model"):
            C.save_config({"hermes": {"model": "bad model; rm"}})

    def test_invalid_tool_settings_are_refused_on_save_and_reset_on_load(self):
        with self.assertRaises(ValueError):
            C.save_config({"tools": {"provider_pool": ["antigravity"]}})
        with self.assertRaises(ValueError):
            C.save_config({"tools": {"agent_profile": {"permissions": ["root"]}}})
        cfg = C.save_config({"tools": {"pool_cooldown_s": 5}})
        self.assertEqual(cfg["tools"]["pool_cooldown_s"], 60)
        raw = json.loads(C.CONFIG_PATH.read_text("utf-8"))
        raw["tools"].update(provider_pool=["antigravity"], agent_profile={"permissions": ["root"]})
        self.write_raw(raw)
        loaded = C.load_config()["tools"]
        self.assertEqual(loaded["provider_pool"], [], "a damaged saved pool disables failover instead of breaking startup")
        self.assertEqual(loaded["agent_profile"], C.DEFAULTS["tools"]["agent_profile"])

    def test_mcp_agent_validation_and_recovery(self):
        with self.assertRaisesRegex(ValueError, "valid name"):
            C.save_config({"mcp_agent": {"tool": "bad name!"}})
        with self.assertRaisesRegex(ValueError, "at most 500"):
            C.save_config({"mcp_agent": {"models": [" "]}})
        cfg = C.save_config({"mcp_agent": {"models": ["a", " a ", "b"], "timeout_s": 9999}})
        self.assertEqual((cfg["mcp_agent"]["models"], cfg["mcp_agent"]["timeout_s"]), (["a", "b"], 600))
        raw = json.loads(C.CONFIG_PATH.read_text("utf-8"))
        raw["mcp_agent"]["tool"] = "bad name!"
        self.write_raw(raw)
        self.assertEqual(C.load_config()["mcp_agent"], C.DEFAULTS["mcp_agent"], "a malformed optional adapter is disabled")

    def test_damaged_settings_are_quarantined_and_defaults_used(self):
        for payload in ("{not json", "[1, 2]"):
            with self.subTest(payload):
                self.write_raw(payload)
                before = set(C.CONFIG_PATH.parent.glob(C.CONFIG_PATH.name + ".corrupt-*"))
                cfg = C.load_config()
                self.assertEqual(cfg["default_cloud"], C.DEFAULTS["default_cloud"])
                copies = set(C.CONFIG_PATH.parent.glob(C.CONFIG_PATH.name + ".corrupt-*"))
                self.assertTrue(copies, "a copy of the unreadable file is kept before defaults are used")
                for copy in copies - before:
                    copy.unlink()

    def test_legacy_settings_are_migrated_read_only(self):
        self.write_raw({"claude_model": "claude-old"})
        self.assertEqual(C.load_config()["providers"]["anthropic"]["model"], "claude-old", "v1.0 model without providers")
        self.write_raw({"anthropic_api_key": "sk-legacy-key-123456", "claude_model": "ignored", "default_cloud": "nope",
                        "agent_modes": {"assistant": "not-a-mode"}, "agent_models": {"assistant": "m1", "ghost": "x"},
                        "providers": {"openai": {"model": "gpt", "api_key": "k"}, "ghost": {}},
                        "research_providers": {"engine_mode": "feynman", "engine_priority": ["feynman"]},
                        "search": {"n_results": 4, "unknown": 1}, "openscience": {"token": "keep"}})
        cfg = C.load_config()
        self.assertEqual(cfg["providers"]["anthropic"]["api_key"], "sk-legacy-key-123456")
        self.assertNotEqual(cfg["providers"]["anthropic"]["model"], "ignored", "v1.1 providers win over the v1.0 model")
        self.assertEqual(cfg["default_cloud"], "anthropic")
        self.assertEqual(cfg["agent_models"]["assistant"], "m1")
        self.assertNotIn("ghost", cfg["agent_models"])
        self.assertEqual(cfg["search"]["n_results"], 4)
        C.save_config({"latex_online": True})
        self.assertEqual(json.loads(C.CONFIG_PATH.read_text("utf-8"))["openscience"], {"token": "keep"},
                         "retired settings stay on disk as opaque history")
        with self.assertRaises(ValueError):
            C.save_config({"openscience": {}})

    def test_save_applies_each_kind_of_setting(self):
        agent = next(iter(C.AGENTS))
        cfg = C.save_config({"agent_modes": {agent: "local"}, "agent_models": {agent: " m2 "},
                             "providers": {"openai": {"model": " gpt-x ", "api_key": " sk-new "}, "ghost": {}, "anthropic": "bad"},
                             "default_cloud": "openai", "lmstudio_base_url": "http://127.0.0.1:1234",
                             "search": {"web_engine": "unknown", "n_results": "x", "read_pages": 1, "mailto": " me@x.org "},
                             "memory": {"keep_recent_turns": 0}})
        self.assertEqual((cfg["agent_modes"][agent], cfg["agent_models"][agent]), ("local", "m2"))
        self.assertEqual((cfg["providers"]["openai"]["model"], cfg["providers"]["openai"]["api_key"]), ("gpt-x", "sk-new"))
        self.assertEqual((cfg["default_cloud"], cfg["lmstudio_base_url"]), ("openai", "http://127.0.0.1:1234"))
        self.assertEqual((cfg["search"]["web_engine"], cfg["search"]["read_pages"], cfg["search"]["mailto"]),
                         ("duckduckgo", True, "me@x.org"))
        self.assertEqual(cfg["memory"]["keep_recent_turns"], 1)
        cfg = C.save_config({"providers": {"openai": {"api_key": "sk-ne••••"}}, "agent_models": {agent: ""}})
        self.assertEqual(cfg["providers"]["openai"]["api_key"], "sk-new", "a masked key leaves the stored key unchanged")
        self.assertNotIn(agent, cfg["agent_models"])
        public = C.public_config(cfg)
        self.assertTrue(public["providers"]["openai"]["has_key"])
        self.assertNotIn("sk-new", json.dumps(public))
        self.assertEqual(public["version"], C.APP_VERSION)


class Projects(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="phdlab-projects-"))
        self.addCleanup(lambda: C.activate_project(str(C.GLOBAL_DIR)))

    def test_open_activate_rename_and_forget(self):
        with self.assertRaises(ValueError):
            C.create_project("  ")
        with self.assertRaises(FileNotFoundError):
            C.open_project(str(self.tmp / "missing"))
        with self.assertRaises(FileNotFoundError):
            C.activate_project(str(self.tmp / "missing"))
        folder = self.tmp / "copied"
        folder.mkdir()
        info = C.open_project(str(folder))
        self.assertEqual(Path(C.active_project()["data_dir"]), folder.resolve())
        self.assertEqual(C.rename_project(info["data_dir"], "Renamed")["name"], "Renamed")
        listed = {Path(p["data_dir"]): p for p in C.list_projects()}
        self.assertTrue(listed[folder.resolve()]["active"])
        self.assertTrue(listed[C.GLOBAL_DIR.resolve()]["is_default"])
        refs = self.tmp / "refs"
        C.save_config({"references_dir": str(refs)})
        self.assertEqual(Path(C.active_project()["references_dir"]), refs.resolve())
        C.forget_project(info["data_dir"])
        self.assertEqual(Path(C.active_project()["data_dir"]), C.GLOBAL_DIR.resolve(), "forgetting the active project reopens the default")
        self.assertTrue(folder.is_dir(), "files on disk are never deleted")
        with self.assertRaises(ValueError):
            C.forget_project(str(C.GLOBAL_DIR))

    def test_scoped_operations_keep_their_project_and_missing_active_falls_back(self):
        folder = self.tmp / "scoped"
        C.create_project("Scoped", str(folder))
        C.activate_project(str(C.GLOBAL_DIR))
        with C.project_scope(folder):
            self.assertEqual(C.data_dir(), folder.resolve())
            self.assertEqual(Path(C.active_project()["data_dir"]), folder.resolve())
        self.assertTrue(C.workspace().is_dir())
        self.assertTrue(C.refs_dir().is_dir())
        raw = json.loads(C.CONFIG_PATH.read_text("utf-8"))
        raw["active_project"] = str(self.tmp / "deleted")
        C.CONFIG_PATH.write_text(json.dumps(raw), "utf-8")
        self.assertEqual(Path(C.active_project()["data_dir"]), C.GLOBAL_DIR.resolve())


if __name__ == "__main__":
    unittest.main()
