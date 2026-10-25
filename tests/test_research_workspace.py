"""Offline acceptance for the v5.2 corpus and v5.3 federation; no model/native research runs."""
import _env  # noqa: F401
import asyncio
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.core import config
from backend.knowledge import corpus as K, research_context as C, research_jobs as J, research_store as S, sources
from backend.research_engines import workspaces as W


class ResearchWorkspace(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("federated acceptance", code_project=None)
        self.a = S.save_topic(S.TopicInput(title="Topic A", keywords=["denoising"]))["id"]
        self.b = S.save_topic(S.TopicInput(title="Topic B"))["id"]

    def record(self, **patches):
        return {"title": "MRI denoising", "doi": "https://doi.org/10.1234/TEST", "authors": ["A. Author"], "year": 2024,
                "source": "OpenAlex", "url": "https://doi.org/10.1234/TEST", "pdf_url": "https://example.org/paper.pdf", **patches}

    def ingest(self):
        return K.ingest(self.a, [self.record()])["added"][0]

    def stable_file(self, root, name, content=b"result 1"):
        p = Path(root) / name
        p.write_bytes(content)
        os.utime(p, (time.time() - 5, time.time() - 5))
        return p

    def test_metadata_dedup_versions_topics_and_curation(self):
        pid = self.ingest()
        self.assertEqual(K.ingest(self.a, [self.record(doi="10.1234/test")])["duplicates"], 1)
        self.assertEqual(len(K.paper(self.a, pid)["versions"]), 1)
        K.ingest(self.b, [self.record(source="Semantic Scholar", abstract="Additional abstract")])
        self.assertEqual(K.search(self.b)["papers"][0]["id"], pid)
        self.assertEqual(len(K.paper(self.a, pid)["versions"]), 2)
        K.curate(self.a, [pid], "verify", "Reviewed methods and limitations")
        self.assertEqual(K.paper(self.a, pid)["level"], 4)
        self.assertEqual(K.paper(self.b, pid)["level"], 0)
        self.assertNotIn("10.1234/test", K.bibliography(self.a))
        K.curate(self.a, [pid], "accept")
        self.assertIn("10.1234/test", K.bibliography(self.a))
        self.assertFalse((config.data_dir() / "library.json").exists())
        self.assertFalse((config.data_dir() / "memory/research.json").exists())

    def test_duplicate_conflicts_and_no_title_fuzzy_merge(self):
        p = self.ingest()
        other = K.ingest(self.a, [self.record(doi="10.1234/other")])["added"][0]
        self.assertNotEqual(p, other)
        K.ingest(self.a, [self.record(arxiv_id="2401.12345")])
        result = K.ingest(self.a, [self.record(doi="10.1234/other", arxiv_id="2401.12345")])
        self.assertTrue(result["conflicts"])
        with self.assertRaises(ValueError):
            K.curate(self.a, [p], "verify")
        with self.assertRaises(ValueError):
            K.curate(self.a, [p], "screen")

    def test_pagination_100_papers_no_ai(self):
        with patch("backend.providers.models.call_agent", side_effect=AssertionError("No AI")):
            K.ingest(self.a, [self.record(title=f"Paper {i}", doi=f"10.1234/p{i}") for i in range(120)])
            self.assertEqual(K.search(self.a, limit=25)["total"], 120)
            first = K.search(self.a, limit=25)
            second = K.search(self.a, limit=25, offset=25)
            self.assertFalse({p["id"] for p in first["papers"]} & {p["id"] for p in second["papers"]})
            self.assertEqual(K.search(self.a, q="Paper 119")["total"], 1)
            self.assertEqual(K.search(self.a, source="Semantic Scholar")["total"], 0)

    def test_pdf_parse_exact_evidence_reprocess_and_checksum(self):
        from pdfgen import make_pdf
        pid = self.ingest()
        vid = K.paper(self.a, pid)["versions"][0]["id"]
        raw = make_pdf([[(12, "MRI denoising baseline evidence")]])
        K.store_document(self.a, pid, vid, raw, {"url": "https://example.org/paper.pdf", "license": "unknown"})
        self.assertEqual(K.paper(self.a, pid)["level"], 1)
        K.index_document(self.a, pid, vid)
        K.index_document(self.a, pid, vid)
        evidence = K.retrieve(self.a, "denoising")
        self.assertEqual(evidence[0]["page"], 1)
        self.assertEqual(evidence[0]["version_id"], vid)
        self.assertEqual(K.retrieve(self.b, "denoising"), [])
        self.assertIn("page 1", C.resolve(self.a, evidence[0]["id"])["text"])
        self.assertIsNone(C.resolve(self.b, evidence[0]["id"]))
        with self.assertRaises(ValueError):
            C.validate_sources(self.b, ["paper:" + pid])
        sha = hashlib.sha256(raw).hexdigest()
        K.object_path(sha).write_bytes(b"%PDFcorrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            K.index_document(self.a, pid, vid)

    def test_parser_failure_keeps_file_and_metadata(self):
        pid = self.ingest()
        vid = K.paper(self.a, pid)["versions"][0]["id"]
        K.store_document(self.a, pid, vid, b"%PDF-invalid", {})
        with self.assertRaises(ValueError):
            K.index_document(self.a, pid, vid)
        self.assertEqual(K.paper(self.a, pid)["level"], 1)
        self.assertEqual(K.paper(self.a, pid)["versions"][0]["document"]["status"], "parse_failed")

    def test_workspace_offline_sync_versions_tombstones_idempotency(self):
        a = W.link(self.a, W.WorkspaceInput(engine="openscience"))
        b = W.link(self.b, W.WorkspaceInput(engine="openscience"))
        self.assertNotEqual(a["path"], b["path"])
        path = self.stable_file(a["path"], "paper notes.md")
        self.assertEqual(W.sync(a["id"])["changed"], 1)
        self.assertEqual(W.sync(a["id"])["changed"], 0)
        self.assertEqual(len(W.artifacts(self.a)), 1)
        self.assertEqual(W.artifacts(self.b), [])
        old = W.artifacts(self.a)[0]
        self.stable_file(a["path"], path.name, b"result version 2")
        W.sync(a["id"])
        self.assertEqual(len(W.artifacts(self.a, history=True)), 2)
        self.assertIn("result 1", W.artifact_text(self.a, old["id"])["text"])
        self.assertEqual(W.search(self.a, "version")[0]["version"], 2)
        path.unlink()
        self.assertEqual(W.sync(a["id"])["deleted"], 1)
        self.assertFalse(W.artifacts(self.a)[0]["available"])
        self.assertEqual(W.get(a["id"])["artifact_count"], 0)
        self.assertEqual(len(W.artifacts(self.a, history=True)), 3)
        self.assertEqual(W.sync(a["id"])["deleted"], 0)

    def test_partial_sync_does_not_tombstone_and_large_files_are_metadata_only(self):
        w = W.link(self.a, W.WorkspaceInput(engine="feynman"))
        path = self.stable_file(w["path"], "result.md")
        W.sync(w["id"])
        with patch.object(W, "_inventory", return_value=([], {"complete": False, "errors": [], "unstable": ["result.md"]})):
            self.assertEqual(W.sync(w["id"])["deleted"], 0)
        self.assertTrue(W.artifacts(self.a)[0]["available"])
        large = Path(w["path"]) / "model.ckpt"
        with large.open("wb") as f:
            f.truncate(33 * 1024 * 1024)
        os.utime(large, (time.time()-5, time.time()-5))
        result = W.sync(w["id"])
        model = next(a for a in W.artifacts(self.a) if a["path"] == large.name)
        self.assertIsNone(model["sha256"])
        self.assertEqual(result["skipped"][0]["reason"], "metadata_only: hash/copy budget")

    def test_workspace_paths_symlinks_missing_cli_no_model(self):
        w = W.link(self.a, W.WorkspaceInput(engine="feynman"))
        with self.assertRaises(ValueError):
            W.link(self.b, W.WorkspaceInput(engine="openscience", path=w["path"]))
        with self.assertRaises(ValueError):
            W.link(self.a, W.WorkspaceInput(engine="feynman", path="../bad"))
        with self.assertRaises(ValueError):
            W.link(self.a, W.WorkspaceInput(engine="feynman", path=str(config.data_dir())))
        with patch("backend.execution.tools.which", return_value=None):
            self.assertEqual(W.open_workspace(w["id"])["status"], "unavailable")
        with patch.object(W, "IS_WIN", False), patch("backend.execution.tools.which", return_value="/usr/bin/feynman"), patch("subprocess.Popen", side_effect=AssertionError("No hidden interactive launch")):
            self.assertEqual(W.open_workspace(w["id"])["status"], "terminal_required")
        self.assertFalse(W.get(w["id"])["capabilities"]["external_session_enumeration"])
        # Execute the real reparse escape oracle on unprivileged Windows too.
        with _env.tempfile.TemporaryDirectory(prefix='phdlab-private-link-') as private:
            outside = Path(private) / 'secret.md'
            outside.write_text('private')
            link = Path(w['path']) / 'leak.md'
            try:
                link.symlink_to(outside)
            except OSError:
                if os.name != 'nt': raise
                _env.directory_link(outside.parent, Path(w['path']) / 'leak-directory')
            report = W.sync(w['id'])
            self.assertTrue(report['errors'])
            self.assertFalse(W.artifacts(self.a))

    def test_jobs_dry_run_cancel_retry_failures_and_quota(self):
        job = J.enqueue(self.a, "discover", {"dry_run": True})
        with patch.object(sources, "discover", side_effect=AssertionError("Dry run must be offline")):
            asyncio.run(J.execute(job))
        self.assertEqual(J.list_jobs(self.a)[0]["payload"]["result"]["network_calls"], 0)
        job = J.enqueue(self.a, "discover")
        with self.assertRaises(ValueError):
            J.enqueue(self.a, "discover")
        J.cancel(job["id"])
        retried = J.retry(job["id"])
        with patch.object(sources, "discover", new=AsyncMock(return_value={"records": [self.record(doi=f"10.1234/{i}") for i in range(80)], "query": "MRI", "errors": []})):
            asyncio.run(J.execute(retried))
        self.assertEqual(K.search(self.a)["total"], 30)

    def test_no_oa_no_download_no_memory_promotion(self):
        pid = K.ingest(self.a, [self.record(source="Crossref", pdf_url="https://example.org/paywall.pdf")])["added"][0]
        job = J.enqueue(self.a, "download", {"paper_ids": [pid]})
        with patch.object(sources, "resolve_oa", new=AsyncMock(return_value=[])), patch("backend.knowledge.download.pdf_bytes_limited", side_effect=AssertionError("No OA")):
            asyncio.run(J.execute(job))
        self.assertEqual(J.list_jobs(self.a)[0]["status"], "partial")
        self.assertEqual(K.paper(self.a, pid)["level"], 0)
        f = C.finding(self.a, "Candidate claim", ["paper:" + pid])
        self.assertEqual(f["status"], "pending")
        C.review_finding(self.a, f["id"], True, "Reviewed with caveats")
        self.assertEqual(C.findings(self.a)[0]["status"], "approved")
        self.assertFalse((config.data_dir() / "memory/research.json").exists())

    def test_topic_context_no_leak_and_api_references(self):
        from backend.agent import sessions, policy, context
        pid = self.ingest()
        s = sessions.create("Scoped topic")
        s["topic_id"] = self.b
        s["selected_sources"] = ["paper:" + pid]
        eff = policy.effective(s, {"context_mode": "expanded", "mcp_tools": []})
        with patch("backend.agent.project_context.Adapter.state", side_effect=AssertionError("Project context must not leak")), patch.object(context, "_retrieved", side_effect=AssertionError("Global memory must not leak")):
            compiled = context.compile(s, "denoising", eff)
        self.assertNotIn("MRI denoising", compiled["text"])
        self.assertTrue(compiled["manifest"]["omitted"])
        self.assertEqual(policy.values(eff)["mcp_tools"], ["-"])

    def test_api_scopes_validation_and_no_ai_quick_action(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        from backend.agent import orchestrator, sessions
        client = TestClient(app)
        pid = self.ingest()
        session = client.post("/api/chat/sessions", json={"topic_id": self.a}).json()
        self.assertEqual(session["topic_id"], self.a)
        with patch.object(orchestrator, "_spawn", side_effect=AssertionError("No provider for quick actions")):
            response = client.post(f"/api/chat/sessions/{session['id']}/turns", json={"text": "/find"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(client.post("/api/research/topics", json={"title": "bad", "pdf_limit": 100}).status_code, 422)
        self.assertEqual(client.get(f"/api/research/topics/{self.b}/papers/{pid}").status_code, 400)
        other = client.post("/api/chat/sessions", json={"topic_id": self.b}).json()
        self.assertEqual(client.post(f"/api/chat/sessions/{other['id']}/turns", json={"text": "/review", "overrides": {"sources": ["paper:" + pid]}}).status_code, 400)
        self.assertEqual(client.post(f"/api/research/topics/{self.a}/findings", json={"text":"claim", "source_evidence_ids":["paper:" + pid]}).status_code, 200)
        old_id = S.project_id()
        _env.fresh_project("another real project", code_project=None)
        self.assertNotEqual(old_id, S.project_id())
        self.assertEqual(client.get(f"/api/research/topics/{self.a}").status_code, 400)

    def test_zotero_readonly_import_and_optional_adapters(self):
        from backend.plugins.local_research import import_zotero, capabilities
        records = [{"title":f"Zotero paper {i}", "DOI":f"10.1234/z{i}", "author":[{"given":"Alice","family":"Smith"}], "issued":{"date-parts":[[2023]]}} for i in range(20)]
        self.assertEqual(len(import_zotero(self.a, records)["added"]), 20)
        self.assertEqual(import_zotero(self.a, records)["duplicates"], 20)
        self.assertEqual(K.search(self.a)["papers"][0]["authors"], ["Alice Smith"])
        self.assertTrue(all(not p["auto_install"] for p in capabilities()))
        self.assertNotIn("10.1234/z", K.bibliography(self.a))
        self.assertFalse((config.data_dir() / "library.json").exists())

    def test_real_optuna_bounded_resume(self):
        from backend.plugins.local_research import run_optuna
        try:
            import optuna
        except ImportError:
            self.skipTest("Optional Optuna not installed")
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        def objective(trial):
            return (trial.suggest_float("x", -2, 2) - 0.5) ** 2
        with self.assertRaises(ValueError):
            run_optuna(objective, name="study")
        first = run_optuna(objective, name="study", trials=3, approved=True)
        resumed = run_optuna(objective, name="study", trials=10, approved=True)
        self.assertEqual(first["trials_total"], 3)
        self.assertEqual(resumed["trials_before"], 3)
        self.assertEqual(resumed["trials_total"], 10)
        self.assertIsNotNone(resumed["best_value"])

    def test_server_side_storage_budget_and_content_dedup(self):
        from pdfgen import make_pdf
        profile = S.get_topic(self.a)
        for key in ("id", "created", "updated"):
            profile.pop(key)
        S.save_topic(S.TopicInput(**{**profile, "storage_mb": 1, "max_pdf_mb": 1}), self.a)
        pid = self.ingest()
        vid = K.paper(self.a, pid)["versions"][0]["id"]
        with self.assertRaisesRegex(ValueError, "file-size"):
            K.store_document(self.a, pid, vid, b"%PDF" + b"x" * (1024*1024), {})
        raw = make_pdf([[(12, "Small verified test input")]])
        K.store_document(self.a, pid, vid, raw, {})
        other = K.ingest(self.a, [self.record(doi="10.1234/dedup", title="Different paper record")])["added"][0]
        other_vid = K.paper(self.a, other)["versions"][0]["id"]
        K.store_document(self.a, other, other_vid, raw, {})
        with S.db() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM documents").fetchone()[0], 1)
        self.assertEqual(J._storage(self.a), len(raw))

    def test_new_oa_version_does_not_create_another_paper(self):
        pid = K.ingest(self.a, [self.record(doi="", source="Crossref")])["added"][0]
        vid = K.add_oa_version(self.a, pid, {"url":"https://example.org/authorized.pdf", "provider":"Unpaywall", "version":"acceptedVersion", "access":"open"})
        self.assertEqual(K.search(self.a)["total"], 1)
        self.assertEqual(K.paper(self.a, pid)["versions"][-1]["id"], vid)

    def test_native_launch_argv_duplicate_detection_and_no_api_keys(self):
        import subprocess
        from unittest.mock import MagicMock
        w = W.link(self.a, W.WorkspaceInput(engine="openscience"))
        proc = MagicMock(pid=1234)
        proc.wait.side_effect = subprocess.TimeoutExpired("openscience", 0.5)
        proc.poll.return_value = None
        with patch.object(W, "IS_WIN", False), patch("backend.execution.tools.which", return_value="C:/Program Files/Engine/openscience.exe"), \
             patch("backend.execution.tools.node_argv", return_value=["C:/Program Files/Engine/openscience.exe"]), \
             patch("subprocess.Popen", return_value=proc) as launch:
            result = W.open_workspace(w["id"])
            self.assertEqual(result["status"], "started")
            self.assertEqual(launch.call_args.args[0], ["C:/Program Files/Engine/openscience.exe", "web", w["path"]])
            self.assertFalse(launch.call_args.kwargs["shell"])
            self.assertNotIn("OPENAI_API_KEY", launch.call_args.kwargs["env"])
            self.assertEqual(W.open_workspace(w["id"])["status"], "already_running")
            self.assertEqual(launch.call_count, 1)
        W._processes.pop((str(config.data_dir()), w["id"]), None)

    def test_windows_engine_opens_independent_terminal_and_editor_uses_registered_root(self):
        import base64
        import subprocess
        from unittest.mock import MagicMock
        w = W.link(self.a, W.WorkspaceInput(engine="feynman"))
        proc = MagicMock(pid=4321)
        proc.wait.side_effect = subprocess.TimeoutExpired("powershell", 0.5)
        proc.poll.return_value = None
        argv = ["C:/Program Files/node.exe", "D:/engine's files/feynman.js"]
        with patch.object(W, "IS_WIN", True), patch("backend.execution.tools.node_argv", return_value=argv), patch("subprocess.Popen", return_value=proc) as launch:
            result = W.open_workspace(w["id"])
            self.assertEqual(result["status"], "started")
            args = launch.call_args.args[0]
            self.assertEqual(args[:4], ["powershell.exe", "-NoLogo", "-NoProfile", "-NoExit"])
            command = base64.b64decode(args[-1]).decode("utf-16le")
            self.assertIn("engine''s files", command)
            self.assertIn("'--cwd'", command)
            self.assertNotIn("--prompt", command)
            self.assertEqual(launch.call_args.kwargs["cwd"], w["path"])
            self.assertFalse(launch.call_args.kwargs["shell"])
            self.assertNotIn("OPENAI_API_KEY", launch.call_args.kwargs["env"])
            self.assertEqual(result["log"], "")
            self.assertEqual(W.open_workspace(w["id"])["status"], "already_running")
            self.assertEqual(launch.call_count, 1)
        W._processes.pop((str(config.data_dir()), w["id"]), None)
        with patch("backend.execution.vscode.vscode_cli", return_value="code.exe"), patch("backend.execution.tools.run_cli", return_value=(0, "")) as run:
            self.assertEqual(W.open_editor(w["id"])["status"], "started")
            self.assertEqual(run.call_args.args[0], ["code.exe", "--new-window", w["path"]])
        with patch("backend.execution.vscode.vscode_cli", return_value=None):
            with self.assertRaisesRegex(ValueError, "VS Code not found"):
                W.open_editor(w["id"])
        with patch("backend.execution.vscode.vscode_cli", return_value="code.exe"), patch("backend.execution.tools.run_cli", return_value=(1, "")):
            with self.assertRaisesRegex(ValueError, "could not open"):
                W.open_editor(w["id"])
        with self.assertRaisesRegex(ValueError, "not found"):
            W.open_editor("unknown-workspace")

    def test_relink_and_snapshot_search_preserve_identity_history(self):
        w = W.link(self.a, W.WorkspaceInput(engine="openscience"))
        self.stable_file(w["path"], "offline.md", b"Denoising offline result: unverified")
        W.sync(w["id"])
        newpath = Path(w["path"]).parent / "Relocated workspace with spaces"
        newpath.mkdir()
        self.stable_file(newpath, "offline.md", b"Denoising offline result: unverified")
        relinked = W.relink(w["id"], W.WorkspaceInput(engine="openscience", path=str(newpath), sync_interval_minutes=60))
        self.assertEqual(relinked["id"], w["id"])
        self.assertTrue((Path(w["path"])/"offline.md").exists())
        self.assertEqual(W.sync(w["id"])["changed"], 0)
        results = K.retrieve(self.a, "Denoising")
        self.assertTrue(any(r["id"].startswith("artifact:") for r in results))
        self.assertEqual(K.retrieve(self.b, "Denoising"), [])

    def test_schedules_disabled_and_restart_recovery(self):
        pid = self.ingest()
        old = J.enqueue(self.a, "discover")
        J._update(old["id"], "running", old["payload"])
        queued = J.enqueue(self.a, "download", {"paper_ids":[pid], "dry_run":True})
        async def check():
            stop = asyncio.Event()
            execute = J.execute
            async def finish(job):
                await execute(job)
                stop.set()
            with patch.object(J, "list_projects", return_value=[config.active_project()]), patch.object(J, "schedule_due"), patch.object(J, "execute", finish), patch.object(sources, "discover", side_effect=AssertionError("No automatic replay")):
                await asyncio.wait_for(J.worker(stop), timeout=5)
        asyncio.run(check())
        statuses = {j["id"]:j["status"] for j in J.list_jobs(self.a)}
        self.assertEqual(statuses[old["id"]], "interrupted")
        self.assertEqual(statuses[queued["id"]], "completed")
        before = len(J.list_jobs(self.b))
        J.schedule_due()
        self.assertEqual(len(J.list_jobs(self.b)), before)

    def test_crossref_and_unpaywall_official_response_contracts(self):
        import httpx
        from backend.knowledge import websearch as WS
        real = httpx.AsyncClient
        def handler(req):
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message":{"items":[{"DOI":"10.1234/TEST", "title":["Paper"], "author":[{"given":"A","family":"B"}], "published":{"date-parts":[[2024]]}, "link":[{"URL":"https://example.org/paywall.pdf"}]}]}})
            return httpx.Response(200, json={"is_oa":True,"updated":"2026-10-21", "oa_locations":[{"url_for_pdf":"https://example.org/legal.pdf","license":"cc-by","version":"acceptedVersion"}]})
        config.save_config({"search":{"mailto":"researcher@example.org"}})
        with patch.object(WS, "_client", lambda *args, **kwargs: real(transport=httpx.MockTransport(handler))):
            records = asyncio.run(sources.crossref("paper", 10, 2020, {}))
            self.assertEqual(records[0]["doi"], "10.1234/test")
            self.assertEqual(records[0]["pdf_url"], "")
            oa = asyncio.run(sources.resolve_oa({"doi":"10.1234/test"}))
            self.assertEqual(oa[0]["license"], "cc-by")
            self.assertEqual(oa[0]["version"], "acceptedVersion")

    def test_discovery_failure_isolated_and_topic_exclusions_apply(self):
        with patch.object(sources.WS, "openalex", new=AsyncMock(side_effect=RuntimeError("offline"))), \
             patch.object(sources.WS, "arxiv", new=AsyncMock(return_value=[self.record(title="excluded paper")])), \
             patch.object(sources.WS, "semantic_scholar", new=AsyncMock(return_value=[])), \
             patch.object(sources, "crossref", new=AsyncMock(return_value=[self.record(title="allowed paper")])):
            profile = S.get_topic(self.a)
            profile["exclusions"] = ["excluded"]
            result = asyncio.run(sources.discover(profile))
            self.assertEqual(len(result["records"]), 1)
            self.assertTrue(result["errors"])

    def test_docling_requires_explicit_local_models(self):
        from backend.plugins import document_parser
        with patch("subprocess.run", side_effect=AssertionError("Do not download models or launch parser implicitly")):
            with self.assertRaisesRegex(ValueError, "local artifacts"):
                document_parser.pages(Path("fixture.pdf"))

    def test_new_version_resets_review_without_losing_prior_attestation(self):
        pid = self.ingest()
        K.curate(self.a, [pid], "verify", "Reviewed version one")
        K.ingest(self.a, [self.record(abstract="A new version's claims")])
        p = K.paper(self.a, pid)
        self.assertEqual(p["level"], 0)
        self.assertEqual(p["association"]["attestation"]["note"], "Reviewed version one")
        self.assertEqual(len(p["association"]["attestation"]["version_ids"]), 1)
        self.assertIn("review_reset", p["association"])

    def test_reparse_keeps_historical_citation_ids(self):
        from pdfgen import make_pdf
        pid = self.ingest()
        vid = K.paper(self.a, pid)["versions"][0]["id"]
        raw = make_pdf([[(12, "First extraction evidence")]])
        K.store_document(self.a, pid, vid, raw, {})
        K.index_document(self.a, pid, vid)
        old = K.retrieve(self.a, "First")[0]["id"]
        with patch("backend.knowledge.pdf_indexer.pages", return_value=(["Revised extraction evidence"],1)):
            K.index_document(self.a, pid, vid)
        self.assertIn("First extraction", C.resolve(self.a, old)["text"])
        self.assertIn("Revised extraction", K.retrieve(self.a, "Revised")[0]["text"])
        with self.assertRaisesRegex(ValueError, "new source version"):
            K.store_document(self.a, pid, vid, raw + b"changed", {})


if __name__ == "__main__":
    unittest.main()
