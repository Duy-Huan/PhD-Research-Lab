"""Legacy text modules (coverage pass): paper project/assembly, writing briefs, live critic, provenance seals, prompts."""
import _env  # noqa: F401  (must be first)
import asyncio
import io
import json
import struct
import unittest
import zipfile
import zlib
from unittest import mock

from backend import brief as BR, critic as CR, paper as PA, prompts as PR, provenance as PV, review_prompts as RP
from backend.config import workspace


def tiny_png() -> bytes:
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    return PV.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b"")


def tiny_jpeg() -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    dqt = b"\xff\xdb" + struct.pack(">H", 4) + b"\x00\x00"
    return b"\xff\xd8" + app0 + dqt + b"\xff\xda\x00\x02SCANDATA\xff\xd9"


class Paper(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-paper")

    def test_project_state_and_corruption(self):
        p = PA.load_project()
        p["title"] = "T"
        PA.save_project(p)
        self.assertEqual(PA.load_project()["title"], "T")
        (workspace() / "project.json").write_text("{half-written", "utf-8")
        self.assertEqual(PA.load_project()["title"], "")
        self.assertTrue(list(workspace().glob("project.json.corrupt-*")), "a damaged paper must be kept, not overwritten")
        (workspace() / "project.json").write_text("[1, 2]", "utf-8")
        PA.load_project()
        with mock.patch("pathlib.Path.read_text", side_effect=PermissionError("locked")):
            self.assertEqual(PA.load_project()["style"], "IEEE")
        PA.write_ws("x.txt", "hi")
        self.assertEqual(PA.read_ws("x.txt"), "hi")
        self.assertEqual(PA.read_ws("nope.txt"), "")

    def test_cleaning_and_citations(self):
        self.assertEqual(PA.clean_section("abstract", "\\begin{abstract}\\section{A}Text\\end{abstract}"), "Text")
        self.assertTrue(PA.clean_section("methodology", "\\documentclass{x}\nBody").startswith("\\section{Methodology}"))
        self.assertEqual(PA.clean_section("custom_x", "Body").split("\n")[0], "\\section{Custom_X}")
        self.assertTrue(PA.clean_section("introduction", "\\section{Intro}\nX\\bibliography{refs}").endswith("X"))
        tex, unknown = PA.fix_citations("A \\citet{good,bad} B \\citep[p.~3]{bad} C \\cite{good}", {"good"})
        self.assertIn("\\citet{good}", tex)  # the natbib command is preserved
        self.assertIn("[CITATION NEEDED]", tex)
        self.assertEqual(unknown, ["bad"])
        self.assertEqual(PA.used_keys("\\cite{a, b}\\citep{c}"), {"a", "b", "c"})

    def test_assemble_styles_and_zip(self):
        p = PA.load_project()
        p.update(title="Paper", authors="Ann | MIT | ann@mit.edu | USA\nBob", keywords="k1",
                 sections={"abstract": "Abs \\cite{nokey}", "introduction": "\\section{Introduction}\nIntro"})
        main, bib, rep = PA.assemble(p)
        self.assertIn("\\IEEEauthorblockN{Ann}", main)
        self.assertIn("\\nocite{*}", main)  # no valid citation left
        self.assertEqual(rep["unknown"], ["nokey"])
        self.assertIn("methodology", rep["missing_sections"])
        p["style"] = "ACM"
        main, _, _ = PA.assemble(p)
        self.assertIn("\\email{ann@mit.edu}", main)
        self.assertIn("\\country{Country}", main)
        main, _, rep = PA.assemble({"sections": {}})
        self.assertIn("[TBD: abstract]", main)
        self.assertEqual(rep["placeholders"], 2)
        PA.save_project(p)
        z = zipfile.ZipFile(io.BytesIO(PA.build_zip()))
        self.assertTrue({"main.tex", "references.bib", "README.md"} <= set(z.namelist()))
        self.assertIn("Paper", z.read("README.md").decode())


class Brief(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-brief")

    def test_clean_and_render(self):
        b = BR.clean_brief({"must": ["a", " ", 3], "avoid": "notalist", "tone": "concise", "length": "weird", "words": "500",
                            "cite": ["ok_key", "bad key!"], "results": [{"ref": "notes", "as": "table"}, {"ref": "evil"},
                                                                       {"ref": "table:1", "as": "nope"}], "results_only": False})
        self.assertEqual(b["must"], ["a", "3"])
        self.assertEqual(b["avoid"], [])
        self.assertEqual((b["tone"], b["length"], b["words"]), ("concise", "", 500))
        self.assertEqual(b["cite"], ["ok_key"])
        self.assertEqual([r["as"] for r in b["results"]], ["table", "auto"])
        self.assertEqual(BR.clean_brief({"words": "99999"})["words"], 0)
        self.assertEqual(BR.clean_paper_brief({"story": "s" * 7000})["story"], "s" * 6000)
        p = {"section_notes": {"introduction": "Motivate HSI denoising"},
             "section_briefs": {"introduction": {"outline": ["gap", "idea"], "must": ["m"], "avoid": ["x"], "tone": "formal",
                                                 "words": 400, "cite": ["k1", "k2"], "results": [{"ref": "notes"}, {"ref": "table:7", "as": "figure"}]},
                                "methodology": {"length": "short"}},
             "paper_brief": {"story": "S", "style": "St", "terms": "T", "avoid": "A"}}
        fake = {"notes": {"title": "Notes", "kind": "notes", "body": "PSNR 31.2", "figure": None}}
        with mock.patch("backend.results.resolve", side_effect=lambda ref, room: fake.get(ref)):
            a = BR.render(p, "introduction", "author", valid_keys=["k1"])
            e = BR.render(p, "methodology", "editor")
            r = BR.render(p, "introduction", "reviewer")
        for frag in ("PAPER-WIDE BRIEF", "1. gap", "Must include", "Must avoid", "Tone", "about 400 words", "k1", "PSNR 31.2",
                     "no longer available", "Present ONLY"):
            self.assertIn(frag, a)
        self.assertNotIn("k2", a.split("prominence")[1].split("\n")[0])
        self.assertIn("Target length: Noticeably shorter", e)
        self.assertTrue(r.startswith("AUTHOR'S BRIEF that this section must satisfy"))
        self.assertEqual(BR.render({}, "introduction"), "")
        self.assertTrue(BR.is_empty(BR.get_brief({}, "x")))

    def test_figure_results(self):
        p = {"section_briefs": {"experiments": {"results": [{"ref": "runfig:run-abc123/fig.png", "as": "figure", "note": "main plot"},
                                                            {"ref": "up:0123456789", "as": "figure"}], "results_only": False}}}
        res = {"runfig:run-abc123/fig.png": {"title": "Curve", "kind": "figure", "body": "loss curve",
                                             "figure": {"path": "figures/fig.png", "label": "fig:curve"}},
               "up:0123456789": {"title": "Table", "kind": "table", "body": "a,b"}}
        with mock.patch("backend.results.resolve", side_effect=lambda ref, room: res.get(ref)):
            out = BR.render(p, "experiments")
        self.assertIn("\\includegraphics[width=\\linewidth]{figures/fig.png}", out)
        self.assertIn("Author's note for R1: main plot", out)
        self.assertIn("present as: auto", out)  # figure requested but the result has no image
        self.assertNotIn("Present ONLY", out)


class Critic(unittest.TestCase):
    def test_rules(self):
        text = ("Intro $x$ and $y\n\n\\begin{equation}a$b\\end{equation}\n\\end{itemize}\n\n"
                "\\begin{align}\nx\n\\end{equation}\n\nBad {brace\n\n\\cite{good,missing} [TBD: numbers] % $ comment\n"
                "Escaped \\$ and $$ display $$ ok\n\\begin{figure}")
        issues = CR.check_rules(text, {"good"})
        msgs = " | ".join(i["message"] for i in issues)
        for frag in ("Unbalanced inline math", "without a matching \\begin", "closes \\begin{align}", "Unbalanced braces",
                     "Not in references.bib: missing", "Placeholder [TBD", "never closed"):
            self.assertIn(frag, msgs)
        self.assertEqual(CR.check_rules("all fine $x$.", None), [])
        self.assertEqual(CR.complete_part("a\n\nb", False), "a")
        self.assertEqual(CR.complete_part("ab", False), "")
        self.assertEqual(CR.complete_part("ab", True), "ab")

    def test_bib_keys(self):
        _env.fresh_project("legacy-critic")
        (workspace() / "references.bib").write_text("@article{smith2020,\n title={x}}\n@inproceedings{ doe21 ,", "utf-8")
        self.assertEqual(CR.bib_keys(), {"smith2020", "doe21"})
        with mock.patch("backend.library.included", side_effect=RuntimeError), mock.patch("backend.config.workspace", side_effect=RuntimeError):
            self.assertEqual(CR.bib_keys(), set())

    def test_llm_and_stream(self):
        async def fake(agent, system, user, max_tokens=0, temperature=0):
            return {"text": json.dumps({"issues": [{"quote": "bad formula", "severity": "fatal", "kind": "math", "message": "wrong"},
                                                   {"message": ""}, "junk", {"quote": "", "message": "global"}]}), "engine": "groq"}

        async def broken(*a, **k):
            return {"text": "no json", "engine": "x"}

        async def body():
            with mock.patch("backend.llm.call_agent", fake):
                out = await CR.check_llm("line one\nhas a bad formula here", offset_line=10)
                self.assertEqual([(o["severity"], o["line"]) for o in out], [("warning", 12), ("warning", 0)])
                self.assertEqual(await CR.check_llm("   "), [])
                cfg = {"critic": {"enabled": True, "llm": True, "interval_chars": 200}}
                with mock.patch.object(CR, "bib_keys", return_value=set()):
                    sc = CR.StreamCritic(cfg)
                self.assertEqual(sc.feed("short"), [])
                txt = ("$unbalanced\n\n" + "word " * 60 + "\n\nbad formula\n\n") * 2
                got = sc.feed(txt)
                self.assertTrue(any(i["kind"] == "math" for i in got))
                self.assertEqual(sc.feed(txt + "x" * 10), [])  # nothing new in the complete part
                await asyncio.sleep(0.05)
                self.assertTrue(sc.llm_ready())
                self.assertEqual(sc.llm_ready(), [])
                sc.feed(txt + "more words " * 40 + "\n\n")
                fin = await sc.final(txt + "\\cite{nokey}")
                self.assertIsInstance(fin, list)
            with mock.patch("backend.llm.call_agent", broken):
                self.assertEqual(await CR.check_llm("x"), [])

            async def boom(*a, **k):
                raise RuntimeError("down")
            with mock.patch("backend.llm.call_agent", boom):
                sc = CR.StreamCritic({"critic": {"enabled": True, "llm": True, "interval_chars": 200}})
                sc.feed("text " * 100 + "\n\nmore")
                await asyncio.sleep(0.05)
                self.assertEqual(sc.llm_ready(), [])
                self.assertEqual(sc.llm_errors, 1)

            async def slow(*a, **k):
                await asyncio.sleep(5)
            with mock.patch("backend.llm.call_agent", slow):
                sc = CR.StreamCritic({"critic": {"enabled": True, "llm": True, "interval_chars": 200}})
                sc.feed("text " * 100 + "\n\nmore")
                await sc.final("text", wait_s=0.05)
                self.assertIsNone(sc.task)
            off = CR.StreamCritic({"critic": {"enabled": False}})
            self.assertEqual(off.feed("x" * 5000), [])
            self.assertEqual(await off.final("x"), [])
        asyncio.run(body())


class Provenance(unittest.TestCase):
    rec = {"run_id": "run-1", "git_sha": "abc", "clearml_task_id": "", "cmd": "python train.py --epochs 3 --lr=1e-3"}

    def test_png_jpeg_svg_csv_round_trips(self):
        r = PV.record("run-1", {"git": {"sha": "abc", "dirty": 1, "branch": "main"}, "clearml": {"task_id": "t1"},
                                "cmd": "python train.py --epochs 3"})
        self.assertTrue(r["git_dirty"])
        png = PV.png_write(tiny_png(), r)
        self.assertEqual(PV.png_read(PV.png_write(png, r))["run_id"], "run-1")  # resealing replaces the old seal
        self.assertEqual(PV.png_read(tiny_png()), {})
        jpg = PV.jpeg_write(tiny_jpeg(), r)
        self.assertEqual(PV.jpeg_read(PV.jpeg_write(jpg, r))["git_sha"], "abc")
        self.assertEqual(PV.jpeg_read(tiny_jpeg()), {})
        svg = PV.svg_write('<?xml version="1.0"?>\n<svg></svg>', self.rec)
        self.assertNotIn("--", svg.split("<!--")[1].split("-->")[0])  # valid XML comment
        self.assertEqual(PV.svg_read(svg)["cmd"], self.rec["cmd"])  # exact round trip, no "- -"
        self.assertEqual(PV.svg_read(PV.svg_write("<svg/>", self.rec))["run_id"], "run-1")
        self.assertEqual(PV.svg_read("<svg/>"), {})
        self.assertEqual(PV.svg_read("<!-- PHD-PROVENANCE {bad} -->"), {})
        csv = PV.csv_write(PV.csv_write("a,b\n1,2", self.rec), self.rec)
        self.assertEqual(csv.count("# Provenance"), 1)
        self.assertEqual(PV.csv_read(csv)["clearml_task_id"], "")
        self.assertEqual(PV.csv_read("a,b"), {})

    def test_bytes_dispatch_and_errors(self):
        self.assertIsNone(PV.seal_bytes("a.txt", b"x", self.rec))
        self.assertIsNone(PV.seal_bytes("a.csv", b"x", self.rec, csv_header=False))
        self.assertTrue(PV.seal_bytes("a.svg", b"<svg/>", self.rec).startswith(b"<!--"))
        self.assertEqual(PV.read_bytes("a.png", PV.seal_bytes("a.png", tiny_png(), self.rec))["run_id"], "run-1")
        self.assertEqual(PV.read_bytes("a.jpg", PV.seal_bytes("a.jpg", tiny_jpeg(), self.rec))["run_id"], "run-1")
        self.assertEqual(PV.read_bytes("x", PV.seal_bytes("a.svg", b"<svg >", self.rec))["run_id"], "run-1")
        self.assertEqual(PV.read_bytes("a.csv", PV.seal_bytes("a.csv", b"a\n1", self.rec))["run_id"], "run-1")
        self.assertEqual(PV.read_bytes("a.bin", b"\x00"), {})
        self.assertEqual(PV.read_bytes("a.png", PV.PNG_SIG + b"\x00\x00"), {})  # truncated PNG
        self.assertEqual(PV.read_bytes("a.jpg", b"\xff\xd8\x00\x00\x00\x00"), {})  # corrupt JPEG
        for bad in (lambda: list(PV._png_chunks(b"nope")), lambda: list(PV._jpeg_segments(b"nope")),
                    lambda: list(PV._jpeg_segments(b"\xff\xd8\xff\xe0\x00\x10"))):
            with self.assertRaises(PV.ProvenanceError):
                bad()
        sealed = PV.png_write(tiny_png(), self.rec).replace(b'"run_id": "run-1"', b'"run_id": xrun-1x')
        self.assertEqual(PV.png_read(sealed)["run_id"], "run-1")  # falls back to the plain tEXt fields
        itxt = tiny_png()[:-12] + PV._png_chunk(b"iTXt", b"phd_run_id\x00\x00\x00\x00\x00run-9") + tiny_png()[-12:]
        self.assertEqual(PV.png_read(itxt)["run_id"], "run-9")
        jbad = PV.jpeg_write(tiny_jpeg(), self.rec).replace(b'"run_id"', b'run_id')
        self.assertEqual(PV.jpeg_read(jbad), {})

    def test_seal_run_find_and_inspect(self):
        _env.fresh_project("legacy-prov")
        from backend.sandbox import runs_dir
        rd = runs_dir() / "run-xyz"
        rd.mkdir(parents=True)
        (rd / "fig.png").write_bytes(tiny_png())
        (rd / "metrics.csv").write_text("a\n1", "utf-8")
        (rd / "broken.png").write_bytes(PV.PNG_SIG + b"junk")
        (rd / "notes.txt").write_text("x", "utf-8")
        rep = PV.seal_run(rd, "run-xyz", {"git": {"sha": "s1"}})
        self.assertEqual(rep["sealed"], 2)
        self.assertEqual(len(rep["errors"]), 1)
        digest = PV.sha256((rd / "fig.png").read_bytes())
        self.assertEqual(PV.find_by_hash(digest, runs_dir())["file"], "fig.png")
        self.assertIsNone(PV.find_by_hash("0" * 64, runs_dir()))
        (runs_dir() / "bad").mkdir()
        (runs_dir() / "bad" / "provenance.json").write_text("{", "utf-8")
        self.assertIsNone(PV.find_by_hash("0" * 64, runs_dir()))
        out = PV.inspect("fig.png", (rd / "fig.png").read_bytes())
        self.assertTrue(out["found"])
        self.assertEqual(out["run"]["id"], "run-xyz")
        with mock.patch("backend.sandbox.get_run", side_effect=KeyError("run-xyz")):
            self.assertIn("not in this project", PV.inspect("fig.png", (rd / "fig.png").read_bytes())["run_error"])
        with mock.patch("backend.sandbox.get_run", return_value={"id": "run-xyz", "stderr": "e" * 2000, "clearml": {"task_id": "T9"}}), \
                mock.patch("backend.integrations.experiment.get_backend") as gb:
            gb.return_value.get_experiment.return_value = {"task_id": "T9", "status": "completed"}
            out = PV.inspect("fig.png", (rd / "fig.png").read_bytes())
        self.assertEqual(len(out["run"]["stderr_tail"]), 1500)
        self.assertEqual(out["clearml"]["status"], "completed")
        with mock.patch("backend.integrations.experiment.get_backend", side_effect=RuntimeError("no sdk")):
            out = PV.inspect("x.png", PV.png_write(tiny_png(), {**self.rec, "clearml_task_id": "T1"}))
        self.assertIn("no sdk", out["clearml"]["error"])
        self.assertFalse(PV.inspect("x.bin", b"zz")["found"])
        with mock.patch.dict("sys.modules", {"backend.config": None}):
            self.assertIn("?", PV.record("r", {})["app"])


class Prompts(unittest.TestCase):
    def test_builders(self):
        _env.fresh_project("legacy-prompts")
        self.assertIn("ONLINE LITERATURE", PR.lit2plan_user("idea", "", "exp", "lib", online="S1"))
        self.assertNotIn("ONLINE", PR.lit2plan_user("idea", "d", "exp", "lib"))
        self.assertIn("novelty", PR.experiment_user("novelty", "d", "c").lower())
        self.assertIn("f.pdf", PR.pdf_parser_user("f.pdf", {"title": "t"}, "text"))
        p = {"title": "T", "sections": {"introduction": "I" * 5000, "methodology": ""}, "contribution": "C"}
        a = PR.author_user("abstract", "Abstract", p, "digest", ["k"], instructions="  AUTHOR'S BRIEF X", deep=True)
        self.assertIn("DEEP MODE", a)
        self.assertNotIn("AUTHOR'S INSTRUCTIONS", a)
        self.assertIn("AUTHOR'S INSTRUCTIONS", PR.author_user("abstract", "Abstract", p, "d", [], instructions="be short"))
        self.assertIn("NONE - do not cite", PR.author_user("abstract", "Abstract", {}, "d", []))
        self.assertIn("unknown keys", PR.reviewer_user("tex", "d", {"unknown": ["x"]}))
        self.assertIn("take precedence", PR.editor_user("introduction", "tex", "rev", [], "d", instructions="fix it"))
        self.assertNotIn("INSTRUCTIONS", PR.editor_user("introduction", "tex", "rev", ["k"], "d"))
        s = PR.section_reviewer_user("introduction", "Introduction", "tex", {"venue": "CVPR"}, "d", ["k"])
        self.assertIn("tex", s)
        self.assertIn("SHARED CONTEXT", PR.tool_chat_system("lit2plan", "", "shared", "d"))
        self.assertIn("no output generated yet", PR.tool_chat_system("experiment", "", "", "d"))
        self.assertIn("Vietnamese", PR.output_language("vi"))
        self.assertEqual(PR.output_language("en"), "")
        with mock.patch("backend.results.digest", return_value="R1 PSNR"):
            self.assertIn("R1 PSNR", PR._uploaded_results())
        with mock.patch("backend.results.digest", side_effect=RuntimeError):
            self.assertEqual(PR._uploaded_results(), "")

    def test_review_prompts(self):
        self.assertEqual(RP.venue_label({"type": "journal", "quartile": "Q2", "name": "TPAMI"}), "Journal · Q2 · TPAMI")
        self.assertEqual(RP.venue_label({"scale": "h5", "h5": "100+"}), "Conference · h5 100+")
        self.assertEqual(RP.venue_label({}), "Conference · ICORE A")
        j = RP.venue_brief({"type": "journal", "quartile": "Q9", "name": " TIP ", "field": "imaging", "blind": False})
        self.assertIn("Q1", j)
        self.assertIn("single-blind", j)
        self.assertIn("NAMED VENUE: TIP", j)
        self.assertIn("Equivalent ICORE bar", RP.venue_brief({"scale": "h5", "h5": "bogus"}))
        self.assertIn("ICORE/CORE A", RP.venue_brief({"rank": "Z"}))
        for n in (1, 2, 3):
            if n in RP.PERSONAS:
                self.assertIn("R1", RP.reviewer_system({"rank": "A*"}, RP.PERSONAS[n][0]))
        self.assertIn("paper", RP.reviewer_user("paper", "pre", "T"))
        self.assertTrue(RP.meta_system({"type": "journal"}))
        self.assertIn("reviews", RP.issues_user("p", "reviews", "m", "v"))
        self.assertIn("extra", RP.fix_user("v", {"title": "t", "detail": "d", "location": "l"}, "ex", "latex", "extra"))
        self.assertTrue(RP.fix_user("v", {"title": "t"}, "ex", "docx"))
        self.assertIn("digest", RP.response_user("v", "m", "r", "digest"))


if __name__ == "__main__":
    unittest.main()
