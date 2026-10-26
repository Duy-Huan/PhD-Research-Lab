"""Risk-aware acceptance evidence checks. No model calls and no subjective scoring."""
from __future__ import annotations
import hashlib
import fnmatch
import json
from pathlib import Path
import zipfile
from .uat_journeys import JOURNEYS, CHECKS

RAW_FILES = {'final.png','trace.zip','agent-history.json','browser-evidence.json','agent-result.json'}


def unexpected_events(browser: dict) -> list[dict]:
    """Exempt only the exact declared controlled fault, never an entire phase."""
    fault=browser.get('controlled_fault') or {}
    if not isinstance(fault,dict):return list(browser.get('events',[])) or [{'kind':'malformed-controlled-fault'}]
    def expected(event):
        if event.get('expected_fault_id')=='UAT-EGRESS-CANARY':
            return (event.get('url')=='http://example.invalid/uat-canary' or
                    (event.get('fault_url')=='http://example.invalid/uat-canary' and event.get('kind')=='console'
                     and "Access to fetch at 'http://example.invalid/uat-canary'" in event.get('text','')
                     and 'blocked by CORS policy' in event.get('text','')))
        return (fault.get('id')=='UAT-CONFIG-503' and fault.get('path')=='/api/config'
                and fault.get('method')=='GET' and fault.get('status')==503
                and event.get('expected_fault_id')==fault['id'] and event.get('path')==fault['path']
                and ((event.get('kind')=='http' and event.get('status')==503)
                     or (event.get('kind')=='console' and event.get('url','').endswith('/api/config') and '503' in event.get('text',''))))
    return [event for event in browser.get('events',[]) if not expected(event)]


def validate_run(folder: Path, source: str, journey: str, strict: bool = True) -> list[str]:
    """Validate actual per-run records, independently of a model's PASS claim."""
    errors=[]
    try:
        for name in RAW_FILES:
            raw_path=folder/name
            if raw_path.is_symlink() or not raw_path.resolve().is_relative_to(folder.resolve()) or raw_path.stat().st_size>50_000_000:
                return ['Unsafe, aliased or oversized per-journey raw evidence']
        png=(folder/'final.png').read_bytes()
        if not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png)<24 or int.from_bytes(png[16:20],'big')<320 or int.from_bytes(png[20:24],'big')<200:
            errors.append('Screenshot is not a plausible full application PNG')
        if not zipfile.is_zipfile(folder/'trace.zip'):errors.append('Browser trace is not a valid ZIP')
        history=json.loads((folder/'agent-history.json').read_text(encoding='utf-8'))
        browser=json.loads((folder/'browser-evidence.json').read_text(encoding='utf-8'))
        agent=json.loads((folder/'agent-result.json').read_text(encoding='utf-8'))
        if not history.get('history'):errors.append('No executed agent action history')
        if browser.get('confirmation')!='PASS' or agent.get('ai_success') is not True or not agent.get('steps'):
            errors.append('Actual browser/model records do not confirm the declared journey')
        if strict and (agent.get('mode')!='REAL_LOCAL' or agent.get('adapter')!='browser-use'
                       or not agent.get('version') or not agent.get('model_requested')
                       or agent.get('status') in ('BLOCKED','FAILED','ERROR','MOCKED','NOT_RUN')
                       or type(agent.get('steps')) is not int or agent['steps'] < 1):
            errors.append('Actual local adapter/model execution identity is incomplete')
        for raw in (browser,agent):
            if (strict or 'journey' in raw) and raw.get('journey')!=journey:errors.append('Raw journey identity does not match declaration')
            if (strict or 'source_sha256' in raw) and raw.get('source_sha256')!=source:errors.append('Raw journey source identity is stale')
        checks=browser.get('checks')
        if checks is not None and (not isinstance(checks,list) or not checks or any(c.get('passed') is not True for c in checks)):
            errors.append('A deterministic journey assertion failed or did not execute')
        if strict and (browser.get('oracle_version')!=1 or not isinstance(checks,list)
                       or {c.get('id') for c in checks}!=CHECKS.get(journey,set())):
            errors.append('Required deterministic journey assertions are missing')
        if unexpected_events(browser):errors.append('Unexpected browser console, page or network errors require investigation')
    except (ValueError,KeyError,TypeError,AttributeError,OSError):
        errors.append('Malformed or missing per-journey raw evidence')
    return errors


