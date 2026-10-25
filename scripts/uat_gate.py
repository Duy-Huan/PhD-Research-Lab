"""Check risk-triggered AI-UAT evidence in CI; never starts a model or personal browser."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from devtools.verification.selection import changed_files
from devtools.verification.runner import identity
from devtools.verification.uat_gate import requirements,validate_manifest
from devtools.verification.journeys import relevant_contracts,browser_plan


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True);p.add_argument('--manifest',type=Path,default=ROOT/'docs/qa/evidence/uat/qualified/manifest.json');args=p.parse_args()
    paths=changed_files(ROOT,args.base)
    all_contracts=[json.loads(path.read_text(encoding='utf-8')) for path in (ROOT/'docs/qa/contracts').glob('*.json')]
    contracts=relevant_contracts(paths,all_contracts)
    policy=requirements(paths,contracts);errors=validate_manifest(args.manifest,identity(ROOT)['sha256'],policy)
    plan=browser_plan(ROOT,paths,contracts,'pr');errors.extend(plan['errors'])
    report={'decision':'BLOCKED' if errors else 'PASS','exploration':'REQUIRED' if policy['required'] else 'NOT_APPLICABLE',
            'policy':policy,'selection':plan,'errors':errors,'limitation':'A policy not-applicable result is not a passing exploratory test'}
    out=ROOT/'output/playwright/ci/uat-policy';out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
    return 2 if errors else 0


if __name__=='__main__':raise SystemExit(main())
