import _env  # noqa: F401  (must be first)
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from backend import critic, provenance as P

REC = {"run_id": "20260101-120000-abcd", "git_sha": "a" * 40, "git_dirty": False, "git_branch": "main",
       "clearml_task_id": "b" * 32, "cmd": "python train.py", "sealed": "2026-01-01T00:00:00+00:00", "app": "test"}


def tiny_png() -> bytes:
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return P.PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"")


def tiny_jpeg() -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sos = b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
    return b"\xff\xd8" + app0 + sos + b"\x12\x34\x56" + b"\xff\xd9"


class Provenance(unittest.TestCase):
    def test_png_roundtrip_and_reseal(self):
        sealed = P.png_write(tiny_png(), REC)
        self.assertEqual(P.png_read(sealed)["clearml_task_id"], "b" * 32)
        resealed = P.png_write(sealed, {**REC, "clearml_task_id": "c" * 32})
        self.assertEqual(P.png_read(resealed)["clearml_task_id"], "c" * 32)
        self.assertEqual(resealed.count(b"phd_provenance"), 1)  # old seal replaced, not duplicated
        self.assertTrue(resealed.endswith(b"IEND\xaeB`\x82"))  # still a valid PNG ending

    def test_jpeg_roundtrip_keeps_app0_first(self):
        sealed = P.jpeg_write(tiny_jpeg(), REC)
        self.assertEqual(sealed[2:4], b"\xff\xe0")  # JFIF header stays right after SOI
        self.assertEqual(P.jpeg_read(sealed)["run_id"], REC["run_id"])
        self.assertTrue(sealed.endswith(b"\xff\xd9"))

    def test_svg_and_csv(self):
        svg = '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        s = P.svg_write(svg, REC)
        self.assertTrue(s.startswith('<?xml version="1.0"?>'))
        self.assertEqual(P.svg_read(s)["git_sha"], "a" * 40)
        c = P.csv_write("a,b\n1,2\n", REC)
        self.assertEqual(c.splitlines()[1], "a,b")
        self.assertEqual(P.csv_read(P.csv_write(c, REC))["run_id"], REC["run_id"])
        self.assertEqual(P.csv_write(c, REC).count("# Provenance"), 1)

    def test_seal_run_and_hash_lookup(self):
        with tempfile.TemporaryDirectory() as d:
            rd = Path(d) / "20260101-120000-abcd"
            (rd / "figures").mkdir(parents=True)
            (rd / "figures" / "loss.png").write_bytes(tiny_png())
            (rd / "table.csv").write_text("x,y\n1,2\n", "utf-8")
            (rd / "notes.txt").write_text("untouched", "utf-8")
            rep = P.seal_run(rd, rd.name, {"git": {"sha": "a" * 40}, "cmd": "python t.py"})
            self.assertEqual(rep["sealed"], 2)
            self.assertEqual((rd / "notes.txt").read_text("utf-8"), "untouched")
            data = (rd / "figures" / "loss.png").read_bytes()
            self.assertEqual(P.read_bytes("loss.png", data)["run_id"], rd.name)
            hit = P.find_by_hash(P.sha256(data), Path(d))
            self.assertEqual(hit["file"], "figures/loss.png")

    def test_garbage_is_not_a_crash(self):
        self.assertEqual(P.read_bytes("x.png", b"not an image"), {})


class Critic(unittest.TestCase):
    def test_rules(self):
        tex = ("We minimise $x^2 + y.\n\n"
               "\\begin{table}\n\\begin{tabular}{cc}\n1 & 2\n\\end{table}\n\n"
               "As shown in \\cite{good2020,ghost2021}. Result [TBD: PSNR].\n")
        issues = critic.check_rules(tex, {"good2020"})
        msgs = " | ".join(i["message"] for i in issues)
        self.assertIn("odd number of $", msgs)
        self.assertIn("closes \\begin{tabular}", msgs)
        self.assertIn("ghost2021", msgs)
        self.assertNotIn("good2020,", msgs)
        self.assertTrue(any(i["kind"] == "placeholder" for i in issues))

    def test_clean_text_has_no_errors(self):
        tex = "The loss $\\mathcal{L}=\\sum_i x_i$ and $$a=b$$.\n\n\\begin{equation}\nE=mc^2 \\$5\n\\end{equation}\n"
        self.assertEqual([i for i in critic.check_rules(tex, set()) if i["severity"] == "error"], [])

    def test_only_complete_paragraphs_while_streaming(self):
        self.assertEqual(critic.complete_part("para one\n\npara two half $x", False), "para one")
        self.assertIn("half", critic.complete_part("para one\n\npara two half $x", True))

    def test_stream_critic_reports_each_issue_once(self):
        sc = critic.StreamCritic({"critic": {"enabled": True, "llm": False, "interval_chars": 200}})
        sc.keys = set()
        text = ("x " * 120) + "\\cite{nope}\n\n"
        first = sc.feed(text)
        self.assertTrue(any("nope" in i["message"] for i in first))
        self.assertEqual(sc.feed(text + "y " * 150 + "\n\n"), [])
        sc.close()


if __name__ == "__main__":
    unittest.main()
