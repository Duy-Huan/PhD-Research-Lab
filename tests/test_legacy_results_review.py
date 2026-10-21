"""Legacy results catalogue + external paper review (coverage pass)."""
import _env  # noqa: F401  (must be first)
import asyncio
import json
import unittest
from unittest import mock

from backend.paper import results as RS
from backend.paper import review as RX
from backend.core.config import workspace
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
