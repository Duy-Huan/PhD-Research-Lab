"""FQC-COVERAGE-662: remote compute hand-off validation — every refusal in bundle creation and in importing a
returned results.zip (receipt identity, status, intervals, artifacts, metrics, unlisted files), plus idempotent
re-import and retained-file integrity. Real bundles, zips and project files; no code is executed."""
import hashlib
import io
import json
import unittest
import zipfile

import _env
from backend.core import config
from backend.execution import remote_compute as RC


class Base(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"rc-{self._testMethodName[:30]}")
        from backend.execution.code_projects import active_dir
        self.code = active_dir()
        (self.code / "train.py").write_text("print('training')", "utf-8")
        (self.code / "conf.yaml").write_text("lr: 0.1", "utf-8")


class Create(Base):
    def test_specifications_are_validated_before_any_bundle_exists(self):
        sha = "a" * 64
        bad = [
            ({"files": ["train.py"], "token": "sk-ant-api03-" + "x" * 40}, "Credentials"),
            ({"files": ["train.py"], "compute_target": "mainframe"}, "Unknown compute target"),
            ({"files": "train.py"}, "list of relative"),
            ({"files": []}, "1–200"),
            ({"files": ["sub\\train.py"]}, "canonical"),
            ({"files": ["missing.py"]}, "outside the selected"),
            ({"files": ["train.py", "conf.yaml"], "entrypoint": "conf.yaml", "required_artifacts": ["../x"]}, "simple file names"),
            ({"files": ["train.py"], "required_artifacts": ["CON.txt"]}, "Reserved device"),
            ({"files": ["train.py"], "max_seconds": True}, "max_seconds"),
            ({"files": ["train.py"], "max_seconds": 0}, "max_seconds"),
            ({"files": ["train.py"], "dataset_manifest": {"a": 1}}, "must be a list"),
            ({"files": ["train.py"], "dataset_manifest": [{"path": "/abs.csv", "sha256": sha}]}, "relative paths"),
            ({"files": ["train.py"], "dataset_manifest": [{"path": "a.csv", "sha256": sha}, {"path": "A.CSV", "sha256": sha}]}, "duplicate"),
            ({"files": ["conf.yaml"]}, "Entrypoint must be included"),
        ]
        for spec, message in bad:
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                RC.create(spec)
        (self.code / "notes.bin").write_bytes(b"x")
        with self.assertRaisesRegex(ValueError, "Only code"):
            RC.create({"files": ["notes.bin"], "entrypoint": "notes.bin"})
        with self.assertRaisesRegex(ValueError, "Invalid remote run id"):
            RC.get("../x")
        self.assertEqual(RC.list_runs(), [])

    def test_historical_runs_are_read_only_and_approval_is_idempotent(self):
        run = RC.create({"files": ["train.py", "conf.yaml"], "compute_target": "local-gpu",
                         "dataset_manifest": [{"path": "data/x.csv", "sha256": "b" * 64}]})
        rid = run["run_id"]
        self.assertEqual(RC.approve(rid)["status"], "ready_for_handoff")
        self.assertEqual(len(RC.approve(rid)["approvals"]), 1, "approving twice changes nothing")
        record = RC.get(rid)
        record["backend"] = "clearml"
        (RC.folder(rid) / "run.json").write_text(json.dumps(record), "utf-8")
        with self.assertRaisesRegex(ValueError, "read-only"):
            RC.approve(rid)
        (RC.folder(rid) / "bundle.zip").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            RC.bundle(rid)


