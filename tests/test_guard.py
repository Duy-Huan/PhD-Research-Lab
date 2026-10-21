"""Hardware guard: slots per resource class, the VRAM gate before a GPU slot, waiting and cancellation, pid checks."""
import _env  # noqa: F401  (must be first)
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from backend.core import config
from backend.execution import guard, resources


class Guard(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        guard.reset()
        self.addCleanup(guard.reset)

    def test_capacity_can_only_be_lowered(self):
        self.assertEqual(guard.capacity("gpu"), 1)
        config.save_config({"runs": {"slot_cli": 1, "slot_gpu": 5}})
        self.assertEqual((guard.capacity("cli"), guard.capacity("gpu")), (1, 1))
        self.assertGreater(guard.capacity("none"), 1000)
        with self.assertRaises(ValueError):
            guard.capacity("tpu")

    def test_one_gpu_job_at_a_time_and_reentrant(self):
        guard.try_acquire("gpu", "A", gpu_check=False)
        guard.try_acquire("gpu", "A", gpu_check=False)  # same holder: no second slot
        with self.assertRaises(guard.Busy) as e:
            guard.try_acquire("gpu", "B", gpu_check=False)
        self.assertEqual((e.exception.cls, e.exception.holders), ("gpu", ["A"]))
        self.assertEqual(guard.snapshot()["gpu"]["held_by"], ["A"])
        guard.release("gpu", "A")
        guard.try_acquire("gpu", "B", gpu_check=False)
        guard.release_all("B")
        self.assertEqual(guard.snapshot()["gpu"]["held_by"], [])

    def test_vram_gate_blocks_a_gpu_slot(self):
        with mock.patch.object(resources, "vram_gate", side_effect=resources.VramBusy(["m1"], 9000)):
            with self.assertRaises(guard.Busy) as e:
                guard.try_acquire("gpu", "A")
            self.assertIn("unload", e.exception.reason)
            config.save_config({"resources": {"auto_unload_for_gpu": True}})
            with mock.patch("backend.providers.lifecycle.free_vram_for_gpu", return_value={"ok": True}):
                guard.try_acquire("gpu", "A")
        self.assertEqual(guard.snapshot()["gpu"]["held_by"], ["A"])

    def test_acquire_waits_then_gets_the_slot(self):
        guard.try_acquire("cpu", "A")
        reasons = []
        t = threading.Timer(0.3, lambda: guard.release("cpu", "A"))
        t.start()
        guard.acquire("cpu", "B", on_wait=reasons.append)
        self.assertEqual(len(reasons), 1)
        self.assertIn("in use by A", reasons[0])
        guard.release("cpu", "B")

    def test_acquire_gives_up_on_timeout_or_cancel(self):
        guard.try_acquire("cpu", "A")
        with self.assertRaises(guard.Busy):
            guard.acquire("cpu", "B", timeout=0.2)
        with self.assertRaises(guard.Busy):
            guard.acquire("cpu", "B", cancelled=lambda: True)

    def test_pid_alive(self):
        self.assertTrue(guard.pid_alive(os.getpid()))
        self.assertFalse(guard.pid_alive(None))
        self.assertFalse(guard.pid_alive("x"))
        self.assertFalse(guard.pid_alive(0))
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        time.sleep(0.2)
        self.assertFalse(guard.pid_alive(p.pid))


if __name__ == "__main__":
    unittest.main()
