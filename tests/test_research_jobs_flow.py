"""FQC-COVERAGE-662: deterministic research jobs end to end on a real topic database.

Discovery quota and auto-download, legal-OA download (stored, indexed, parse failure, quota, fetch failure,
cancellation), indexing, sync, failure/interrupt states, scheduling and the background worker. Network sources and
PDF fetching are replaced at the sources/download boundary; PDFs, storage and indexing are real.
"""
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import _env
from backend.knowledge import corpus as K, research_jobs as J, research_store as S
from pdfgen import make_pdf

PDF = make_pdf([[(12, "Diffusion denoising evidence")]])


def record(i, **extra):
    return {"title": f"Denoising paper {i}", "doi": f"10.5555/p{i}", "authors": ["A. Author"], "year": 2024,
            "source": "OpenAlex", "url": f"https://doi.org/10.5555/p{i}", **extra}


class Jobs(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"jobs-{self._testMethodName[:30]}", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Denoising", keywords=["denoising"], metadata_limit=2, pdf_limit=2))["id"]
        self.addCleanup(patch.stopall)
        patch.object(J.asyncio, "sleep", AsyncMock()).start()

    def topic(self, **changes):
        current = S.get_topic(self.tid)
        body = {k: current[k] for k in S.TopicInput.model_fields if k in current}
        return S.save_topic(S.TopicInput(**{**body, **changes}), self.tid)

    def live_job(self):
        """A running download job id (one per test), so cancellation checks see an active job."""
        if getattr(self, "_live", None):
            return self._live
        with S.db() as c:
            jid = S.uid()
            c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)", (jid, self.tid, "download", "running", S.now(), S.now(), "{}"))
        self._live = jid
        return jid

    def run_job(self, kind, payload=None):
        job = J.enqueue(self.tid, kind, payload)
        asyncio.run(J.execute(job))
        return next(j for j in J.list_jobs(self.tid) if j["id"] == job["id"])

    def test_enqueue_validates_kind_selection_and_topic(self):
        for kind, payload, message in (("train", None, "Unsupported"), ("download", {"paper_ids": []}, "Select papers first"),
                                       ("index", {"paper_ids": ["x"] * 101}, "at most 100")):
            with self.subTest(kind), self.assertRaisesRegex(ValueError, message):
                J.enqueue(self.tid, kind, payload)
        with patch("backend.research_engines.workspaces.get", return_value={"topic_id": "other"}):
            with self.assertRaisesRegex(ValueError, "outside this topic"):
                J.enqueue(self.tid, "sync", {"workspace_id": "w"})
        self.topic(archived=True)
        with self.assertRaisesRegex(ValueError, "archived"):
            J.enqueue(self.tid, "discover")

    def test_discovery_keeps_the_unique_quota_and_auto_downloads(self):
        self.topic(auto_download=True)
        found = {"records": [record(1), record(1), record(2), record(3)], "errors": ["arxiv: timeout"], "query": "denoising"}
        with patch.object(J.sources, "discover", AsyncMock(return_value=found)), \
                patch.object(J, "download_papers", AsyncMock(return_value={"downloaded": 2})) as download:
            job = self.run_job("discover")
        result = job["payload"]["result"]
        self.assertEqual((job["status"], result["discovered"], len(result["added"])), ("partial", 2, 2))
        self.assertEqual(result["downloads"], {"downloaded": 2})
        self.assertEqual(download.call_args.args[2], result["added"])
        status = J.schedule_status(S.get_topic(self.tid))
        self.assertFalse(status["enabled"])
        self.assertEqual(status["last_status"], "partial")

    def test_download_stores_indexes_and_reports_each_failure(self):
        ids = K.ingest(self.tid, [record(1), record(2), record(3)])["added"]
        locations = {ids[0]: [{"url": "https://oa.example/1.pdf", "license": "cc-by", "version": "published"}],
                     ids[1]: [], ids[2]: [{"url": "https://oa.example/3.pdf"}]}
        fetched = {"https://oa.example/1.pdf": PDF}

        async def fetch(url, cap):
            if url not in fetched:
                raise ValueError("publisher blocked the request")
            return fetched[url]
        with patch.object(J.sources, "resolve_oa", AsyncMock(side_effect=lambda p: locations[p["id"]])), \
                patch("backend.knowledge.download.pdf_bytes_limited", fetch):
            result = asyncio.run(J.download_papers(self.live_job(), self.tid, ids))
            self.assertEqual((result["downloaded"], result["indexed"], result["deferred_by_quota"]), (1, 1, 1))
            self.assertEqual([e["error"] for e in result["errors"]], ["No verified legal OA PDF found; metadata retained"])
            again = asyncio.run(J.download_papers(self.live_job(), self.tid, [ids[0], ids[2]]))
        self.assertEqual(again["downloaded"], 0, "an already stored version is never fetched again")
        self.assertEqual(again["errors"], [{"paper_id": ids[2], "error": "publisher blocked the request"}])

    def test_download_parse_failure_quota_and_cancellation(self):
        pid = K.ingest(self.tid, [record(1)])["added"][0]
        location = [{"url": "https://oa.example/1.pdf"}]
        with patch.object(J.sources, "resolve_oa", AsyncMock(return_value=location)), \
                patch("backend.knowledge.download.pdf_bytes_limited", AsyncMock(return_value=PDF)), \
                patch.object(J.corpus, "index_document", side_effect=RuntimeError("parser crashed")):
            result = asyncio.run(J.download_papers(self.live_job(), self.tid, [pid]))
        self.assertEqual(result["downloaded"], 1)
        self.assertTrue(result["errors"][0]["error"].startswith("PDF preserved; parse failed"))
        other = K.ingest(self.tid, [record(2)])["added"][0]
        with patch.object(J.sources, "resolve_oa", AsyncMock(return_value=[{"url": "https://oa.example/2.pdf"}])), \
                patch.object(J, "_storage", return_value=10 ** 12):
            result = asyncio.run(J.download_papers(self.live_job(), self.tid, [other]))
        self.assertEqual(result["errors"][0]["error"], "Topic storage quota reached")
        with patch.object(J, "cancelled", return_value=True):
            self.assertEqual(asyncio.run(J.download_papers(self.live_job(), self.tid, [other]))["downloaded"], 0)

    def test_index_sync_failure_and_interrupt_states(self):
        pid = K.ingest(self.tid, [record(1)])["added"][0]
        vid = K.paper(self.tid, pid)["versions"][0]["id"]
        K.store_document(self.tid, pid, vid, PDF, {"url": "https://oa.example/1.pdf", "license": "unknown"})
        self.assertEqual(self.run_job("index", {"paper_ids": [pid]})["payload"]["result"]["indexed"], 1)
        with patch.object(J.corpus, "index_document", side_effect=RuntimeError("bad pdf")):
            self.assertEqual(self.run_job("index", {"paper_ids": [pid]})["status"], "partial")
        with patch("backend.research_engines.workspaces.get", return_value={"topic_id": self.tid}), \
                patch("backend.research_engines.workspaces.sync", return_value={"changed": 1}):
            self.assertEqual(self.run_job("sync", {"workspace_id": "w"})["status"], "completed")
        with patch.object(J.sources, "discover", AsyncMock(side_effect=RuntimeError("all sources down"))):
            failed = self.run_job("discover")
        self.assertEqual((failed["status"], failed["payload"]["error"]), ("failed", "all sources down"))
        with patch.object(J.sources, "discover", AsyncMock(side_effect=asyncio.CancelledError())):
            job = J.enqueue(self.tid, "discover")
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(J.execute(job))
        self.assertEqual(J.list_jobs(self.tid)[0]["status"], "interrupted")
        self.assertEqual(J.retry(job["id"])["payload"]["retry_of"], job["id"])
        with self.assertRaises(ValueError):
            J.cancel("missing")
        claimed = next(j for j in J.list_jobs(self.tid) if j["payload"].get("retry_of") == job["id"])
        J.cancel(claimed["id"])
        asyncio.run(J.execute(claimed))
        self.assertEqual(next(j for j in J.list_jobs(self.tid) if j["id"] == claimed["id"])["status"], "cancelled",
                         "a cancelled job is never claimed")

    def test_scheduled_discovery_respects_cadence_and_disabled_topics(self):
        self.topic(cadence="daily", enabled=True)
        self.assertEqual(J.schedule_status(S.get_topic(self.tid))["next_run"] is not None, True)
        workspaces = [{"id": "w1", "sync_interval_minutes": 30}, {"id": "w2"}]
        with patch("backend.research_engines.workspaces.list_workspaces", return_value=workspaces), \
                patch("backend.research_engines.workspaces.get", return_value={"topic_id": self.tid}):
            J.schedule_due()
            J.schedule_due()  # pending jobs are never duplicated
        kinds = sorted(j["kind"] for j in J.list_jobs(self.tid))
        self.assertEqual(kinds, ["discover", "sync"])
        discover = next(j for j in J.list_jobs(self.tid) if j["kind"] == "discover")
        self.assertTrue(discover["payload"]["scheduled"])
        self.topic(enabled=False)
        asyncio.run(J.execute(discover))
        self.assertEqual(J.list_jobs(self.tid)[-1]["status"] in ("cancelled", "queued"), True)
        job = next(j for j in J.list_jobs(self.tid) if j["id"] == discover["id"])
        self.assertEqual(job["status"], "cancelled", "disabled scheduled discovery is cancelled, not run")
        status = J.schedule_status({**S.get_topic(self.tid), "enabled": True, "cadence": "weekly"})
        expected = datetime.fromisoformat(discover["created"]) + timedelta(days=7)
        self.assertEqual(status["next_run"], expected.isoformat())

    def test_worker_recovers_running_jobs_and_runs_the_queue(self):
        job = J.enqueue(self.tid, "discover", {"dry_run": True})
        stale = J.enqueue(self.tid, "index", {"paper_ids": [K.ingest(self.tid, [record(9)])["added"][0]]})
        with S.db() as c:
            c.execute("UPDATE jobs SET status='running' WHERE id=?", (stale["id"],))

        async def run():
            stop = asyncio.Event()
            original = J.execute

            async def execute_once(queued):
                await original(queued)
                stop.set()
            with patch.object(J, "execute", execute_once), patch("backend.execution.protocols.recover"):
                await asyncio.wait_for(J.worker(stop), 30)
        asyncio.run(run())
        states = {j["id"]: j["status"] for j in J.list_jobs(self.tid)}
        self.assertEqual(states[stale["id"]], "interrupted")
        self.assertEqual(states[job["id"]], "completed")


if __name__ == "__main__":
    unittest.main()