class Import(Base):
    def setUp(self):
        super().setUp()
        self.run = RC.create({"files": ["train.py"], "required_artifacts": ["out.txt", "metrics.json"]})
        self.rid = self.run["run_id"]
        RC.approve(self.rid)
        self.n = 0

    def receipt(self, **changes):
        base = {"schema_version": 1, "backend": "native", "run_id": self.rid, "manifest_sha256": RC.get(self.rid)["manifest_sha256"],
                "status": "completed", "metrics": {"acc": 0.9}, "code_checksums_verified": True, "environment": {"python": "3"},
                "started": 1.0, "ended": 2.0, "exit_code": 0, "missing_artifacts": [], "failure": ""}
        return {**base, **changes}

    def archive(self, receipt=None, files=None, extra=None, artifacts=None):
        files = files if files is not None else {"out.txt": b"result", "metrics.json": json.dumps({"acc": 0.9}).encode()}
        receipt = receipt or self.receipt()
        if artifacts is None:
            artifacts = [{"name": n, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)} for n, b in files.items()]
        receipt = {**receipt, "artifacts": artifacts}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("execution.json", json.dumps(receipt))
            for name, data in files.items():
                z.writestr("artifacts/" + name, data)
            for name, data in (extra or {}).items():
                z.writestr(name, data)
        self.n += 1
        path = config.data_dir() / f"results-{self.n}.zip"
        path.write_bytes(buffer.getvalue())
        return path

    def test_valid_results_import_once_and_are_served_back(self):
        path = self.archive()
        record = RC.import_results(self.rid, path)
        digest = record["imports"][-1]["sha256"]
        self.assertEqual(RC.import_results(self.rid, path)["imports"], record["imports"], "re-import is idempotent")
        self.assertEqual(RC.imported_file(self.rid, digest, "out.txt").read_bytes(), b"result")
        with self.assertRaisesRegex(ValueError, "Unknown imported artifact"):
            RC.imported_file(self.rid, digest, "other.txt")
        with self.assertRaisesRegex(ValueError, "Unknown retained native import"):
            RC.imported_file(self.rid, "0" * 64, "out.txt")
        stored = RC.folder(self.rid) / "imports" / digest / "artifacts" / "out.txt"
        stored.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "Imported artifact changed"):
            RC.imported_file(self.rid, digest, "out.txt")
        with self.assertRaisesRegex(ValueError, "artifact changed; preserve"):
            RC.import_results(self.rid, path)

    def test_inconsistent_results_are_refused(self):
        ok = {"out.txt": b"result", "metrics.json": json.dumps({"acc": 0.9}).encode()}
        cases = [
            (dict(receipt=self.receipt(run_id="rc-000000000000")), "does not match the approved"),
            (dict(receipt=self.receipt(status="unknown")), "Invalid result status"),
            (dict(receipt=self.receipt(code_checksums_verified=False)), "verified code inputs"),
            (dict(receipt=self.receipt(started=5.0, ended=1.0)), "execution interval"),
            (dict(receipt=self.receipt(exit_code=1)), "exit zero"),
            (dict(artifacts="x"), "Invalid artifact manifest"),
            (dict(artifacts=["x"]), "Invalid artifact entry"),
            (dict(artifacts=[{"name": "secret.bin", "sha256": "0" * 64, "bytes": 1}]), "Unexpected or duplicate"),
            (dict(artifacts=[{"name": "out.txt", "sha256": "0" * 64, "bytes": 6}]), "Artifact checksum mismatch"),
            (dict(artifacts=[{"name": "out.txt", "sha256": "0" * 64, "bytes": 99}]), "invalid digest/size"),
            (dict(extra={"artifacts/hidden.txt": b"x"}), "Unlisted files"),
            (dict(files={"out.txt": b"r"}), "missing required artifacts"),
            (dict(receipt=self.receipt(metrics={"acc": 0.5})), "differ from the raw metrics"),
            (dict(receipt=self.receipt(status="failed", metrics={"a": 1}), files={"out.txt": b"r"}), "require the raw metrics.json"),
            (dict(files={**ok, "metrics.json": b"{\"a\": NaN}"}), "Non-finite metric"),
        ]
        for kwargs, message in cases:
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                RC.import_results(self.rid, self.archive(**kwargs))
        missing_receipt = config.data_dir() / "no-receipt.zip"
        with zipfile.ZipFile(missing_receipt, "w") as z:
            z.writestr("artifacts/out.txt", b"x")
        with self.assertRaisesRegex(ValueError, "Missing or oversized execution receipt"):
            RC.import_results(self.rid, missing_receipt)
        self.assertEqual(RC.get(self.rid).get("imports", []), [], "nothing is recorded for a refused import")

    def test_failed_runs_are_retained_with_their_log(self):
        receipt = self.receipt(status="failed", metrics={}, exit_code=1, failure="crashed")
        record = RC.import_results(self.rid, self.archive(receipt=receipt, files={"execution.log": b"trace"}))
        self.assertEqual(record["imports"][-1]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
