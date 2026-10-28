"""FQC-COVERAGE-662: the portable remote launcher, executed in-process on a real extracted bundle.

The launcher is copied verbatim into approved compute bundles and normally runs on a worker, so these tests load the
copy from a temporary bundle and drive main() end to end: checksums, the child run, artifacts, metrics and receipts.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _env  # noqa: F401

SOURCE = Path(__file__).resolve().parent.parent / "backend/execution/remote_runner.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Bundle:
    def __init__(self, root: Path, entry: str, required=(), dataset=None, max_seconds=60, target="local-cpu"):
        self.root = root
        (root / "code").mkdir(parents=True)
        shutil.copy2(SOURCE, root / "run.py")
        (root / "code" / "main.py").write_text(entry, encoding="utf-8")
        files = [{"path": "main.py", "sha256": sha(root / "code" / "main.py")}]
        self.manifest = {"run_id": "run-1", "files": files, "dataset_manifest": dataset or [], "compute_target": target,
                         "entrypoint": "main.py", "required_artifacts": list(required), "max_seconds": max_seconds}
        self.write()

    def write(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def load(self):
        """The launcher's own source, placed in this bundle (main() resolves the bundle from __file__)."""
        spec = importlib.util.spec_from_file_location(f"bundle_runner_{id(self)}", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.__file__ = str(self.root / "run.py")
        return module

    def run(self):
        module = self.load()
        return module, module.main()

    def receipt(self):
        return json.loads((self.root / "execution.json").read_text(encoding="utf-8"))


class RemoteRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="phdlab-bundle-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def bundle(self, entry, **kw):
        return Bundle(self.tmp / "b", entry, **kw)

    def test_completed_run_collects_artifacts_metrics_and_a_results_zip(self):
        b = self.bundle("import os, pathlib, json\nout = pathlib.Path(os.environ['RUN_DIR'])\n"
                        "(out / 'table.csv').write_text('a,b\\n1,2\\n')\n(out / 'metrics.json').write_text(json.dumps({'acc': 0.9}))\n",
                        required=["table.csv"])
        _, code = b.run()
        self.assertEqual(code, 0)
        receipt = b.receipt()
        self.assertEqual((receipt["status"], receipt["metrics"], receipt["exit_code"]), ("completed", {"acc": 0.9}, 0))
        self.assertEqual({a["name"] for a in receipt["artifacts"]}, {"table.csv", "execution.log"})
        with zipfile.ZipFile(b.root / "results.zip") as archive:
            self.assertEqual(set(archive.namelist()), {"execution.json", "artifacts/table.csv", "artifacts/execution.log"})

    def test_failures_are_reported_in_the_receipt(self):
        cases = {
            "exit": ("raise SystemExit(3)\n", [], "Process exited with code 3"),
            "missing": ("pass\n", ["figure.png"], "Required outputs missing: figure.png"),
            "metrics": ("import os, pathlib\n(pathlib.Path(os.environ['RUN_DIR']) / 'metrics.json').write_text('[1]')\n", [],
                        "Invalid metrics.json: metrics.json must be an object"),
            "nan": ("import os, pathlib\n(pathlib.Path(os.environ['RUN_DIR']) / 'metrics.json').write_text('{\"a\": NaN}')\n", [],
                    "Invalid metrics.json: Non-finite metric: NaN"),
            "tamper": ("import pathlib\npathlib.Path(__file__).write_text('changed')\n", [],
                       "Approved source changed during execution: main.py"),
        }
        for name, (entry, required, failure) in cases.items():
            with self.subTest(name):
                root = self.tmp / name
                b = Bundle(root, entry, required=required)
                _, code = b.run()
                self.assertEqual(code, 1)
                self.assertEqual((b.receipt()["status"], b.receipt()["failure"]), ("failed", failure))

    def test_time_limit_stops_the_owned_run(self):
        b = self.bundle("import time\ntime.sleep(60)\n", max_seconds=1)
        _, code = b.run()
        self.assertEqual((code, b.receipt()["failure"]), (1, "Approved execution time limit exceeded"))

    def test_launch_error_is_a_failed_receipt(self):
        b = self.bundle("pass\n")
        module = b.load()
        with mock.patch.object(module.subprocess, "Popen", side_effect=OSError("no interpreter")):
            self.assertEqual(module.main(), 1)
        self.assertEqual(b.receipt()["failure"], "OSError: no interpreter")

    def test_checksums_and_bundle_paths_are_enforced_before_running(self):
        b = self.bundle("pass\n")
        b.manifest["files"][0]["sha256"] = "0" * 64
        b.write()
        with self.assertRaisesRegex(RuntimeError, "Code/config checksum mismatch"):
            b.run()
        b.manifest["files"] = [{"path": "../manifest.json", "sha256": "x"}]
        b.write()
        with self.assertRaisesRegex(ValueError, "outside approved bundle"):
            b.run()

    def test_dataset_checksums_are_verified(self):
        data = self.tmp / "data"
        data.mkdir()
        (data / "x.csv").write_text("1\n", encoding="utf-8")
        b = self.bundle("pass\n", dataset=[{"path": "x.csv", "sha256": sha(data / "x.csv")}])
        with mock.patch.dict(os.environ, {"PHDLAB_DATASET_DIR": str(data)}):
            _, code = b.run()
            self.assertEqual((code, b.receipt()["dataset_checksums_verified"]), (0, True))
            shutil.rmtree(b.root / "outputs")
            (data / "x.csv").write_text("2\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Dataset checksum mismatch: x.csv"):
                b.run()

    def test_existing_outputs_are_never_overwritten(self):
        b = self.bundle("pass\n")
        (b.root / "outputs").mkdir()
        with self.assertRaisesRegex(RuntimeError, "outputs/ already exists"):
            b.run()

    def test_gpu_targets_require_a_gpu_runtime(self):
        b = self.bundle("pass\n", target="local-gpu")
        cuda = mock.Mock(is_available=mock.Mock(return_value=False))
        with mock.patch.dict(sys.modules, {"torch": mock.Mock(cuda=cuda)}):
            with self.assertRaisesRegex(RuntimeError, "requires a GPU runtime"):
                b.run()
        cuda = mock.Mock(is_available=mock.Mock(return_value=True), get_device_name=mock.Mock(return_value="T4"))
        torch = mock.Mock(cuda=cuda, __version__="2.4", version=mock.Mock(cuda="12.1"))
        with mock.patch.dict(sys.modules, {"torch": torch}):
            _, code = b.run()
        self.assertEqual((code, b.receipt()["environment"]["gpu"]), (0, "T4"))

    def test_oversized_results_are_refused(self):
        b = self.bundle("import os, pathlib\n(pathlib.Path(os.environ['RUN_DIR']) / 'big.bin').write_bytes(b'x' * 10)\n",
                        required=["big.bin"])
        module = b.load()
        module.MAX_RESULT_BYTES = 5
        with self.assertRaisesRegex(RuntimeError, "Results exceed 256 MiB"):
            module.main()


if __name__ == "__main__":
    unittest.main()
