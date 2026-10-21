"""Search → ranked source → save → library/context: regression at actual HTTP and persistence boundaries."""
import _env
import asyncio
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from backend.app import app
from backend.core import config
from backend.knowledge import download as D, library as L, ranking as R, websearch as WS
from pdfgen import make_pdf

CSV = 'Rank;Sourceid;Title;Issn;SJR;SJR Best Quartile;Categories\n1;123;Test Journal;1234-567X;1,25;Q1;AI (Q1)\n'
PAPER = {"kind": "paper", "title": "A reliable test paper", "url": "https://example.com/paper", "doi": "10.1234/test",
         "authors": ["Doe, J"], "year": 2025, "venue": "Test Journal", "issn": ["1234-567X"]}


class Literature(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("literature-" + self._testMethodName[:30])
        self.c = TestClient(app)  # don't start background workers or paid providers
        R._cache.clear()
        self.rankfile = Path(tempfile.mkdtemp(dir=config.GLOBAL_DIR)) / "ranks.json"
        p = mock.patch.object(R, "_path", return_value=self.rankfile)
        p.start()
        self.addCleanup(p.stop)
        self.pdf = make_pdf([[(18, "A Reliable Test Paper"), (10, "Abstract. Evidence from a test.")]])

    def client(self, handler):
        return mock.patch.object(WS, "_client", lambda timeout=15: httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    def test_search_save_metadata_and_context_survives_scan(self):
        async def result(*a, **kw):
            self.assertEqual(a, ("both", ["vision"], ["vision"], 20, 2024))
            return {"sources": [{**PAPER, "id": "S1"}], "errors": []}
        with mock.patch.object(WS, "search", side_effect=result):
            res = self.c.post("/api/search", json={"query": "vision", "n_results": 20, "year_from": 2024})
        self.assertEqual(res.status_code, 200)
        source = res.json()["sources"][0]
        saved = self.c.post("/api/library/save", json={"source": source}).json()
        self.assertFalse(saved["pdf_saved"])
        self.assertTrue(saved["entry"]["metadata_only"])
        key, name = saved["entry"]["key"], saved["entry"]["file"]
        self.assertEqual(len(self.c.get("/api/library").json()["references"]), 1)
        self.assertTrue(self.c.post("/api/library/save", json={"source": source}).json()["already_saved"])
        self.assertIn("doi", self.c.get("/api/library/bib").text)
        from backend.agent.project_context import resolve_source
        self.assertIn(PAPER["title"], resolve_source("ref:" + key, expanded=True)["text"])
        self.assertEqual(self.c.post("/api/library/refine", json={"file": name}).status_code, 422)
        self.assertEqual(self.c.get("/api/library/file/" + name).status_code, 404)
        self.assertEqual(self.c.delete("/api/library/" + name).status_code, 200)
        self.assertEqual(self.c.get("/api/library").json()["references"], [])

    def test_save_pdf_and_repeated_source_keep_keys_metadata_and_ranking(self):
        source = {**PAPER, "source": "IEEE", "pdf_url": "https://example.com/p.pdf", "journal_ranking": {"quartile": "Q1", "year": 2024}}
        with mock.patch.object(D, "pdf_bytes", mock.AsyncMock(return_value=self.pdf)):
            res = self.c.post("/api/library/save", json={"source": source}).json()
        e = res["entry"]
        self.assertTrue(res["pdf_saved"])
        self.assertEqual((config.refs_dir() / e["file"]).read_bytes(), self.pdf)
        self.c.put("/api/library/" + e["file"], json={"key": "curated", "title": "Curated title"})
        lib = self.c.get("/api/library").json()["references"]
        self.assertEqual((len(lib), lib[0]["key"], lib[0]["title"], lib[0]["journal_ranking"]["quartile"]), (1, "curated", "Curated title", "Q1"))
        # Same DOI returned through another index cannot replace curated fields.
        self.assertTrue(L.save_source({**PAPER, "url": "https://another.org/x"})["already_saved"])
        self.assertEqual(self.c.get("/api/library/file/" + e["file"]).content, self.pdf)

    def test_metadata_upgrade_keeps_curated_fields_and_avoids_pdf_collision(self):
        first = L.save_source(PAPER)["entry"]
        first["key"], first["key_locked"], first["include"] = "curated", True, False
        L.save_library({first["file"]: first})
        # Preserve an existing unrelated PDF, even if its generated name happens to collide.
        collision = first["file"].replace(".paper.json", ".pdf")
        (config.refs_dir() / collision).write_bytes(self.pdf + b"unrelated")
        with mock.patch.object(D, "pdf_bytes", mock.AsyncMock(return_value=self.pdf)):
            result = self.c.post("/api/library/save", json={"source": {**PAPER, "pdf_url": "https://example.com/pdf"}}).json()
        self.assertTrue(result["upgraded"])
        self.assertEqual(result["entry"]["key"], "curated")
        self.assertFalse(result["entry"]["include"])
        self.assertNotEqual(result["entry"]["file"], collision)
        self.assertNotIn(first["file"], L.load_library())
        self.assertEqual((config.refs_dir() / collision).read_bytes(), self.pdf + b"unrelated")

    def test_failed_pdf_still_saves_and_is_bound_to_original_project(self):
        original = config.data_dir()
        other = config.create_project("lit-other")["data_dir"]
        config.activate_project(str(original))
        async def failure(url):
            config.activate_project(other)
            raise httpx.ConnectError("no PDF")
        with mock.patch.object(D, "pdf_bytes", side_effect=failure):
            res = self.c.post("/api/library/save", json={"source": {**PAPER, "pdf_url": "https://example.com/p.pdf"}}).json()
        self.assertTrue(res["warning"])
        self.assertFalse(L.load_library())
        with config.project_scope(original):
            self.assertEqual(len(L.load_library()), 1)

    def test_search_validation_and_config_masks_new_keys(self):
        for body in ({}, {"query": "x", "mode": "none"}, {"query": "x" * 2001}, {"query": "q", "year_from": "bad"},
                     {"query": "q", "n_results": 31}, {"query": "q", "year_from": 1800}):
            self.assertEqual(self.c.post("/api/search", json=body).status_code, 400)
        for body in ({}, {"source": []}, {"source": {"title": "x", "url": "file:///secret"}},
                     {"source": {"title": "x", "url": "https://a:b@evil.test"}}):
            self.assertEqual(self.c.post("/api/library/save", json=body).status_code, 400)
        config.save_config({"search": {"serpapi_key": "secret-abc", "openalex_key": "secret-abc", "ieee_key": "secret-abc"}})
        safe = self.c.get("/api/config").json()
        self.assertNotIn("secret-abc", json.dumps(safe))
        self.assertEqual(config.load_config()["search"]["ieee_key"], "secret-abc")

    def test_ieee_and_scholar_contracts(self):
        def handler(req):
            if "ieee" in req.url.host:
                self.assertEqual(req.url.params["start_year"], "2020")
                return httpx.Response(200, json={"articles": [
                    {"title": "IEEE paper", "authors": {"authors": [{"full_name": "A"}]}, "publication_year": "2025",
                     "publication_title": "IEEE Access", "doi": "10.1234/i", "abstract_url": "https://ieeexplore.ieee.org/document/1",
                     "pdf_url": "https://example.com/i.pdf", "access_type": "Open Access", "content_type": "Journals", "issn": "1234-567X"},
                    {"title": "Locked", "pdf_url": "https://example.com/locked", "accessType": "Locked", "content_type": "Conferences"}]})
            self.assertEqual(req.url.params["engine"], "google_scholar")
            self.assertEqual(req.url.params["as_ylo"], "2020")
            return httpx.Response(200, json={"organic_results": [
                {"title": "Scholar paper", "link": "https://example.com/x", "publication_info": {"summary": "A - Journal, 2024", "authors": [{"name": "A"}]},
                 "resources": [{"file_format": "HTML"}, {"file_format": "PDF", "link": "https://example.com/s.pdf"}],
                 "inline_links": {"cited_by": {"total": 9}}, "snippet": "Abstract"}, {"title": "Unknown"}]})
        with self.client(handler):
            ieee = asyncio.run(WS.ieee("q", 10, "key", 2020))
            scholar = asyncio.run(WS.google_scholar("q", 10, "key", 2020))
        self.assertEqual((ieee[0]["year"], ieee[0]["publication_type"]), (2025, "journal"))
        self.assertEqual((ieee[1]["pdf_url"], ieee[1]["publication_type"]), ("", "conference"))
        self.assertEqual((scholar[0]["year"], scholar[0]["citations"], scholar[0]["pdf_url"]), (2024, 9, "https://example.com/s.pdf"))
        self.assertIsNone(scholar[1]["year"])
        for adapter in (WS.ieee, WS.google_scholar):
            with self.client(lambda req: httpx.Response(200, json={"error": "secret never expose"})):
                with self.assertRaises(WS.SearchError) as exc:
                    asyncio.run(adapter("q", 10, "key"))
                self.assertNotIn("secret", str(exc.exception))

    def test_multisource_partial_failure_dedup_and_year(self):
        config.save_config({"search": {"ieee_key": "ieee", "serpapi_key": "scholar", "read_pages": False}})
        with mock.patch.object(WS, "openalex", mock.AsyncMock(return_value=[{**PAPER, "source": "OpenAlex"}])), \
                mock.patch.object(WS, "semantic_scholar", mock.AsyncMock(side_effect=httpx.ConnectError("offline"))), \
                mock.patch.object(WS, "arxiv", mock.AsyncMock(return_value=[{**PAPER, "source": "arXiv", "doi": "", "pdf_url": "https://arxiv.org/pdf/test"}])), \
                mock.patch.object(WS, "ieee", mock.AsyncMock(return_value=[{**PAPER, "source": "IEEE Xplore"}])), \
                mock.patch.object(WS, "google_scholar", mock.AsyncMock(return_value=[{**PAPER, "source": "Google Scholar"}])), \
                mock.patch.object(WS, "web_query", mock.AsyncMock(return_value=[{"kind": "web", "title": "Web", "url": "https://example.org"}])), \
                mock.patch.object(R, "_openalex", mock.AsyncMock(return_value={})):
            res = asyncio.run(WS.search("both", ["q"], ["q"], 20, 2020))
        self.assertEqual(len(res["sources"]), 2)
        p = res["sources"][0]
        self.assertEqual(len(p["sources"]), 4)
        self.assertTrue(p["pdf_url"])
        self.assertEqual(len(res["errors"]), 1)
        self.assertEqual(res["provider_status"]["google_scholar"], "configured")
        self.assertIn("journal_ranking", WS.compact([p])[0])
        # Same title with different DOIs is not evidence of the same work.
        merged = WS._interleave([[PAPER], [{**PAPER, "doi": "10.1234/other"}]])
        self.assertEqual(len(merged), 2)
        merged = WS._interleave([[{**PAPER, "source": "arXiv", "venue": "arXiv preprint", "publication_type": "repository"}],
                                [{**PAPER, "source": "IEEE", "publication_type": "journal"}]])
        self.assertEqual(merged[0]["venue"], "Test Journal")

    def test_ieee_discovery_only_trusted_publisher_documents(self):
        with mock.patch.object(WS, "web_query", mock.AsyncMock(return_value=[
            {"url": "https://ieeexplore.ieee.org/document/123", "title": "yes", "snippet": "s"},
            {"url": "https://ieeexplore.ieee.org.evil.com/document/1", "title": "bad"},
            {"url": "https://ieeexplore.ieee.org/search", "title": "index"}])):
            found = asyncio.run(WS.ieee_discovery("q", 10, {}))
        self.assertEqual([(p["title"], p["kind"]) for p in found], [("yes", "paper")])

    def test_arxiv_api_timeout_falls_back_to_domain_search(self):
        with mock.patch.object(WS, "arxiv", mock.AsyncMock(side_effect=httpx.ReadTimeout("slow"))), \
                mock.patch.object(WS, "web_query", mock.AsyncMock(return_value=[
                    {"url": "https://arxiv.org/abs/2501.12345", "title": "Preprint", "snippet": "summary"},
                    {"url": "https://evil.com/abs/2501.12345"}, {"url": "https://arxiv.org/search"}])):
            errors = []
            records = asyncio.run(WS.arxiv_search("q", 3, {}, errors))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["pdf_url"], "https://arxiv.org/pdf/2501.12345")
        self.assertIn("timed out", errors[0])
        self.assertEqual(records[0]["publication_type"], "repository")

    def test_ranking_import_match_and_unknowns(self):
        response = self.c.post("/api/journals/import", data={"year": "2024"}, files={"file": ("ranks.csv", CSV.encode(), "text/csv")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["records"], 1)
        papers = [dict(PAPER), {"venue": "arXiv preprint"}, {"venue": "Unknown"}]
        with mock.patch.object(R, "_openalex", mock.AsyncMock(return_value={})):
            asyncio.run(R.enrich(papers, {}))
        self.assertEqual((papers[0]["journal_ranking"]["quartile"], papers[0]["journal_ranking"]["sjr"], papers[0]["journal_ranking"]["year"]), ("Q1", 1.25, 2024))
        self.assertEqual(papers[1]["journal_ranking"]["status"], "not_applicable")
        self.assertEqual(papers[2]["journal_ranking"]["status"], "unavailable")
        rows = R._local_records()
        self.assertTrue(R._match({"venue": "Test Journal"}, rows))
        self.assertFalse(R._match({"venue": "Test Journal", "issn": ["9999-999X"]}, rows))
        for year, text in ((1800, CSV), (2024, "x,y\nwrong,thing")):
            with self.assertRaises(ValueError): R.import_scimago(text, year)
        self.rankfile.write_text("[]")
        self.assertEqual(R._local_records(), [])
        self.rankfile.write_text("{broken")
        self.assertEqual(R._local_records(), [])

    def test_openalex_journal_identity_cache_and_metrics_are_not_sjr(self):
        calls = []
        def handler(req):
            calls.append(req)
            doc = {"id": "https://openalex.org/S123", "type": "journal", "display_name": "Test Journal", "issn": ["1234-567X"],
                   "summary_stats": {"h_index": 99, "2yr_mean_citedness": 2.4}, "works_count": 1000, "cited_by_count": 10000}
            return httpx.Response(200, json={"results": [doc]} if req.url.path.endswith("/sources") else doc)
        with self.client(handler):
            p = dict(PAPER)
            asyncio.run(R.enrich([p], {"openalex_key": "key"}))
            asyncio.run(R.enrich([p], {}))
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].url.params["api_key"], "key")
            self.assertEqual(p["journal_ranking"]["h_index"], 99)
            self.assertNotIn("quartile", p["journal_ranking"])
            self.assertEqual(p["journal_ranking"]["status"], "metrics")
            R._cache.clear()
            self.assertTrue(asyncio.run(R._openalex({"source_id": "https://openalex.org/S123"}, {})))
            R._cache.clear()
            self.assertTrue(asyncio.run(R._openalex({"venue": "Test Journal"}, {})))
            self.assertEqual(asyncio.run(R._openalex({"venue": "Different Journal"}, {})), {})
        with self.client(lambda r: httpx.Response(200, json={"type": "repository"})):
            self.assertFalse(asyncio.run(R._openalex({"source_id": "S999"}, {})))
        with mock.patch.object(R, "_openalex", mock.AsyncMock(side_effect=httpx.ConnectError("offline"))):
            p = dict(PAPER)
            asyncio.run(R.enrich([p], {}))
            self.assertIn("error", p["journal_ranking"])

    def test_public_pdf_redirect_validation_and_download_limits(self):
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with mock.patch.object(socket, "getaddrinfo", return_value=public):
            asyncio.run(D.public_url("https://example.com/file"))
        for value in ("file:///etc/passwd", "https://u:p@example.com"):
            with self.assertRaises(ValueError): asyncio.run(D.public_url(value))
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with mock.patch.object(socket, "getaddrinfo", return_value=private):
            with self.assertRaises(ValueError): asyncio.run(D.public_url("https://local.test"))
        real_client = httpx.AsyncClient
        def handle(req):
            if req.url.path == "/redirect": return httpx.Response(302, headers={"location": "/pdf"})
            if req.url.path == "/loop": return httpx.Response(302, headers={"location": "/loop"})
            return httpx.Response(200, content=self.pdf if req.url.path == "/pdf" else b"login page")
        with mock.patch.object(D.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw)), \
                mock.patch.object(D, "public_url", mock.AsyncMock()):
            self.assertEqual(asyncio.run(D.pdf_bytes("https://example.com/redirect")), self.pdf)
            for url in ("https://example.com/login", "https://example.com/loop"):
                with self.assertRaises(ValueError): asyncio.run(D.pdf_bytes(url))
            with mock.patch.object(D, "MAX_PDF_BYTES", 5):
                with self.assertRaises(ValueError): asyncio.run(D.pdf_bytes("https://example.com/pdf"))

    def test_web_pages_validate_every_redirect_and_bound_response_size(self):
        def handler(req):
            if req.url.path == "/redirect": return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
            if req.url.path == "/loop": return httpx.Response(302, headers={"location": "/loop"})
            if req.url.path == "/error": return httpx.Response(500)
            if req.url.path == "/pdf": return httpx.Response(200, content=self.pdf)
            return httpx.Response(200, text="<p>text</p>" + " " * 600001, headers={"content-type": "text/html"})
        async def public(url):
            if "127.0.0.1" in url: raise ValueError("private")
        with self.client(handler), mock.patch.object(D, "public_url", side_effect=public) as guard:
            self.assertEqual(asyncio.run(WS.read_page("https://example.com/redirect")), "")
            self.assertEqual(guard.call_args.args[0], "http://127.0.0.1/private")
            for path in ("/loop", "/error", "/pdf"):
                self.assertEqual(asyncio.run(WS.read_page("https://example.com" + path)), "")
            self.assertEqual(asyncio.run(WS.read_page("https://example.com/text")), "text")

    def test_journal_number_validation_and_empty_identity(self):
        self.assertIsNone(R._number("bad"))
        self.assertIsNone(R._number("nan"))
        self.assertIsNone(R._number("-1"))
        self.assertEqual(asyncio.run(R._openalex({}, {})), {})
        R.import_scimago(CSV, 2024)
        paper = {"venue": "Abbreviation"}
        with mock.patch.object(R, "_openalex", mock.AsyncMock(return_value={"source": "OpenAlex", "title": "Test Journal", "issn": ["1234567X"]})):
            asyncio.run(R.enrich([paper], {}))
        self.assertEqual(paper["journal_ranking"]["quartile"], "Q1")
        for i in range(256): R._cache[str(i)] = (0, {})
        with self.client(lambda req: httpx.Response(200, json={"type": "journal"})):
            asyncio.run(R._openalex({"source_id": "S7777"}, {}))
        self.assertEqual(len(R._cache), 256)

    def test_many_results_keep_web_and_filter_before_cap(self):
        old = [{"kind": "paper", "title": "old" + str(i), "year": 1990} for i in range(40)]
        recent = [{"kind": "paper", "title": "new" + str(i), "year": 2025} for i in range(40)]
        web = [{"kind": "web", "title": "web" + str(i), "url": "https://example.com/" + str(i)} for i in range(30)]
        config.save_config({"search": {"read_pages": False}})
        with mock.patch.object(WS, "openalex", mock.AsyncMock(return_value=old + recent)), \
                mock.patch.object(WS, "arxiv_search", mock.AsyncMock(return_value=[])), \
                mock.patch.object(WS, "semantic_scholar", mock.AsyncMock(return_value=[])), \
                mock.patch.object(WS, "ieee_discovery", mock.AsyncMock(return_value=[])), \
                mock.patch.object(WS, "web_query", mock.AsyncMock(return_value=web)), \
                mock.patch.object(R, "enrich", mock.AsyncMock()):
            res = asyncio.run(WS.search("both", ["q"], ["q"], 30, 2020))
        self.assertEqual(len(res["sources"]), 30)
        self.assertEqual(sum(s["kind"] == "web" for s in res["sources"]), 6)
        self.assertFalse(any(s["title"].startswith("old") for s in res["sources"]))

    def test_legacy_root_library_copies_without_overwrite(self):
        base = config.data_dir()
        legacy = base / "references"
        (legacy / "old.pdf").write_bytes(self.pdf)
        target = base / "data"
        with mock.patch.object(config, "ROOT", base), mock.patch.object(config, "_DATA_OVERRIDE", ""):
            existing = base / "existing-project"
            existing.mkdir()
            (existing / config.META_NAME).write_text(json.dumps({"references_dir": str(legacy)}))
            self.assertEqual(config.project_info(existing)["references_dir"], str(existing / "references"))
            self.assertEqual((existing / "references" / "old.pdf").read_bytes(), self.pdf)
            info = config._ensure_project(target, "Migrated", str(legacy))
            self.assertEqual(info["references_dir"], str(target / "references"))
            self.assertEqual((target / "references" / "old.pdf").read_bytes(), self.pdf)
            self.assertTrue((legacy / "old.pdf").exists())
            config._ensure_project(target)
            (target / "references" / "old.pdf").write_bytes(b"different")
            with self.assertRaises(ValueError): config._ensure_project(target, references_dir=str(legacy), update_refs=True)
            self.assertEqual((legacy / "old.pdf").read_bytes(), self.pdf)

    def test_journal_tool_uses_same_ranker(self):
        from backend.providers import mcp_tools as MT
        with mock.patch.object(R, "_openalex", mock.AsyncMock(return_value={})):
            res = MT.call("journal_ranking", {"venue": "Test Journal", "issn": "1234-567X"})
        self.assertIn("journal_ranking", res["structuredContent"]["result"])

