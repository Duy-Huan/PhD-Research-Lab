"""v5.1: GitHub skill plugins (data/plugins), the AI-Scientist-v2 adapter, automatic venue ranking (CORE + SCImago from
Downloads), document export (.md/.tex/.docx/.html/.pdf), notes on answers, the revision guide of a review and the
interface language. No network: GitHub, CORE and the model are replaced by fakes."""
import _env  # noqa: F401  (must be first)
import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import plugins as PG
from backend.agent import AIWSError, sessions, skills
from backend.core import config, i18n
from backend.knowledge import ranking as RK
from backend.paper import export as EX
from backend.plugins import ai_scientist as AS


def gh_zip(files: dict, top: str = "repo-abc123") -> bytes:
    """A GitHub codeload archive: every file under one top folder."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(top + "/", "")
        for name, text in files.items():
            z.writestr(f"{top}/{name}", text)
    return buf.getvalue()


SKILL_MD = """---
name: Paper Summary
description: >
  Summarise a scientific paper
  in a fixed template
license: MIT
---
# Paper summary
Use [the checklist](references/checklist.md) and [missing](nope.md).
"""
AIS_REVIEW = 'reviewer_system_prompt_base = ("You review." "Be critical.")\n' \
             'reviewer_system_prompt_neg = reviewer_system_prompt_base + " Reject when unsure."\n' \
             'neurips_form = """## Review Form\\nScore it."""\nx = compute()\n'
AIS_WRITEUP = 'writeup_system_message_template = """Write well. Limit {page_limit} pages. Keep {{braces}}."""\n' \
              'writeup_prompt = """IDEA {idea_text} SUM {summaries} PLOTS {plot_list} TEX {latex_writeup} KEEP {other}"""\n'
AIS_IDEA = 'tools = []\nsystem_prompt = f"""You propose ideas. Be novel.\n\nYou have access to the following tools:\n{tools}"""\n'
TEMPLATE = "\\documentclass{article}\\graphicspath{{../figures/}}\n\\begin{document}\n\\begin{abstract}x\\end{abstract}\n\\end{document}\n"


def ais_repo() -> dict:
    return {"ai_scientist/perform_llm_review.py": AIS_REVIEW, "ai_scientist/perform_writeup.py": AIS_WRITEUP,
            "ai_scientist/perform_ideation_temp_free.py": AIS_IDEA, "ai_scientist/blank_icml_latex/template.tex": TEMPLATE,
            "ai_scientist/blank_icml_latex/icml2025.sty": "% sty", "README.md": "# AI Scientist"}


