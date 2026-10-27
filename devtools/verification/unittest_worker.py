"""Run selected unittest modules in a child process, then clean owned disposable state."""
from __future__ import annotations
import argparse
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest


def _execute(output: str, data: str, modules: list[str], mode: str, layer: str) -> None:
    root=Path(__file__).resolve().parents[2]
    sys.path[:0]=[str(root),str(root/'tests')]
    os.environ.update(PHDLAB_DATA_DIR=data,PHDLAB_QA_OFFLINE='1',JUPYTER_DATA_DIR=data+'/_jupyter')
    from tools.backend_quality_gate import QualityGateTestResult
    from .layers import load_modules
    suite=load_modules(unittest.defaultTestLoader,modules)
    from devtools.verification.layers import partition
    suite, deferred = partition(suite, layer)
    result=unittest.TextTestRunner(verbosity=2,resultclass=QualityGateTestResult).run(suite)
    Path(output).write_text(json.dumps({'mode':mode,'cases':result.test_cases_recorded,
        'subtests':result.subtests,'deferred_tests':deferred,'test_layer':layer,'total':result.testsRun,'passed':result.wasSuccessful(),
        'skipped':len(result.skipped),'cleanup_complete':False,'disposable_data':data,
        'limitations':['Offline fixtures do not qualify external providers; skips remain unqualified']},indent=2),encoding='utf-8')
    raise SystemExit(0 if result.testsRun and result.wasSuccessful() else 1)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('modules',nargs='+')
    parser.add_argument('--mode',choices=['MOCKED','REAL_LOCAL'],default='MOCKED')
    parser.add_argument('--layer',choices=['software','live','all'],default='software')
    args=parser.parse_args()
    output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    child=None;cleanup_error=None;data=None;code=1
    allocation=tempfile.TemporaryDirectory(prefix='phdlab-verify-')
    data=Path(allocation.name).resolve()
    if not data.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not data.name.startswith('phdlab-verify-'):
        raise RuntimeError('Unexpected disposable allocation; refuse recursive cleanup')
    try:
        with allocation:
            child=multiprocessing.get_context('spawn').Process(target=_execute,
                args=(str(output),str(data),args.modules,args.mode,args.layer))
            child.start();child.join(timeout=1100)
            if child.is_alive():
                child.terminate();child.join(timeout=10)
                if child.is_alive():child.kill();child.join(timeout=10)
                code=124
            else:code=child.exitcode if child.exitcode is not None else 1
    except OSError as exc:
        cleanup_error=type(exc).__name__+': '+str(exc)
        code=1
    report=json.loads(output.read_text(encoding='utf-8')) if output.is_file() else {
        'mode':args.mode,'cases':[],'total':0,'passed':False,'skipped':0}
    report.update(disposable_data=str(data),cleanup_complete=not data.exists(),child_exit_code=code)
    if cleanup_error:report['cleanup_error']=cleanup_error
    if code or data.exists():report['passed']=False
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if code==0 and report.get('passed') and report['cleanup_complete'] else 1


if __name__=='__main__':raise SystemExit(main())
