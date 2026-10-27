"""FQC-PROJECTS-ROOT-662: the owner can choose a default folder (any drive) where new projects are created.

Projects created with an explicit folder keep it; without one they go to ui.projects_root when set, otherwise to the
app data projects folder. The setting only accepts absolute paths and never moves existing projects.
"""
import tempfile
import unittest
from pathlib import Path

import _env
from backend.core import config


class ProjectsRoot(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.tmp = tempfile.TemporaryDirectory(prefix="phdlab-projects-root-")
        self.addCleanup(self.tmp.cleanup)

    def test_new_projects_go_to_the_chosen_default_folder(self):
        root = Path(self.tmp.name) / "Research"
        config.save_config({"ui": {"projects_root": str(root)}})
        info = config.create_project("Chapter three")
        self.assertEqual(Path(info["data_dir"]).resolve().parent, root.resolve())
        second = config.create_project("Chapter three")
        self.assertNotEqual(second["data_dir"], info["data_dir"], "an existing project folder is never reused silently")
        self.assertEqual(Path(second["data_dir"]).resolve().parent, root.resolve())

    def test_explicit_folder_wins_and_unset_root_keeps_the_app_folder(self):
        explicit = Path(self.tmp.name) / "elsewhere"
        info = config.create_project("Explicit", str(explicit))
        self.assertEqual(Path(info["data_dir"]).resolve(), explicit.resolve())
        config.save_config({"ui": {"projects_root": ""}})
        self.assertEqual(Path(config.create_project("Default")["data_dir"]).resolve().parent, config.PROJECTS_ROOT.resolve())

    def test_relative_root_is_refused(self):
        with self.assertRaises(ValueError):
            config.save_config({"ui": {"projects_root": "relative/folder"}})


if __name__ == "__main__":
    unittest.main()
