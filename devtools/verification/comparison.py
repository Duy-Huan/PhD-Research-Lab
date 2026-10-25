"""Compare fixed-policy observations, never rank different suites by absolute PASS counts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare(left: dict, right: dict, critical: list[dict]) -> dict:
    if any(subject.get('source',{}).get('stable') is not True for subject in (left,right)):
        raise ValueError('INCOMPARABLE: source checkout changed during execution')
    for key in ('suite_sha256', 'environment_sha256', 'policy_sha256'):
        if not left.get('manifest', {}).get(key) or left['manifest'].get(key) != right.get('manifest', {}).get(key):
            raise ValueError('INCOMPARABLE: different ' + key)
    rank={'PASS':0,'SKIP':1,'NOT_RUN':2,'BLOCKED':3,'UNVERIFIED':3,'FAIL':4,'ERROR':5}
    def assess(subject):
        cases={}
        for case in subject.get('cases',[]):
            name=case.get('id');status=case.get('status','NOT_RUN')
            if status not in rank:status='NOT_RUN'
            if name and rank[status]>=rank.get(cases.get(name),-1):cases[name]=status
        workflows=[]
        for workflow in critical:
            ids=workflow['case_ids'];states=[cases.get(name,'NOT_RUN') for name in ids]
            status=('NOT_RUN' if not states else 'FAIL' if any(s in ('FAIL','ERROR') for s in states)
                    else 'PASS' if all(s=='PASS' for s in states) else 'BLOCKED')
            workflows.append({**workflow,'status':status,'case_states':dict(zip(ids,states))})
        passed=sum(w['status']=='PASS' for w in workflows)
        defects=subject.get('confirmed_defects',[])
        counts={severity:sum(d.get('severity')==severity and d.get('status')=='CONFIRMED_UNRESOLVED' for d in defects)
                for severity in ('P0','P1','P2','P3')}
        return {'source':subject.get('source'), 'critical_software_checks':workflows,
                'critical_pass_rate':{'passed':passed,'required':len(workflows),
                                     'percent':round(100*passed/len(workflows),2) if workflows else None},
                'known_confirmed_unresolved_defects':counts,'defect_inventory_complete':subject.get('defect_inventory_complete',False),
                'coverage':subject.get('coverage',{}),'execution_counts':{s:sum(v==s for v in cases.values()) for s in rank},
                'full_research_acceptance':subject.get('full_research_acceptance','NOT_RUN')}
    return {'schema_version':1,'comparability':'SAME_RECORDED_SUITE_ENVIRONMENT_POLICY',
            'manifest':left['manifest'],'main':assess(left),'candidate':assess(right),
            'limitations':['Manifest equality establishes recorded inputs, not correctness of the tests',
                           'Critical software checks are not all-provider/scientific acceptance',
                           'Missing/skipped/failed cases never count as PASS',
                           'Raw PASS counts do not rank branches; coverage denominators may differ with implemented source',
                           'Unclassified test failures are not automatically confirmed product defects or assigned severity']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--critical',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    result=compare(json.loads(args.main.read_text(encoding='utf-8')),json.loads(args.candidate.read_text(encoding='utf-8')),
                   json.loads(args.critical.read_text(encoding='utf-8')))
    if args.out.exists():parser.error('Use a fresh output path; preserve earlier comparisons')
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({side:result[side]['critical_pass_rate'] for side in ['main','candidate']}))
    return 0


if __name__=='__main__':raise SystemExit(main())
