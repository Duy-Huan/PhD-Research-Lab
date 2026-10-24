"""Shared AI-UAT policy and orchestration, separate from application agents."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid
from urllib.parse import urlsplit
import json
import os
import shutil
import subprocess
import sys
import time


def validate_target(url: str) -> str:
    try:
        parsed=urlsplit(url);port=parsed.port
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or not port or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise ValueError('Only an owned loopback HTTP application origin is permitted')
        return f'http://127.0.0.1:{port}'
    except (ValueError,TypeError) as exc:
        raise ValueError('Invalid isolated UAT application target') from exc


def run_space(root: Path) -> Path:
    root=root.resolve();root.mkdir(parents=True,exist_ok=True)
    path=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex)
    path.mkdir(exist_ok=False)
    return path


def exploration_required(risk: str) -> bool:
    if risk not in ('LOW','MEDIUM','HIGH','CRITICAL'):raise ValueError('Unknown feature risk')
    return risk in ('HIGH','CRITICAL')


def bounded_options(steps: int,deadline: int) -> dict:
    if type(steps) is not int or type(deadline) is not int or not 1<=steps<=12 or not 1<=deadline<=180:
        raise ValueError('UAT requires 1..12 steps and a 1..180 second total deadline')
    return {'max_steps':steps,'timeout_s':deadline,'max_failures':3}


def exploratory_verdict(record: dict) -> str:
    if not record.get('adapter_available'):return 'BLOCKED'
    if record.get('unexpected_browser_errors'):return 'FAIL'
    if record.get('deterministic_confirmation')=='FAIL' or any(d.get('status')=='CONFIRMED' for d in record.get('defects',[])):
        return 'FAIL'
    if record.get('ai_success') and record.get('steps',0)>0 and record.get('deterministic_confirmation')=='PASS' and record.get('evidence_complete') and not record.get('defects'):
        return 'PASS'
    return 'UNVERIFIED'


def allowed_settings_write(method: str, path: str, body: object) -> bool:
    """The first-time exploration lease can mutate only disposable UI language."""
    return (method=='POST' and path=='/api/config' and isinstance(body,dict) and set(body)=={'ui'}
            and isinstance(body['ui'],dict) and set(body['ui'])=={'language'}
            and body['ui']['language'] in ('en','vi'))


def execute(out: Path, model: str = 'spark-x2.5-4b', steps: int = 6, deadline: int = 180, source: str = 'UNATTESTED') -> dict:
    """Own the app/browser lifecycle; optional adapter failures stay explicit."""
    from .browser import application
    root=Path(__file__).resolve().parents[2]
    options=bounded_options(steps,deadline)
    python=root/'output/playwright/browser-uat-env'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    record={'adapter_available':python.is_file(),'profile':'uat','mode':'REAL_LOCAL',
            'scope':'First-time persona: settings navigation and VI -> EN persistence','source_sha256':source,
            'defects':[],'deterministic_confirmation':'NOT_RUN'}
    if not python.is_file():
        record.update(decision='BLOCKED',reason='Install the optional hash-locked Browser Use environment; no cloud fallback')
        (out/'uat-report.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');return record
    browser=None
    with application(out,model=model,browser_uat=True) as env:
        data={'url':validate_target(env['PHDLAB_E2E_URL']),'out':str(out),'model':model,**options}
        path=out/'uat-options.json';path.write_text(json.dumps(data,indent=2),encoding='utf-8')
        with (out/'browser-console.log').open('wb') as blog,(out/'agent-console.log').open('wb') as alog:
            try:
                browser=subprocess.Popen([shutil.which('node') or 'node',str(root/'devtools/verification/uat_browser.mjs'),str(path)],
                    cwd=root,stdin=subprocess.PIPE,stdout=blog,stderr=subprocess.STDOUT,text=True,env=env)
                for _ in range(120):
                    if browser.poll() is not None:raise RuntimeError('Owned browser lease exited before readiness')
                    if (out/'browser-lease.json').is_file():break
                    time.sleep(.25)
                else:raise TimeoutError('Owned browser did not become ready')
                keep={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','LOCALAPPDATA','USERPROFILE'}
                worker_env={k:v for k,v in os.environ.items() if k.upper() in keep}
                worker_env.update(ANONYMIZED_TELEMETRY='false',BROWSER_USE_CLOUD_SYNC='false',PYTHONIOENCODING='utf-8',
                                  OPENAI_API_KEY='local-uat-only',BROWSER_USE_API_KEY='',DO_NOT_TRACK='1',
                                  XDG_CONFIG_HOME=str(out/'adapter-config'),XDG_CACHE_HOME=str(out/'adapter-cache'),
                                  BROWSER_USE_CONFIG_DIR=str(out/'adapter-config'),PYTHONDONTWRITEBYTECODE='1')
                subprocess.run([str(python),str(root/'devtools/verification/browser_use_worker.py'),str(path)],
                    cwd=out,env=worker_env,stdout=alog,stderr=subprocess.STDOUT,timeout=deadline+10)
                if (out/'agent-result.json').is_file():record.update(json.loads((out/'agent-result.json').read_text(encoding='utf-8')))
                browser.stdin.write('{"action":"finish"}\n');browser.stdin.flush();browser.wait(timeout=30)
                if (out/'browser-evidence.json').is_file():
                    evidence=json.loads((out/'browser-evidence.json').read_text(encoding='utf-8'))
                    record['deterministic_confirmation']=evidence['confirmation']
                    record['unexpected_browser_errors']=[e for e in evidence.get('events',[]) if e.get('phase')!='EXPECTED_FAULT_INJECTION']
                record['evidence_complete']=all((out/name).is_file() for name in ['agent-history.json','browser-evidence.json','trace.zip','final.png'])
            except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
                record['error']=type(exc).__name__+': '+str(exc)[:1000]
            finally:
                if browser and browser.poll() is None:
                    if browser.stdin:browser.stdin.close()
                    try:browser.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        browser.terminate()
                        try:browser.wait(timeout=10)
                        except subprocess.TimeoutExpired:browser.kill();browser.wait(timeout=10)
    record['decision']=exploratory_verdict(record)
    if record.get('error') and record['decision']!='FAIL':record['decision']='BLOCKED'
    from .defects import defect_report
    findings=[]
    for event in record.get('unexpected_browser_errors',[]):
        findings.append({'title':'Unexpected browser event','expected':'No unexpected browser error',
                         'actual':event,'actions':record.get('actions',[]),
                         'artifacts':['browser-evidence.json','trace.zip','final.png'],
                         'classification':'UNCLASSIFIED'})
    if record.get('observations'):
        findings.append({'title':'AI exploratory observation','expected':'Complete the declared journey',
                         'actual':record['observations'],'actions':record.get('actions',[]),
                         'artifacts':['agent-history.json'],'classification':'UNCLASSIFIED'})
    (out/'defects.json').write_text(json.dumps(defect_report(findings,source, 'REAL_LOCAL',out),
                                              indent=2,default=str)+'\n',encoding='utf-8')
    (out/'uat-report.json').write_text(json.dumps(record,indent=2,default=str)+'\n',encoding='utf-8')
    return record