class Plugins(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.addCleanup(lambda: shutil.rmtree(PG.root(), ignore_errors=True))
        self.addCleanup(lambda: (config.data_dir() / "plugins.json").unlink(missing_ok=True))
        self.addCleanup(skills._cache.clear)
        PG._cache.clear()

    def install(self, url, files, sha="c0ffee12345"):
        with mock.patch.object(PG, "_resolve", return_value=("main", sha)), \
                mock.patch.object(PG, "_download", return_value=gh_zip(files)):
            return PG.install(url)

    def test_parse_url_and_ids(self):
        self.assertEqual(PG.parse_url("https://github.com/a/b.git"), {"owner": "a", "repo": "b", "ref": "", "subdir": ""})
        self.assertEqual(PG.parse_url("a/b/tree/dev/skills/x/"), {"owner": "a", "repo": "b", "ref": "dev", "subdir": "skills/x"})
        for bad in ("", "https://gitlab.com/a/b", "a/b/tree/main/../../etc"):
            with self.subTest(bad), self.assertRaises(PG.PluginError):
                PG.parse_url(bad)
        self.assertEqual(PG.plugin_id("SakanaAI", "AI-Scientist-v2"), "sakanaai-ai-scientist-v2")
        self.assertEqual(PG.plugin_id("o", "r", "skills/pdf"), "o-r-skills-pdf")
        with self.assertRaises(PG.PluginError):
            PG._dir("../x")
        with self.assertRaises(PG.PluginError):
            PG._dir("not-installed")

    def test_extract_strips_top_folder_and_refuses_unsafe_archives(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        n = PG.extract(gh_zip({"a/SKILL.md": "x", "b.txt": "y"}), d / "r1")
        self.assertEqual(n, 2)
        self.assertTrue((d / "r1" / "a" / "SKILL.md").is_file())
        self.assertEqual(PG.extract(gh_zip({"skills/one/SKILL.md": "x", "other.md": "y"}), d / "r2", "skills"), 1)
        self.assertTrue((d / "r2" / "one" / "SKILL.md").is_file())
        with self.assertRaises(PG.PluginError):
            PG.extract(gh_zip({"x.md": "y"}), d / "r3", "missing")
        with self.assertRaises(PG.PluginError):
            PG.extract(b"not a zip", d / "r4")
        evil = io.BytesIO()
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("top/../../escape.txt", "x")
        with self.assertRaises(PG.PluginError):
            PG.extract(evil.getvalue(), d / "r5")
        link = io.BytesIO()
        with zipfile.ZipFile(link, "w") as z:
            info = zipfile.ZipInfo("top/link")
            info.external_attr = 0o120777 << 16
            z.writestr(info, "/etc/passwd")
            z.writestr("top/ok.md", "ok")
        self.assertEqual(PG.extract(link.getvalue(), d / "r6"), 1)  # the symbolic link is skipped
        with mock.patch.object(PG, "MAX_FILES", 1), self.assertRaises(PG.PluginError):
            PG.extract(gh_zip({"a": "1", "b": "2"}), d / "r7")
        with mock.patch.object(PG, "MAX_UNPACKED", 1), self.assertRaises(PG.PluginError):
            PG.extract(gh_zip({"a": "12345"}), d / "r8")

    def test_yaml_subset_and_slug(self):
        y = PG._yaml("name: x\ndesc: |\n  line 1\n  line 2\nfold: >\n  a\n  b\nlist: [a, 'b']\nq: \"quoted\"\nnot a line\n")
        self.assertEqual((y["desc"], y["fold"], y["list"], y["q"]), ("line 1\nline 2", "a b", ["a", "b"], "quoted"))
        self.assertEqual(PG.slug("Paper Summary!"), "paper-summary")
        self.assertEqual(PG.slug("1st"), "s-1st")
        self.assertEqual(PG.slug("!!!"), "s")
        self.assertEqual(PG._category("latex writing"), "writing")
        self.assertEqual(PG._category("train a model"), "experiment")
        self.assertEqual(PG._category("search"), "research")

    def test_install_discovers_agent_skills_and_phdlab_skills(self):
        files = {"summary/SKILL.md": SKILL_MD, "summary/references/checklist.md": "- item A",
                 "review/SKILL.md": "---\nname: referee\ndescription: Critique a paper\n---\nBe harsh.",
                 "dup/SKILL.md": "---\nname: referee\n---\nSecond.", "noyaml/SKILL.md": "Just text.",
                 "skills/mine.md": "---\nname: mine\ntitle: Mine\n---\nDo it.", "skills/bad.md": "---\nname: B!\n---\n",
                 "skills/plain.md": "no front matter", "docs/guide.md": "# not a skill", ".hidden/SKILL.md": "x"}
        man = self.install("https://github.com/acme/sci-skills", files)
        names = sorted(s["name"] for s in man["skills"])
        self.assertEqual(names, ["mine", "noyaml", "paper-summary", "referee", "referee-2"])
        self.assertTrue(man["enabled"])
        self.assertEqual(len(man["errors"]), 1)
        loaded = {s["name"]: s for s in PG.project_skills()}
        ps = loaded["paper-summary"]
        self.assertIn("Summarise a scientific paper in a fixed template", ps["description"])
        self.assertIn("## Reference: references/checklist.md", ps["instructions"])  # linked reference inlined
        self.assertEqual(loaded["referee"]["agent"], "reviewer")
        self.assertEqual(ps["origin"], "plugin")
        # the chat sees them; a disabled skill disappears; disabling the plugin hides all of them
        cat = {s["name"]: s for s in skills.catalog()}
        self.assertEqual(cat["paper-summary"]["plugin"], "acme-sci-skills")
        PG.set_skill("referee", False)
        self.assertNotIn("referee", {s["name"] for s in skills.catalog()})
        self.assertFalse(next(s for s in PG.describe("acme-sci-skills")["skills"] if s["name"] == "referee")["enabled"])
        PG.set_skill("referee", True)
        PG.set_enabled("acme-sci-skills", False)
        self.assertNotIn("paper-summary", {s["name"] for s in skills.catalog()})
        self.assertEqual([p["id"] for p in PG.list_plugins()], ["acme-sci-skills"])
        # update keeps the switch; remove moves the folder to _trash
        PG.set_enabled("acme-sci-skills", True)
        with mock.patch.object(PG, "_resolve", return_value=("main", "newsha")), \
                mock.patch.object(PG, "_download", return_value=gh_zip({"x/SKILL.md": "---\nname: only\n---\nx"})):
            up = PG.update("acme-sci-skills")
        self.assertEqual((up["commit"], [s["name"] for s in up["skills"]], up["enabled"]), ("newsha", ["only"], True))
        self.assertEqual(PG.remove("acme-sci-skills"), {"removed": "acme-sci-skills"})
        self.assertEqual(PG.list_plugins(), [])
        self.assertTrue(any((PG.root() / "_trash").iterdir()))

    def test_plugin_skills_never_replace_builtin_commands(self):
        self.install("https://github.com/acme/clash", {"w/SKILL.md": "---\nname: write\ndescription: other write\n---\nx"})
        cat = {s["name"]: s for s in skills.catalog()}
        self.assertEqual(cat["write"]["origin"], "builtin")
        self.assertEqual(cat["clash-write"]["plugin"], "acme-clash")

    def test_broken_plugin_folder_is_reported_not_fatal(self):
        with mock.patch.object(PG, "project_skills", side_effect=OSError("disk")):
            skills._cache.clear()
            self.assertIn("write", skills.load())
            self.assertTrue(any(e["origin"] == "plugin" for e in skills.errors()))

    def test_ai_scientist_adapter(self):
        man = self.install(AS.URL, ais_repo())
        self.assertEqual(man["adapter"], "ai_scientist")
        self.assertEqual([s["name"] for s in man["skills"]], ["ais-idea", "ais-review", "ais-write"])
        repo = AS.repo_dir()
        p = AS.prompts(repo)
        self.assertEqual(p["reviewer_system_prompt_neg"], "You review.Be critical. Reject when unsure.")
        self.assertEqual(p["idea_system"], "You propose ideas. Be novel.")  # the upstream tool protocol is dropped
        self.assertEqual(p["source"], {"review": True, "writeup": True, "ideation": True})
        self.assertIs(AS.prompts(repo), p)  # cached until the source changes
        review = skills.get("ais-review")
        self.assertEqual(review["agent"], "reviewer")
        self.assertIn("## Review Form", review["instructions"])
        self.assertIn("Limit 8 pages. Keep {braces}", skills.get("ais-write")["instructions"])
        st = AS.status()
        self.assertEqual((st["installed"], st["templates"], st["commit"]), (True, ["icml"], "c0ffee1234"))
        # the full manuscript: template + figures + bibliography, disclosure enforced, unknown citations dropped
        with mock.patch("backend.knowledge.library.build_bibtex", return_value="@article{good2024,\n title={T}\n}\n"), \
                mock.patch("backend.knowledge.library.included", return_value=[]):
            system, user, out = AS.prepare("icml")
        self.assertIn("Limit 8 pages", system)
        self.assertIn("KEEP {other}", user)
        self.assertIn("good2024", user)
        self.assertIn("graphicspath{{figures/}", user)
        self.assertTrue((out / "icml2025.sty").is_file())
        with self.assertRaises(ValueError):
            AS.prepare("nips")
        with self.assertRaises(ValueError):
            AS.prepare("icbinb")  # not in this repository snapshot
        with self.assertRaises(ValueError):
            AS.finish("no latex here", out)
        res = AS.finish("```latex\n\\documentclass{article}\\begin{document}\\begin{abstract}A\\end{abstract}"
                        "\\cite{good2024,bad1} \\citep{bad2}\\end{document}\n```", out)
        tex = (out / "template.tex").read_text("utf-8")
        self.assertIn("\\paragraph{Disclosure.}", tex)
        self.assertIn("\\cite{good2024}", tex)
        self.assertNotIn("bad2", tex)
        self.assertEqual(res["dropped_citations"], ["bad1", "bad2"])
        AS.finish("\\documentclass{article}\\begin{document}Body\\end{document}", out)
        self.assertIn("\\section*{Disclosure}", (out / "template.tex").read_text("utf-8"))
        names = zipfile.ZipFile(io.BytesIO(AS.bundle())).namelist()
        self.assertIn("template.tex", names)
        with mock.patch("backend.paper.latex.which", return_value=None):
            self.assertFalse(AS.compile_pdf()["ok"])
        PG.remove(AS.PLUGIN_ID)
        self.assertEqual(AS.status(), {"installed": False, "url": AS.URL})

    def test_prompts_fallback_and_static_strings(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        p = AS.prompts(d)
        self.assertEqual(p["neurips_form"], AS.FALLBACK["neurips_form"])
        (d / "bad.py").write_text("x = (", "utf-8")
        self.assertEqual(AS.module_strings(d / "bad.py"), {})
        self.assertEqual(AS.module_strings(d / "missing.py"), {})
        self.assertEqual(AS._fmt("{a} {b} {{c}}", a=1), "1 {b} {c}")


class Ranking(unittest.TestCase):
    CSV = "\n".join([f"{i},Conference number {i} on things,CNF{i},ICORE2026,{'A*' if i % 2 else 'B'},Yes,4602" for i in range(60)]
                    + ["98,Advances in Neural Information Processing Systems (was NIPS),NeurIPS,ICORE2026,A*,Yes,4602",
                       "2042,IEEE International Conference on Acoustics Speech and Signal Processing,ICASSP,ICORE2026,Multiconference,Yes,",
                       "short,row"])

    def setUp(self):
        _env.isolate_config(self)
        self.addCleanup(lambda: shutil.rmtree(RK._dir(), ignore_errors=True))
        RK._cache.clear()

    def fetch(self):
        resp = mock.Mock(content=self.CSV.encode(), raise_for_status=lambda: None)
        with mock.patch("httpx.get", return_value=resp):
            return RK.refresh_core("ICORE2026")

    def test_core_download_and_matching(self):
        self.assertEqual(self.fetch(), {"source": "ICORE2026", "records": 62, "ranked": 61})
        for venue, acr in [("NeurIPS 2023", "NeurIPS"), ("Proc. NIPS", "NeurIPS"), ("Advances in Neural Information Processing Systems 36", "NeurIPS"),
                           ("ICASSP 2024 — Seoul", "ICASSP"), ("Pattern Recognition", None), ("the cnf3 workshop", None), ("", None)]:
            with self.subTest(venue):
                self.assertEqual(RK.match_core(venue).get("acronym"), acr)
        look = RK.lookup("CNF1 2025")
        self.assertEqual((look["conference"]["rank"], look["conference"]["source_url"]), ("A*", "https://portal.core.edu.au/conf-ranks/1/"))
        self.assertEqual(RK.lookup("ICASSP 2024")["conference"]["rank_raw"], "Multiconference")
        with self.assertRaises(ValueError):
            RK.refresh_core("nonsense")
        with mock.patch("httpx.get", return_value=mock.Mock(content=b"1,a,b,c,A", raise_for_status=lambda: None)), self.assertRaises(ValueError):
            RK.refresh_core("CORE2023")  # an incomplete export never replaces the data
        self.assertEqual(RK.status()["conferences"]["records"], 62)

    def test_scimago_from_downloads_and_library_check(self):
        self.fetch()
        dl = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, dl, True)
        with mock.patch.dict(os.environ, {"PHDLAB_DOWNLOADS": str(dl)}):
            self.assertEqual(RK.scan_downloads(), {"imported": False})
            (dl / "scimagojr 2024.csv").write_text("Sourceid;Title;Issn;SJR;SJR Best Quartile;Categories\n"
                                                    "1;IEEE Transactions on Geoscience and Remote Sensing;01962892, 15580644;2,4;Q1;Remote Sensing\n", "cp1252")
            res = RK.scan_downloads()
            self.assertEqual((res["imported"], res["year"], res["records"]), (True, 2024, 1))
            self.assertEqual(RK.scan_downloads(), {"imported": False, "file": "scimagojr 2024.csv"})  # same file: once
            out = RK.auto_refresh({"ranking": {"auto": True, "watch_downloads": True, "core_source": "ICORE2026", "refresh_days": 30}})
            self.assertNotIn("core", out)  # fresh CORE data is not downloaded again
            st = RK.status()
            self.assertEqual((st["journals"]["year"], st["journals"]["origin"], st["downloads"]), (2024, "scimagojr 2024.csv", ["scimagojr 2024.csv"]))
        self.assertEqual(RK.auto_refresh({"ranking": {"auto": False}}), {})
        with mock.patch.object(RK, "refresh_core", side_effect=OSError("offline")):
            out = RK.auto_refresh({"ranking": {"auto": True, "watch_downloads": False, "core_source": "CORE2023"}})
        self.assertEqual(out, {"core": {"error": "offline"}})
        j = RK.rank_entry({"venue": "IEEE Transactions on Geoscience and Remote Sensing", "issn": "0196-2892"})
        self.assertEqual((j["status"], j["quartile"], j["sjr"]), ("ranked", "Q1", 2.4))
        c = RK.rank_entry({"booktitle": "CNF3 proceedings"})
        self.assertEqual((c["status"], c["core_rank"]), ("conference", "A*"))
        self.assertEqual(RK.rank_entry({"venue": "Unknown Venue"})["status"], "unavailable")
        self.assertEqual(RK.rank_entry({}), {})
        # enrichment of search results: a conference gets its CORE rank, a journal its quartile
        papers = [{"venue": "Proceedings of CNF5", "publication_type": "conference"}]
        _env.run_async(RK.enrich(papers, {}))
        self.assertEqual(papers[0]["journal_ranking"]["core_rank"], "A*")

    def test_legacy_location_migrates(self):
        legacy = config.GLOBAL_DIR / "journal_rankings.json"
        legacy.write_text(json.dumps({"year": 2023, "records": []}), "utf-8")
        new = RK._dir() / "scimago.json"
        new.unlink(missing_ok=True)
        self.assertEqual(RK._path(), new)
        self.assertTrue(new.exists() and not legacy.exists())


class Export(unittest.TestCase):
    MD = ("# Kết quả\n\nMô hình **ViT** đạt *85%* với $F=2Nd^2$ và [link](https://example.com) ~~cũ~~.\n\n$$a^2+b^2$$\n\n"
          "- một\n- hai\n  1. con\n\n> trích dẫn\n\n---\n\n| A | B |\n|---|---|\n| 1 | x_y |\n\n```python\nprint('a & b')\n```\n\n"
          "```chart\n{\"title\": \"Acc\", \"x\": [1], \"series\": [{\"name\": \"s\", \"data\": [1]}]}\n```\n\n"
          "```svg\n<svg></svg>\n```\n\n![img](a.png) line  \nbreak `code`\n\n```phdlab-action\n{\"x\": 1}\n```\n")
    PNG = "data:image/png;base64," + __import__("base64").b64encode(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + (64).to_bytes(4, "big") + (32).to_bytes(4, "big") + b"\0" * 20).decode()

    def test_latex(self):
        tex, files = EX.to_latex(self.MD, "Báo cáo", {"chart-0": self.PNG})
        for part in ("\\section{Kết quả}", "\\textbf{ViT}", "\\emph{85\\%}", "$F=2Nd^2$", "\\[a^2+b^2\\]", "\\href{https://example.com}",
                     "\\begin{itemize}", "\\begin{enumerate}", "\\begin{quote}", "\\begin{tabular}{ll}", "x\\_y", "\\begin{verbatim}",
                     "\\includegraphics", "\\caption{Acc}", "[T5]{fontenc}", "\\maketitle", "\\sout{", "\\texttt{code}"):
            self.assertIn(part, tex, part)
        self.assertNotIn("phdlab-action", tex)
        self.assertEqual(list(files), ["chart-0.png"])
        plain, _ = EX.to_latex("Hello", "")
        self.assertIn("[T1]{fontenc}", plain)
        self.assertNotIn("\\maketitle", plain)

    def test_docx_is_valid_wordprocessingml(self):
        import xml.dom.minidom as M
        jpeg = "data:image/jpeg;base64," + __import__("base64").b64encode(b"\xff\xd8\xff\xc0\x00\x11\x08\x00\x20\x00\x40" + b"\0" * 12).decode()
        data = EX.to_docx(self.MD, "Báo cáo", {"chart-0": self.PNG, "svg-0": jpeg})
        with self.assertRaises(EX.ExportError):
            EX.decode_image("data:image/png;base64,abc")
        z = zipfile.ZipFile(io.BytesIO(data))
        for n in z.namelist():
            if n.endswith((".xml", ".rels")):
                M.parseString(z.read(n))
        doc = z.read("word/document.xml").decode()
        for part in ("Heading1", "Kết quả", "<w:b/>", "w:hyperlink", "Cambria Math", "<w:tbl>", "ListParagraph", "Consolas", "<w:drawing>",
                     "w:pBdr", "Quote", "Caption"):
            self.assertIn(part, doc, part)
        self.assertIn("word/media/image1.png", z.namelist())
        self.assertIn("word/media/image2.jpeg", z.namelist())

    def test_export_entry_point_and_formats(self):
        md, name, mime = EX.export("md", "T", "body")
        self.assertEqual((md, name), (b"# T\n\nbody", "T.md"))
        tex, name, _ = EX.export("tex", "Báo cáo", "x")
        self.assertTrue(name.endswith(".tex") and tex.startswith(b"\\documentclass"))
        zipped, name, mime = EX.export("tex", "T", self.MD, images={"chart-0": self.PNG})
        self.assertEqual((name, mime), ("T.zip", EX.MIME["zip"]))
        self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(zipped)).namelist()), ["chart-0.png", "main.tex"])
        html, _, _ = EX.export("html", "T", "$x$", lang="en")
        self.assertIn(b'lang="en"', html)
        self.assertIn(b"katex.render", html)  # the app's KaTeX renders math of a server-built document
        ui, _, _ = EX.export("html", "T", "", html="<p onclick='x()'>hi</p><script>bad()</script><iframe src=x></iframe><a href=\"javascript:x\">l</a>")
        self.assertNotIn(b"bad()", ui)
        self.assertNotIn(b"onclick", ui)
        self.assertNotIn(b"<iframe", ui)
        self.assertNotIn(b"javascript:", ui)
        self.assertNotIn(b"katex.render", ui)
        for args in (("zip", "T", "x"), ("md", "T", "  ")):
            with self.assertRaises(EX.ExportError):
                EX.export(*args)
        with mock.patch.object(EX, "browser", return_value=None), self.assertRaises(EX.ExportError):
            EX.export("pdf", "T", "x")
        with self.assertRaises(EX.ExportError):
            EX.decode_image("data:image/gif;base64,AAAA")
        self.assertEqual(EX.image_size(b"nothing"), (800, 600))
        jpeg = b"\xff\xd8\xff\xe0\x00\x04ab\xff\xc0\x00\x11\x08\x00\x20\x00\x40" + b"\0" * 10
        self.assertEqual(EX.image_size(jpeg), (64, 32))
        self.assertEqual(EX.safe_name("", "md"), "export.md")
        f = EX.save_copy(b"x", "a.md")
        self.assertTrue(f.is_file() and f.parent.name == "exports")

    @unittest.skipUnless(EX.browser(), "needs Edge / Chrome")
    def test_pdf_through_the_local_browser(self):
        pdf, name, mime = EX.export("pdf", "Báo cáo", "# Xin chào\n\n$E=mc^2$")
        self.assertTrue(pdf.startswith(b"%PDF") and name == "Báo_cáo.pdf" and mime == "application/pdf")


