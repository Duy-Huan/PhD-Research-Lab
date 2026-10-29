"""FQC-CI-WATCHDOG-661: the CI regression step always ends before the job limit with visible progress evidence.

Windows 3.12 push runs were killed at the job limit three times without logs or artifacts, so the step-level and
runner-level bounds evidently did not end the step. The watchdog is a separate parent process: it prints heartbeats to
the console, and at its deadline writes diagnostics, stops the owned process tree and returns a failure code so the
always() artifact upload runs. It never turns a failing or hung command into PASS.
"""
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import _env  # noqa: F401  (repository import path)

try:
    from devtools.verification import ci_watchdog
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing


class Watchdog(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        self.dir = Path(tempfile.mkdtemp(prefix='phdlab-watchdog-'))

    def run_guard(self, code, deadline, interval=0.2):
        progress = self.dir / 'backend-current-test.json'
        progress.write_text(json.dumps({'test': 'test_x.Case.test_y', 'completed_cases': 41}), 'utf-8')
        lines = []
        rc = ci_watchdog.guard([sys.executable, '-c', code], deadline_s=deadline, interval_s=interval,
                               out=self.dir, progress=progress, emit=lines.append)
        return rc, lines

    def test_passing_command_keeps_its_exit_code_and_reports_heartbeats(self):
        rc, lines = self.run_guard('import time; time.sleep(0.7)', deadline=30)
        self.assertEqual(rc, 0)
        beats = [line for line in lines if line.startswith('watchdog heartbeat')]
        self.assertTrue(beats, lines)
        self.assertIn('completed_cases=41', beats[0])
        self.assertIn('test_x.Case.test_y', beats[0])
        self.assertFalse((self.dir / 'watchdog-timeout.json').exists())

    def test_failing_command_is_never_turned_into_pass(self):
        rc, _ = self.run_guard('import sys; sys.exit(3)', deadline=30)
        self.assertEqual(rc, 3)

    def test_hung_tree_is_stopped_at_deadline_with_diagnostics(self):
        child = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time; time.sleep(600)"]); time.sleep(600)'
        started = time.monotonic()
        rc, lines = self.run_guard(child, deadline=1.5)
        self.assertLess(time.monotonic() - started, 20, 'the guard itself must end promptly')
        self.assertEqual(rc, ci_watchdog.TIMEOUT_EXIT)
        report = json.loads((self.dir / 'watchdog-timeout.json').read_text('utf-8'))
        self.assertEqual(report['status'], 'TIMEOUT')
        self.assertEqual(report['progress']['test'], 'test_x.Case.test_y')
        self.assertGreaterEqual(len(report['processes']), 2, 'owned parent and descendant are recorded')
        self.assertTrue(all(p['stopped'] for p in report['processes']), report['processes'])
        self.assertTrue(any('TIMEOUT' in line for line in lines))

    def test_unrelated_processes_survive_the_timeout_stop(self):
        bystander = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(bystander.wait, 10)
        self.addCleanup(bystander.kill)
        rc, _ = self.run_guard('import time; time.sleep(600)', deadline=1)
        self.assertEqual(rc, ci_watchdog.TIMEOUT_EXIT)
        self.assertIsNone(bystander.poll(), 'only the owned tree is stopped, never by executable name')

    def test_cli_wraps_the_real_regression_command(self):
        proc = subprocess.run([sys.executable, '-m', 'devtools.verification.ci_watchdog', '--deadline-s', '30',
                               '--interval-s', '0.2', '--out', str(self.dir), '--', sys.executable, '-c', 'print("inner ok")'],
                              cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('inner ok', proc.stdout)

    def test_workflow_runs_backend_regression_under_the_watchdog_below_step_and_job_limits(self):
        text = (Path(__file__).resolve().parents[1] / '.github/workflows/quality.yml').read_text('utf-8')
        # 6.6.3: the Windows 3.11 push run hit the 1500 s stage budget at case 1287 of 1313 with no stuck test. After the
        # 6.6.3 release the owner asked for every CI time limit at 1.5x, so runs never fail only for being slow.
        # The order stays stage < watchdog < step < job.
        self.assertIn('-m devtools.verification.ci_watchdog --deadline-s 2790', text)
        self.assertIn('timeout-minutes: 50', text)
        self.assertIn('timeout-minutes: 60', text)
        runner = (Path(__file__).resolve().parents[1] / 'devtools/verification/runner.py').read_text('utf-8')
        stage = int(re.search(r"timeout=(\d+)\)\s+# measured Windows", runner).group(1))
        self.assertEqual(stage, 2700)
        self.assertLess(stage, 2790)
        self.assertLess(2790, 50 * 60)
        self.assertLess(50, 60)

    def test_every_ci_job_limit_is_one_and_a_half_times_its_6_6_3_value(self):
        root = Path(__file__).resolve().parents[1]
        def limits(name):
            return [int(m) for m in re.findall(r'timeout-minutes: (\d+)', (root / '.github/workflows' / name).read_text('utf-8'))]
        # policy, backend job, backend step, frontend, security, browser, installers
        self.assertEqual(limits('quality.yml'), [15, 60, 50, 30, 23, 23, 45])
        self.assertEqual(limits('release.yml'), [8, 38, 45, 15])
        self.assertEqual(limits('automerge.yml'), [8])
        browser = (root / 'devtools/verification/browser.py').read_text('utf-8')
        self.assertIn("timeout=2700 if args.profile in ('full','release') else 900", browser)


if __name__ == '__main__':
    unittest.main()
