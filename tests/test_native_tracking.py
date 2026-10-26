"""Native process tracking: actual CPU smoke run and controlled journal failure contracts.

Vendor-specific tests retired with exact IDs/reasons in test-retirement-native-migration.json.
No remote service, paid model call or scientific validation is claimed here.
"""
import hashlib
import json
import time
import unittest
from unittest.mock import patch

import _env
from backend.core import config
from backend.execution import sandbox, tracker
from backend.execution.tools import IntegrationError


class NativeTracking(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project('native-tracking')

    def fixture(self, **extra):
        record={'id':'fixture-run','status':'done','exit_code':0,'started':1,'metrics':{'loss':.25},**extra}
        folder=sandbox.runs_dir()/record['id'];folder.mkdir(exist_ok=True)
        (folder/'run.json').write_text(json.dumps(record),'utf-8')
        return record,folder

    def test_real_cpu_execution_is_recorded_with_metrics_and_hash(self):
        sandbox.save_settings({'mode':'local','gpu':False,'timeout_s':30})
        (sandbox.code_dir()/'native_tracking.py').write_text("import os,json\nfrom pathlib import Path\nPath(os.environ['RUN_DIR'],'metrics.json').write_text(json.dumps({'loss':0.33}))\nprint('native execution')\n",'utf-8')
        job=sandbox.start_job('python native_tracking.py','run','Native tracking smoke')
        deadline=time.monotonic()+40
        while job.status not in ('done','failed','stopped') and time.monotonic()<deadline:time.sleep(.05)
        self.assertEqual(job.status,'done')
        # The journal is persisted after terminal status assignment; wait for that commit.
        journal=sandbox.runs_dir()/job.id/'run.json'
        while time.monotonic()<deadline:
            if journal.is_file() and json.loads(journal.read_text('utf-8')).get('status')=='done':break
            time.sleep(.02)
        actual=tracker.record_run(job.id)
        self.assertEqual(actual['exit_code'],0)
        self.assertEqual(actual['metrics']['loss'],.33)
        self.assertEqual(actual['record_sha256'],hashlib.sha256(journal.read_bytes()).hexdigest())
        self.assertEqual(actual['scientific_status'],'NOT_VERIFIED_BY_PROCESS_EXIT')

    def test_failed_experiment_is_recorded_as_failed(self):
        record,folder=self.fixture(status='failed',exit_code=1)
        value=tracker.record_run(record['id'])
        self.assertEqual(value['status'],'failed');self.assertEqual(value['exit_code'],1)
        self.assertTrue((folder/'tracking.json').is_file())

    def test_running_missing_and_corrupt_journals_are_never_success(self):
        record,folder=self.fixture(status='running',exit_code=None)
        with self.assertRaises(IntegrationError):tracker.record_run(record['id'])
        (folder/'run.json').write_text('{corrupt')
        with self.assertRaises((IntegrationError,ValueError)):tracker.record_run(record['id'])
        self.assertFalse((folder/'tracking.json').exists())
        with self.assertRaises(sandbox.SandboxError):tracker.record_run('missing-run')

    def test_legacy_references_and_original_journal_survive_native_recording(self):
        record,folder=self.fixture(clearml={'task_id':'old-task','session_zip':'clearml/offline.zip'})
        original=(folder/'run.json').read_bytes()
        value=tracker.record_run(record['id'])
        self.assertTrue(value['legacy_tracker_reference_preserved'])
        self.assertEqual((folder/'run.json').read_bytes(),original)
        self.assertEqual(sandbox.get_run(record['id'])['clearml']['task_id'],'old-task')

    def test_no_service_configuration_or_credentials_are_injected(self):
        self.assertEqual(tracker.run_env('/runs/run1',{}),{'PHDLAB_TRACKING_BACKEND':'native'})
        self.assertEqual(tracker.status()['backend'],'native')
        self.assertFalse(tracker.status()['remote_service_required'])
        with patch('subprocess.run') as subprocess_run:
            with self.assertRaisesRegex(IntegrationError,'retired'):tracker.run_worker('probe',{})
            subprocess_run.assert_not_called()

    def test_native_index_uses_real_process_timestamps_and_exposes_failed_metrics(self):
        self.fixture(status='failed')
        index=tracker.list_records()
        self.assertEqual(index['process_runs'][0]['started'],1)
        self.assertEqual(index['process_runs'][0]['status'],'failed')
        self.assertEqual(index['process_runs'][0]['metrics'],{'loss':.25})


if __name__=='__main__':unittest.main()
