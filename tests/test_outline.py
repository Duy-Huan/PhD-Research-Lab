"""Research outline: five levels, versions, attachments (PDF, Word, Markdown, text) and the brief the agents read."""
import _env  # noqa: F401  (must be first)
import io
import unittest
import zipfile

from backend.agent import AIWSError, outline
from pdfgen import make_pdf


def docx(paragraphs: list) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r><w:r><w:tab/></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="w"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


class Outline(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("outline-" + self._testMethodName[:20])

    def test_levels_grow_with_the_fields(self):
        o = outline.get()
        self.assertEqual((o["level"], o["level_label"]), (0, ""))
        self.assertIn("not written yet", outline.brief())
        o = outline.update({"keywords": "ViT, pruning; edge\n edge"})
        self.assertEqual((o["level"], o["keywords"]), (1, ["ViT", "pruning", "edge"]))
        o = outline.update({"keywords": ["a", " ", "b"], "topic": "Lightweight ViT"})
        self.assertEqual((o["level"], o["keywords"], o["level_label"]), (2, ["a", "b"], "Chủ đề"))
        o = outline.update({"direction": "pruning + distillation", "method": "ImageNet-100, top-1"}, "chat", "accepted")
        self.assertEqual(o["level"], 4)
        o = outline.update({"proposal": "# Proposal\nfull text"})
        self.assertEqual((o["level"], o["level_label"]), (5, "Đề cương nghiên cứu"))
        self.assertEqual(len(o["versions"]), 4)
        b = outline.brief()
        for part in ("level 5/5", "Keywords: a, b", "Chủ đề: Lightweight ViT", "Proposal:"):
            self.assertIn(part, b)

    def test_versions_restore_and_errors(self):
        outline.update({"topic": "first"})
        outline.update({"topic": "second"})
        self.assertEqual(outline.restore(-1)["topic"], "first")
        with self.assertRaises(AIWSError):
            outline.restore(99)
        with self.assertRaises(AIWSError):
            outline.update({"title": "x"})
        with self.assertRaises(AIWSError):
            outline.update({})

    def test_attachments_of_every_supported_kind(self):
        a = outline.attach("đề cương.md", "# Đề cương\nMục tiêu: ViT".encode())
        self.assertEqual((a["kind"], a["path"].startswith("proposal/")), ("md", True))
        self.assertIn("Mục tiêu", outline.attachment_text(a["id"]))
        b = outline.attach("đề cương.md", b"second copy")  # same name → numbered, never overwritten
        self.assertNotEqual(a["name"], b["name"])
        d = outline.attach("proposal.docx", docx(["Tên đề tài", "Phương pháp &amp; dữ liệu"]))
        self.assertIn("Phương pháp & dữ liệu", outline.attachment_text(d["id"]))
        p = outline.attach("p.pdf", make_pdf([[(12, "Research proposal about pruning")]]))
        self.assertIn("pruning", outline.attachment_text(p["id"]))
        self.assertEqual(len(outline.get()["attachments"]), 4)
        self.assertIn("Attached", outline.brief())
        self.assertEqual(outline.remove_attachment(b["id"]), {"removed": b["id"]})
        with self.assertRaises(AIWSError):
            outline.remove_attachment(b["id"])

    def test_attachment_errors(self):
        for name, data, why in (("x.exe", b"MZ", "Attach PDF"), ("x.md", b"", "empty"), ("x.docx", b"not a zip", "Word")):
            with self.subTest(name), self.assertRaisesRegex(AIWSError, why):
                outline.attach(name, data)
        with self.assertRaises(AIWSError):
            outline.attachment_text("bad id")
        with self.assertRaises(AIWSError):
            outline.attachment_text("att-0123abcd")
        original = outline.MAX_FILE
        outline.MAX_FILE = 3
        self.addCleanup(lambda: setattr(outline, "MAX_FILE", original))
        with self.assertRaisesRegex(AIWSError, "40 MB"):
            outline.attach("x.txt", b"abcdef")

    def test_brief_survives_a_missing_attachment_text(self):
        a = outline.attach("x.txt", b"hello proposal")
        from backend.core.config import workspace
        (workspace() / "outline_text" / f"{a['id']}.txt").unlink()
        self.assertIn("Research outline", outline.brief())


if __name__ == "__main__":
    unittest.main()