class NotesGuideLanguage(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)

    def test_notes_on_answers(self):
        s = sessions.create("notes")
        m = sessions.add_message(s["id"], "assistant", "Kết quả: độ chính xác 85%", "t1")
        n = sessions.add_note(s["id"], {"message_id": m["id"], "quote": "85%", "prefix": "chính xác ", "text": "Kiểm chứng", "junk": 1})
        self.assertEqual((n["status"], n["quote"], n["text"]), ("open", "85%", "Kiểm chứng"))
        self.assertNotIn("junk", n)
        p = sessions.add_note(s["id"], {"message_id": m["id"], "point": {"chart": "Acc", "series": "A", "x": 3, "y": 0.8, "evil": 1}})
        self.assertEqual(p["point"], {"chart": "Acc", "series": "A", "x": "3", "y": "0.8"})
        up = sessions.update_note(s["id"], n["id"], {"status": "resolved", "text": "ok", "quote": "ignored"})
        self.assertEqual((up["status"], up["text"], up["quote"]), ("resolved", "ok", "85%"))
        for bad in ({"quote": "x"}, {"message_id": m["id"]}, {"message_id": "m-none", "quote": "x"}):
            with self.subTest(bad), self.assertRaises(AIWSError):
                sessions.add_note(s["id"], bad)
        with self.assertRaises(AIWSError):
            sessions.update_note(s["id"], "nt-none", {"text": "x"})
        self.assertEqual(sessions.delete_note(s["id"], p["id"]), {"deleted": p["id"]})
        with self.assertRaises(AIWSError):
            sessions.delete_note(s["id"], p["id"])
        from backend.app import app
        c = TestClient(app)
        r = c.post(f"/api/chat/sessions/{s['id']}/notes", json={"message_id": m["id"], "quote": "Kết quả"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(c.get(f"/api/chat/sessions/{s['id']}/notes").json()["notes"]), 2)
        nid = r.json()["id"]
        self.assertEqual(c.put(f"/api/chat/sessions/{s['id']}/notes/{nid}", json={"text": "x"}).json()["text"], "x")
        self.assertEqual(c.delete(f"/api/chat/sessions/{s['id']}/notes/{nid}").status_code, 200)
        self.assertEqual(c.post(f"/api/chat/sessions/{s['id']}/notes", json={}).status_code, 400)

    def test_language_of_app_messages_and_agent_instructions(self):
        from backend.agent import dashboard, launch, orchestrator
        config.save_config({"ui": {"language": "en", "prose_font": "serif"}})
        self.assertEqual(config.load_config()["ui"], {**config.DEFAULTS["ui"], "language": "en", "prose_font": "serif"})
        self.assertEqual((i18n.lang(), i18n.L("vi", "en")), ("en", "en"))
        self.assertIn("**Project:**", dashboard.status_text())
        self.assertIn("**/ commands**", launch.help_text())
        self.assertIn("Literature review", launch.help_text().replace("Find, filter and synthesise literature on a topic", "Literature review"))
        text = orchestrator.instructions("global")
        self.assertIn("Answer in English", text)
        self.assertIn("```chart", text)
        self.assertIn("Planned run", orchestrator._run_started({"id": "R", "steps": [{"label": "a"}], "status": "APPROVAL_PENDING"}))
        config.save_config({"ui": {"language": "fr"}})
        self.assertEqual(config.load_config()["ui"]["language"], "vi")  # unknown choice keeps the default
        self.assertIn("Answer in Vietnamese", orchestrator.instructions("global"))
        self.assertIn("Đã bắt đầu run", orchestrator._run_started({"id": "R", "steps": [], "status": "RUNNING"}))

    def test_revision_guide_and_review_exports(self):
        from backend.app import app
        from backend.paper import review as RX
        c = TestClient(app)
        meta = RX.create_review("paper.md", b"# Title\n\n" + b"We propose X. Accuracy is 90% on the held-out set.\n" * 30)
        rid = meta["id"]
        self.assertEqual(c.get(f"/api/review/{rid}/download/guide").status_code, 400)  # no issues yet
        r = c.post(f"/api/review/{rid}/stage", json={"stage": "guide"})
        self.assertEqual(r.status_code, 400)  # reviewers first

        def put(s):
            s["reviewers"] = {"R1": {"text": "Weak baselines."}}
            s["issues"] = [{"id": "I1", "severity": "major", "title": "Baselines", "location": "Sec 4", "problem": "Too weak",
                            "fix": "Add two baselines", "status": "open", "raised_by": ["R1"]},
                           {"id": "I2", "severity": "critical", "title": "Claim", "location": "Abstract", "problem": "Unsupported",
                            "fix": "", "status": "open", "raised_by": ["R1"]}]
            s["fixes"] = {"I1": {"original": "old", "revised": "new", "status": "accepted", "plan": "run them"},
                          "I2": {"original": "a", "revised": "b", "status": "dismissed"}}
            s["meta"] = {"text": "AC", "decision": "Major revision"}
        RX.update_state(rid, put)
        md = c.get(f"/api/review/{rid}/download/guide").text
        self.assertLess(md.index("I2 · CRITICAL"), md.index("I1 · MAJOR"))  # critical first
        self.assertIn("**Area-chair decision:** Major revision", md)
        self.assertIn("After:", md)
        self.assertIn("[TBD: decide the fix]", md)
        self.assertIn("ORIGINAL: old", RX.fixes_digest(RX.load_state(rid)))
        docx = c.get(f"/api/review/{rid}/download/guide?format=docx")
        self.assertEqual(docx.status_code, 200)
        self.assertTrue(docx.content.startswith(b"PK"))
        self.assertEqual(c.get(f"/api/review/{rid}/download/report?format=tex").status_code, 200)
        self.assertEqual(c.get(f"/api/review/{rid}/download/fixes?format=html").status_code, 200)
        self.assertEqual(c.get(f"/api/review/{rid}/download/response?format=md").status_code, 404)
        self.assertEqual(c.get(f"/api/review/{rid}/download/response?format=docx").status_code, 400)  # nothing to export
        # the model-written guide replaces the automatic one
        with mock.patch("backend.providers.models.stream_agent") as sa:
            async def fake(*a, **k):
                yield "delta", "# Revision guide\nStep 1"
                yield "meta", {"text": "# Revision guide\nStep 1", "engine": "fake", "note": ""}
            sa.side_effect = fake
            body = c.post(f"/api/review/{rid}/stage", json={"stage": "guide", "language": "en"}).text
        self.assertIn('"type": "done"', body)
        self.assertEqual(c.get(f"/api/review/{rid}/download/guide").text, "# Revision guide\nStep 1")
        self.assertEqual(RX.load_state(rid)["guide"]["engine"], "fake")


class Api(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.addCleanup(lambda: shutil.rmtree(PG.root(), ignore_errors=True))
        from backend.app import app
        self.c = TestClient(app)

    def test_plugin_endpoints(self):
        self.assertEqual(self.c.post("/api/plugins", json={}).status_code, 400)
        with mock.patch.object(PG, "_resolve", side_effect=OSError("offline")):
            self.assertEqual(self.c.post("/api/plugins", json={"url": "a/b"}).status_code, 502)
            self.assertEqual(self.c.post("/api/paper/ais/install").status_code, 502)
        self.assertEqual(self.c.post("/api/plugins", json={"url": "gitlab.com/x"}).status_code, 400)
        with mock.patch.object(PG, "_resolve", return_value=("main", "s1")), \
                mock.patch.object(PG, "_download", return_value=gh_zip({"k/SKILL.md": "---\nname: k\n---\nx"})):
            out = self.c.post("/api/plugins", json={"url": "acme/k"}).json()
            self.assertEqual(out["id"], "acme-k")
            self.assertEqual(self.c.post("/api/plugins/acme-k/update").status_code, 200)
            ais = self.c.post("/api/paper/ais/install")
        self.assertEqual(ais.status_code, 200)
        listing = self.c.get("/api/plugins").json()
        self.assertEqual(sorted(p["id"] for p in listing["plugins"]), ["acme-k", "sakanaai-ai-scientist-v2"])
        self.assertFalse(self.c.put("/api/plugins/acme-k", json={"enabled": False}).json()["enabled"])
        self.assertEqual(self.c.put("/api/plugins/skills/k", json={"enabled": False}).json(), {"skill": "k", "enabled": False})
        with mock.patch.object(PG, "_resolve", side_effect=OSError("offline")):
            self.assertEqual(self.c.post("/api/plugins/acme-k/update").status_code, 502)
        self.assertEqual(self.c.delete("/api/plugins/acme-k").status_code, 200)
        self.assertEqual(self.c.delete("/api/plugins/acme-k").status_code, 400)
        st = self.c.get("/api/paper/ais").json()
        self.assertEqual((st["installed"], st["has_tex"]), (True, False))
        self.assertEqual(self.c.get("/api/paper/ais/download/tex").status_code, 404)
        self.assertEqual(self.c.post("/api/paper/ais/writeup", json={"template": "nope"}).status_code, 400)

    def test_ranking_export_and_library_check(self):
        with mock.patch.object(RK, "auto_refresh", return_value={}):
            st = self.c.get("/api/ranking").json()
            self.assertIn("scimago_url", st)
            self.assertEqual(self.c.post("/api/library/rank", json={}).json()["checked"] >= 0, True)
        self.assertEqual(self.c.get("/api/ranking/lookup").status_code, 400)
        self.assertEqual(self.c.get("/api/ranking/lookup?venue=Nowhere").json(), {"venue": "Nowhere"})
        r = self.c.post("/api/export", json={"format": "docx", "title": "Báo cáo", "markdown": "# Hi"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("filename*=UTF-8''B%C3%A1o_c%C3%A1o.docx", r.headers["content-disposition"])
        self.assertEqual(self.c.post("/api/export", json={"format": "rtf", "markdown": "x"}).status_code, 400)
        with mock.patch.object(EX, "browser", return_value=None):
            self.assertEqual(self.c.post("/api/export", json={"format": "pdf", "markdown": "x"}).status_code, 501)
            self.assertFalse(self.c.get("/api/export/capabilities").json()["pdf"])


if __name__ == "__main__":
    unittest.main()