def requirements(changed: list[str], contracts: list[dict]) -> dict:
    ui=any(p.startswith(('frontend/src/','static/')) for p in changed)
    active=[c for c in contracts if isinstance(c,dict) and isinstance(c.get('browser_acceptance'),dict)
            and ('applies_to' not in c['browser_acceptance'] or any(fnmatch.fnmatchcase(p,pattern)
                 for p in changed for pattern in c['browser_acceptance']['applies_to']))]
    explicit=[c['browser_acceptance'] for c in active]
    required=any(r.get('required') is True for r in explicit)
    critical=any(p.startswith(('backend/agent/','backend/api/','backend/providers/','backend/memory/')) for p in changed)
    high=any(p.startswith(('frontend/src/features/harness/','frontend/src/features/office3d/')) for p in changed)
    risk='CRITICAL' if ui and critical else 'HIGH' if ui and high else 'MEDIUM' if ui else 'LOW'
    for c in active:
        if c.get('browser_acceptance',{}).get('required') and c.get('risk') in ('HIGH','CRITICAL'):
            rank={'LOW':0,'MEDIUM':1,'HIGH':2,'CRITICAL':3}
            risk=max((risk,c['risk']),key=rank.__getitem__);required=True
    if ui and risk in ('HIGH','CRITICAL'):required=True
    return {'required':required,'risk':risk,'ui_changed':ui,
            'journeys':sorted({j for r in explicit for j in r.get('journeys',[])}),
            'independent_review':required and (risk=='CRITICAL' or any(r.get('independent_review') for r in explicit)),
            'reason':'Contract/affected high-risk UI requires exploration' if required else 'No mandatory exploratory LLM for this low/medium or non-UI scope'}


def validate_manifest(path: Path, source_digest: str, policy: dict) -> list[str]:
    if not policy['required']:return []
    if not policy.get('journeys'):return ['Required high-risk UAT journeys have not been defined in a reviewed feature contract']
    if not path.is_file():return ['Required AI-UAT evidence is missing; unavailable exploration is not PASS']
    try:
        data=json.loads(path.read_text(encoding='utf-8'));errors=[]
        if data.get('decision')!='PASS' or data.get('mode') not in ('REAL_LOCAL','REAL_INTEGRATION'):
            errors.append('Exploratory acceptance is incomplete or mocked')
        if data.get('source_sha256')!=source_digest:errors.append('UAT source/dependency identity is stale')
        if not set(policy['journeys']).issubset(set(data.get('verified_journeys',[]))):errors.append('Required journeys have not completed')
        if not data.get('verified_journeys'):errors.append('No actual completed user journey')
        declared=data.get('verified_journeys',[])
        if not isinstance(declared,list) or len(declared)!=len(set(declared)) or not set(declared)<=set(JOURNEYS):
            errors.append('Unknown or duplicate exploratory journeys')
        if data.get('release_blocking_defects',0)!=0:errors.append('Unresolved release-blocking defects')
        if policy.get('independent_review') and data.get('review',{}).get('status')!='APPROVED':errors.append('Independent critical acceptance review is pending')
        artifacts=data.get('artifacts',[])
        version=data.get('schema_version',1)
        journeys=data.get('journeys',{})
        if version==2:
            if not isinstance(journeys,dict) or set(journeys)!=set(declared):errors.append('Separate evidence for every declared journey is required')
            expected={f'journeys/{j}/{name}' for j in declared for name in RAW_FILES}
            if {a.get('path') for a in artifacts}!=expected:errors.append('Per-journey raw browser/action evidence is absent or aliased')
        elif version!=1 or declared!=['settings-language']:
            errors.append('Legacy settings-only evidence cannot qualify additional journeys')
        elif not RAW_FILES.issubset({a.get('path') for a in artifacts}):
            errors.append('Required raw browser/action evidence is absent')
        if len({a.get('path') for a in artifacts})!=len(artifacts):errors.append('Duplicate raw UAT artifact')
        if version==2:
            histories=[a.get('sha256') for a in artifacts if a.get('path','').endswith('/agent-history.json')]
            if len(histories)!=len(set(histories)):errors.append('One action history cannot qualify multiple journeys')
        for record in artifacts:
            artifact=(path.parent/record['path']).resolve()
            if not artifact.is_relative_to(path.parent.resolve()) or not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest()!=record.get('sha256'):
                errors.append('Missing, unsafe or modified raw UAT artifact')
        if not errors:
            for journey in declared:
                if version==2:
                    record=journeys[journey]
                    if record.get('decision')!='PASS' or record.get('source_sha256')!=source_digest or record.get('mode')!='REAL_LOCAL':
                        errors.append('Incomplete per-journey execution: '+journey)
                    folder=path.parent/'journeys'/journey
                else:folder=path.parent
                errors.extend(journey+': '+e for e in validate_run(folder,source_digest,journey,strict=version==2))
        return errors
    except (ValueError,KeyError,TypeError,AttributeError,OSError):return ['Malformed AI-UAT manifest']
