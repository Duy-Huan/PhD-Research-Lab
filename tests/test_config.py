import _env  # noqa: F401  (must be first)
import json
import unittest

from backend import config as C


class ConfigV32(unittest.TestCase):
    def test_data_dir_is_isolated(self):
        self.assertNotEqual(C.GLOBAL_DIR.resolve(), (_env.ROOT / "data").resolve())

    def test_new_sections_have_defaults(self):
        cfg = C.load_config()
        for sec in C.SECTIONS_V32:
            self.assertIn(sec, cfg)
        self.assertEqual(cfg["memory"]["high_watermark_tokens"], 16000)
        self.assertEqual(cfg["memory"]["low_watermark_tokens"], 2000)
        self.assertEqual(cfg["memory"]["chunk_tokens"], 3500)
        self.assertEqual(cfg["codex"]["sandbox"], "read-only")
        self.assertTrue(C.DEFAULTS["clearml"]["enabled"])
        self.assertEqual(cfg["clearml"]["mode"], "offline")  # ClearML through the Python SDK, no server needed
        self.assertTrue(C.DEFAULTS["clearml"]["auto_record"])
        self.assertTrue(C.DEFAULTS["codex"]["enabled"])
        self.assertEqual(cfg["codex"]["windows_sandbox"], "unelevated")
        self.assertTrue(cfg["resources"]["require_unload"])  # GPU runs refused while LLMs hold VRAM
        self.assertNotIn("jit_unload", cfg["resources"])  # no automatic unloading

    def test_coercion_and_choices(self):
        cfg = C.save_config({"memory": {"high_watermark_tokens": "12000", "unknown_key": 5, "embed_engine": "bogus"},
                             "codex": {"sandbox": "danger-full-access"}, "resources": {"require_unload": "false"},
                             "clearml": {"mode": "cloud-magic"}})
        self.assertEqual(cfg["memory"]["high_watermark_tokens"], 12000)
        self.assertNotIn("unknown_key", cfg["memory"])
        self.assertEqual(cfg["memory"]["embed_engine"], "auto")
        self.assertEqual(cfg["codex"]["sandbox"], "read-only")  # never danger-full-access
        self.assertEqual(cfg["clearml"]["mode"], "offline")
        self.assertFalse(cfg["resources"]["require_unload"])
        C.save_config({"memory": {"high_watermark_tokens": 16000}, "resources": {"require_unload": True}})

    def test_secret_masking_and_masked_value_keeps_secret(self):
        C.save_config({"clearml": {"access_key": "AK1234567890XYZ", "secret_key": "SECRETSECRET123456"}})
        pub = C.public_config(C.load_config())
        self.assertNotIn("SECRETSECRET123456", json.dumps(pub))
        self.assertTrue(pub["clearml"]["has_secret_key"])
        C.save_config({"clearml": {"secret_key": pub["clearml"]["secret_key"]}})  # masked echo from the UI
        self.assertEqual(C.load_config()["clearml"]["secret_key"], "SECRETSECRET123456")
        C.save_config({"clearml": {"access_key": "", "secret_key": ""}})

    def test_auto_mode_and_new_providers(self):
        self.assertTrue(C._valid_mode("auto"))
        for pid in ("deepinfra", "ninerouter", "omniroute"):
            self.assertIn(pid, C.PROVIDERS)
        self.assertTrue(C.PROVIDERS["ninerouter"]["local_gateway"])
        cfg = C.save_config({"agent_modes": {"critic": "auto", "author": "nonsense"}})
        self.assertEqual(cfg["agent_modes"]["critic"], "auto")
        self.assertNotEqual(cfg["agent_modes"]["author"], "nonsense")


if __name__ == "__main__":
    unittest.main()
