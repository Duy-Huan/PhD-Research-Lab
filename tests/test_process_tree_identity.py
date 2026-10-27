"""FQC-PROCESS-TREE-661: stopping an owned process never kills unrelated processes through reused Windows PIDs.

Root cause of the Windows CI jobs that died without log or artifact: cancellation walked "ParentProcessId == our PID"
(and taskkill /T), which also matches long-lived processes whose real parent died and whose PID our child reused.
"""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _env  # noqa: F401  (repository import path)

try:
    from backend.execution.processes import select_descendants, stop_tree
    MISSING = None
except ImportError as missing:  # RED before the fix
    MISSING = missing

ROOT = Path(__file__).resolve().parents[1]


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING


class DescendantSelection(Base):
    def test_stale_parent_links_from_reused_pids_are_excluded(self):
        # 100 = our process (created t=50). 200 is a real child, 300 its grandchild.
        # 900 is an unrelated runner process created at t=10 whose dead parent once had PID 100.
        # 950 is an unrelated process whose dead parent once had PID 200 (created before 200 existed).
        parents = {200: 100, 300: 200, 900: 100, 901: 900, 950: 200}
        created = {200: 60, 300: 70, 900: 10, 901: 11, 950: 55}.get
        self.assertEqual(select_descendants(100, 50, parents, created), [200, 300])

    def test_processes_that_vanished_are_skipped(self):
        self.assertEqual(select_descendants(1, 5, {2: 1, 3: 2}, {3: 9}.get), [])


class RealWindowsTree(Base):
    def test_owned_tree_stops_and_bystander_survives(self):
        bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(bystander.wait, 10)
        self.addCleanup(bystander.kill)
        folder = tempfile.TemporaryDirectory(prefix="phdlab-tree-")
        self.addCleanup(folder.cleanup)
        marker = Path(folder.name) / "child.pid"
        code = ("import subprocess,sys,time,pathlib;"
                "c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);"
                f"pathlib.Path(r'{marker}').write_text(str(c.pid));time.sleep(60)")
        owned = subprocess.Popen([sys.executable, "-c", code])
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        child = int(marker.read_text())
        stop_tree(owned)
        self.assertIsNotNone(owned.wait(10), "the owned process is stopped on every platform")
        self.assertIsNone(bystander.poll(), "an unrelated process survives")
        if sys.platform.startswith("win"):  # the identity-checked tree walk is Windows-only; POSIX uses process groups
            import ctypes
            k = ctypes.WinDLL("kernel32")
            handle = k.OpenProcess(0x100000, False, child)  # SYNCHRONIZE
            alive = bool(handle) and k.WaitForSingleObject(handle, 3000) != 0
            if handle:
                k.CloseHandle(handle)
            self.assertFalse(alive, "the owned grandchild is stopped")
        else:
            import os
            import signal
            try:
                os.kill(child, signal.SIGKILL)  # our own leftover grandchild; this test started it
            except ProcessLookupError:
                pass


class NoUnsafeTreeKill(Base):
    def test_cancellation_paths_use_the_identity_checked_stop(self):
        for rel in ("backend/providers/cli.py", "backend/execution/sandbox.py", "backend/execution/remote_runner.py",
                    "devtools/verification/ci_repair.py"):
            with self.subTest(rel=rel):
                self.assertNotIn("taskkill", (ROOT / rel).read_text("utf-8"))

    def test_cli_cancel_falls_back_to_the_owned_handle_when_tree_stop_fails(self):
        from backend.providers import cli
        proc = mock.Mock(pid=123, poll=mock.Mock(return_value=None))
        with mock.patch.object(cli.sys, "platform", "win32"), \
                mock.patch("backend.execution.processes.stop_tree", side_effect=OSError("denied")):
            cli.kill_tree(proc)
        proc.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
