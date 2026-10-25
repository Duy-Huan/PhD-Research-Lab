"""Risk-aware acceptance evidence checks. No model calls and no subjective scoring."""
from __future__ import annotations
import hashlib
import fnmatch
import json
from pathlib import Path
import zipfile


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
        if data.get('release_blocking_defects',0)!=0:errors.append('Unresolved release-blocking defects')
        if policy.get('independent_review') and data.get('review',{}).get('status')!='APPROVED':errors.append('Independent critical acceptance review is pending')
        artifacts=data.get('artifacts',[])
        required={'final.png','trace.zip','agent-history.json','browser-evidence.json','agent-result.json'}
        if not required.issubset({a.get('path') for a in artifacts}):errors.append('Required raw browser/action evidence is absent')
        for record in artifacts:
            artifact=(path.parent/record['path']).resolve()
            if not artifact.is_relative_to(path.parent.resolve()) or not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest()!=record.get('sha256'):
                errors.append('Missing, unsafe or modified raw UAT artifact')
        if not errors:
            png=(path.parent/'final.png').read_bytes()
            if not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png)<24 or int.from_bytes(png[16:20],'big')<320 or int.from_bytes(png[20:24],'big')<200:
                errors.append('Screenshot is not a plausible full application PNG')
            if not zipfile.is_zipfile(path.parent/'trace.zip'):errors.append('Browser trace is not a valid ZIP')
            history=json.loads((path.parent/'agent-history.json').read_text(encoding='utf-8'))
            browser=json.loads((path.parent/'browser-evidence.json').read_text(encoding='utf-8'))
            agent=json.loads((path.parent/'agent-result.json').read_text(encoding='utf-8'))
            if not history.get('history'):errors.append('No executed agent action history')
            if browser.get('confirmation')!='PASS' or agent.get('ai_success') is not True or not agent.get('steps'):
                errors.append('Actual browser/model records do not confirm the declared journey')
            if any(e.get('phase')!='EXPECTED_FAULT_INJECTION' for e in browser.get('events',[])):
                errors.append('Unexpected browser console, page or network errors require investigation')
        return errors
    except (ValueError,KeyError,TypeError,AttributeError,OSError):return ['Malformed AI-UAT manifest']
