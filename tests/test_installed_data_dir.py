"""FQC-INSTALLERS-662: an installed copy keeps research data outside its installation folder.

PHDLAB_DATA_DIR always wins; a copy carrying the installer marker uses the per-user folder (%LOCALAPPDATA%\\PhDLab,
$XDG_DATA_HOME/phdlab or ~/.local/share/phdlab, ~/Library/Application Support/PhDLab); a source checkout keeps data/.
The installer build stages the exact qualified archives and merges verified installer records into the manifest."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import _env
from backend.core import config

sys.path.insert(0, str(_env.ROOT / "scripts"))
import build_installers as B  # noqa: E402


class DataFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="phdlab-install-"))

    def test_installed_copy_uses_the_per_user_folder(self):
        root = self.tmp / "Programs" / "PhDLab" / "app"
        root.mkdir(parents=True)
        self.assertEqual(config.default_global_dir(root, {}, "win32"), root / "data", "a source checkout keeps data/")
        (root / config.INSTALL_MARKER).write_text("{}", "utf-8")
        local = self.tmp / "Local"
        win = config.default_global_dir(root, {"LOCALAPPDATA": str(local)}, "win32")
        self.assertEqual(win, local / "PhDLab")
        self.assertFalse(win.is_relative_to(root.parent), "data never lives in the installation folder")
        self.assertEqual(config.default_global_dir(root, {"XDG_DATA_HOME": "/x"}, "linux"), Path("/x") / "phdlab")
        self.assertEqual(config.default_global_dir(root, {}, "linux"), Path.home() / ".local" / "share" / "phdlab")
        self.assertEqual(config.default_global_dir(root, {}, "darwin"), Path.home() / "Library" / "Application Support" / "PhDLab")
        self.assertEqual(config.user_data_dir({}, "win32"), Path.home() / "AppData" / "Local" / "PhDLab")

    def test_explicit_data_folder_always_wins(self):
        root = self.tmp / "app"
        root.mkdir()
        (root / config.INSTALL_MARKER).write_text("{}", "utf-8")
        chosen = self.tmp / "D-drive" / "lab"
        self.assertEqual(config.default_global_dir(root, {"PHDLAB_DATA_DIR": f"  {chosen}  "}, "win32"), chosen.resolve())


class Staging(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="phdlab-stage-"))
        self.assets = self.tmp / "assets"
        self.assets.mkdir()

    def release(self, tamper=False):
        records = []
        for kind, files in (("source", {"start.py": b"print(1)", "backend/app.py": b"app", "docs/qa/evidence.json": b"{}", "tests/test_x.py": b""}), ("web", {"index.html": b"<html>"})):
            path = self.assets / f"phdlab-9.9.9-{kind}.zip"
            with zipfile.ZipFile(path, "w") as z:
                for name, data in files.items():
                    z.writestr(name, data)
            records.append({"name": path.name, "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if tamper:
            records[0]["sha256"] = "0" * 64
        (self.assets / "manifest.json").write_text(json.dumps({"version": "9.9.9", "source_sha": "a" * 40, "assets": records}), "utf-8")

    def test_stage_unpacks_the_qualified_archives_and_marks_the_install(self):
        self.release()
        app = self.tmp / "app"
        manifest = B.stage_app(self.assets, app)
        self.assertEqual(manifest["version"], "9.9.9")
        self.assertEqual((app / "frontend" / "dist" / "index.html").read_bytes(), b"<html>")
        self.assertTrue((app / "backend" / "app.py").is_file())
        self.assertFalse((app / "docs").exists() or (app / "tests").exists(), "development-only material is not installed")
        marker = json.loads((app / config.INSTALL_MARKER).read_text("utf-8"))
        self.assertEqual((marker["version"], marker["source_sha"]), ("9.9.9", "a" * 40))

    def test_tampered_or_unsafe_archives_are_refused(self):
        self.release(tamper=True)
        with self.assertRaisesRegex(ValueError, "does not match its manifest"):
            B.stage_app(self.assets, self.tmp / "app")
        evil = self.tmp / "evil.zip"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../outside.txt", b"x")
        with self.assertRaisesRegex(ValueError, "Unsafe archive entry"):
            B._extract(evil, self.tmp / "dest")

    def test_merge_adds_verified_installers_once(self):
        self.release()
        built = self.tmp / "built"
        built.mkdir()
        setup = built / "phdlab-9.9.9-windows-x64-setup.exe"
        setup.write_bytes(b"MZ installer")
        (built / (setup.name + ".json")).write_text(json.dumps(B.asset_record(setup)), "utf-8")
        manifest = B.merge(self.assets, [built])
        self.assertEqual([a["name"] for a in manifest["assets"]][-1], setup.name)
        self.assertTrue((self.assets / setup.name).is_file())
        with self.assertRaisesRegex(ValueError, "Duplicate release asset"):
            B.merge(self.assets, [built])
        setup.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "does not match its build record"):
            B.merge(self.assets, [built])

    def test_embedded_python_is_pinned_and_verified(self):
        self.assertRegex(B.PYTHON_EMBED["sha256"], r"^[0-9a-f]{64}$")
        cache = self.tmp / "cache"
        cache.mkdir()
        (cache / Path(B.PYTHON_EMBED["url"]).name).write_bytes(b"not python")
        with self.assertRaisesRegex(ValueError, "pinned SHA-256"):
            B.fetch_embed(cache)
        self.assertFalse((cache / Path(B.PYTHON_EMBED["url"]).name).exists(), "a mismatching download is discarded")
        lock = (_env.ROOT / B.LOCK).read_text("utf-8")
        self.assertIn("--hash=sha256:", lock)
        for dev_only in ("coverage==", "ruff==", "pip-audit==", "bandit=="):
            self.assertNotIn(dev_only, lock, "installers ship runtime packages only")


if __name__ == "__main__":
    unittest.main()
