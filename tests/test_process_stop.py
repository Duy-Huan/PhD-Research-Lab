"""Cancellation survives failed Windows tree termination without claiming an unobserved exit."""
import _env
import unittest
from unittest import mock

from backend.execution import sandbox


class ProcessStop(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("process-stop")

    def test_tree_stop_failure_falls_back_to_the_owned_process_handle(self):
        # 6.6.1: taskkill /T was replaced by the identity-checked stop_tree (reused parent PIDs killed CI runners).
        for failure in (OSError("access denied"), None):
            with self.subTest(failure=repr(failure)):
                job = sandbox.Job("run", "python slow.py")
                job.status, job.mode = "running", "local"
                job.proc = mock.Mock(pid=123, poll=mock.Mock(return_value=None))
                sandbox.JOBS[job.id] = job
                self.addCleanup(sandbox.JOBS.pop, job.id, None)
                with mock.patch.object(sandbox, "IS_WIN", True), mock.patch.object(sandbox.subprocess, "run") as run, \
                        mock.patch("backend.execution.processes.stop_tree", side_effect=failure) as stop:
                    result = sandbox.stop_job(job.id)
                stop.assert_called_once_with(job.proc)
                run.assert_not_called()  # no taskkill
                self.assertEqual(job.proc.kill.call_count, 1 if failure else 0)
                self.assertTrue(job.stop_requested)
                self.assertEqual(result["status"], "running")  # only the waiter may confirm the exit


if __name__ == "__main__":
    unittest.main()
