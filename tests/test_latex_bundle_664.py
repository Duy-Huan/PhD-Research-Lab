"""FQC-LATEX-BUNDLE-664 (agent/PLAN_6.6.4_L3.md A6 part 2): the installers ship a LaTeX engine for the PDF.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): the host had no LaTeX, so the paper's PDF step could only
report that compilation was unavailable. The .exe and .deb now carry Tectonic 0.17.0 (pinned SHA-256) in <install>/tools,
and the app finds it there. These tests use local archives and a stand-in binary; they never download or run Tectonic."""
import hashlib
import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import _env
from backend.paper import latex as LB, writer
from scripts import build_installers as B

IS_WIN = os.name == "nt"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Bundle(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def archive(self, kind: str, member: str, body: bytes = b"stand-in binary") -> Path:
        if kind == "zip":
            path = self.tmp / "tectonic-x.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("tectonic-0.17.0/" + member, body)
                z.writestr("tectonic-0.17.0/README.txt", "other file")
        else:
            path = self.tmp / "tectonic-x.tar.gz"
            with tarfile.open(path, "w:gz") as t:
                info = tarfile.TarInfo(member)
                info.size = len(body)
                t.addfile(info, io.BytesIO(body))
        return path

    def pin(self, platform: str, archive: Path, member: str):
        spec = {"url": archive.as_uri(), "sha256": digest(archive), "member": member}
        return patch.dict(B.TECTONIC, {platform: spec})

    def test_the_pins_are_exact_release_assets(self):
        for platform, member in (("windows", "tectonic.exe"), ("linux", "tectonic")):
            spec = B.TECTONIC[platform]
            self.assertTrue(spec["url"].startswith("https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/"))
            self.assertRegex(spec["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(spec["member"], member)
        import inspect
        self.assertIn('stage_tectonic("windows", cache, stage / "tools")', inspect.getsource(B.build_windows))
        self.assertIn('stage_tectonic("linux", cache, opt / "tools")', inspect.getsource(B.build_deb))

    def test_only_the_binary_is_staged_from_a_matching_archive(self):
        for platform, kind, member in (("windows", "zip", "tectonic.exe"), ("linux", "tar", "tectonic")):
            with self.subTest(platform=platform):
                archive = self.archive(kind, member)
                tools = self.tmp / f"tools-{platform}"
                with self.pin(platform, archive, member):
                    staged = B.stage_tectonic(platform, self.tmp / f"cache-{platform}", tools)
                self.assertEqual(staged, tools / member)
                self.assertEqual(staged.read_bytes(), b"stand-in binary")
                self.assertEqual(sorted(p.name for p in tools.iterdir()), sorted([member, "tectonic-LICENSE.txt"]))
                self.assertIn("MIT License", (tools / "tectonic-LICENSE.txt").read_text("utf-8"))
                if not IS_WIN:
                    self.assertTrue(os.access(staged, os.X_OK))

    def test_a_tampered_download_or_missing_binary_is_refused(self):
        archive = self.archive("zip", "tectonic.exe")
        spec = {"url": archive.as_uri(), "sha256": "0" * 64, "member": "tectonic.exe"}
        cache = self.tmp / "cache"
        with patch.dict(B.TECTONIC, {"windows": spec}), self.assertRaisesRegex(ValueError, "pinned SHA-256"):
            B.stage_tectonic("windows", cache, self.tmp / "tools")
        self.assertFalse(any(cache.iterdir()))  # the mismatching download is deleted, never used
        wrong = self.archive("zip", "other.exe")
        with self.pin("windows", wrong, "tectonic.exe"), self.assertRaisesRegex(ValueError, "not found once"):
            B.stage_tectonic("windows", self.tmp / "cache2", self.tmp / "tools2")

    def test_the_installer_smoke_refuses_a_missing_or_wrong_engine(self):
        # The success path runs the real binary in the CI installer jobs (smoke-windows / smoke-deb).
        import sys
        with self.assertRaisesRegex(RuntimeError, "missing"):
            B.check_latex(self.tmp / "tools" / "tectonic.exe")
        with self.assertRaisesRegex(RuntimeError, "does not run"):
            B.check_latex(Path(sys.executable))  # runs, but is not Tectonic 0.17.0

    def test_the_app_finds_the_bundled_engine(self):
        tools = self.tmp / "tools"
        tools.mkdir()
        binary = tools / ("tectonic.exe" if IS_WIN else "tectonic")
        binary.write_bytes(b"stand-in")
        binary.chmod(0o755)
        # PATH emptied; the bundled folder is searched before any TeX install folder of this host.
        with patch.dict(os.environ, {"PHDLAB_TOOLS_DIR": str(tools), "PATH": ""}):
            self.assertEqual(LB.bundled_dir(), tools)
            self.assertEqual(LB._extra_dirs()[0], str(tools))
            self.assertEqual(Path(LB.which("tectonic") or "").resolve().parent, tools.resolve())
            self.assertIn("tectonic", LB.engines()["available"])
        with patch.dict(os.environ, {"PHDLAB_TOOLS_DIR": ""}):
            self.assertEqual(LB.bundled_dir(), Path(LB.__file__).resolve().parents[2].parent / "tools")  # <install>/tools

    def test_an_offline_first_compile_says_what_to_do(self):
        _env.fresh_project("latex bundle tests", code_project=None)
        project = writer.load_project()
        project.setdefault("sections", {})["introduction"] = "Text."
        writer.save_project(project)
        offline = "error: failed to connect to relay.fullyjustified.net: dns error"
        with patch.object(LB, "engines", return_value={"available": ["tectonic"], "default": "tectonic", "online": False}), \
                patch.object(LB, "_compile_local", return_value=offline):
            report = LB.compile_pdf(engine="tectonic")
        self.assertFalse(report["ok"])
        self.assertIn("connect to the internet once", " ".join(report["notes"]))
        with patch.object(LB, "engines", return_value={"available": ["tectonic"], "default": "tectonic", "online": False}), \
                patch.object(LB, "_compile_local", return_value="! Undefined control sequence."):
            report = LB.compile_pdf(engine="tectonic")
        self.assertNotIn("internet", " ".join(report["notes"]))  # a LaTeX error is not blamed on the network


if __name__ == "__main__":
    unittest.main()
