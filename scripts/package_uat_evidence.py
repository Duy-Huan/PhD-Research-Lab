"""Package only an actually passing, matching-source canonical UAT run for CI review."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from devtools.verification.runner import identity


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--out',type=Path,default=ROOT/'docs/qa/evidence/uat/qualified');args=p.parse_args()
    report=json.loads(args.report.read_text(encoding='utf-8'))
    if report.get('profile')!='uat' or report.get('decision')!='PASS' or not report.get('source_stable') or report.get('source',{}).get('sha256')!=identity(ROOT)['sha256']:
        p.error('Only an actually passing current-source canonical UAT run can be packaged')
    folder=args.report.resolve().parent/'uat';uat=json.loads((folder/'uat-report.json').read_text(encoding='utf-8'))
    if uat.get('decision')!='PASS' or uat.get('deterministic_confirmation')!='PASS':p.error('No deterministic confirmation of the AI journey')
    out=args.out.resolve()
    if not any(out.is_relative_to((ROOT/base).resolve()) for base in ('docs/qa/evidence','output/playwright')):
        p.error('Use an owned evidence directory; never export raw UAT to unrelated storage')
    if out.exists():p.error('Qualified evidence already exists; preserve it and review a new version explicitly')
    files=['final.png','trace.zip','agent-history.json','browser-evidence.json','agent-result.json']
    for name in files:
        if not (folder/name).is_file():p.error('Required raw UAT artifact missing: '+name)
    out.mkdir(parents=True)
    artifacts=[]
    for name in files:
        src=folder/name
        if not src.is_file():p.error('Required raw UAT artifact missing: '+name)
        shutil.copy2(src,out/name);artifacts.append({'path':name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
    manifest={'decision':'PASS','mode':'REAL_LOCAL','source_sha256':report['source']['sha256'],'tested_base_commit':report['head_sha'],
              'verified_journeys':['settings-language'],'artifacts':artifacts,'release_blocking_defects':0,
              'review':{'status':'PENDING','note':'An AI self-report is not independent acceptance review'},
              'scope':uat['scope'],'limitations':['Only the named journey is qualified; other personas are not implied']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(out/'manifest.json');return 0


if __name__=='__main__':raise SystemExit(main())
