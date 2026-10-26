"""Package only an actually passing, matching-source canonical UAT run for CI review."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from devtools.verification.runner import identity
from devtools.verification.uat_gate import RAW_FILES, validate_run
from devtools.verification.uat_journeys import JOURNEYS


def collect_reports(reports: list[Path], source: str, head: str) -> tuple[dict, dict[str,bytes]]:
    """Read all runs before writing; a deterministic self-test is never AI-UAT."""
    journeys={};content={};histories=set()
    for report_path in reports:
        report=json.loads(report_path.read_text(encoding='utf-8'))
        if (report.get('profile')!='uat' or report.get('decision')!='PASS' or not report.get('source_stable')
                or report.get('source',{}).get('sha256')!=source or report.get('head_sha')!=head):
            raise ValueError('Only passing canonical UAT runs on current source and exact head can be packaged')
        folder=report_path.resolve().parent/'uat';uat=json.loads((folder/'uat-report.json').read_text(encoding='utf-8'))
        journey=uat.get('journey')
        if journey not in JOURNEYS or journey in journeys:raise ValueError('Unknown or duplicate journey report')
        if uat.get('decision')!='PASS' or uat.get('mode')!='REAL_LOCAL' or uat.get('deterministic_confirmation')!='PASS' or uat.get('source_sha256')!=source:
            raise ValueError('No matching-source deterministic confirmation of '+journey)
        errors=validate_run(folder,source,journey)
        if errors:raise ValueError('; '.join(errors))
        history_digest=hashlib.sha256((folder/'agent-history.json').read_bytes()).hexdigest()
        if history_digest in histories:raise ValueError('One action history cannot qualify multiple journeys')
        histories.add(history_digest)
        journeys[journey]={'decision':'PASS','mode':'REAL_LOCAL','source_sha256':source,'tested_base_commit':head,'scope':uat['scope']}
        for name in sorted(RAW_FILES):content[f'journeys/{journey}/{name}']=(folder/name).read_bytes()
    if not journeys:raise ValueError('No actually executed UAT reports')
    manifest={'schema_version':2,'decision':'PASS','mode':'REAL_LOCAL','source_sha256':source,'tested_base_commit':head,
        'verified_journeys':sorted(journeys),'journeys':journeys,
        'artifacts':[{'path':name,'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in sorted(content.items())],
        'release_blocking_defects':0,'review':{'status':'PENDING','note':'Actual independent acceptance review is still required'},
        'limitations':['Only individually executed named journeys are included; synthetic setup and controlled faults are not scientific/provider qualification']}
    return manifest,content


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,default=ROOT/'docs/qa/evidence/uat/qualified');args=p.parse_args()
    out=args.out.resolve()
    if not any(out.is_relative_to((ROOT/base).resolve()) for base in ('docs/qa/evidence','output/playwright')):
        p.error('Use an owned evidence directory; never export raw UAT to unrelated storage')
    if out.exists():p.error('Qualified evidence already exists; preserve it and review a new version explicitly')
    if any(not any(path.resolve().is_relative_to((ROOT/base).resolve()) for base in ('output/playwright','docs/qa/evidence')) for path in args.report):
        p.error('Canonical input reports must belong to owned verification evidence')
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        manifest,content=collect_reports(args.report,identity(ROOT)['sha256'],head)
    except (OSError,ValueError,KeyError,TypeError) as exc:p.error(str(exc))
    out.mkdir(parents=True)
    for name,raw in content.items():
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(out/'manifest.json');return 0


if __name__=='__main__':raise SystemExit(main())
