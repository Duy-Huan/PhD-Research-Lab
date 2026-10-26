"""Native experiment tracking, derived from existing project-owned run stores.

The sandbox/protocol journals own process status, raw measurements and provenance.
This index adds no second database, background SDK hooks or third-party service.
Legacy ClearML fields/files remain untouched historical data.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import secrets
import time

from backend.core.config import data_dir
from backend.execution.tools import IntegrationError
from backend.knowledge.research_store import safe_child


def status() -> dict:
    return {'state':'READY','backend':'native','remote_service_required':False,
            'source_of_truth':['sandbox run.json and raw artifacts','native protocol/trial journals'],
            'scientific_verification':'Independent raw-result verification/replay/review remains required'}


def record_run(run_id: str, project: str='') -> dict:
    """Snapshot a real terminal process record. A failed experiment is retained as failed."""
    from backend.execution import sandbox
    from backend.memory.store import replace_retry
    root=safe_child(sandbox.runs_dir(),run_id)
    path=safe_child(root,'run.json')
    run=sandbox.get_run(run_id)
    if not path.is_file():raise IntegrationError('Native run journal is missing; process execution is unverified')
    raw=path.read_bytes()
    if run.get('status') not in ('done','failed','stopped'):
        raise IntegrationError('Experiment has no terminal process record yet; live logs remain available')
    original=json.loads(raw)
    if original.get('id')!=run_id or original.get('status')!=run.get('status'):
        raise IntegrationError('Native process/journal identity or terminal status changed; inspect preserved evidence')
    value={'schema_version':1,'backend':'native','run_id':run_id,'status':run['status'],
           'exit_code':run.get('exit_code'),'record':'run.json','record_sha256':hashlib.sha256(raw).hexdigest(),
           'recorded_at':time.time(),'metrics':run.get('metrics') or {},'git':run.get('git') or {},
           'environment':run.get('environment') or {},'figures':run.get('figures') or [],
           'legacy_tracker_reference_preserved':bool(run.get('clearml')),
           'scientific_status':'NOT_VERIFIED_BY_PROCESS_EXIT'}
    target=safe_child(root,'tracking.json');temporary=target.with_suffix('.partial-'+secrets.token_hex(4))
    temporary.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),'utf-8')
    replace_retry(temporary,target)
    return value


def list_records(limit: int=100) -> dict:
    """Read the current project's existing process and research-protocol indexes."""
    from backend.execution import sandbox, protocols
    from backend.knowledge import research_store as store
    limit=max(1,min(500,int(limit)))
    jobs=sandbox.list_runs(limit)
    process_records=[{'kind':'process','run_id':run['id'],'status':run.get('status'),
                      'exit_code':run.get('exit_code'),'metrics':run.get('metrics') or {},
                      'started':run.get('started'),'git':run.get('git') or {},
                      'scientific_status':'SEPARATE_VERIFICATION_REQUIRED'} for run in jobs]
    layout=store.paper_project_layout()
    experiments=[]
    for topic in layout['topics'][:100]:
        for run in protocols.runs(topic['topic_id'])[:limit]:
            experiments.append({'kind':'protocol','run_id':run['id'],'topic_id':topic['topic_id'],
                'status':run['status'],'created':run.get('created'),
                'comparison':run.get('payload',{}).get('comparison'),
                'scientific_status':'SEPARATE_VERIFICATION_REQUIRED'})
    return {**status(),'project':str(data_dir().resolve()),'process_runs':process_records,
            'protocol_runs':experiments[:limit],'protocol_truncated':len(experiments)>limit or layout['topic_count']>100,
            'legacy_history_preserved':True}


def run_env(run_dir_in_sandbox: str,cfg: dict|None=None) -> dict:
    """Native scripts already receive RUN_DIR; no vendor credentials/configuration are injected."""
    return {'PHDLAB_TRACKING_BACKEND':'native'}


def auto_record(run_id: str) -> dict:
    return record_run(run_id)


def run_worker(*args,**kwargs):
    raise IntegrationError('ClearML software execution is retired. Use native experiment records and portable result-bundle import; historical data is preserved.')
