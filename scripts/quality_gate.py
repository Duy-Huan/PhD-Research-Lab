"""Fail-closed CI policy/aggregation. Uses the same contract validators as /verify."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from devtools.verification.contracts import validate_contract, validate_tdd, validate_promotion
from devtools.verification.evidence import aggregate
from devtools.verification.baseline import validate_baseline

REQUIRED = {'development':['policy','backend','frontend','security','browser','uat-policy'],
            'qa':['development-gate','live-qualification'],
            'release':['qa-gate','release-approval']}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['policy','aggregate'])
    parser.add_argument('--phase',choices=list(REQUIRED))
    args=parser.parse_args(); errors=[]
    if args.command=='aggregate':
        if not args.phase: parser.error('aggregate requires --phase')
        try:
            needs=json.loads(os.environ.get('NEEDS_JSON','{}'))
            upstream={name:value.get('result') if isinstance(value,dict) else None for name,value in needs.items()}
            states={name:{'success':'PASS','failure':'FAIL'}.get(result,'BLOCKED')
                    for name,result in upstream.items()}
        except (ValueError,AttributeError): states={}; upstream={}
        decision=aggregate(states,REQUIRED[args.phase]); print(json.dumps({
            'phase':args.phase,'decision':decision,'states':states,'upstream_results':upstream}))
        return 0 if decision=='PASS' else 1
    errors += validate_baseline(ROOT/'docs/qa/KNOWN_ISSUES_BASELINE.json', ROOT)
    contracts=sorted((ROOT/'docs/qa/contracts').glob('*.json'))
    if not contracts: errors.append('No feature quality contracts')
    for path in contracts:
        try:
            contract=json.loads(path.read_text(encoding='utf-8'))
            errors += [str(path.relative_to(ROOT))+': '+e for e in validate_contract(contract,ROOT)]
            errors += [str(path.relative_to(ROOT))+': '+e for e in validate_tdd(contract,ROOT)]
        except (ValueError,TypeError,AttributeError,OSError): errors.append('Invalid contract: '+str(path))
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        text=path.read_text(encoding='utf-8')
        for action in re.findall(r'^\s*-?\s*uses:\s*([^\s#]+)',text,re.MULTILINE):
            if not action.startswith('./') and not re.fullmatch(r'[\w.-]+/[\w./-]+@[0-9a-f]{40}',action):
                errors.append('Action must be pinned to a full commit SHA: '+action)
        if 'permissions:' not in text or 'write-all' in text: errors.append('Missing least-privilege permissions: '+path.name)
        if re.search(r'^\s*paths(?:-ignore)?:',text,re.MULTILINE): errors.append('Mandatory workflows must not be path-filtered: '+path.name)
    event_path=os.environ.get('GITHUB_EVENT_PATH')
    if event_path and os.environ.get('GITHUB_EVENT_NAME')=='pull_request':
        event=json.loads(Path(event_path).read_text(encoding='utf-8')); pr=event['pull_request']
        # Human authorization is a separate protected release-approval job/environment.
        errors += validate_promotion(pr['head']['ref'],pr['base']['ref'],human_approved=pr['base']['ref']=='main')
    print(json.dumps({'decision':'FAIL' if errors else 'PASS','errors':errors},indent=2))
    return 1 if errors else 0


if __name__=='__main__': raise SystemExit(main())
