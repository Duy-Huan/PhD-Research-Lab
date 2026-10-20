"""Legacy storage modules (coverage pass): chat sessions, shared context hub, IDE workspace files, folder browser."""
import _env  # noqa: F401  (must be first)
import json
import os
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

from backend import chat_store as CS, context_hub as CH, fs_browse as FB, ide_fs as FS
from backend.config import workspace
from backend.sandbox import code_dir


class ChatStore(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-chat")

    def test_crud_titles_and_active(self):
        d = CS.create_session(None, [{"role": "user", "content": "--- FILE: data.csv ---\nrows"}, {"role": "bogus", "content": "x"},
                                     {"role": "assistant", "content": "ok", "tables": ["t", 3], "added": [2, 1.0, "x"],
                                      "sources": [{"u": 1}, "s"]}], tool="lit2plan", context="ctx")
        self.assertEqual(d["title"], "📎 data.csv")
        self.assertEqual(d["messages"][1]["tables"], ["t"])
        self.assertEqual(d["messages"][1]["added"], [1, 2])
        self.assertEqual(CS.get_active("lit2plan"), d["id"])
        long = CS.create_session("", [{"role": "user", "content": "q" * 80}])
        self.assertTrue(long["title"].endswith("…"))
        self.assertEqual(CS.auto_title([]), "New chat")
        self.assertEqual(CS.auto_title([{"role": "user", "content": "\n\n"}]), "New chat")
        s = CS.save_session(d["id"], title="  My title ")
        self.assertEqual(s["title"], "My title")
        s = CS.save_session(d["id"], [{"role": "user", "content": "new"}])
        self.assertEqual(s["title"], "My title")  # a researcher title is kept
        self.assertEqual(CS.save_session("fresh-id", [{"role": "user", "content": "hello"}])["title"], "hello")
        loaded = CS.load_session(d["id"])
        self.assertEqual(loaded["tool"], "lit2plan")
        metas = CS.list_sessions("lit2plan")
        self.assertEqual([m["id"] for m in metas], [d["id"]])
        self.assertTrue(metas[0]["has_context"])
        self.assertEqual(len(CS.list_sessions()), 3)
        self.assertEqual(CS.clean_messages("x"), [])
        self.assertEqual(CS._tool("weird"), "data")

    def test_delete_moves_to_trash_and_picks_next(self):
        a = CS.create_session("a", tool="paper")
        time.sleep(1.1)
        b = CS.create_session("b", tool="paper")
        self.assertEqual(CS.delete_session(b["id"]), a["id"])
        self.assertTrue((CS._trash_dir() / f"{b['id']}.json").exists())
        self.assertIsNone(CS.delete_session(a["id"]))
        with self.assertRaises(CS.SessionNotFound):
            CS.delete_session(a["id"])
        with self.assertRaises(CS.SessionNotFound):
            CS.load_session("../evil")
        with self.assertRaises(CS.SessionNotFound):
            CS.load_session("missing")
        self.assertIsNone(CS.get_active("review"))
        CS.set_active("review", "bad id!")
        self.assertIsNone(CS.get_active("review"))

    def test_record_turn_merges_with_stored_metadata(self):
        d = CS.create_session("t", [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1", "engine": "x"}])
        out = CS.record_turn(d["id"], [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
                                       {"role": "user", "content": "q2"}], {"content": "a2", "engine": "claude"})
        self.assertEqual([m["content"] for m in out["messages"]], ["q1", "a1", "q2", "a2"])
        self.assertEqual(out["messages"][1]["engine"], "x")
        fresh = CS.record_turn("brand-new", [{"role": "user", "content": "hi"}], {"content": "yo"})
        self.assertEqual(len(fresh["messages"]), 2)

    def test_corrupt_files_and_legacy_migration(self):
        d = CS.create_session("x")
        p = CS._path(d["id"])
        p.write_text("{oops", "utf-8")
        self.assertNotIn(d["id"], [m["id"] for m in CS.list_sessions()])
        self.assertTrue(list(CS._sess_dir().glob("*.corrupt-*.json")))
        CS._state_path().write_text(json.dumps({"active": "legacy-active"}), "utf-8")
        self.assertEqual(CS._state(), {"data": "legacy-active"})
        CS._state_path().write_text(json.dumps({"active": 5}), "utf-8")
        self.assertEqual(CS._state(), {})
        CS._legacy_path().write_text(json.dumps({"messages": [{"role": "user", "content": "old chat"}], "updated": "2020-01-01"}), "utf-8")
        metas = CS.list_sessions("data")
        self.assertIn("old chat", [m["title"] for m in metas])
        self.assertTrue((workspace() / "chat_session.migrated.json").exists())
        CS._legacy_path().write_text(json.dumps({"messages": []}), "utf-8")
        CS.migrate_legacy()
        self.assertFalse(CS._legacy_path().exists())

    def test_attachment_refs_are_cleaned(self):
        m = CS._clean_message({"role": "user", "content": "see", "attachments": [{"id": "att-1", "name": "f.pdf"}, "junk"]})
        self.assertIsInstance(m["attachments"], list)


class ContextHub(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-hub")

    def test_outputs_notes_and_shared_block(self):
        ws = workspace()
        (ws / "lit2plan.md").write_text("PLAN " * 3000, "utf-8")
        (ws / "lit2plan_sources.json").write_text(json.dumps({"sources": [1]}), "utf-8")
        (ws / "masterclass_guide.md").write_text("GUIDE", "utf-8")
        (ws / "masterclass_meta.json").write_text("{bad", "utf-8")
        (ws / "review.md").write_text("REVIEW", "utf-8")
        self.assertEqual(CH.tool_output("lit2plan")["sources"], [1])
        self.assertEqual(CH.tool_output("masterclass")["content"], "GUIDE")
        self.assertIn("Peer review", CH.tool_output("paper")["content"])
        self.assertEqual(CH.tool_output("unknown"), {"content": "", "updated": None})
        self.assertIn("review_id", CH.tool_output("review"))
        (ws / "lit2plan_sources.json").write_text("{bad", "utf-8")
        self.assertNotIn("sources", CH.tool_output("lit2plan"))
        (ws / "masterclass_meta.json").write_text(json.dumps({"level": "PhD"}), "utf-8")
        self.assertEqual(CH.tool_output("masterclass")["level"], "PhD")
        n = CH.add_note("nope-tool", "  pinned fact  ", "chat")
        self.assertEqual((n["tool"], n["text"]), ("data", "pinned fact"))
        for i in range(3):
            CH.add_note("lit2plan", f"note {i} " + "x" * 100)
        block = CH.build_shared_context("experiment", {"lit2plan": [{"role": "user", "content": "q"}], "experiment": [{"role": "user", "content": "z"}],
                                                       "paper": []}, per_output=100, notes_budget=250)
        self.assertIn("…[truncated]", block)
        self.assertIn("Pinned notes", block)
        self.assertIn("recent chat", block)
        self.assertNotIn("note 0", block)  # oldest note dropped by the budget
        CH.delete_note(n["id"])
        self.assertNotIn(n["id"], [x["id"] for x in CH.load_notes()])
        self.assertIsNone(CH._mtime(ws / "nope"))

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


class FsBrowse(unittest.TestCase):
    def test_list_and_mkdir(self):
        root = Path(_env.os.environ["PHDLAB_DATA_DIR"]) / "browse"
        (root / "b" / "x").mkdir(parents=True, exist_ok=True)
        (root / "A").mkdir(exist_ok=True)
        (root / ".hidden").mkdir(exist_ok=True)
        (root / "paper.pdf").write_bytes(b"%PDF")
        (root / "project_meta.json").write_text("{}", "utf-8")
        d = FB.list_dir(str(root))
        self.assertEqual([x["name"] for x in d["dirs"]], ["A", "b"])
        self.assertEqual(d["pdfs"], 1)
        self.assertTrue(d["is_project"])
        self.assertTrue(d["drives"])
        self.assertEqual(FB.list_dir(str(root / "no" / "such"))["path"], str(root.resolve()))
        self.assertEqual(FB.list_dir("")["path"], str(Path.home().resolve()))
        self.assertIn("new", [x["name"] for x in FB.list_dir(FB.make_dir(str(root), "new")["parent"])["dirs"]])
        for bad in ("", "a/b", "..", "x:y"):
            with self.assertRaises(ValueError):
                FB.make_dir(str(root), bad)
        with mock.patch("os.scandir", side_effect=PermissionError):
            self.assertEqual(FB.list_dir(str(root))["error"], "Access denied")
        with mock.patch("os.scandir", side_effect=OSError("io")):
            self.assertEqual(FB.list_dir(str(root))["error"], "io")
        with mock.patch.object(Path, "resolve", side_effect=OSError):
            self.assertTrue(FB.list_dir("C:/x")["path"])
        with mock.patch.object(FB.os, "name", "posix"):
            self.assertEqual(FB._drives(), [{"name": "/", "path": "/"}])

    def test_native_picker_paths(self):
        def run(out="", err=""):
            return subprocess.CompletedProcess([], 0, stdout=out, stderr=err)
        with mock.patch("subprocess.run", return_value=run(json.dumps({"path": "C:/Users"}))):
            r = FB.pick_folder_native("C:/definitely/missing")
            self.assertTrue(r["native"])
            self.assertFalse(r["cancelled"])
        with mock.patch("subprocess.run", return_value=run(json.dumps({"path": ""}))):
            self.assertTrue(FB.pick_folder_native()["cancelled"])
        with mock.patch("subprocess.run", return_value=run(json.dumps({"error": "no tk"}))):
            self.assertFalse(FB.pick_folder_native()["native"])
        with mock.patch("subprocess.run", return_value=run("", "Traceback")):
            self.assertEqual(FB.pick_folder_native()["error"], "Traceback")
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertFalse(FB.pick_folder_native()["native"])


if __name__ == "__main__":
    unittest.main()
