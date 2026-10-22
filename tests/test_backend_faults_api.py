"""Offline API boundary regressions: disconnected streams, recovery and malformed provider responses."""
import _env  # noqa: F401
import asyncio
import importlib
import io
import json
import types
import unittest
from unittest import mock

from fastapi import HTTPException, UploadFile
from backend.agent import runs, sessions
from backend.api import chat, code, common, library, projects, review, system
from backend.core import config
from backend.paper import review as RX
from backend.providers import models

APP = importlib.import_module("backend.app")


async def records(response):
    out = []
    async for part in response.body_iterator:
        if isinstance(part, bytes):
            part = part.decode()
        out.extend(json.loads(line[6:]) for line in part.splitlines() if line.startswith("data: "))
    return out


class ApiFaults(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("api-faults-" + self._testMethodName[:25])

    async def test_stream_finalize_errors_are_terminal_events(self):
        async def stream(*a, **kw):
            yield "meta", {"text": "answer", "engine": "fake", "note": ""}
        def fail(exc):
            def finalize(meta):
                raise exc
            return finalize
        with mock.patch.object(models, "stream_agent", stream):
            for exc, expected in [(HTTPException(409, "stale revision"), "stale revision"),
                                  (RuntimeError("disk unavailable"), "RuntimeError: disk unavailable")]:
                result = await records(common.sse_job("utility", "", "", fail(exc)))
                self.assertEqual(result[-1], {"type": "error", "detail": expected})
                self.assertFalse(any(x["type"] == "done" for x in result))
        async def empty(*a, **kw):
            yield "meta", {"text": " ", "engine": "fake", "note": ""}
        with mock.patch.object(models, "stream_agent", empty):
            result = await records(common.sse_job("utility", "", "", lambda m: {}))
            self.assertIn("empty answer", result[-1]["detail"])
        with self.assertRaises(HTTPException) as raised:
            await common.call(fail(HTTPException(422, "invalid input")), {})
        self.assertEqual(raised.exception.status_code, 422)

    async def test_streams_stop_on_disconnect_and_deadline(self):
        sid = sessions.create()["id"]
        rid = runs.create("research", "stream fixture", start=False)["id"]
        for module, create, waiter, args in [
            (chat, chat.events_stream, "store.wait_events", (sid,)),
            (system, system.events_stream, "bus.wait", ()),
            (importlib.import_module("backend.api.runs"), importlib.import_module("backend.api.runs").runs_stream,
             "runs.wait_events", (rid,)),
        ]:
            for disconnected in (True, False):
                request = types.SimpleNamespace(headers={}, is_disconnected=mock.AsyncMock(return_value=disconnected))
                clock = types.SimpleNamespace(time=mock.Mock(side_effect=[0, .1, 2]))
                parent, attr = waiter.split(".")
                with mock.patch.object(module, "asyncio", types.SimpleNamespace(get_running_loop=lambda: clock)), \
                     mock.patch.object(getattr(module, parent), attr, return_value=[{"seq": 5, "id": f"{sid}:5", "type": "sample"}]):
                    response = await create(*args, request, timeout=1)
                    output = await records(response)
                self.assertTrue(any(x.get("seq") == 5 for x in output))
                self.assertEqual(request.is_disconnected.await_count, 1)
                if disconnected:
                    self.assertFalse(any(x["type"] == "stream.timeout" for x in output))

    async def test_job_stream_waits_then_stops_without_leaking_a_task(self):
        from backend.execution import sandbox
        job = types.SimpleNamespace(status="running", exit_code=None, since=mock.Mock(return_value=[]))
        request = types.SimpleNamespace(is_disconnected=mock.AsyncMock(side_effect=[False, True]))
        pause = mock.AsyncMock()
        with mock.patch.dict(sandbox.JOBS, {"fault-job": job}), mock.patch.object(code, "asyncio", types.SimpleNamespace(sleep=pause)):
            output = await records(await code.job_stream("fault-job", request))
        self.assertEqual(output, [])
        self.assertEqual(job.since.call_count, 2)
        pause.assert_awaited_once_with(.3)

    async def test_missing_memory_candidate_does_not_break_conversation(self):
        sid = sessions.create()["id"]
        sessions.update(sid, lambda s: s["memory"].append("missing-candidate"))
        result = await chat.get(sid)
        self.assertEqual(result["memory_items"], [])
        self.assertEqual(result["id"], sid)

    async def test_ranking_upload_size_and_encoding_and_sparse_metadata_update(self):
        with self.assertRaises(HTTPException) as raised:
            await library.import_rankings(UploadFile(io.BytesIO(b"x" * (20 * 1024 * 1024 + 1)), filename="large.csv"), 2024)
        self.assertEqual(raised.exception.status_code, 413)
        from backend.knowledge import ranking
        with mock.patch.object(ranking, "import_scimago", return_value={"records": 1}) as imported:
            result = await library.import_rankings(UploadFile(io.BytesIO("Title;Café".encode("cp1252")), filename="r.csv"), 2024)
        self.assertEqual(result["records"], 1)
        self.assertEqual(imported.call_args.args, ("Title;Café", 2024))
        from backend.knowledge.library import save_source
        e = save_source({"title": "A source", "url": "https://example.org/p"})["entry"]
        result = await library.update(e["file"], {"authors": "A;B"})
        self.assertEqual(result["authors"], ["A", "B"])

    async def test_reviewer_prunes_old_personas_and_handles_invalid_issue_json(self):
        rid = RX.create_review("paper.md", ("Title\n\n" + "A reproducible study. " * 80).encode())["id"]
        RX.update_state(rid, lambda s: s["reviewers"].update({"OLD": {"text": "old"}}))
        async def good(*a, **kw):
            yield "meta", {"text": "A review.", "engine": "fake", "note": ""}
        with mock.patch.object(models, "stream_agent", good):
            output = await records(review.review_stage(rid, {"stage": "reviewer"}))
            self.assertEqual(output[-1]["type"], "done")
            self.assertNotIn("OLD", RX.load_state(rid)["reviewers"])
            output = await records(review.review_stage(rid, {"stage": "issues"}))
        self.assertEqual(output[-1]["type"], "error")
        self.assertIn("Could not parse", output[-1]["detail"])
        RX.update_state(rid, lambda s: s.update(issues=[{"id": "I1"}, {"id": "I2"}], fixes={"I1": {"status": "proposed"}}))
        r = await review.review_issue(rid, "I1", {})
        self.assertEqual(r["fix"]["status"], "proposed")
        r = await review.review_issue(rid, "I2", {"status": "not-valid", "revised": 3})
        self.assertIsNone(r["fix"])

    async def test_portable_local_actions_and_nontext_file_response(self):
        with mock.patch.object(projects.sys, "platform", "linux"):
            self.assertEqual(projects.projects_reveal()["path"], str(config.data_dir()))
            self.assertFalse((await system.provider_connect("feynman"))["launched"])
        p = config.data_dir() / "plot.png"
        p.write_bytes(b"png fixture")
        self.assertEqual(projects.project_file("plot.png").media_type, "image/png")

    async def test_startup_and_shutdown_survive_optional_service_failures(self):
        from backend import memory
        from backend.providers import lifecycle, registry
        from backend.execution import sandbox
        with mock.patch.object(registry, "registry", side_effect=RuntimeError("offline CLI")):
            APP._warm()
        with mock.patch.object(sandbox, "stop_all", side_effect=RuntimeError("already stopped")), \
             mock.patch.object(lifecycle, "unload_all_local", mock.AsyncMock(side_effect=RuntimeError("server gone"))):
            await APP._shutdown()
        config.save_config({"lifecycle": {"unload_on_exit": False}})
        with mock.patch.object(lifecycle, "unload_all_local", mock.AsyncMock()) as unload:
            await APP._shutdown()
            unload.assert_not_called()
        async def worker(stop):
            await stop.wait()
        async def broken_reaper(stop):
            raise RuntimeError("reaper unavailable")
        with mock.patch.object(memory, "worker", worker), mock.patch.object(lifecycle, "reaper", broken_reaper), \
             mock.patch.object(runs, "recover_all", side_effect=ValueError("damaged run")), \
             mock.patch.object(APP, "_shutdown", mock.AsyncMock()), mock.patch.object(APP, "_warm"):
            async with APP.lifespan(None):
                await asyncio.sleep(0)
