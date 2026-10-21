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

from backend.paper import writer as PA, review_prompts as RP
from backend.knowledge import provenance as PV
from backend.core.config import workspace


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



if __name__ == "__main__":
    unittest.main()
