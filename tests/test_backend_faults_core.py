"""Configuration recovery, write protection, event notifications and content-free telemetry failures."""
import _env
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import threading
import unittest
from unittest import mock

from backend.core import bus, config as C, telemetry as T


class CoreFaults(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("core-faults")

    def test_config_corruption_and_legacy_credentials_recover_without_erasing_original(self):
        original = C.CONFIG_PATH.read_text("utf-8")
        C.CONFIG_PATH.write_text("[]", "utf-8")
        self.assertIn("providers", C.load_config())
        self.assertTrue(list(C.GLOBAL_DIR.glob("config.json.corrupt-*")))
        C.CONFIG_PATH.write_text(json.dumps({"anthropic_api_key": "legacy-key", "claude_model": "legacy-model", "default_cloud": "invalid"}))
        cfg = C.load_config()
        self.assertEqual(cfg["providers"]["anthropic"]["api_key"], "legacy-key")
        self.assertEqual(cfg["providers"]["anthropic"]["model"], "legacy-model")
        self.assertEqual(cfg["default_cloud"], "anthropic")
        C.CONFIG_PATH.write_text(original)
        real_read = Path.read_text
        def denied(path, *a, **kw):
            if path == C.CONFIG_PATH: raise PermissionError("temporarily locked")
            return real_read(path, *a, **kw)
        with mock.patch.object(Path, "read_text", denied):
            self.assertIn("providers", C.load_config())

    def test_settings_masked_values_and_bad_types_preserve_valid_configuration(self):
        C.save_config({"providers": {"custom": {"api_key": "a-secret-credential", "model": "m"}},
                       "search": {"serpapi_key": "a-secret-credential"}, "agent_models": {"research": "chosen"}})
        C.save_config({"providers": {"nope": {}, "custom": {"api_key": C.mask("a-secret-credential")}},
                       "search": {"serpapi_key": C.mask("a-secret-credential"), "web_engine": "invalid", "n_results": "bad", "mailto": " me@example.org "},
                       "agent_models": {"research": "", "unknown": "bad"}, "agent_modes": {"unknown": "cloud"},
                       "default_cloud": "nope", "local_model": "local", "latex_online": False})
        cfg = C.load_config()
        self.assertEqual(cfg["providers"]["custom"]["api_key"], "a-secret-credential")
        self.assertEqual(cfg["search"]["serpapi_key"], "a-secret-credential")
        self.assertEqual(cfg["search"]["mailto"], "me@example.org")
        self.assertNotIn("research", cfg["agent_models"])
        self.assertNotIn("unknown", cfg["agent_modes"])
        self.assertEqual(C._coerce(3, "wrong"), 3)
        self.assertEqual(C._coerce({}, []), {})
        self.assertEqual(C._coerce([], {}), [])
        self.assertEqual(C._coerce(1.5, "2.5"), 2.5)
        C.save_config({"references_dir": str(C.data_dir() / "new-references")})
        self.assertEqual(C.refs_dir().name, "new-references")

    def test_missing_projects_are_safe_and_registry_deduplicates(self):
        with self.assertRaises(FileNotFoundError): C.activate_project(str(C.GLOBAL_DIR / "absent"))
        with self.assertRaises(FileNotFoundError): C.open_project(str(C.GLOBAL_DIR / "absent"))
        with self.assertRaises(ValueError): C.create_project(" ")
        with self.assertRaises(ValueError): C.forget_project(str(C.GLOBAL_DIR))
        cfg = C.load_config()
        cfg["active_project"] = str(C.GLOBAL_DIR / "absent")
        self.assertEqual(C.active_project(cfg)["data_dir"], str(C.GLOBAL_DIR))
        empty = C.GLOBAL_DIR / "without-meta"
        empty.mkdir(exist_ok=True)
        cfg["active_project"] = str(empty)
        self.assertEqual(C.active_project(cfg)["data_dir"], str(empty))
        self.assertTrue((empty / C.META_NAME).exists())
        cfg["projects"] = [str(empty), str(empty), str(C.GLOBAL_DIR)]
        with mock.patch.object(C, "load_config", return_value=cfg):
            self.assertEqual(len(C.list_projects()), 2)

    def test_telemetry_keeps_no_secrets_even_on_failure_or_unavailable_disk(self):
        saved = list(T.RING)
        self.addCleanup(lambda: (T.RING.clear(), T.RING.extend(saved)))
        T.RING.clear()
        clean = T._clean({"provider": "valid", "error": "password=private-secret", "role": "free text with spaces",
                          "tool": [], "cache_hit": True, "candidate_count": 1, "prompt": "forbidden", "client": None})
        self.assertEqual(clean["error"], "[REDACTED]")
        self.assertNotIn("role", clean)
        with self.assertRaisesRegex(RuntimeError, "secret"), mock.patch.object(C, "data_dir", side_effect=OSError), \
                mock.patch.object(T, "_file", side_effect=PermissionError):
            with T.span("fault", request_id="req-explicit") as span:
                span.update(cache_hit=False)
                raise RuntimeError("secret=top-secret-value")
        with T.span("success") as span:
            span.update(cache_hit=True)
        with T.span("without_cache"):
            pass
        report = T.summary()
        self.assertEqual(report["fault"]["errors"], 1)
        self.assertEqual(report["success"]["cache_hit_rate"], 1)
        self.assertIsNone(report["without_cache"]["cache_hit_rate"])
        self.assertNotIn("top-secret-value", json.dumps(list(T.RING)))
        p = C.data_dir() / "ops.jsonl"
        p.write_text("x" * 20)
        with mock.patch.object(T, "_file", return_value=p), mock.patch.object(T, "MAX_FILE", 1):
            T.record({"operation": "rotation", "latency_ms": 1, "ok": True})
        self.assertTrue(p.with_suffix(".jsonl.1").exists())

    def test_event_wait_timeout_and_notifications_and_reset(self):
        bus.reset()
        self.assertEqual(bus.wait(bus.last(), timeout=0), [])
        timer = threading.Timer(0.01, lambda: bus.publish("ready", client="cli"))
        timer.start()
        evs = bus.wait(0, timeout=1)
        timer.join()
        self.assertEqual(evs[0]["type"], "ready")
        self.assertEqual(bus.since(0)["last"], 1)
        bus.reset()
        self.assertEqual(bus.since()["events"], [])

