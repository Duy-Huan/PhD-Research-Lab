"""Real periodic diagnostic capture must not race native frame metadata or leak workers."""
import _env
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path

from devtools.verification.diagnostics import periodic_stacks


class StackDiagnostics(unittest.TestCase):
    def test_snapshots_survive_churning_frames_without_dumping_local_values(self):
        secret_local='DO_NOT_CAPTURE_LOCAL_VALUES_639204'
        def churn_frames():
            deadline=time.monotonic()+0.25
            while time.monotonic()<deadline:
                code=(lambda:7).__code__.replace(co_filename='controlled-dynamic-frame')
                types.FunctionType(code,{})()
                time.sleep(0.001)
        with tempfile.TemporaryDirectory(prefix='phdlab-stack-contract-') as directory:
            path=Path(directory)/'stacks.log'
            with periodic_stacks(path,interval_s=0.005) as worker:
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    churn_frames()
                    if path.read_text('utf-8').count('Python stack snapshot')>=2:
                        break
            self.assertFalse(worker.is_alive())
            data=path.read_text('utf-8')
            self.assertGreaterEqual(data.count('Python stack snapshot'),2)
            self.assertIn('churn_frames',data)
            self.assertNotIn(secret_local,data)
            path.rename(path.with_suffix('.closed'))

    def test_test_failure_propagates_and_diagnostic_thread_is_joined(self):
        error=AssertionError('Controlled regression must remain FAIL')
        with tempfile.TemporaryDirectory(prefix='phdlab-stack-failure-') as directory:
            with self.assertRaises(AssertionError) as caught:
                with periodic_stacks(Path(directory)/'stacks.log',interval_s=0.01) as worker:
                    raise error
            self.assertIs(caught.exception,error)
            self.assertFalse(worker.is_alive())

    def test_invalid_interval_cannot_start_an_unbounded_worker(self):
        before=set(threading.enumerate())
        with tempfile.TemporaryDirectory(prefix='phdlab-stack-bounds-') as directory:
            for value in (0,-1,float('nan'),float('inf'),True):
                with self.subTest(interval=value),self.assertRaises(ValueError):
                    with periodic_stacks(Path(directory)/'stacks.log',interval_s=value):
                        self.fail('Invalid diagnostic interval was accepted')
        self.assertEqual(set(threading.enumerate()),before)
