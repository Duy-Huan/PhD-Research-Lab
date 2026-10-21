"""Upgrade regressions: old curated knowledge survives the v5 unified memory format."""
import _env
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from backend import memory
from backend.core import config
from backend.memory import knowledge, notes


class KnowledgeMigration(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("knowledge-migration")
        self.path = memory.mem_dir() / "knowledge.json"

    def write(self, payload):
        self.path.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        return self.path.read_bytes()

    def test_full_records_import_once_without_changing_the_original(self):
        old = {"id": "M-abc", "name": "Swin attention", "text": "Keep the shifted window method.",
               "refs": ["liang2021swinir"], "code_ref": "models/swin.py", "created": "2025-01-01", "custom": {"x": 2}}
        before = self.write({"concepts": [{"id": "K-abc", "name": "PSNR", "text": "Quality in dB."}], "methods": [old]})
        existing = notes.add_note("data", "An existing project note")
        first = notes.load_notes()
        self.assertEqual(len(first), 3)
        method = next(n for n in first if n.get("legacy_knowledge", {}).get("kind") == "method")
        self.assertEqual(method["legacy_knowledge"]["record"], old)
        for fragment in ("Swin attention", "shifted window", "liang2021swinir", "models/swin.py"):
            self.assertIn(fragment, method["text"])
        self.assertEqual(method["ts"], old["created"])
        self.assertIn(existing["id"], [n["id"] for n in first])
        self.assertEqual(notes.load_notes(), first)
        self.assertEqual(self.path.read_bytes(), before)
        _env.fresh_project("other-knowledge-project")
        self.assertEqual(notes.load_notes(), [])

    def test_curated_records_survive_the_rolling_note_limit(self):
        records = [{"id": f"K-{i}", "name": f"Concept {i}", "text": f"Definition {i}"} for i in range(205)]
        self.write({"concepts": records})
        self.assertEqual(len(notes.load_notes()), len(records))
        with mock.patch.object(notes, "MAX_NOTES", 2):
            for i in range(4):
                notes.add_note("data", f"Recent {i}")
        loaded = notes.load_notes()
        self.assertEqual(len([n for n in loaded if n.get("legacy_knowledge")]), len(records))
        self.assertEqual([n["text"] for n in loaded if not n.get("legacy_knowledge")], ["Recent 2", "Recent 3"])

    def test_concurrent_readers_and_interrupted_import_are_retryable(self):
        before = self.write({"concepts": [{"id": "K-1", "name": "PSNR", "text": "A curated metric."}]})
        with mock.patch.object(notes, "_save_notes", side_effect=OSError("disk temporarily unavailable")):
            with self.assertRaises(OSError):
                notes.load_notes()
        self.assertEqual(self.path.read_bytes(), before)
        with ThreadPoolExecutor(max_workers=6) as pool:
            loaded = list(pool.map(lambda _: notes.load_notes(), range(12)))
        self.assertTrue(all(len(row) == 1 for row in loaded))
        self.assertEqual(len({row[0]["id"] for row in loaded}), 1)

    def test_unreadable_or_malformed_legacy_data_is_preserved(self):
        self.assertEqual(knowledge.legacy_notes(), [])
        for payload in ([], {"concepts": "invalid", "methods": [None, "invalid"]}):
            original = self.write(payload)
            self.assertEqual(notes.load_notes(), [])
            self.assertEqual(self.path.read_bytes(), original)
        self.path.write_text("{damaged", "utf-8")
        self.assertEqual(notes.load_notes(), [])
        self.assertEqual(self.path.read_text("utf-8"), "{damaged")
        self.write({"methods": [{"code_ref": "method.py", "refs": ["reference"]}]})
        item = notes.load_notes()[0]
        self.assertTrue(item["source"].startswith("memory/knowledge.json#legacy-"))
        self.assertEqual(item["ts"], "")
        self.assertIn("method:", item["text"])

    def test_invalid_notes_are_quarantined_before_import(self):
        notes._notes_path().write_text('{"notes": ["invalid"]}', "utf-8")
        self.write({"concepts": [{"name": "kept", "text": "original survives"}]})
        loaded = notes.load_notes()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(len(list(config.workspace().glob("shared_context.json.corrupt-*"))), 1)


if __name__ == "__main__":
    unittest.main()
