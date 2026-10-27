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
    def test_reparented_descendants_are_reaped_before_cleanup_is_reported(self):
        """Actual helper owns its subreaper scope; no host-wide process policy changes."""
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='phdlab-reaping-contract-') as folder:
            root = Path(folder)
            helper = root / 'reaper.py'
            helper.write_text(r'''import ctypes,json,os,subprocess,sys
from pathlib import Path
import psutil
sys.path.insert(0,sys.argv[1])
from devtools.verification.runner import run_command
root=Path(sys.argv[2])
subreaper=sys.platform.startswith('linux')
if subreaper:
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0:
        raise OSError(ctypes.get_errno(),'Private helper subreaper setup failed')
program=root/'parent.py'
program.write_text("import json,subprocess,sys,time,psutil\nfrom pathlib import Path\nchild=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\nPath(sys.argv[1]).write_text(json.dumps({'child':child.pid,'created':psutil.Process(child.pid).create_time()}))\ntime.sleep(60)\n")
sibling=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
observed=None
try:
    result=run_command('private-reaping',[sys.executable,str(program),str(root/'pid.json')],root,root,timeout=2)
    record=json.loads((root/'pid.json').read_text())
    observed={'result':result,'child_exists':psutil.pid_exists(record['child']),
              'unrelated_alive':sibling.poll() is None,'private_linux_subreaper':subreaper}
finally:
    if (root/'pid.json').exists():
        record=json.loads((root/'pid.json').read_text())
        try:
            child=psutil.Process(record['child'])
            if child.create_time()==record['created']:
                child.kill()
                if subreaper:
                    try:os.waitpid(child.pid,0)
                    except ChildProcessError:pass
                else:child.wait(timeout=5)
        except psutil.NoSuchProcess:pass
    sibling.kill();sibling.wait(timeout=10)
print(json.dumps(observed))
''', encoding='utf-8')
            process = subprocess.run([sys.executable, str(helper), str(repository), str(root)],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            observed = json.loads(process.stdout)
            self.assertEqual((observed['result']['status'], observed['result']['exit_code']), ('FAIL', 124))
            self.assertFalse(observed['child_exists'], 'No owned zombie or live descendant may remain')
            self.assertTrue(observed['unrelated_alive'], 'Unrelated processes must never be terminated')
            self.assertGreaterEqual(observed['result']['process_cleanup']['descendants_observed'], 1)
            self.assertEqual(observed['result']['process_cleanup']['surviving_descendants'], [])

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
