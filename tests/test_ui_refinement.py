"""Pins, registered-project browsing and the shared PDF naming contract."""
import _env  # noqa: F401
import hashlib
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import app
from backend.agent import sessions, AIWSError
from backend.core import config
from backend.knowledge import library as L
from pdfgen import make_pdf


class UIRefinement(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("ui-refinement")

    def test_pin_persists_and_validates_message_and_boolean(self):
        s = sessions.create("Pinned")
        sessions.update(s["id"], lambda s: s["messages"].append({"id": "m1", "role": "user", "content": "Evidence"}))
        result = sessions.pin_message(s["id"], "m1", True)
        self.assertTrue(result["messages"][0]["pinned"])
        sessions.reset_memory()
        self.assertTrue(sessions.get(s["id"])["messages"][0]["pinned"])
        self.assertFalse(sessions.pin_message(s["id"], "m1", False)["messages"][0]["pinned"])
        for mid, value in [("missing", True), ("m1", "true"), ("m1", None)]:
            with self.assertRaises(AIWSError):
                sessions.pin_message(s["id"], mid, value)
        with TestClient(app) as client:
            self.assertEqual(client.put(f"/api/chat/sessions/{s['id']}/messages/m1/pin", json={"pinned": True}).status_code, 200)

    def test_registered_project_browse_does_not_switch_or_leak_sessions(self):
        a = config.active_project()
        s = sessions.create("Project A only")
        b = config.create_project("Project B")
        other = sessions.create("Project B only")
        with TestClient(app) as client:
            r = client.get("/api/projects/conversations", params={"directory": a["data_dir"]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual([x["id"] for x in r.json()["sessions"]], [s["id"]])
            self.assertEqual(config.active_project()["data_dir"], b["data_dir"])
            r = client.get("/api/projects/conversations", params={"directory": str(config.GLOBAL_DIR.parent)})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(sessions.get(other["id"])["title"], "Project B only")
            with self.assertRaises(AIWSError):
                sessions.pin_message(s["id"], "m1", True)

    def test_pdf_upload_drop_download_share_naming_and_keep_original(self):
        metadata = {"title": "A Study of Image Restoration", "authors": ["Nguyen, An"], "year": "2024"}
        pdf = make_pdf([[(16, metadata["title"])]])
        digest = hashlib.sha256(pdf).hexdigest()
        expected = "2024_Nguyen_A-Study-of-Image-Restoration_" + digest[:12] + ".pdf"
        with patch.object(L, "heuristic_metadata", return_value=dict(metadata)):
            e = L.ingest_pdf("../../random.pdf", pdf)
            self.assertEqual(e["file"], expected)
            self.assertEqual(e["original_name"], "random.pdf")
            self.assertEqual(L.ingest_pdf("same.pdf", pdf)["file"], expected)
            # Files dropped directly into references are normalized on scan as well.
            (config.refs_dir() / "dropped.pdf").write_bytes(pdf)
            L.scan_directory()
            self.assertFalse((config.refs_dir() / "dropped.pdf").exists())
        self.assertEqual(len(L.load_library()), 1)
        self.assertEqual((config.refs_dir() / expected).read_bytes(), pdf)
        config.create_project("Downloads")
        source = {**metadata, "url": "https://example.org/study"}
        self.assertEqual(L.save_source(source, pdf)["entry"]["file"], expected)
        config.create_project("Metadata upgrade")
        L.save_source(source)
        self.assertEqual(L.save_source(source, pdf)["entry"]["file"], expected)

    def test_duplicate_filenames_do_not_overwrite_and_unknown_metadata_is_safe(self):
        a = b"%PDF-broken first"
        b = b"%PDF-broken second"
        e1 = L.ingest_pdf("paper.pdf", a)
        e2 = L.ingest_pdf("paper.pdf", b)
        self.assertNotEqual(e1["file"], e2["file"])
        self.assertEqual((config.refs_dir() / e1["file"]).read_bytes(), a)
        self.assertTrue(e1["file"].startswith("nd_Unknown_paper_"))
        self.assertLess(len(L.canonical_pdf_name({"title": "../CON:*?" * 1000, "authors": "A Person", "year": "../2024"}, "a" * 64)), 150)
        for name, content in [("x.txt", a), ("x.pdf", b"not pdf"), ("x.pdf", b"%PDF" + b"x" * (30 * 1024 * 1024))]:
            with self.assertRaises(ValueError):
                L.ingest_pdf(name, content)
        self.assertFalse(list(config.refs_dir().glob("tmp*.pdf")))

    def test_scan_prunes_missing_records_while_ingesting_and_isolates_invalid_files(self):
        L.save_library({"gone.pdf": {"file": "gone.pdf", "title": "Removed paper", "sha1": "gone"}})
        (config.refs_dir() / "valid.pdf").write_bytes(make_pdf([[(16, "A Real Paper With A Title")]]))
        (config.refs_dir() / "invalid.pdf").write_bytes(b"not a PDF")
        result = L.scan_directory()["library"]
        self.assertNotIn("gone.pdf", result)
        self.assertEqual(len(result), 2)
        self.assertFalse(result["invalid.pdf"]["include"])
        self.assertIn("PDF", result["invalid.pdf"]["error"])
        again = L.scan_directory()["library"]
        self.assertEqual(len(again), 2)
        self.assertFalse(again["invalid.pdf"]["pdf_available"])

    def test_uppercase_extension_alias_cannot_delete_the_canonical_pdf_on_windows(self):
        pdf = make_pdf([[(16, "A Paper With A Canonical Name")]])
        entry = L.ingest_pdf("source.PDF", pdf)
        path = config.refs_dir() / entry["file"]
        path.rename(path.with_suffix(".PDF"))
        L.save_library({})  # A directory import must discover the existing uppercase extension.
        result = L.scan_directory()["library"]
        self.assertEqual(len(result), 1)
        self.assertEqual((config.refs_dir() / next(iter(result))).read_bytes(), pdf)
