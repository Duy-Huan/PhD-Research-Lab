import _env
import asyncio
import unittest
from unittest.mock import patch
from backend.agent import workflow_worker as W, missions as M
from backend.core import config
import test_autonomy


class WorkflowWorkerTests(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("independent-worker", code_project=None)
        config.save_config({"research_os": {"enabled": True}})
        self.helper = test_autonomy.AutonomyTests()
        from backend.knowledge import research_store as S
        self.helper.tid = S.save_topic(S.TopicInput(title="Scheduler test"))["id"]

    def test_slow_mission_does_not_block_other_five_and_stop_reconciles_it(self):
        mids = [self.helper.approve(self.helper.spec("L3"))["id"] for _ in range(6)]
        project = config.active_project()
        original = M._dispatch
        counts, peak, active = [], 0, 0

        async def run():
            stop = asyncio.Event()
            blocked = asyncio.Event()

            async def dispatch(m, task, key):
                nonlocal active, peak
                active += 1; peak = max(peak, active)
                try:
                    if m["id"] == mids[0]: await blocked.wait()
                    await asyncio.sleep(.01)
                    counts.append((m["id"], task.id))
                    result = await original(m, task, key)
                    if len(counts) >= 10: stop.set()
                    return result
                finally: active -= 1

            with patch.object(W, "list_projects", return_value=[project]), patch.object(M, "_dispatch", side_effect=dispatch):
                await asyncio.wait_for(W.worker(stop), timeout=15)

        asyncio.run(run())
        self.assertLessEqual(peak, 4)
        self.assertEqual(len(set(counts)), 10)
        self.assertEqual(M.get(mids[0])["status"], "interrupted")
        self.assertTrue(all(M.get(mid)["tasks"][1]["status"] == "completed" for mid in mids[1:]))

    def test_project_switch_does_not_redirect_inflight_task(self):
        first_project = config.active_project()
        m = self.helper.approve(self.helper.spec("L3"))
        original = M._dispatch
        second = config.create_project("other-project")

        async def run():
            stop = asyncio.Event()
            async def dispatch(mission, task, key):
                self.assertEqual(config.data_dir(), __import__('pathlib').Path(first_project["data_dir"]))
                config.activate_project(second["data_dir"])
                await asyncio.sleep(.01)
                self.assertEqual(config.data_dir(), __import__('pathlib').Path(first_project["data_dir"]))
                result = await original(mission, task, key)
                stop.set()
                return result
            with patch.object(W, "list_projects", return_value=[first_project, second]), patch.object(M, "_dispatch", side_effect=dispatch):
                await asyncio.wait_for(W.worker(stop), timeout=5)
        asyncio.run(run())
        with config.project_scope(first_project["data_dir"]): self.assertEqual(M.get(m["id"])["tasks"][0]["status"], "completed")
        with self.assertRaises(ValueError): M.get(m["id"])

    def test_empty_and_unavailable_projects_do_not_crash_worker(self):
        async def run():
            stop = asyncio.Event()
            async def finish(): await asyncio.sleep(.3); stop.set()
            with patch.object(W, "list_projects", return_value=[config.active_project()]):
                await asyncio.gather(W.worker(stop), finish())
        asyncio.run(run())

    def test_dispatch_exception_is_observed_and_worker_can_stop_cleanly(self):
        self.helper.approve(self.helper.spec("L3"))
        async def run():
            stop = asyncio.Event()
            async def fail(_mid): raise RuntimeError("Injected dispatch failure")
            with patch.object(W, "list_projects", return_value=[config.active_project()]), patch.object(M, "tick", side_effect=fail), patch.object(W.LOG, "exception", side_effect=lambda *_: stop.set()) as logged:
                await asyncio.wait_for(W.worker(stop), timeout=5)
                logged.assert_called()
        asyncio.run(run())

    def test_cancelled_dispatch_propagates_cancellation(self):
        self.helper.approve(self.helper.spec("L3"))
        async def run():
            async def cancel(_mid): raise asyncio.CancelledError()
            with patch.object(W, "list_projects", return_value=[config.active_project()]), patch.object(M, "tick", side_effect=cancel):
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(W.worker(asyncio.Event()), timeout=5)
        asyncio.run(run())

    def test_unavailable_database_is_logged_instead_of_killing_scheduler(self):
        async def run():
            stop = asyncio.Event()
            with patch.object(W, "list_projects", return_value=[config.active_project()]), patch.object(M, "recover", side_effect=OSError("Injected database unavailable")), patch.object(W.LOG, "exception", side_effect=lambda *_: stop.set()) as logged:
                await asyncio.wait_for(W.worker(stop), timeout=5)
                logged.assert_called()
        asyncio.run(run())
