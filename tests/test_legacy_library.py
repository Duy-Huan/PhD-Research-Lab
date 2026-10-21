"""Legacy reference pipeline (coverage pass): PDF library + BibTeX, chat attachments, internet search, LaTeX build."""
import _env  # noqa: F401  (must be first)
import asyncio
import io
import json
import subprocess
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import httpx

from backend.knowledge import attachments as AT, library as L, websearch as WS
from backend.paper import latex as LB
from backend.core.config import refs_dir, workspace
from pdfgen import PAPER, make_pdf


def mock_client(handler):
    """Patch an httpx.AsyncClient factory so requests go to `handler`."""
    real = httpx.AsyncClient

    def factory(*a, **k):
        k.pop("transport", None)
        return real(*a, transport=httpx.MockTransport(handler), **k)
    return factory


class Library(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-lib")
        (refs_dir() / "smith2023.pdf").write_bytes(make_pdf(PAPER, {"Author": "Alice Smith; Bob Jones", "CreationDate": "D:20230101"}))
        (refs_dir() / "untitled.pdf").write_bytes(make_pdf([[(10, "short"), (10, "Proceedings of the Workshop on Things")]], {"Title": "Microsoft Word - draft.doc"}))
        (refs_dir() / "broken.pdf").write_bytes(b"%PDF-1.4 garbage")


    def test_corrupt_library_is_kept(self):
        L.scan_directory()
        L._lib_path().write_text("{oops", "utf-8")
        self.assertEqual(L.load_library(), {})
        self.assertTrue(list(L._lib_path().parent.glob("library.json.corrupt-*")))
        L._lib_path().write_text("[]", "utf-8")
        self.assertEqual(L.load_library(), {})
        with mock.patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertEqual(L.load_library(), {})

    def test_keys_merge_and_escaping(self):
        lib = {"a.pdf": {"title": "On the CNN", "authors": ["Müller, Hans"], "year": "2020"},
               "b.pdf": {"title": "On the CNN", "authors": ["Hans Müller"], "year": "2020"},
               "c.pdf": {"title": "", "authors": [], "key": "locked1", "key_locked": True},
               "d.pdf": {"title": "!!!", "authors": ["  "]}}
        L.assign_keys(lib)
        self.assertEqual({lib["a.pdf"]["key"], lib["b.pdf"]["key"]}, {"muller2020cnn", "muller2020cnna"})
        self.assertEqual(lib["c.pdf"]["key"], "locked1")
        self.assertEqual(lib["d.pdf"]["key"], "anonndpaper")
        many = {f"{i:03d}.pdf": {"title": "Same", "authors": ["X Y"], "year": "2021"} for i in range(30)}
        L.assign_keys(many)
        self.assertEqual(len({e["key"] for e in many.values()}), 30)
        e = L.merge_llm_metadata({"key": "k", "entry_type": "x"}, {"title": " T ", "authors": "A B and C D", "year": 2021,
                                                                   "venue": "unknown", "doi": None})
        self.assertEqual((e["title"], e["authors"], e["year"], e["entry_type"]), ("T", ["A B", "C D"], "2021", "article"))
        self.assertNotIn("key", e)
        locked = L.merge_llm_metadata({"key": "k", "key_locked": True}, {"authors": ["Z"]})
        self.assertEqual(locked["key"], "k")
        b = L.entry_to_bibtex({"key": "k", "entry_type": "inproceedings", "title": "RISC-V on FPGA_x", "authors": ["A & B"],
                               "venue": "Conf", "volume": "1", "number": "2", "pages": "1 - 9", "year": "2020", "publisher": "P",
                               "doi": " 10.1/x "})
        for frag in ("booktitle = {Conf}", "{RISC-V}", "{FPGA}\\_x","A \\& B", "pages     = {1--9}", "doi       = {10.1/x}"):
            self.assertIn(frag, b)
        self.assertIn("howpublished", L.entry_to_bibtex({"key": "m", "entry_type": "misc", "venue": "V"}))
        self.assertIn("$\\ell_1$", L._esc("Sparse $\\ell_1$ & more"))
        self.assertEqual(L._split_authors(""), [])
        self.assertEqual(L._last_name(""), "anon")
        self.assertFalse(L._valid_meta_title("Untitled document"))

    def test_title_picker_and_no_backend(self):
        self.assertEqual(L._pick_title([], True, 100), "")
        self.assertEqual(L._pick_title([(20, 10, "A Long Enough Title Here"), (9, 12, "small")], True, 100), "A Long Enough Title Here")
        with mock.patch.object(L, "PDF_BACKEND", "none"):
            with self.assertRaises(RuntimeError):
                L._require_backend()

    def test_encrypted_and_failing_pages(self):
        class Page:
            mediabox = mock.Mock(height=792)

            def extract_text(self, visitor_text=None):
                if visitor_text:
                    visitor_text("A Very Big Title For The Paper", [1, 0, 0, 1, 0, 0], [20, 0, 0, 20, 50, 700], {}, 1)
                    visitor_text("x", [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0], {}, 1)
                    visitor_text("bad", None, None, {}, "nan?")
                    raise RuntimeError("visitor unsupported")
                return "Some page text"

        class Reader:
            is_encrypted = True
            metadata = None
            pages = [Page(), Page()]

            def __init__(self, *_):
                pass

            def decrypt(self, _):
                raise RuntimeError("needs password")
        with mock.patch.object(L, "PdfReader", Reader), mock.patch.object(L, "PDF_BACKEND", "pypdf"):
            r = L._read_pdf(Path("x.pdf"))
            self.assertEqual(r["pages"], 2)
            self.assertEqual(L.pdf_pages(Path("x.pdf"))[1], 2)

        class BadPage(Page):
            def extract_text(self, visitor_text=None):
                raise RuntimeError("bad stream")

        class Reader2(Reader):
            pages = [BadPage()]
            is_encrypted = False
        with mock.patch.object(L, "PdfReader", Reader2), mock.patch.object(L, "PDF_BACKEND", "pypdf"):
            self.assertEqual(L.pdf_pages(Path("x.pdf"))[0], [""])


class Attachments(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-att")

    def _zip(self, files: dict) -> bytes:
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for k, v in files.items():
                z.writestr(k, v)
        return b.getvalue()

    def test_uploads_of_every_kind(self):
        docx = self._zip({"word/document.xml": "<w:p><w:t>Hello &amp; welcome</w:t></w:p><w:p><w:tab/>x</w:p>"})
        pptx = self._zip({"ppt/slides/slide2.xml": "<a:p>Second</a:p>", "ppt/slides/slide1.xml": "<a:p>First</a:p>"})
        xlsx = self._zip({"xl/sharedStrings.xml": "<si><t>name</t></si><si><t>psnr, db</t></si>",
                          "xl/worksheets/sheet1.xml": '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row><row><c><v>31.2</v></c><c t="inlineStr"><is><t>ok</t></is></c></row>'})
        nb = json.dumps({"cells": [{"cell_type": "code", "source": ["x = 1"]}, {"cell_type": "markdown", "source": ["# T"]}]}).encode()
        html = b"<html><head><title>Page</title><script>bad()</script></head><body><h1>Head</h1><p>Body text</p><nav>menu</nav></body></html>"
        cases = {"a.docx": (docx, "docx", "Hello & welcome"), "b.pptx": (pptx, "pptx", "--- Slide 1 ---\nFirst"),
                 "c.xlsx": (xlsx, "xlsx", "name,psnr; db\n31.2,ok"), "d.ipynb": (nb, "notebook", "```python\nx = 1"),
                 "e.html": (html, "html", "## Head"), "f.py": (b"print(1)", "text", "print(1)"), "noext": (b"raw", "text", "raw"),
                 "g.pdf": (make_pdf(PAPER), "pdf", "Hyperspectral"), "h.png": (b"\x89PNGxx", "image", "")}
        for name, (data, kind, frag) in cases.items():
            m = AT.add_upload(name, data)
            self.assertEqual(m["kind"], kind, name)
            self.assertIn(frag, AT.get_text(m["id"]), name)
        self.assertNotIn("bad()", AT.get_text(AT.add_upload("x.htm", html)["id"]))
        for bad, msg in (("x.exe", "Unsupported"), ("scan.pdf", "no extractable text"), ("bad.docx", "could not read")):
            data = make_pdf([[(10, " ")]]) if bad == "scan.pdf" else b"not a zip"
            with self.assertRaises(AT.AttachmentError) as cm:
                AT.add_upload(bad, data)
            self.assertIn(msg, str(cm.exception))
        with mock.patch.object(AT, "MAX_UPLOAD", 3):
            with self.assertRaises(AT.AttachmentError):
                AT.add_upload("big.txt", b"1234")
        self.assertEqual(len(list((AT._dir()).glob("*.exe"))), 0)  # refused files are removed


    def test_corrupt_index_is_kept(self):
        AT.add_upload("a.txt", b"precious")
        (AT._dir() / "index.json").write_text("{bad", "utf-8")
        AT.add_upload("b.txt", b"new")
        self.assertTrue(list(AT._dir().glob("index.json.corrupt-*")))
        (AT._dir() / "index.json").write_text("[]", "utf-8")
        self.assertEqual(AT._index(), {})
        with mock.patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertEqual(AT._index(), {})



class WebSearch(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-web")

    def handler(self, req):
        u = req.url
        if "openalex" in u.host or "openalex" in u.path:
            return httpx.Response(200, json={"results": [
                {"id": "W1", "doi": "https://doi.org/10.1/abc", "display_name": " Spectral  Nets ", "publication_year": 2024,
                 "authorships": [{"author": {"display_name": "A"}}, {}], "primary_location": {"source": {"display_name": "TGRS"}},
                 "cited_by_count": 5, "best_oa_location": {"pdf_url": "https://p/x.pdf"},
                 "abstract_inverted_index": {"world": [1], "hello": [0]}},
                {"id": "W2", "display_name": "Old", "publication_year": 2001, "primary_location": None}]})
        if "arxiv" in u.host or "arxiv" in u.path:
            return httpx.Response(200, text="""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/1</id><title>Spectral Nets</title><published>2024-01-01</published><summary>S</summary>
<author><name>A</name></author><link title="pdf" href="http://arxiv.org/pdf/1"/><arxiv:doi>10.1/abc</arxiv:doi></entry>
<entry><id>http://arxiv.org/abs/2</id><title>New</title><published></published><summary>T</summary></entry></feed>""")
        if "semanticscholar" in u.host or "/s2/" in u.path:
            if req.url.params.get("query") == "limited":
                return httpx.Response(429)
            return httpx.Response(200, json={"data": [{"title": "S2 Paper", "year": 2023, "externalIds": {}, "url": "https://s2/1",
                                                       "authors": [{"name": "B"}], "openAccessPdf": None, "citationCount": 1}]})
        if "duckduckgo" in u.host or "/ddg" in u.path:
            q = dict(httpx.QueryParams(req.content.decode())).get("q")
            if q == "blocked":
                return httpx.Response(200, text="<html>anomaly detected</html>")
            return httpx.Response(200, text='<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsite.org%2Fa">Site <b>A</b></a>'
                                            '<a class="result__snippet" href="x">snip</a>'
                                            '<a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Ad</a>'
                                            '<a class="result__a" href="//other.org/b">B</a>')
        if "tavily" in u.host or "/tavily" in u.path:
            key = json.loads(req.content)["api_key"]
            return httpx.Response(401) if key == "bad" else httpx.Response(200, json={"results": [{"title": "Tv", "url": "https://tv", "content": "c"}]})
        if "brave" in u.host or "/brave" in u.path:
            if req.headers.get("x-subscription-token") == "bad":
                return httpx.Response(401)
            return httpx.Response(200, json={"web": {"results": [{"title": "Br", "url": "https://br", "description": "<b>d</b>"}]}})
        if u.host == "site.org":
            return httpx.Response(200, text="<html><body><p>Page body</p></body></html>", headers={"content-type": "text/html"})
        return httpx.Response(500)

    def run_search(self, *a, **k):
        async def go():
            with mock.patch.object(WS, "_client", lambda timeout=15: httpx.AsyncClient(transport=httpx.MockTransport(self.handler))), \
                    mock.patch("backend.knowledge.download.public_url", mock.AsyncMock()):
                return await WS.search(*a, **k)
        return asyncio.run(go())

    def test_papers_and_web(self):
        r = self.run_search("both", ["spectral"], ["spectral web"], n=4, year_from=2020)
        titles = [s["title"] for s in r["sources"]]
        self.assertIn("Spectral Nets", titles)
        self.assertNotIn("Old", titles)  # year filter
        merged = next(s for s in r["sources"] if s["title"] == "Spectral Nets")
        self.assertEqual(merged["abstract"], "hello world")
        self.assertEqual([s["id"] for s in r["sources"]], [f"S{i}" for i in range(1, len(r["sources"]) + 1)])
        web = [s for s in r["sources"] if s["kind"] == "web"]
        self.assertEqual(web[0]["url"], "https://site.org/a")
        self.assertEqual(web[0]["page"], "Page body")
        self.assertNotIn("Ad", [w["title"] for w in web])
        self.assertEqual(r["errors"], [])

    def test_engines_and_errors(self):
        _env.config.save_config({"search": {"web_engine": "tavily", "tavily_key": "k", "read_pages": False}})
        self.assertEqual(self.run_search("web", [], ["q"])["sources"][0]["title"], "Tv")
        _env.config.save_config({"search": {"tavily_key": ""}})
        self.assertIn("no API key", self.run_search("web", [], ["q"])["errors"][0])
        _env.config.save_config({"search": {"web_engine": "brave", "brave_key": "bad"}})
        self.assertIn("rejected", self.run_search("web", [], ["q"])["errors"][0])
        _env.config.save_config({"search": {"brave_key": "ok"}})
        self.assertEqual(self.run_search("web", [], ["q"])["sources"][0]["snippet"], "d")
        _env.config.save_config({"search": {"brave_key": ""}})
        self.assertTrue(self.run_search("web", [], ["q"])["errors"])
        _env.config.save_config({"search": {"web_engine": "tavily", "tavily_key": "bad"}})
        self.assertIn("rejected", self.run_search("web", [], ["q"])["errors"][0])
        _env.config.save_config({"search": {"web_engine": "duckduckgo", "read_pages": True}})
        self.assertIn("blocked", self.run_search("web", [], ["blocked"])["errors"][0])
        r = self.run_search("papers", ["limited"], [])
        self.assertTrue(any("rate limit" in e for e in r["errors"]))
        self.assertEqual(self.run_search("off", ["x"], ["y"])["sources"], [])

        async def fail(*a, **k):
            raise httpx.ConnectError("x")

        async def http500(*a, **k):
            raise httpx.HTTPStatusError("x", request=httpx.Request("GET", "http://x"), response=httpx.Response(503))

        async def weird(*a, **k):
            raise KeyError("display_name")

        async def go():
            errs = []
            for c in (fail(), http500(), weird()):
                self.assertEqual(await WS._safe("X", c, errs), [])
            return errs
        errs = asyncio.run(go())
        self.assertEqual(len(errs), 3)
        self.assertIn("HTTP 503", errs[1])



class Latex(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-latex")
        from backend.paper import writer as paper
        p = paper.load_project()
        p["sections"] = {"abstract": "Abs", "introduction": "\\section{Introduction}\nIntro"}
        paper.save_project(p)

    LOG = ("! Undefined control sequence.\nl.42 \\foo\n! Undefined control sequence.\nl.42 \\foo\n"
           "error: main.tex:30: Missing $ inserted\nLaTeX Warning: Citation `ghost' on page 1 undefined\n"
           "LaTeX Warning: Reference `fig:x' on page 1 undefined\nOverfull \\hbox (1pt too wide)\n"
           "! LaTeX Error: File `IEEEtran.cls' not found.\nOutput written on main.pdf (3 pages, 1 bytes).")

    def test_parse_log_and_quick_layout(self):
        from backend.paper.writer import assemble
        main = assemble()[0]
        r = LB.parse_log(self.LOG, main)
        self.assertEqual(len([e for e in r["errors"] if e["line"] == 42]), 1)  # duplicates removed
        self.assertEqual(r["undefined_citations"], ["ghost"])
        self.assertEqual(r["undefined_refs"], ["fig:x"])
        self.assertEqual((r["overfull"], r["pages"], r["missing_files"]), (1, 3, ["IEEEtran.cls"]))
        self.assertEqual(LB._section_of(None, []), "")
        q = LB.quick_layout(main)
        self.assertIn("\\documentclass[10pt,twocolumn]{article}", q)
        self.assertIn("\\bibliographystyle{plain}", q)
        self.assertIn("\\usepackage{xcolor}", LB.quick_layout("\\documentclass{x}\n\\begin{document}\n"))
        self.assertTrue(LB.install_help())

    def test_engines_and_compile_paths(self):
        found = {"pdflatex": "C:/tex/pdflatex.exe", "bibtex": "C:/tex/bibtex.exe", "kpsewhich": "C:/tex/kpsewhich.exe",
                 "latexmk": "C:/tex/latexmk.exe", "tectonic": "C:/t/tectonic.exe", "xelatex": None}
        calls = []

        def run(cmd, cwd, timeout):
            calls.append(Path(cmd[0]).stem)
            if Path(cmd[0]).stem in ("pdflatex", "latexmk", "tectonic"):
                (cwd / "main.aux").write_text("\\bibdata{references}", "utf-8")
                (cwd / "main.pdf").write_bytes(b"%PDF")
                (cwd / "main.log").write_text("Output written on main.pdf (1 page, 9 bytes).", "utf-8")
            return 0, "ok"
        with mock.patch.object(LB, "which", side_effect=lambda n: found.get(n)), mock.patch.object(LB, "_run", run), \
                mock.patch.object(LB, "class_available", return_value=True):
            info = LB.engines()
            self.assertEqual(info["default"], "pdflatex")
            for eng in ("pdflatex", "latexmk", "tectonic"):
                r = LB.compile_pdf(eng)
                self.assertTrue(r["ok"], eng)
                self.assertEqual(r["pages"], 1)
            with self.assertRaises(RuntimeError):
                LB.compile_pdf("xelatex")
            with self.assertRaises(RuntimeError):
                LB.compile_pdf("online")
        self.assertEqual(calls.count("bibtex"), 1)
        with mock.patch.object(LB, "which", return_value=None), mock.patch.object(LB, "load_config", return_value={"latex_online": False}):
            with self.assertRaises(LB.NoEngine):
                LB.compile_pdf()
            self.assertIsNone(LB.class_available("IEEEtran"))

    def test_quick_layout_fallbacks_and_timeout(self):
        def run_missing(cmd, cwd, timeout):
            (cwd / "main.log").write_text("! LaTeX Error: File `IEEEtran.cls' not found.", "utf-8")
            if "documentclass[10pt,twocolumn]{article}" in (cwd / "main.tex").read_text("utf-8"):
                (cwd / "main.pdf").write_bytes(b"%PDF")
            return 1, ""
        with mock.patch.object(LB, "which", side_effect=lambda n: "C:/tex/" + n), mock.patch.object(LB, "_run", run_missing), \
                mock.patch.object(LB, "class_available", return_value=None):
            r = LB.compile_pdf("pdflatex")
        self.assertTrue(r["ok"])
        self.assertEqual(r["layout"], "simple")
        self.assertIn("quick layout", r["notes"][0])
        with mock.patch.object(LB, "which", side_effect=lambda n: "C:/tex/" + n), mock.patch.object(LB, "_run", run_missing), \
                mock.patch.object(LB, "class_available", return_value=False):
            self.assertIn("is not installed", LB.compile_pdf("pdflatex")["notes"][0])

        def slow(*a, **k):
            raise subprocess.TimeoutExpired("pdflatex", 1)
        with mock.patch.object(LB, "which", side_effect=lambda n: "C:/tex/" + n), mock.patch.object(LB, "_run", slow), \
                mock.patch.object(LB, "class_available", return_value=True):
            with self.assertRaises(RuntimeError):
                LB.compile_pdf("pdflatex")

    def test_online_and_helpers(self):
        _env.config.save_config({"latex_online": True})
        with mock.patch.object(LB, "which", return_value=None), \
                mock.patch("httpx.post", return_value=httpx.Response(200, content=b"%PDF-1.5 x")):
            self.assertTrue(LB.compile_pdf("online")["ok"])
        with mock.patch("httpx.post", return_value=httpx.Response(400, json={"logs": "! Error"})):
            self.assertEqual(LB._compile_online("m", "b", LB.build_dir()), "! Error")
        with mock.patch("httpx.post", return_value=httpx.Response(502, text="gateway")):
            self.assertIn("HTTP 502", LB._compile_online("m", "b", LB.build_dir()))
        with mock.patch("httpx.post", side_effect=httpx.ConnectError("x")):
            with self.assertRaises(RuntimeError):
                LB._compile_online("m", "b", LB.build_dir())
        _env.config.save_config({"latex_online": False})
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="/x/IEEEtran.cls\n")), \
                mock.patch.object(LB, "which", return_value="kpsewhich"):
            self.assertTrue(LB.class_available("IEEEtran"))
        with mock.patch("subprocess.run", side_effect=OSError), mock.patch.object(LB, "which", return_value="kpsewhich"):
            self.assertIsNone(LB.class_available("IEEEtran"))
        self.assertIsInstance(LB._extra_dirs(), list)
        with mock.patch.object(LB.sys, "platform", "linux"):
            self.assertIsInstance(LB._extra_dirs(), list)
            self.assertIn("apt", LB.install_help()[0])
        with mock.patch("shutil.which", side_effect=lambda n, path=None: "/found/" + n if path else None), \
                mock.patch.object(LB, "_extra_dirs", return_value=["/opt/tex"]):
            self.assertEqual(LB.which("pdflatex"), "/found/pdflatex")
        self.assertEqual(LB._run([LB.sys.executable, "-c", "print('hi')"], workspace(), 30)[0], 0)


if __name__ == "__main__":
    unittest.main()
