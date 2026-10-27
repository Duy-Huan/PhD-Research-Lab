"""Owner's three-branch development and promotion contract."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess

LOCAL_STEPS = {'contract','protected-files','test-discovery','workflow-contract-policy','workflow-syntax',
               'github-policy-tests','backend','frontend-types','frontend-tests','frontend-build','deterministic-browser'}


def development_errors(branch: str) -> list[str]:
    return [] if branch == 'dev' else ['AI source development/repair commits are allowed only on dev']


def promotion_errors(head: str, base: str) -> list[str]:
    return [] if (head, base) in {('dev', 'qa'), ('qa', 'main')} else ['Allowed promotion: dev -> qa -> main']


def report_errors(report: dict, source: str) -> list[str]:
    errors = []
    if (report.get('decision')!='PASS' or report.get('profile')!='pr'
            or report.get('component')!='all' or report.get('source_stable') is not True
            or report.get('source',{}).get('sha256')!=source):
        errors.append('A fresh, stable, complete local software regression is required')
    counts=report.get('counts',{})
    if type(counts.get('PASS')) is not int or counts.get('PASS',0)<=0:
        errors.append('No passing software cases were executed')
    if any(type(v) is not int or v<0 for v in counts.values()) or any(v for k,v in counts.items() if k!='PASS'):
        errors.append('Every selected software regression must execute and PASS; no skip/error/not-run')
    states={step.get('id'):step.get('status') for step in report.get('steps',[])}
    if any(states.get(name)!='PASS' for name in LOCAL_STEPS) or any(v!='PASS' for v in states.values()):
        errors.append('Required local checks are incomplete or non-passing')
    return errors


def receipt_path(root: Path) -> Path:
    common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=root,text=True).strip())
    if not common.is_absolute():common=root/common
    return common.resolve()/'agent-verification/dev.json'


def record_report(root: Path, path: Path, report: dict) -> None:
    if subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()!='dev':return
    raw=path.read_bytes()
    target=receipt_path(root);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps({'report':str(path.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),
                               'decision':report['decision'],'source':report['source']['sha256']},indent=2)+'\n',encoding='utf-8')
    temp.replace(target)
