"""REAL_LOCAL process containment; an expired gate must not leave owned workers."""
import _env
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import psutil
from devtools.verification.runner import run_command
from tools.backend_quality_gate import QualityGateTestResult


class TimeoutContainment(unittest.TestCase):
    def test_deadline_stops_owned_descendant_and_preserves_unrelated_process(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-timeout-contract-') as folder:
            root=Path(folder);pidfile=root/'owned-child.json'
            program=root/'parent.py'
            program.write_text('''import json,subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
Path(sys.argv[1]).write_text(json.dumps({'child':child.pid}))
time.sleep(60)
''','utf-8')
            sibling=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
            try:
                result=run_command('owned-timeout',[sys.executable,str(program),str(pidfile)],root,root,timeout=2)
                self.assertEqual((result['status'],result['exit_code']),('FAIL',124))
                child=json.loads(pidfile.read_text('utf-8'))['child']
                self.assertFalse(psutil.pid_exists(child),'Timed-out owned descendant must actually stop')
                self.assertIsNone(sibling.poll(),'An unrelated process with the same executable must survive')
                self.assertGreaterEqual(result['process_cleanup']['descendants_observed'],1)
                self.assertEqual(result['process_cleanup']['surviving_descendants'],[])
                stage=json.loads((root/'owned-timeout-stage.json').read_text('utf-8'))
                self.assertEqual(stage['status'],'FAIL')
            finally:
                sibling.kill();sibling.wait(timeout=10)

    def test_current_case_progress_names_actual_running_test(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-progress-contract-') as folder:
            target=Path(folder)/'progress.json'
            class Actual(unittest.TestCase):
                def test_observation(inner):
                    value=json.loads(target.read_text('utf-8'))
                    inner.assertEqual(value['test'],inner.id())
                    inner.assertEqual(value['status'],'RUNNING')
                    inner.assertIn('timestamp',value)
            with patch.dict('os.environ',{'PHDLAB_VERIFY_PROGRESS':str(target)}):
                result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=QualityGateTestResult).run(Actual('test_observation'))
            self.assertTrue(result.wasSuccessful())
            self.assertEqual(result.testsRun,1)


if __name__=='__main__':unittest.main()
