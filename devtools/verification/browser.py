"""Run a real offline browser smoke against an owned disposable application process."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import json
import uuid
from contextlib import contextmanager
from .uat import run_space


@contextmanager
def application(out: Path, model: str = 'spark-x2.5-4b', browser_uat: bool = False):
    root=Path(__file__).resolve().parents[2]
    nonce=uuid.uuid4().hex
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
    keep={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','LOCALAPPDATA','USERPROFILE','HOME','APPDATA',
          'PLAYWRIGHT_BROWSERS_PATH','PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD','LANG','LC_ALL','CI','HEADED'}
    env={key:value for key,value in os.environ.items() if key.upper() in keep}
    env.update(PHDLAB_E2E_URL=f'http://127.0.0.1:{port}',PHDLAB_E2E_OUTPUT=str(out),PHDLAB_QA_OFFLINE='1',PYTHONIOENCODING='utf-8',
               XDG_CONFIG_HOME=str(out/'server-config'),XDG_CACHE_HOME=str(out/'server-cache'))
    with (out/'server.log').open('wb') as log:
        command=[sys.executable,'tools/playwright_server.py','--data',str(out/'data'),'--port',str(port),'--model',model,'--lease-token',nonce]
        if browser_uat:command.append('--browser-uat')
        server=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,env=env)
        try:
            for _ in range(120):
                if server.poll() is not None: raise RuntimeError('Disposable server exited; inspect server.log')
                try:
                    with urllib.request.urlopen(env['PHDLAB_E2E_URL']+'/api/qa/lease',timeout=1) as response:
                        lease=json.load(response)
                        if lease.get('nonce')==nonce and Path(lease.get('data','')).resolve()==(out/'data').resolve(): break
                except OSError: time.sleep(.25)
            else: raise RuntimeError('Disposable server did not become ready')
            yield env
        finally:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=10)


def main() -> int:
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=['feature','pr','full','release'],default='pr')
    parser.add_argument('--base',default='origin/dev')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    from .journeys import browser_plan,relevant_contracts
    from .selection import changed_files
    changed=changed_files(root,args.base)
    contracts=[json.loads(path.read_text(encoding='utf-8')) for path in (root/'docs/qa/contracts').glob('*.json')]
    selected=relevant_contracts(changed,contracts)
    plan=browser_plan(root,changed,selected,args.profile)
    if args.out:
        out=args.out.resolve()
        if not out.is_relative_to((root/'output/playwright').resolve()) or out.exists():
            parser.error('--out must be a new directory under output/playwright/')
        out.mkdir(parents=True)
    else:out=run_space(root/'output/playwright/ci/browser')
    (out/'selection.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    if plan['errors']:
        print(json.dumps({'decision':'BLOCKED','errors':plan['errors']}));return 2
    boundary=subprocess.run([sys.executable,'-m','devtools.verification.unittest_worker',str(out/'boundaries.json'),
                             'browser_acceptance_integration','--mode','REAL_LOCAL'],cwd=root,timeout=150)
    if boundary.returncode:
        print(json.dumps({'decision':'FAIL','scope':'Disposable browser/worker capability boundaries',
                          'evidence':str(out/'boundaries.json')}));return boundary.returncode
    with application(out) as env:
        npx=shutil.which('npx.cmd' if os.name=='nt' else 'npx') or 'npx'
        code=subprocess.run([npx,'--no-install','playwright','test',*plan['tests']],cwd=root/'frontend',env=env,
                            timeout=1800 if args.profile in ('full','release') else 600).returncode
        results=out/'results.json'
        stats=json.loads(results.read_text(encoding='utf-8')).get('stats',{}) if results.is_file() else {}
        if not code and (not stats.get('expected') or stats.get('skipped') or stats.get('unexpected') or stats.get('flaky')):
            code=2
        print(json.dumps({'decision':'PASS' if code==0 else 'FAIL','scope':'Deterministic Playwright only',
                          'plan':str(out/'selection.json'),'results':str(out/'results.json')}))
        return code


if __name__=='__main__': raise SystemExit(main())
