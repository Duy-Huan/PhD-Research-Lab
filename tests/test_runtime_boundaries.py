"""Real subprocess protocol faults and HTTP compute handoff boundaries, with no cloud execution."""
import _env
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend.core import config
from backend.providers import app_server as A, cli as C
from backend.execution import remote_compute as RC


class RPC(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("rpc-contract")
        self.peer = str(Path(__file__).parent / "providers" / "fake_app_server.py")

    def connection(self, mode):
        return SimpleNamespace(_prefix=lambda: [sys.executable, self.peer, mode], env=lambda: {})

    def test_catalog_real_pipe_deduplicates_and_reports_rejection(self):
        for mode in ("ok", "catalog_error", "eof"):
            with self.subTest(mode=mode), mock.patch.dict(C.CONNECTORS, {"codex": self.connection(mode)}):
                if mode == "ok":
                    self.assertEqual(A.model_catalog(), ["catalog-model"])
                else:
                    with self.assertRaises(A.StartupFailure): A.model_catalog()

    def test_stream_tools_noise_interrupt_error_and_firewall(self):
        for mode in ("tools", "noise", "interrupted", "server_error", "forbidden"):
            context = {"request_id": "rpc-fault-" + mode, "cwd": str(config.data_dir()), "timeout_s": 5,
                       "model": "test-model", "reasoning": "high", "profile": "assisted"}
            with self.subTest(mode=mode):
                if mode in ("server_error", "forbidden"):
                    with self.assertRaises(C.ProviderError) as error:
                        list(A.stream(self.connection(mode), "fixture", context, []))
                    self.assertNotIsInstance(error.exception, A.StartupFailure)
                else:
                    events = list(A.stream(self.connection(mode), "fixture", context, []))
                    if mode == "tools":
                        self.assertEqual([e["type"] for e in events if e["type"].startswith("tool_")], ["tool_call", "tool_result"])
                    self.assertEqual(events[-1]["type"], "request_cancelled" if mode == "interrupted" else "request_completed")
                self.assertNotIn(context["request_id"], C._procs)

    def test_launch_failure_cancel_and_startup_deadline_clean_registry(self):
        context = {"request_id": "rpc-no-start", "cwd": str(config.data_dir()), "timeout_s": 5}
        with mock.patch.object(A.subprocess, "Popen", side_effect=OSError("not installed")):
            with self.assertRaises(A.StartupFailure): list(A.stream(self.connection("ok"), "fixture", context, []))
        for timeout, cancel in ((.00001, None), (5, threading.Event())):
            if cancel: cancel.set()
            context.update(timeout_s=timeout, _cancel=cancel)
            if cancel:
                self.assertEqual(list(A.stream(self.connection("ok"), "fixture", context, []))[-1]["type"], "request_cancelled")
            else:
                with self.assertRaises(A.StartupFailure): list(A.stream(self.connection("ok"), "fixture", context, []))
            self.assertNotIn(context["request_id"], C._procs)


class ComputeAPI(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("compute-api")
        from fastapi.testclient import TestClient
        from backend.app import app
        from backend.execution.code_projects import active_dir
        (active_dir() / "train.py").write_text("print('baseline')", "utf-8")
        self.client = TestClient(app)

    def test_approval_download_and_native_results_import_end_to_end(self):
        import subprocess,zipfile,json
        from backend.execution.code_projects import active_dir
        (active_dir()/'train.py').write_text("import os,json\nfrom pathlib import Path\nPath(os.environ['RUN_DIR'],'metrics.json').write_text(json.dumps({'loss':0.1}))\n",'utf-8')
        self.assertEqual(self.client.get('/api/compute/runs').status_code,200)
        created=self.client.post('/api/compute/runs',json={'files':['train.py'],'compute_target':'docker','required_artifacts':['metrics.json']})
        self.assertEqual(created.status_code,200,created.text)
        rid=created.json()['run_id'];url='/api/compute/runs/'+rid
        self.assertEqual(self.client.get(url).json()['status'],'awaiting_approval')
        self.assertEqual(self.client.get(url+'/bundle').status_code,400)
        self.assertEqual(self.client.post(url+'/approve').status_code,200)
        downloaded=self.client.get(url+'/bundle')
        self.assertTrue(downloaded.content.startswith(b'PK'))
        with mock.patch('backend.execution.tracker.run_worker') as old_worker:
            self.assertEqual(self.client.post(url+'/sync',json={'task_id':'task123456'}).status_code,410)
            old_worker.assert_not_called()
        malformed=self.client.post(url+'/results',content=b'not-a-zip',headers={'Content-Type':'application/zip'})
        self.assertEqual(malformed.status_code,422,malformed.text)
        self.assertNotIn('Traceback',malformed.text)
        unpack=config.data_dir()/'cpu-http-worker';unpack.mkdir()
        with zipfile.ZipFile(RC.bundle(rid)) as archive:archive.extractall(unpack)
        process=subprocess.run([sys.executable,str(unpack/'launch.py')],capture_output=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr.decode(errors='replace'))
        uploaded=self.client.post(url+'/results',content=(unpack/'results.zip').read_bytes(),headers={'Content-Type':'application/zip'})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        actual=uploaded.json()
        self.assertEqual(actual['status'],'completed')
        self.assertEqual(actual['metrics'],{'loss':0.1})
        self.assertEqual(actual['verification']['remote_authenticity'],'NOT_VERIFIED')
        self.assertEqual(actual['verification']['scientific_review'],'pending')
        digest=actual['imports'][0]['sha256']
        artifact=self.client.get(url+'/imports/'+digest+'/file',params={'name':'metrics.json'})
        self.assertEqual(artifact.status_code,200,artifact.text)
        self.assertEqual(json.loads(artifact.content),{'loss':0.1})
