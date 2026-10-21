"""Legacy storage modules (coverage pass): chat sessions, shared context hub, IDE workspace files, folder browser."""
import _env  # noqa: F401  (must be first)
import json
import os
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.memory import notes as CH
from backend.execution import files as FS
from backend.core.config import workspace
from backend.execution.sandbox import code_dir


class ContextHub(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-hub")


    def test_corrupt_notes_file_is_not_silently_destroyed(self):
        CH.add_note("data", "precious")
        CH._notes_path().write_text("{broken json", "utf-8")
        CH.add_note("data", "new")
        copies = list(workspace().glob("shared_context.json.corrupt-*"))
        self.assertTrue(copies, "the damaged notes file must be kept before it is overwritten")
        self.assertIn("broken json", copies[0].read_text("utf-8"))


class IdeFs(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-ide")

    def test_files_lifecycle(self):
        self.assertEqual(FS.create("pkg/a.py")["path"], "pkg/a.py")
        FS.create("pkg/sub", folder=True)
        with self.assertRaises(FS.FsError):
            FS.create("pkg/a.py")
        w = FS.write("pkg/a.py", "print('hello')\n")
        self.assertEqual(FS.read("pkg/a.py")["content"], "print('hello')\n")
        with self.assertRaises(FS.FsError):
            FS.write("pkg/a.py", "x", expected_mtime=w["mtime"] - 100)
        FS.write("pkg/a.py", "print('v2')\n", expected_mtime=w["mtime"])
        with self.assertRaises(FS.FsError):
            FS.write("pkg", "x")
        FS.upload("img.bin", b"\x00\x01")
        self.assertTrue(FS.read("img.bin")["binary"])
        FS.upload("big.txt", b"a" * (FS.MAX_READ + 1))
        with self.assertRaises(FS.FsError):
            FS.read("big.txt")
        with self.assertRaises(FS.FsError):
            FS.read("missing.py")
        with self.assertRaises(FS.FsError):
            FS.read("../../etc/passwd")
        FS.rename("pkg/a.py", "pkg/b.py")
        with self.assertRaises(FS.FsError):
            FS.rename("pkg/a.py", "x.py")
        FS.create("c.py")
        with self.assertRaises(FS.FsError):
            FS.rename("pkg/b.py", "c.py")
        t = FS.tree()
        self.assertIn("pkg", [c["name"] for c in t["children"]])
        self.assertTrue(FS.tree(max_entries=1)["truncated"])
        hits = FS.search("v2")
        self.assertEqual(hits[0]["path"], "pkg/b.py")
        self.assertEqual(FS.search(""), [])
        self.assertEqual(len(FS.search("print", max_hits=1)), 1)
        self.assertIn("pkg/b.py", FS.snapshot(focus=["pkg/b.py"]))
        self.assertIn("v2", FS.snapshot(max_chars=10 ** 6))
        self.assertEqual(FS.delete("pkg/b.py")["trashed"], "pkg/b.py")
        self.assertTrue(list((code_dir() / ".trash").rglob("b.py")))
        with self.assertRaises(FS.FsError):
            FS.delete("")
        with self.assertRaises(FS.FsError):
            FS.delete("ghost.py")
        self.assertFalse(FS.is_text(code_dir() / "nope.py"))
        self.assertFalse(FS.is_text(code_dir() / "image.png"))

    def test_folder_into_itself_and_upload_onto_folder_are_clean_errors(self):
        FS.create("d/inner", folder=True)
        with self.assertRaises(FS.FsError):
            FS.rename("d", "d/inner/d")
        with self.assertRaises(FS.FsError):
            FS.upload("d", b"x")
        with self.assertRaises(FS.FsError):
            FS.upload("", b"x")

    def test_seed_never_overwrites(self):
        (code_dir() / "README.md").write_text("mine", "utf-8")
        created = FS.seed("# design", "print(1)")
        self.assertIn("experiment_skeleton.py", created)
        self.assertNotIn("README.md", created)
        self.assertEqual((code_dir() / "README.md").read_text("utf-8"), "mine")
        self.assertEqual(FS.seed(), [])

    def test_unreadable_entries(self):
        FS.create("z.py")
        with mock.patch.object(Path, "iterdir", side_effect=OSError("denied")):
            self.assertEqual(FS.tree()["children"], [])
        with mock.patch("builtins.open", side_effect=OSError("locked")):
            self.assertFalse(FS.is_text(code_dir() / "z.py"))
        with mock.patch.object(Path, "read_text", side_effect=OSError("locked")):
            self.assertEqual(FS.search("anything"), [])


if __name__ == "__main__":
    unittest.main()
