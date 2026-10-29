"""FQC-LONG-PATHS-664 (agent/PLAN_6.6.4_L3.md A10): warn when a long Windows data path will break package loading.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): a long data folder made Python packages fail to load
(WinError 206) and nothing said why. The system scan now warns when long paths are off and the folder leaves too little
room under the 260-character limit. Advisory only: nothing is moved or changed."""
import sys
import unittest
from unittest.mock import patch

import _env
from backend.execution import sysinfo as I


def scan_items(lp: dict) -> list:
    base = {"gpus": [], "memory": {"total_gb": 16}, "cpu": {"cores": 8}, "docker": {}, "wsl": {}, "tools": {"git": "git", "latex": ["tectonic"]},
            "local_ai": {"lmstudio": True}, "disk": {"free_gb": 100}, "long_paths": lp}
    return [i for i in I.recommend(base)["items"] if i["area"] == "Paths"]


class LongPaths(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)

    def check(self, root: str, enabled: bool, platform: str = "win32") -> dict:
        with patch.object(sys, "platform", platform), patch.object(I, "_long_paths_enabled", return_value=enabled):
            return I.long_paths(root)

    def test_a_long_folder_without_long_paths_is_warned_with_the_fix(self):
        lp = self.check("D:/" + "research-data-" * 7, enabled=False)
        self.assertTrue(lp["at_risk"])
        self.assertGreater(lp["root_chars"] + I.LONG_PATH_ROOM, 260)
        [item] = scan_items(lp)
        self.assertEqual(item["level"], "warn")
        for part in (f"{lp['root_chars']} characters", "WinError 206", "D:\\PhDLab", "LongPathsEnabled = 1"):
            self.assertIn(part, item["text"])

    def test_no_warning_when_long_paths_are_on_or_the_folder_is_short(self):
        for lp in (self.check("D:/" + "research-data-" * 7, enabled=True), self.check("D:/PhDLab", enabled=False)):
            with self.subTest(lp=lp):
                self.assertFalse(lp["at_risk"])
                self.assertEqual(scan_items(lp), [])

    def test_other_systems_are_not_affected(self):
        lp = self.check("/home/" + "x" * 200, enabled=False, platform="linux")
        self.assertEqual(lp, {"applicable": False, "at_risk": False})
        self.assertEqual(scan_items(lp), [])

    def test_an_unreadable_setting_counts_as_off(self):
        import types
        broken = types.SimpleNamespace(HKEY_LOCAL_MACHINE=0, OpenKey=lambda *a: (_ for _ in ()).throw(OSError("access denied")))
        with patch.dict(sys.modules, {"winreg": broken}):
            self.assertFalse(I._long_paths_enabled())

    def test_the_default_root_is_the_active_project(self):
        from backend.core.config import data_dir
        with patch.object(sys, "platform", "win32"), patch.object(I, "_long_paths_enabled", return_value=True):
            self.assertEqual(I.long_paths()["root"], str(data_dir()))


if __name__ == "__main__":
    unittest.main()
