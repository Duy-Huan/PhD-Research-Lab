"""Single owner-authorized UAT exception; original three-failure ledger stays intact."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

from .ci_repair import exclusive_lock
from .evidence import RepairBudget

TASK='TASK-UAT-LOCAL-ADAPTER'


def authorization_dir(root: Path) -> Path:
    common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=root,text=True).strip())
    if not common.is_absolute():common=root/common
    return common.resolve()/'uat-authorizations'


def consume(root: Path,path: Path,source: str,head: str,model: str,steps: int,deadline: int) -> dict:
    folder=authorization_dir(root);path=path.resolve()
    if path.parent!=folder or not path.is_file():raise ValueError('Owner authorization must be external trusted Git metadata, never PR code/artifacts')
    with exclusive_lock(folder/'single-retry.lock'):
        if path.stat().st_size>8000:raise ValueError('Oversized owner authorization')
        raw=path.read_bytes();grant=json.loads(raw)
        if (grant.get('owner')!='Duy-Huan' or grant.get('task_key')!=TASK
                or grant.get('allowed_runs')!=1 or grant.get('used') is not False
                or grant.get('authorization')!='OWNER_CHAT_2026_10_25_SINGLE_BOUNDED_UAT'):
            raise ValueError('Single owner-authorized retry is missing or already consumed')
        if grant.get('source_sha256')!=source or grant.get('head_sha')!=head:
            raise ValueError('Owner retry belongs to different source/head')
        if (model!='spark-x2.5-4b' or grant.get('model')!=model or type(steps) is not int
                or not 1<=steps<=6 or type(deadline) is not int or not 1<=deadline<=600
                or grant.get('max_steps')!=6 or grant.get('deadline_s')!=600):
            raise ValueError('Owner retry is limited to Spark local, six steps and600seconds')
        expiry=datetime.fromisoformat(grant['expires_utc'])
        if expiry.tzinfo is None or expiry<=datetime.now(timezone.utc):raise ValueError('Owner authorization expired')
        ledger=RepairBudget(root/'agent/repair-ledgers/ledger.json',TASK)
        value=ledger._load();item=value.get(TASK,{})
        execution=folder/(TASK+'-single-execution.json')
        if item.get('attempts')!=3 or execution.exists():
            raise ValueError('Preserve exhausted original budget; only one explicitly granted extra execution is allowed')
        grant['used']=True;grant['consumed_utc']=datetime.now(timezone.utc).isoformat()
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(grant,indent=2)+'\n',encoding='utf-8');temp.replace(path)
        receipt={'authorization_sha256':hashlib.sha256(raw).hexdigest(),'grant_file':path.name,
                 'head_sha':head,'source_sha256':source,'model':model,'max_steps':6,'deadline_s':600,
                 'status':'RESERVED','consumed_utc':grant['consumed_utc']}
        temp=execution.with_suffix('.tmp');temp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');temp.replace(execution)
        return receipt


def finish(root: Path,decision: str) -> None:
    folder=authorization_dir(root)
    with exclusive_lock(folder/'single-retry.lock'):
        path=folder/(TASK+'-single-execution.json');receipt=json.loads(path.read_text(encoding='utf-8'))
        if receipt.get('status')!='RESERVED':raise ValueError('No reserved single owner execution')
        receipt['status']=decision;receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');temp.replace(path)
