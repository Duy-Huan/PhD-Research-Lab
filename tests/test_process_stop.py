"""Cancellation survives failed Windows tree termination without claiming an unobserved exit."""
import _env
import subprocess
import unittest
from unittest import mock

from backend.execution import sandbox


class ProcessStop(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("process-stop")

    def test_taskkill_failure_and_timeout_fall_back_to_the_owned_process_handle(self):
        for failure in (subprocess.CompletedProcess([], 1), subprocess.TimeoutExpired("taskkill", 5)):
            with self.subTest(failure=type(failure).__name__):
                job = sandbox.Job("run", "python slow.py")
                job.status, job.mode = "running", "local"
                job.proc = mock.Mock(pid=123, poll=mock.Mock(return_value=None))
                sandbox.JOBS[job.id] = job
                self.addCleanup(sandbox.JOBS.pop, job.id, None)
                kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with mock.patch.object(sandbox, "IS_WIN", True), mock.patch.object(sandbox.subprocess, "run", **kwargs) as kill:
                    result = sandbox.stop_job(job.id)
                job.proc.kill.assert_called_once()
                self.assertEqual(kill.call_args.kwargs["timeout"], 5)
                self.assertTrue(job.stop_requested)
                self.assertEqual(result["status"], "running")  # only the waiter may confirm the exit


if __name__ == "__main__":
    unittest.main()
