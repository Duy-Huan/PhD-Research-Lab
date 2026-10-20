"""Legacy results catalogue + external paper review (coverage pass)."""
import _env  # noqa: F401  (must be first)
import asyncio
import json
import unittest
from unittest import mock

from backend import results as RS, review_ext as RX
from backend.config import workspace
from pdfgen import make_pdf

PAPER_MD = "# Spectral Denoising Transformer\n\n## Abstract\nWe propose X. " + "Body text sentence. " * 60 + \
    "\n## Introduction\nOur previous work showed Y. Contact a@b.edu. See github.com/me/repo. TODO fix.\n" \
    "## Method\nFig. 1 and Table II.\n## Experiments\nResults (1)\n## Conclusion\nDone.\n## Acknowledgments\nThanks.\n" \
    "\nReferences\n[1] A. Paper.\n[2] B. Paper.\n"


def run(c):
    return asyncio.run(c)


class Results(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-results")

    def test_add_update_delete_and_pool(self):
        png = RS.add_file("fig 1!.png", b"\x89PNGdata", title="Curve", notes="loss curve", tags=["a", 1])
        self.assertEqual((png["kind"], png["file"], png["mime"]), ("figure", "fig_1.png", "image/png"))
        js = RS.add_file("m.json", json.dumps({"psnr": 31.2, "flag": True, "name": "x"}).encode())
        self.assertEqual(js["metrics"], {"psnr": 31.2})
        self.assertEqual(RS.add_file("t.tex", b"\\begin{table}x\\end{table}")["kind"], "table")
        self.assertEqual(RS.add_file("d.tex", b"\\section{x}")["kind"], "document")
        self.assertEqual(RS.add_file("t.md", b"| a | b |\n|---|---|\n| 1 | 2 |")["kind"], "table")
        self.assertEqual(RS.add_file("n.md", b"# notes")["kind"], "document")
        self.assertEqual(RS.add_file("s.py", b"print(1)")["kind"], "code")
        self.assertEqual(RS.add_file("x.csv", b"a,b\n1,2")["kind"], "table")
        self.assertEqual(RS.add_file("x.log", b"loss=1")["kind"], "data")
        self.assertEqual(RS.add_file("p.eps", b"%!PS")["kind"], "figure")
        scan = RS.add_file("scan.pdf", make_pdf([[(10, " ")]]))
        self.assertEqual(scan["kind"], "figure")
        self.assertIn("No extractable text", scan["warning"])
        self.assertEqual(RS.add_file("doc.pdf", make_pdf([[(10, "Some report text")]]))["kind"], "document")
        for bad in (("x.exe", b"MZ"), ("e.txt", b""), ("bad.docx", b"zip?")):
            with self.assertRaises(RS.ResultError):
                RS.add_file(*bad)
        with mock.patch.object(RS, "MAX_FILE", 2):
            with self.assertRaises(RS.ResultError):
                RS.add_file("big.txt", b"123")
        note = RS.add_note("", "PSNR 31.5 dB on CAVE\nmore", tags=["lab"], kind="bogus")
        self.assertEqual((note["title"], note["kind"]), ("PSNR 31.5 dB on CAVE", "note"))
        with self.assertRaises(RS.ResultError):
            RS.add_note("t", "  ")
        up = RS.update(note["id"], {"title": "T2", "kind": "table", "tags": ["x", " "], "metrics": {"a": 1, "b": "no"}, "text": "new body"})
        self.assertEqual((up["title"], up["kind"], up["tags"], up["metrics"]), ("T2", "table", ["x"], {"a": 1}))
        self.assertEqual(RS.text(note["id"]), "new body")
        with self.assertRaises(RS.ResultError):
            RS.get("zz")
        with self.assertRaises(RS.ResultError):
            RS.get("0123456789")
        with self.assertRaises(RS.ResultError):
            RS.file_path(note["id"])
        (RS.rdir() / png["id"] / png["file"]).rename(RS.rdir() / png["id"] / "moved.png")
        with self.assertRaises(RS.ResultError):
            RS.file_path(png["id"])
        RS.delete(js["id"])
        RS.add_file("m2.json", b"{}")
        self.assertNotIn(js["id"], [i["id"] for i in RS.load()])
        self.assertTrue((RS.rdir() / "_trash" / js["id"]).exists())
        refs = [p["ref"] for p in RS.pool()]
        self.assertIn(f"up:{note['id']}", refs)

    def test_pool_with_runs_tables_and_resolve(self):
        from backend import paper
        p = paper.load_project()
        p.update(tables=["\\begin{table}\\caption{Main results}\\end{table}", "\\begin{tabular}{c}\\end{tabular}"], results_notes="PSNR up")
        paper.save_project(p)
        fig = RS.add_file("curve.png", b"\x89PNG", title="Loss curve", notes="desc")
        RS.update(fig["id"], {"findings": "converges", "metrics": {"psnr": 31}})
        runs = [{"id": "run-a1b2c3", "status": "done", "metrics": {"psnr": 31.24, "x": "s"}, "cmd": "python t.py",
                 "figures": ["loss.png", "table.csv"]}, {"id": "run-bad", "status": "failed"}]
        run_rec = {"id": "run-a1b2c3", "cmd": "python t.py", "metrics": {"psnr": 31.2}, "stdout": "log",
                   "parsed": {"series": {"loss": [[1, 0.9], [2, 0.5]], "acc": [0.1, 0.2], "bad": [["x", "y"]]}}}
        with mock.patch("backend.sandbox.list_runs", return_value=runs), mock.patch("backend.sandbox.get_run", return_value=run_rec):
            pool = RS.pool()
            refs = {x["ref"]: x for x in pool}
            self.assertIn("run:run-a1b2c3", refs)
            self.assertTrue(refs["runfig:run-a1b2c3/loss.png"]["thumb"])
            self.assertEqual(refs["table:0"]["title"], "Main results")
            self.assertEqual(refs["table:1"]["title"], "LaTeX table 2")
            r = RS.resolve("run:run-a1b2c3")
            self.assertIn("loss: 0.9, 0.5", r["body"])  # [step, value] series are shown (was always dropped)
            self.assertIn("acc: 0.1, 0.2", r["body"])
            self.assertNotIn("bad:", r["body"])
        up = RS.resolve(f"up:{fig['id']}")
        self.assertIn("converges", up["body"])
        self.assertEqual(up["figure"]["path"], f"figures/{RS.figure_name(RS.get(fig['id']))}")
        self.assertEqual(RS.resolve("runfig:run-x/f.pdf")["figure"]["path"], "figures/run-run-x--f.pdf")
        self.assertNotIn("figure", RS.resolve("runfig:run-x/f.csv"))
        self.assertIn("Include verbatim", RS.resolve("table:0")["body"])
        self.assertIsNone(RS.resolve("table:99"))
        self.assertEqual(RS.resolve("notes")["body"], "PSNR up")
        self.assertIsNone(RS.resolve("weird:1"))
        n = RS.add_note("t", "x" * 100)
        self.assertIn("…[truncated]", RS.resolve(f"up:{n['id']}", budget=10)["body"])
        empty = RS.add_file("e.png", b"\x89PNG")
        self.assertEqual(RS.resolve(f"up:{empty['id']}")["body"], "(no description yet)")
        with mock.patch("backend.sandbox.list_runs", side_effect=RuntimeError), mock.patch("backend.paper.load_project", side_effect=RuntimeError):
            self.assertTrue(RS.pool())

    def test_figures_digest_and_corruption(self):
        fig = RS.add_file("f.png", b"\x89PNG", title="My Figure")
        name = RS.figure_name(RS.get(fig["id"]))
        from backend.sandbox import runs_dir
        (runs_dir() / "run-77" / "figures").mkdir(parents=True)
        (runs_dir() / "run-77" / "figures" / "acc.png").write_bytes(b"x")
        tex = f"\\includegraphics[width=1cm]{{figures/{name}}} \\includegraphics{{figures/run-run-77--acc.png}}"
        files = RS.figure_files([tex])
        self.assertEqual(len(files), 2)
        self.assertEqual(RS.figure_files(["nothing"]), [])
        dest = workspace() / "build"
        self.assertEqual(len(RS.copy_figures([tex], dest)), 2)
        self.assertEqual(len(RS.copy_figures([tex], dest)), 2)  # second copy is a no-op
        with mock.patch("backend.sandbox.runs_dir", side_effect=RuntimeError):
            self.assertEqual(len(RS.figure_files([tex])), 1)
        RS.update(fig["id"], {"findings": "F" * 700})
        RS.add_note("note", "excerpt text here")
        d = RS.digest()
        self.assertIn("findings", d)
        self.assertIn("excerpt", d)
        self.assertEqual(RS.digest(purged={f"result:{i['id']}" for i in RS.load()}), "")
        self.assertIn("more result", RS.digest(budget=50))
        self.assertEqual(RS.figure_label({"title": "", "id": "abcd1234"}), "fig:fig-abcd")
        (RS.rdir() / "index.json").write_text("{bad", "utf-8")
        self.assertEqual(RS.load(), [])
        self.assertTrue(list(RS.rdir().glob("index.json.corrupt-*")), "the results catalogue must be kept")

    def test_analysis_and_tables(self):
        img = RS.add_file("p.png", b"\x89PNG" + b"0" * 10)
        tif = RS.add_file("p.tif", b"II*")
        csv = RS.add_file("t.csv", b"model,psnr\nA,31.2")
        tex = RS.add_file("t.tex", b"pre \\begin{table}[t]\\begin{tabular}{c}1\\end{tabular}\\end{table} post")
        note = RS.add_note("n", "x")
        RS.update(note["id"], {"text": ""})
        answers = iter(["**What it shows:** a curve", "**What** csv", "```latex\n\\begin{table}\\begin{tabular}{c}\\end{tabular}\\end{table}\n```", "no table here"])

        async def agent(name, sys, user=None, messages=None, max_tokens=0, temperature=0):
            return {"text": next(answers), "engine": "fake", "note": ""}
        with mock.patch("backend.llm.call_agent", agent):
            self.assertIn("curve", run(RS.analyze(img["id"]))["item"]["findings"])
            self.assertIn("csv", run(RS.analyze(csv["id"]))["item"]["findings"])
            with self.assertRaises(RS.ResultError):
                run(RS.analyze(tif["id"]))
            with self.assertRaises(RS.ResultError):
                run(RS.analyze(note["id"]))
            self.assertEqual(run(RS.to_latex_table(tex["id"]))["engine"], "verbatim")
            self.assertTrue(run(RS.to_latex_table(csv["id"]))["latex"].startswith("\\begin{table}"))
            with self.assertRaises(RS.ResultError):
                run(RS.to_latex_table(csv["id"]))
            with self.assertRaises(RS.ResultError):
                run(RS.to_latex_table(img["id"]))
        (RS.rdir() / img["id"] / img["file"]).write_bytes(b"\x89PNG" + b"0" * (5 * 1024 * 1024 + 1))
        with self.assertRaises(RS.ResultError):
            run(RS.analyze(img["id"]))


class Review(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-review")

    def test_create_prescreen_settings_and_crud(self):
        m = RX.create_review("paper.md", PAPER_MD.encode())
        self.assertEqual(m["title"], "Spectral Denoising Transformer")
        ps = m["prescreen"]
        self.assertEqual((ps["figures"], ps["tables"], ps["references"]), (1, 1, 2))
        self.assertTrue(any("e-mail" in a for a in ps["anonymity"]))
        self.assertTrue(any("previous work" in a for a in ps["anonymity"]))
        self.assertTrue(any("github" in a for a in ps["anonymity"]))
        self.assertIn("TODO", ps["placeholders"])
        txt = RX.prescreen_text(ps, truncated=True)
        self.assertIn("truncated", txt)
        self.assertIn("anonymity", txt)
        tex = ("\\documentclass{article}\\title{A \\\\ Title}\\author{Me}\\begin{document}\\begin{equation}x\\end{equation}"
               + "word " * 200 + "\\cite{a}\\citep{b}\\bibitem{c}\\end{document}")
        t = RX.create_review("p.tex", tex.encode())
        self.assertEqual(t["title"], "A Title")
        self.assertEqual(t["source"], "source.tex")
        self.assertIn("\\author{...} is filled in the LaTeX source", t["prescreen"]["anonymity"])
        self.assertEqual(t["prescreen"]["references"], 1)
        pdf = make_pdf([[(10, "arXiv:1234"), (10, "A Proper Long Paper Title Here")] + [(9, "text " * 20)] * 30])
        pm = RX.create_review("p.pdf", pdf)
        self.assertEqual(pm["title"], "A Proper Long Paper Title Here")
        self.assertIn("[[Page 1]]", RX.paper_text(pm["id"]))
        for name, data, msg in (("x.exe", b"x", "Unsupported"), ("s.pdf", make_pdf([[(10, " ")]]), "OCR"),
                                ("short.txt", b"tiny", "Too little"), ("bad.docx", b"nozip", "Could not read")):
            with self.assertRaises(RX.ReviewError) as cm:
                RX.create_review(name, data)
            self.assertIn(msg, str(cm.exception))
        with mock.patch.object(RX, "MAX_UPLOAD", 3):
            with self.assertRaises(RX.ReviewError):
                RX.create_review("a.txt", b"1234")
        s = RX.set_settings(m["id"], {"venue": {"type": "workshop", "blind": False, "name": "X"}, "n_reviewers": 2, "title": "New"})
        self.assertEqual((s["venue"]["type"], s["n_reviewers"], s["title"]), ("conference", 2, "New"))
        self.assertEqual(s["prescreen"]["anonymity"], [])
        self.assertEqual(RX.get_review(m["id"])["meta"]["title"], "New")
        self.assertEqual(RX.get_active(), m["id"])
        self.assertEqual(len(RX.list_reviews()), 3)
        RX.delete_review(m["id"])
        self.assertEqual(RX.get_active(), "")
        self.assertEqual(len(RX.list_reviews()), 2)
        for bad in ("../x", "0123456789"):
            with self.assertRaises(RX.ReviewError):
                RX.load_meta(bad)
        self.assertEqual(RX._detect_title("x\nshort\n", ".txt"), "")
        self.assertEqual(RX._detect_title("# Heading here\n", ".md"), "Heading here")

    def test_fixes_reports_and_state(self):
        m = RX.create_review("paper.md", PAPER_MD.encode())
        rid = m["id"]
        with self.assertRaises(RX.ReviewError):
            RX.apply_fixes(rid)
        with self.assertRaises(RX.ReviewError):
            RX.add_source(rid, "a.docx", b"x")
        RX.add_source(rid, "main.tex", b"Intro: we   propose X.\nOld sentence here.\nOther text")
        issues = RX.normalise_issues([{"id": "I1", "severity": "Major issue", "quote": "we propose X", "title": "t", "raised_by": ["R1"]},
                                      {"id": "I1", "severity": "CRITICAL!!", "quote": "not in paper at all"},
                                      {"severity": "typo-ish", "problem": "p"}, {"severity": "whatever"}, "junk"], RX.paper_text(rid))
        self.assertEqual([i["severity"] for i in issues], ["critical", "major", "minor", "typo"])
        self.assertEqual(sorted(i["id"] for i in issues), ["I1", "I1b", "I3", "I4"])
        self.assertTrue(next(i for i in issues if i["id"] == "I1")["quote_found"])

        def setup(st):
            st["issues"] = issues
            st["reviewers"] = {"R1": {"text": "**Recommendation:** Accept.\n**Overall score:** 7/10\n**Confidence:** 4/5"}}
            st["meta"] = {"text": "**Decision:** Minor Revision\n**Consensus score:** 6/10", "decision": "Minor"}
            st["fixes"] = {"I1": {"status": "accepted", "original": "we propose X", "revised": "we introduce X", "note": "n"},
                           "I1b": {"status": "accepted", "original": "missing text", "revised": "y"},
                           "I3": {"status": "accepted", "original": "", "revised": "", "plan": "add experiment"},
                           "I4": {"status": "proposed"}}
        RX.update_state(rid, setup)
        out = RX.apply_fixes(rid)
        self.assertEqual((out["applied"], out["not_found"], out["skipped"]), (["I1"], ["I1b"], ["I3"]))
        self.assertIn("we introduce X", RX.source_text(rid))
        self.assertIn("we   propose X", RX.source_text(rid, revised=False))
        self.assertEqual(RX.apply_fixes(rid, ids=["I4"])["applied"], [])
        st = RX.load_state(rid)
        self.assertIn("DONE", RX.issues_digest(st))
        rep = RX.report_md(rid)
        self.assertIn("- [x] **I1", rep)
        fx = RX.fixes_md(rid)
        self.assertIn("**Plan**", fx)
        ctx = RX.chat_context(rid)
        self.assertIn("Meta-review", ctx)
        self.assertEqual(RX.chat_context(""), "")
        self.assertEqual(RX.chat_context("0123456789"), "")
        self.assertEqual(RX.parse_review_header(st["reviewers"]["R1"]["text"]), {"recommendation": "Accept", "score": 7, "confidence": 4})
        self.assertEqual(RX.parse_meta_header(st["meta"]["text"]), {"decision": "Minor Revision", "score": 6})
        self.assertEqual(RX.parse_review_header("nothing")["score"], None)
        self.assertEqual(RX.parse_fix("<<<ORIGINAL\na\n>>>\n<<<REVISED\nb\n>>>")["revised"], "b")
        self.assertEqual(RX.parse_fix("free text")["note"], "free text")
        self.assertEqual(RX.issues_digest({"issues": [], "fixes": {}}), "(no issues extracted)")
        RX.save_state(rid, st)
        (RX._dir(rid) / "state.json").write_text("{corrupt", "utf-8")
        self.assertEqual(RX.load_state(rid)["issues"], [])
        self.assertTrue(list(RX._dir(rid).glob("state.json.corrupt-*")), "reviewer reports must not be silently lost")

    def test_text_matching_and_excerpts(self):
        self.assertIsNone(RX.find_span("abc", "ab"))
        self.assertIsNone(RX.find_span("abc", "      "))
        self.assertEqual(RX.find_span("Hello   wide\nworld here", "Hello wide world"), (0, 18))
        self.assertIsNotNone(RX.find_span("HELLO WIDE WORLD", "hello wide world"))
        self.assertTrue(RX.quote_found("con-\ntinued ﬁne text", "continued fine text"))
        self.assertFalse(RX.quote_found("x", "tiny"))
        m = RX.create_review("paper.md", PAPER_MD.encode())
        rid = m["id"]
        ex, fmt = RX.excerpt_for(rid, {"quote": "Our previous work showed Y"})
        self.assertIn("previous work", ex)
        self.assertIn("plain text", fmt)
        ex, _ = RX.excerpt_for(rid, {"quote": "absent quote", "location": "Section: Method"})
        self.assertTrue(ex.lower().lstrip().startswith(("body", "#", "we", "sentence", "text")) or "Method" in ex)
        ex, _ = RX.excerpt_for(rid, {"location": "appendix"})
        self.assertTrue(ex.startswith("# Spectral"))
        RX.add_source(rid, "main.tex", b"\\section{Method} details")
        self.assertEqual(RX.excerpt_for(rid, {"quote": "details"})[1], "LaTeX source")


if __name__ == "__main__":
    unittest.main()
