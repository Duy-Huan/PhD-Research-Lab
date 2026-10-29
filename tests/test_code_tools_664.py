"""FQC-CODE-TOOLS-664 (agent/PLAN_6.6.4_L3.md A3): the agent opens its own code project and edits files as versioned patches.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): the agent could not create or open a code project, and a
native coding run could only write a new experiments/<run>/ folder, so a one-line fix became a one-line file that the QA
operator applied by hand. Real code projects, files and git in a disposable PHDLAB_DATA_DIR."""
import hashlib
import json
import subprocess
import unittest
from types import SimpleNamespace

import _env
from backend.execution import code_projects, gitops
from backend.tools import registry


class _CodeTools:
    """backend.tools.code_tools, imported on use so each test reports on its own (also on the commit before A3)."""

    def __getattr__(self, name):
        from backend.tools import code_tools
        return getattr(code_tools, name)


CT = _CodeTools()
from backend.tools.spec import ToolError

CODEX = SimpleNamespace(principal="codex")
TRAIN = "import json\nlr = 0.1\nepochs = 3\nprint(json.dumps({'lr': lr}))\n"


def sha(text: str | bytes) -> str:
    return hashlib.sha256(text if isinstance(text, bytes) else text.encode()).hexdigest()


class CodeTools(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("code tools tests", code_project=None)

    def make(self, name="exp", text=TRAIN):
        made = CT.create_project({"name": name, "description": "agent experiment"}, CODEX)
        root = code_projects.active_dir()
        (root / "train.py").write_text(text, "utf-8", newline="")
        gitops.commit("start", ["train.py"])
        return made, root

    def patch(self, edits, path="train.py", digest=None, root=None):
        current = (root or code_projects.active_dir()) / path
        return CT.apply_patch({"path": path, "sha256": digest or sha(current.read_bytes()), "edits": edits,
                               "message": "Lower the learning rate"}, CODEX)

    def test_the_agent_creates_lists_and_opens_code_projects(self):
        made, _ = self.make("exp")
        self.assertEqual((made["name"], made["active"]), ("exp", True))
        CT.create_project({"name": "exp2"}, CODEX)
        self.assertEqual(CT.projects({}, CODEX)["active"], "exp2")
        self.assertEqual(CT.open_project({"name": "exp"}, CODEX), {"name": "exp", "active": True})
        listed = CT.projects({}, CODEX)
        self.assertEqual((listed["active"], sorted(p["name"] for p in listed["projects"])), ("exp", ["exp", "exp2"]))
        for bad in ({"name": "nope"}, {"name": "../escape"}):
            with self.subTest(bad=bad), self.assertRaises(ToolError) as e:
                CT.open_project(bad, CODEX)
            self.assertEqual(e.exception.code, "invalid_input")
        with self.assertRaises(ToolError):
            CT.create_project({"name": "exp"}, CODEX)  # never overwrites an existing project

    def test_a_patch_edits_in_place_and_commits_only_that_file(self):
        _, root = self.make()
        (root / "notes.md").write_text("researcher's unsaved notes\n", "utf-8")
        work = lambda: sorted(f.relative_to(root).as_posix() for f in root.rglob("*") if ".git" not in f.relative_to(root).parts)  # noqa: E731
        before = work()
        done = self.patch([{"old": "lr = 0.1", "new": "lr = 0.01"}])
        self.assertEqual((root / "train.py").read_text("utf-8"), TRAIN.replace("lr = 0.1", "lr = 0.01"))
        self.assertEqual(done["sha256"], sha((root / "train.py").read_bytes()))
        self.assertEqual(done["versioned"], "git")
        self.assertEqual(work(), before)  # no new folder or file per edit (git's own objects aside)
        log = gitops.G(["log", "-1", "--format=%H %s"]).strip()
        self.assertEqual(log.split()[0], done["commit"])
        self.assertIn("agent patch by codex", log)
        self.assertEqual(gitops.G(["show", "--name-only", "--format=", "HEAD"]).split(), ["train.py"])
        self.assertIn("notes.md", gitops.G(["status", "--porcelain"]))  # the researcher's other work stays uncommitted
        version = CT.file_version({"path": "train.py"}, CODEX)
        self.assertEqual((version["sha256"], version["patches"][-1]["commit"]), (done["sha256"], done["commit"]))
        again = self.patch([{"old": "epochs = 3", "new": "epochs = 5"}], digest=done["sha256"])
        self.assertEqual(again["old_sha256"], done["sha256"])
        self.assertEqual(len(CT.file_version({"path": "train.py"}, CODEX)["patches"]), 2)

    def test_a_stale_or_ambiguous_patch_changes_nothing(self):
        _, root = self.make(text=TRAIN + "lr = 0.1\n")
        original = (root / "train.py").read_bytes()
        cases = [([{"old": "lr = 0.1", "new": "lr = 0.2"}], None, "occurs 2 times"),
                 ([{"old": "missing line", "new": "x"}], None, "occurs 0 times"),
                 ([{"old": "epochs = 3", "new": "epochs = 3"}], None, "do not change"),
                 ([{"old": "epochs = 3", "new": "epochs = 4"}], "0" * 64, "changed since you read it")]
        for edits, digest, message in cases:
            with self.subTest(message=message), self.assertRaises(ToolError) as e:
                self.patch(edits, digest=digest)
            self.assertIn(message, e.exception.message)
        self.assertEqual((root / "train.py").read_bytes(), original)
        self.assertEqual(CT.file_version({"path": "train.py"}, CODEX)["patches"], [])
        # Edits apply all-or-nothing: a valid first edit is not written when the second one fails.
        with self.assertRaises(ToolError):
            self.patch([{"old": "epochs = 3", "new": "epochs = 4"}, {"old": "missing", "new": "x"}])
        self.assertEqual((root / "train.py").read_bytes(), original)

    def test_windows_line_endings_are_kept(self):
        _, root = self.make(text=TRAIN.replace("\n", "\r\n"))
        self.patch([{"old": "lr = 0.1\nepochs = 3", "new": "lr = 0.01\nepochs = 3"}])
        self.assertEqual((root / "train.py").read_bytes(), TRAIN.replace("lr = 0.1", "lr = 0.01").replace("\n", "\r\n").encode())

    def test_paths_outside_the_project_git_internals_and_binary_files_are_refused(self):
        _, root = self.make()
        (root / "blob.bin").write_bytes(b"\xff\xfe\x00binary")
        for path, code in (("../outside.py", "invalid_input"), (".git/config", "invalid_input"), ("missing.py", "not_found"),
                           ("blob.bin", "invalid_input")):
            with self.subTest(path=path), self.assertRaises(ToolError) as e:
                CT.apply_patch({"path": path, "sha256": sha((root / path).read_bytes()) if (root / path).is_file() else "0" * 64,
                                "edits": [{"old": "a", "new": "b"}], "message": "m"}, CODEX)
            self.assertEqual(e.exception.code, code)

    def test_without_git_the_patch_is_journalled(self):
        code_projects.create("plain", git=False, vscode=False, seed=False)
        root = code_projects.active_dir()
        (root / "train.py").write_text(TRAIN, "utf-8", newline="")
        done = self.patch([{"old": "lr = 0.1", "new": "lr = 0.01"}])
        self.assertEqual((done["versioned"], done["commit"]), ("journal", None))
        journal = [json.loads(line) for line in CT._journal().read_text("utf-8").splitlines()]
        self.assertEqual((journal[-1]["old_sha256"], journal[-1]["new_sha256"]), (sha(TRAIN), done["sha256"]))
        self.assertFalse(str(CT._journal()).startswith(str(root)))  # the journal never lands in the code folder

    def test_no_open_project_is_a_clear_unavailable_error(self):
        for fn, args in ((CT.apply_patch, {"path": "x.py", "sha256": "0" * 64, "edits": [{"old": "a", "new": "b"}], "message": "m"}),
                         (CT.file_version, {"path": "x.py"})):
            with self.subTest(fn=fn.__name__), self.assertRaises(ToolError) as e:
                fn(args, CODEX)
            self.assertEqual(e.exception.code, "unavailable")

    def test_registry_lists_the_tools_and_mutations_need_workspace_write(self):
        specs = {s.id: s for s in registry.builtin_specs()}
        for tid in ("code.create_project", "code.open_project", "code.apply_patch"):
            self.assertEqual((specs[tid].mutates, specs[tid].permissions), (True, ["workspace_write"]))
        for tid in ("code.projects", "code.file_version"):
            self.assertEqual((specs[tid].mutates, specs[tid].permissions), (False, []))

    def test_patching_is_fast(self):
        self.make()
        digest = None
        import time
        t0 = time.monotonic()
        for i in range(10):
            digest = self.patch([{"old": f"epochs = {3 + i}", "new": f"epochs = {4 + i}"}], digest=digest)["sha256"]
        self.assertLess(time.monotonic() - t0, 10.0)  # under 1 s per patch including the git commit


if __name__ == "__main__":
    unittest.main()
