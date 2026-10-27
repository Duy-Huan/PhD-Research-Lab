"""Generate requirement/test traceability; absent or stale execution stays UNVERIFIED."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from devtools.verification.contracts import validate_contract
from devtools.verification.runner import identity


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--contract',type=Path,required=True);p.add_argument('--report',type=Path)
    args=p.parse_args();contract=json.loads(args.contract.read_text(encoding='utf-8'))
    errors=validate_contract(contract,ROOT)
    if errors:print(json.dumps({'errors':errors}));return 1
    report=json.loads(args.report.read_text(encoding='utf-8')) if args.report else {}
    current=report.get('source',{}).get('sha256')==identity(ROOT)['sha256'] and report.get('source_stable') is True
    cases={case['id']:case for case in report.get('cases',[])} if current else {}
    out=ROOT/'docs/qa/matrices'/(contract['id']+'.csv');out.parent.mkdir(parents=True,exist_ok=True)
    fields=['TestCaseID','Requirement','Preconditions','Steps','Input','ExpectedResult','Priority','TestLevel','Automation','Evidence','Status']
    with out.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for scenario in contract['scenarios']:
            path,_,symbol=scenario['test'].partition('::');case=cases.get(Path(path).stem+'.'+symbol,{})
            writer.writerow({'TestCaseID':scenario['id'],'Requirement':scenario['requirement'],
                'Preconditions':'; '.join(contract['preconditions']),'Steps':'Execute '+scenario['test'],
                'Input':'; '.join(contract['inputs']),'ExpectedResult':scenario['expected'],
                'Priority':contract['risk'],'TestLevel':contract['mode'],'Automation':scenario['test'],
                'Evidence':str(args.report) if case else '', 'Status':case.get('status','UNVERIFIED')})
    print(json.dumps({'matrix':str(out),'rows':len(contract['scenarios']),'matching_execution':current,
                      'limitation':'Scenario inventory/traceability is not exhaustive behavioral or source coverage'}));return 0


if __name__=='__main__':raise SystemExit(main())
