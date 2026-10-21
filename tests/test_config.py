import _env  # noqa: F401  (must be first)
import json
import unittest

from backend.core import config as C


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
        self.assertNotIn("mode", cfg["clearml"])  # ClearML records offline sessions only, no server
        self.assertTrue(C.DEFAULTS["clearml"]["auto_record"])
        self.assertTrue(C.DEFAULTS["codex"]["enabled"])
        self.assertEqual(cfg["codex"]["windows_sandbox"], "unelevated")
        self.assertTrue(cfg["resources"]["require_unload"])  # GPU runs refused while LLMs hold VRAM
        self.assertNotIn("jit_unload", cfg["resources"])  # no automatic unloading

    def test_coercion_and_choices(self):
        try:
            cfg = C.save_config({"memory": {"high_watermark_tokens": "12000", "unknown_key": 5, "embed_engine": "bogus"},
                                 "codex": {"sandbox": "danger-full-access"}, "resources": {"require_unload": "false"},
                                 "clearml": {"mode": "cloud-magic"}})
            self.assertEqual(cfg["memory"]["high_watermark_tokens"], 12000)
            self.assertNotIn("unknown_key", cfg["memory"])
            self.assertNotIn("mode", cfg["clearml"])
            self.assertEqual(cfg["memory"]["embed_engine"], "auto")
            self.assertEqual(cfg["codex"]["sandbox"], "read-only")  # never danger-full-access
            self.assertFalse(cfg["resources"]["require_unload"])
        finally:
            C.save_config({"memory": {"high_watermark_tokens": 16000}, "resources": {"require_unload": True}})

    def test_secret_masking_and_masked_value_keeps_secret(self):
        try:
            C.save_config({"mcp": {"token": "SECRETSECRET123456"}})
            pub = C.public_config(C.load_config())
            self.assertNotIn("SECRETSECRET123456", json.dumps(pub))
            self.assertTrue(pub["mcp"]["has_token"])
            C.save_config({"mcp": {"token": pub["mcp"]["token"]}})  # masked echo from the UI
            self.assertEqual(C.load_config()["mcp"]["token"], "SECRETSECRET123456")
        finally:
            C.save_config({"mcp": {"token": ""}})



if __name__ == "__main__":
    unittest.main()
