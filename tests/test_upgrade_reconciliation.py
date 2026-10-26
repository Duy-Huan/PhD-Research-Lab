"""Regression contracts for gaps found by comparing every upgrade specification."""
import _env
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx

from backend.agent import research_os as O, missions as M
from backend.agent.mission_contracts import MissionSpec
from backend.core import config
from backend.knowledge import corpus as K, research_store as S, source_packs as P, sources


class UpgradeReconciliation(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("Upgrade reconciliation", code_project=None)
        config.save_config({"memory": {"embed_engine": "hashing"}, "research_os": {"enabled": True}})
        self.a = _env.legacy_topic(S.TopicInput(title="MRI"))["id"]
        self.b = _env.legacy_topic(S.TopicInput(title="CT"))["id"]

    def ingest(self, **changes):
        return K.ingest(self.a, [{"title": "MRI restoration", "doi": "10.1234/mri", "year": 2025,
                                  "venue": "Test venue", "publication_type": "article", "citations": 7, **changes}])["paper_ids"][0]

    def test_filters_tags_citation_sort_and_scope(self):
        pid = self.ingest(flags=["preprint"])
        other = self.ingest(doi="10.1234/other", citations=30, year=2024, venue="Other")
        K.tag_papers(self.a, [pid, pid], ["baseline", " MRI "])
        K.associate(self.a, self.b, [pid])
        self.assertEqual(K.search(self.a, tag="MRI", venue="Test", max_year=2025, publication_type="article", pdf=False, flag="preprint")["total"], 1)
        self.assertEqual(K.search(self.b, tag="MRI")["total"], 0)
        self.assertEqual(K.search(self.a, tag="MR")["total"], 0)
        self.assertEqual(K.search(self.a, max_year=2024)["total"], 1)
        self.assertEqual(K.search(self.a, pdf=True)["total"], 0)
        self.assertEqual(K.search(self.a, sort="citations")["papers"][0]["id"], other)
        K.tag_papers(self.a, [pid], ["MRI"], remove=True)
        self.assertEqual(K.search(self.a, tag="MRI")["total"], 0)
        with self.assertRaises(ValueError): K.search(self.a, sort="sql injection")
        with self.assertRaises(ValueError): K.tag_papers(self.b, [other], ["cross-topic"])
        with self.assertRaises(ValueError): K.tag_papers(self.a, [pid], [""])
        with self.assertRaises(ValueError): K.tag_papers(self.a, [pid], list(map(str, range(30))))
        self.assertEqual(K.paper(self.a, pid)["association"]["tags"], ["baseline"])

    def test_missing_enrichment_does_not_erase_known_metadata(self):
        pid = self.ingest(peer_review_status="peer_reviewed")
        self.ingest(source="Crossref", citations=None, publication_type="unknown")
        p = K.paper(self.a, pid)
        self.assertEqual(p["citations"], 7)
        self.assertEqual(p["peer_review_status"], "peer_reviewed")
        self.assertEqual(p["publication_type"], "article")
        with self.assertRaises(ValueError): _env.legacy_topic(S.TopicInput(title="Unknown", sources=["invented"]))
        for name in P.IDS:
            self.assertIn(name, _env.legacy_topic(S.TopicInput(title=name, sources=[name]))["sources"])

    def test_reingesting_legacy_version_without_references_preserves_l4(self):
        import hashlib
        pid=self.ingest()
        K.curate(self.a,[pid],"verify","Prior researcher attestation")
        with S.db() as c:
            row=c.execute("SELECT * FROM versions WHERE paper_id=?",(pid,)).fetchone()
            import json
            payload=json.loads(row["payload"]);payload.pop("references",None)
            identity={k:v for k,v in payload.items() if k!="retrieved_at"}
            c.execute("UPDATE versions SET signature=?,payload=? WHERE id=?",(hashlib.sha256(S.dumps(identity).encode()).hexdigest(),S.dumps(payload),row["id"]))
        self.ingest()
        self.assertEqual(len(K.paper(self.a,pid)["versions"]),1)
        self.assertEqual(K.paper(self.a,pid)["level"],4)

    def test_pmid_dedup_without_doi_and_unknown_citations(self):
        pid = self.ingest(doi="", pmid="12345", citations=None)
        other = self.ingest(doi="", pmid="12345", source="Europe PMC", citations=None)
        self.assertEqual(pid, other)
        self.assertIsNone(K.paper(self.a, pid)["citations"])
        self.assertIsNone(K.normalize({"title": "Bad count", "citations": True})["citations"])

    def test_hybrid_exact_pages_retraction_and_parser_recovery(self):
        from pdfgen import make_pdf
        pid = self.ingest(flags=["retracted"])
        vid = K.paper(self.a, pid)["versions"][0]["id"]
        K.store_document(self.a, pid, vid, make_pdf([[(12, "Denoising restoration MRI evidence")]]), {})
        K.index_document(self.a, pid, vid)
        with patch("backend.providers.models.call_agent", side_effect=AssertionError("No synthesis")):
            hits = K.retrieve(self.a, "MRI", paper_id=pid)
            self.assertEqual(hits[0]["page"], 1)
            self.assertEqual(hits[0]["version_id"], vid)
            self.assertIn("retracted", hits[0]["flags"])
            self.assertIn("lexical, not neural", hits[0]["retrieval"]["vector_engine"])
            self.assertFalse(hits[0]["retrieval"]["external_reranker"])
            self.assertEqual(K.retrieve(self.b, "MRI"), [])
            with self.assertRaises(ValueError): K.retrieve(self.b, "MRI", paper_id=pid)
        from backend.memory.embeddings import Embedder
        embedder = Embedder(config.load_config())
        original = embedder.embed_unit
        with patch("backend.knowledge.evidence_retrieval.get_embedder", return_value=embedder), patch.object(embedder, "embed_unit", side_effect=[RuntimeError("local model offline"), original([hits[0]["text"], "MRI"])]):
            fallback = K.retrieve(self.a, "MRI", paper_id=pid)
        self.assertEqual(fallback[0]["retrieval"]["embedding_error"], "RuntimeError")

    def spec(self, tid, charter):
        return MissionSpec.model_validate({"topic_id": tid, "objective": "Inspect metadata", "control": {
            "charter_id": charter["id"], "charter_digest": charter["digest"], "success_criteria": ["Evidence inspected"],
            "end_date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
            "tasks": [{"id": "inspect", "capability": "paper.inspect"}]})

    def test_charter_dependency_requires_review_and_report_includes_all_papers(self):
        ch = O.create_charter(O.ProjectCharter(goal="Restoration", topics=[O.TopicGoal(topic_id=self.a, goal="MRI"), O.TopicGoal(topic_id=self.b, goal="CT", depends_on=[self.a])], retrieval=[O.RetrievalGrant(requester_topic=self.b, source_topic=self.a)]))
        parent = M.create(self.spec(self.a, ch)); child = M.create(self.spec(self.b, ch))
        with S.db() as c:
            self.assertIn("dependency", O.gate(c, M._get(c, child["id"])))
            c.execute("UPDATE missions SET status='awaiting_review' WHERE id=?", (parent["id"],))
            self.assertIn("dependency", O.gate(c, M._get(c, child["id"])))
        O.review(self.a, parent["id"], "Human reviewed the upstream evidence")
        with S.db() as c: self.assertEqual(O.gate(c, M._get(c, child["id"])), "")
        K.ingest(self.a, [{"title": f"Paper {i}", "doi": f"10.1234/p{i}"} for i in range(112)])
        self.assertEqual(len(O.report(self.a, parent["id"])["papers"]), 112)
        self.assertEqual(len(O.report(self.b, child["id"])["related_topics"][0]["papers"]), 112)

    def pack(self, name, data, capture=None):
        def handler(req):
            if capture is not None: capture.append(req)
            return httpx.Response(200, json=data, request=req)
        client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async def immediate(name, op): return await op()
        with patch.object(P.WS, "_client", client), patch.object(sources, "_paced", immediate):
            return asyncio.run(P.search(name, "MRI", 10, 2019, {}))

    def test_zenodo_restricted_files_never_become_oa(self):
        rec = {"metadata": {"title": "MRI", "access_right": "restricted", "publication_date": "2025-01-01", "creators": [{"name": "A"}], "license": {"id": "cc-by"}}, "files": [{"key": "paper.pdf", "links": {"self": "https://zenodo.org/api/files/p.pdf"}}]}
        self.assertEqual(self.pack("zenodo", {"hits": {"hits": [rec]}})[0]["oa_locations"], [])
        rec["metadata"]["access_right"] = "open"
        result = self.pack("zenodo", {"hits": {"hits": [rec]}})[0]
        self.assertEqual(result["oa_locations"][0]["license"], "cc-by")
        self.assertNotIn("peer_reviewed", K.normalize(result)["flags"])

    def test_europe_pmc_pdf_requires_article_and_location_oa(self):
        record = {"title": "MRI", "isOpenAccess": "Y", "isRetracted": "Y", "pmid": "123", "citedByCount": "12",
                  "fullTextUrlList": {"fullTextUrl": [{"documentStyle": "pdf", "availabilityCode": "OA", "url": "https://europepmc.org/p.pdf"}, {"documentStyle": "pdf", "availabilityCode": "S", "url": "https://publisher.org/pay.pdf"}]}}
        found = self.pack("europe_pmc", {"resultList": {"result": [record]}})[0]
        self.assertEqual(len(found["oa_locations"]), 1)
        self.assertEqual(found["flags"], ["retracted"])
        self.assertEqual(found["citations"], 12)
        record["isOpenAccess"] = "N"
        self.assertEqual(self.pack("europe_pmc", {"resultList": {"result": [record]}})[0]["oa_locations"], [])

    def test_hal_public_deposited_files_and_openreview_visibility(self):
        found = self.pack("hal", {"response": {"docs": [{"title_s": ["MRI"], "fileMain_s": "https://hal.science/p.pdf", "authFullName_s": ["A"]}]}})
        self.assertEqual(found[0]["oa_locations"][0]["version"], "repository deposit")
        note = {"id": "n1", "readers": ["everyone"], "content": {"title": {"value": "MRI"}, "authors": {"value": ["A"]}, "pdf": {"value": "/pdf?id=n1"}}}
        hidden = {**note, "id": "private", "readers": ["private-group"]}
        deleted = {**note, "ddate": 100}
        public = self.pack("openreview", {"notes": [hidden, deleted, note]})
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["peer_review_status"], "unverified_submission")
        self.assertTrue(public[0]["oa_locations"][0]["url"].startswith("https://openreview.net/"))
        note["content"].pop("pdf")
        self.assertEqual(self.pack("openreview", {"notes": [note]})[0]["oa_locations"], [])

    def test_venue_pack_exact_identity_and_no_invented_pdfs(self):
        captured = []
        def handler(req):
            captured.append(req)
            if req.url.path == "/sources":
                return httpx.Response(200, json={"results": [{"id": "https://openalex.org/S123", "display_name": "Proceedings of Machine Learning Research"}, {"id": "https://openalex.org/S999", "display_name": "Unrelated"}]})
            return httpx.Response(200, json={"results": [{"display_name": "MRI", "publication_year": 2025, "is_retracted": True, "locations": [{"is_oa": False, "pdf_url": "https://publisher.org/closed.pdf"}, {"is_oa": True, "pdf_url": "https://proceedings.mlr.press/p.pdf", "version": "publishedVersion"}]}]})
        async def immediate(name, op): return await op()
        with patch.object(P.WS, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))), patch.object(sources, "_paced", immediate):
            found = asyncio.run(P.search("pmlr", "MRI", 10, 2019, {}))
        self.assertEqual(len(found[0]["oa_locations"]), 1)
        self.assertIn("locations.source.id:https://openalex.org/S123", captured[-1].url.params["filter"])
        self.assertNotIn("S999", captured[-1].url.params["filter"])
        with self.assertRaisesRegex(ValueError, "no exact"):
            self.pack("pmlr", {"results": []})

    def test_federated_packs_fail_independently_and_remain_no_llm(self):
        profile = S.get_topic(self.a); profile["sources"] = ["zenodo", "hal"]
        async def search(name, *args):
            if name == "hal": raise httpx.ConnectError("Offline")
            return [{"title": "MRI", "year": 2025}]
        async def immediate(name, op): return await op()
        with patch.object(P, "search", search), patch.object(sources, "_paced", immediate), patch("backend.providers.models.call_agent", side_effect=AssertionError("No AI")):
            found = asyncio.run(sources.discover(profile))
        self.assertEqual(len(found["records"]), 1)
        self.assertTrue(found["errors"])

    def test_schedules_ignore_dry_runs_and_global_job_window(self):
        from backend.knowledge import research_jobs as J
        profile = S.get_topic(self.a)
        _env.legacy_topic(S.TopicInput.model_validate({k:v for k,v in {**profile,"cadence":"weekly","enabled":True}.items() if k not in ("id","created","updated")}), self.a)
        job = J.enqueue(self.a, "discover", {"dry_run": True})
        J._update(job["id"], "completed", job["payload"])
        self.assertIsNone(J.schedule_status(S.get_topic(self.a))["last_run"])
        actual = J.enqueue(self.a, "discover")
        J._update(actual["id"], "completed", {})
        with S.db() as c:
            for _ in range(120):
                at=S.now()
                c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)", (S.uid(),self.b,"discover","completed",at,at,"{}"))
        J.schedule_due()
        with S.db() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM jobs WHERE topic_id=?",(self.a,)).fetchone()[0],2)

    def test_paper_vectors_never_use_remote_memory_embedding_config(self):
        from backend.knowledge.evidence_retrieval import rank
        config.save_config({"ollama_base_url":"https://unrelated-provider.example/api", "memory":{"embed_engine":"ollama","embed_model":"private-model"}})
        with patch("httpx.post", side_effect=AssertionError("No remote paper transfer")), patch("httpx.get", side_effect=AssertionError("No remote probe")), S.db() as c:
            ids, diagnostics = rank(c,self.a,"MRI",[])
        self.assertEqual(ids,[])
        self.assertTrue(diagnostics["remote_embedding_refused"])
        self.assertIn("lexical, not neural",diagnostics["vector_engine"])

    def test_http_filters_tags_sources_and_artifact_isolation(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        from backend.research_engines import workspaces as W
        client=TestClient(app)
        pid=self.ingest()
        base=f"/api/research/topics/{self.a}"
        with patch("backend.providers.models.call_agent",side_effect=AssertionError("No inference")):
            response=client.post(base+"/papers/bulk",json={"paper_ids":[pid],"action":"tag","tags":["MRI"]})
            self.assertEqual(response.status_code,200,response.text)
            response=client.get(base+"/papers",params={"tag":"MRI","max_year":2025,"pdf":False,"sort":"citations"})
            self.assertEqual(response.json()["total"],1)
            self.assertEqual(client.get("/api/research/sources").json()["providers"],list(sources.PROVIDER_IDS))
            w=W.link(self.a,W.WorkspaceInput(engine="phdlab"))
            from pathlib import Path
            import os,time
            path=Path(w["path"])/"result.md";path.write_text("Actual result",encoding="utf-8")
            os.utime(path,(time.time()-5,time.time()-5));W.sync(w["id"])
            aid=W.artifacts(self.a)[0]["id"]
            self.assertIn("Actual result",client.get(base+"/artifacts/"+aid).json()["text"])
            self.assertEqual(client.get(f"/api/research/topics/{self.b}/artifacts/{aid}").status_code,400)
            self.assertEqual(client.get(f"/api/research/topics/{self.b}/evidence",params={"q":"MRI","paper_id":pid}).status_code,400)

    def test_citation_graph_has_versioned_sources_and_no_cross_topic_ids(self):
        target = self.ingest(openalex_id="https://openalex.org/W123")
        source = self.ingest(doi="10.1234/citing", references=["https://openalex.org/W123", "10.1234/mri", "https://untrusted.example/not-an-identifier", "10.1234/unknown"])
        graph = K.citation_graph(self.a)
        self.assertEqual(len(graph["edges"]), 3)
        self.assertEqual({e["cited_paper_id"] for e in graph["edges"]}, {target, None})
        self.assertTrue(all(e["version_id"] for e in graph["edges"]))
        K.associate(self.a,self.b,[source])
        isolated=K.citation_graph(self.b)
        self.assertTrue(all(e["cited_paper_id"] is None for e in isolated["edges"]))
        self.assertNotIn(target,[n["id"] for n in isolated["nodes"]])
        self.assertEqual(self.ingest(doi="10.1234/mri",openalex_id="W123"),target)
        with self.assertRaises(ValueError): self.ingest(references="invalid schema")

    def test_zotero_local_sync_is_read_only_bounded_and_idempotent(self):
        from backend.plugins.local_research import sync_zotero
        original=httpx.AsyncClient; requests=[]
        def handler(req):
            requests.append(req)
            self.assertEqual(req.method,"GET")
            self.assertEqual(req.url.host,"127.0.0.1")
            start=int(req.url.params["start"])
            data=[{"data":{"title":f"Zotero item {i}","DOI":f"10.1234/zot{i}"}} for i in range(start,min(start+100,120))]
            return httpx.Response(200,json=data,headers={"Last-Modified-Version":"42"})
        with patch("httpx.AsyncClient",lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
            with self.assertRaises(ValueError):asyncio.run(sync_zotero(self.a))
            receipt=asyncio.run(sync_zotero(self.a,allow_network=True,max_items=200))
            second=asyncio.run(sync_zotero(self.a,allow_network=True,max_items=100))
        self.assertEqual(receipt["received"],120)
        self.assertEqual(receipt["library_version"],"42")
        self.assertIsNone(receipt["next_start"])
        self.assertEqual(second["next_start"],100)
        self.assertEqual(second["result"]["duplicates"],100)
        self.assertTrue(all(p["level"]==0 and p["state"]=="candidate" for p in K.all_papers(self.a)))
        self.assertNotIn("10.1234/zot",K.bibliography(self.a))
        self.assertEqual(K.search(self.b)["total"],0)

    def test_zotero_changed_library_and_unavailable_service_do_not_fake_success(self):
        from backend.plugins.local_research import sync_zotero
        original=httpx.AsyncClient
        def handler(req):
            start=int(req.url.params["start"])
            return httpx.Response(200,json=[{"title":f"Uncommitted {i}"} for i in range(100)],headers={"Last-Modified-Version":str(start)})
        with patch("httpx.AsyncClient",lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
            with self.assertRaisesRegex(ValueError,"changed during pagination"):
                asyncio.run(sync_zotero(self.a,allow_network=True,max_items=200))
        self.assertEqual(K.search(self.a)["total"],0)
        from fastapi.testclient import TestClient
        from backend.app import app
        client=TestClient(app)
        with patch("backend.plugins.local_research.sync_zotero",new=AsyncMock(side_effect=httpx.ConnectError("offline"))):
            response=client.post(f"/api/research/topics/{self.a}/zotero/sync",json={"allow_network":True})
            self.assertEqual(response.status_code,400)
            self.assertIn("not reachable",response.json()["detail"])
        self.assertEqual(client.post(f"/api/research/topics/{self.a}/zotero/sync",json={}).status_code,400)


if __name__ == "__main__": unittest.main()
