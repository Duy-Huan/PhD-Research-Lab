"""Run the backend regression harness with isolated data and an exact line/branch coverage gate.
Usage: .venv/Scripts/python tools/backend_regression.py [--pattern test_*.py] [--out artifacts/backend-regression]
Exit 1: regression failures; exit 2: incomplete coverage; exit 3: sources changed during the run.
Live integrations remain opt-in through their existing flags.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import coverage
ROOT = Path(__file__).resolve().parents[1]

class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed = []
    def startTest(self, test):
        self.executed.append(test.id())
        super().startTest(test)
    def addError(self, test, err):
        super().addError(test, err)
        self.stream.writeln(self.errors[-1][1])
        self.stream.flush()
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.writeln(self.failures[-1][1])
        self.stream.flush()


def source_snapshot():
    """A report measured while files change cannot certify the final working tree."""
    files = [ROOT / '.coveragerc', ROOT / 'start.py', ROOT / 'mcp_stdio_bridge.py']
    for directory in ('backend', 'tests'):
        files.extend((ROOT / directory).rglob('*.py'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pattern', default='test_*.py')
    parser.add_argument('--out', default='artifacts/backend-regression')
    parser.add_argument('--include-workers', action='store_true', help='Include the standalone ClearML worker in the denominator (no configured worker omission)')
    parser.add_argument('--include-entrypoints', action='store_true', help='Also measure start.py and mcp_stdio_bridge.py')
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
    started = time.monotonic()
    before = source_snapshot()
    with tempfile.TemporaryDirectory(prefix='phdlab-regression-') as data:
        os.environ['PHDLAB_DATA_DIR'] = data
        os.environ['JUPYTER_DATA_DIR'] = str(Path(data) / '_jupyter')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        cov = coverage.Coverage(config_file=str(ROOT / '.coveragerc'), data_file=str(out / '.coverage'))
        if args.include_workers:
            cov.set_option('run:omit', [])
        if args.include_entrypoints:
            cov.set_option('run:source', ['backend', 'start', 'mcp_stdio_bridge'])
        cov.start()
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=args.pattern)
        with (out / 'tests.log').open('w', encoding='utf-8') as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=RecordedResult).run(suite)
        cov.stop()
        cov.save()
        cov.json_report(outfile=str(out / 'coverage.json'))
        cov.xml_report(outfile=str(out / 'coverage.xml'))
        cov.html_report(directory=str(out / 'html'))
        with (out / 'coverage.txt').open('w', encoding='utf-8') as report:
            cov.report(file=report)
        totals = json.loads((out / 'coverage.json').read_text('utf-8'))['totals']
        after = source_snapshot()
        changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
        complete = totals['missing_lines'] == 0 and totals.get('missing_branches', 0) == 0
        summary = {'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':[{'test':test.id(),'reason':reason} for test,reason in result.skipped],
            'unexpected_successes':len(result.unexpectedSuccesses),
            'failed_tests':[test.id() for test,_ in result.failures + result.errors],
            'executed_tests':result.executed,'coverage':totals,'coverage_complete':complete,
            'source_stable':not changed,'changed_sources':changed,
            'quality_gate_passed':result.wasSuccessful() and complete and not changed and not result.skipped,
            'regression_passed':result.wasSuccessful(),'elapsed_seconds':round(time.monotonic()-started,2),
            'scope':('all backend Python including clearml_worker' if args.include_workers else 'all backend Python using the declared .coveragerc source/exclusions') +
                    ('; plus launcher and stdio bridge' if args.include_entrypoints else '')}
        (out / 'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k != 'executed_tests'},indent=2))
        if not result.wasSuccessful():
            for test,trace in result.failures + result.errors: print(test.id(),trace)
            return 1
        if changed:
            return 3
        return 0 if complete and not result.skipped else 2

if __name__ == '__main__':
    raise SystemExit(main())
