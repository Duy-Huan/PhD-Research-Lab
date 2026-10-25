import hashlib,json,sys
from pathlib import Path
root=Path('.').resolve();sys.path.insert(0,str(root))
from devtools.verification.comparison import compare
folder=root/'output/playwright/ci-supervisor/comparison-656'
prep=json.loads((folder/'preparation.json').read_text(encoding='utf-8'))
paths={'frontend/src/features/agent-status/office3d/OfficeScene.tsx':['Click '+chr(0x6d)+chr(0x1edf)+' Runtime'],
 'frontend/src/shared/events/eventAdapter.ts':['Principal Investigator']}
review={'id':'BUG-3D-LOCALE-001','severity':'P2','criterion':'The same hard-coded locale-sensitive labels exist unconditionally in both source revisions; EN must not render Vietnamese system labels',
 'mode':'SOURCE_REVIEW_BOTH_AND_REAL_BROWSER_CANDIDATE','candidate_browser_evidence':'docs/qa/evidence/comparison-6.5.6/candidate/visual/3d-3d-real.png',
 'main_browser_reproduction':'NOT_RUN: the common3D journey fails before reaching this assertion; no claim it reproduced the locale visually on main',
 'sources':{}}
subjects={}
for side in ['main','candidate']:
 subject_root=Path(prep[side+'_root']);review['sources'][side]=[]
 for name,fragments in paths.items():
  p=subject_root/name;text=p.read_text(encoding='utf-8');assert all(fragment in text for fragment in fragments)
  lines=[{'line':i,'text':line} for i,line in enumerate(text.splitlines(),1) if any(fragment in line for fragment in fragments)]
  review['sources'][side].append({'file':name,'sha256':hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'lines':lines})
 p=folder/(side+'-subject.json');d=json.loads(p.read_text(encoding='utf-8'))
 assert not any(x['id']==review['id'] for x in d['confirmed_defects'])
 d['confirmed_defects'].append({'id':review['id'],'severity':'P2','status':'CONFIRMED_UNRESOLVED','description':'English3D view retains Vietnamese HPC labels and agent role text','evidence':'locale-source-review.json','mode':review['mode'],'regression_status':'NOT_IMPLEMENTED','runtime_reproduction':'REPRODUCED' if side=='candidate' else 'NOT_RUN'})
 p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');subjects[side]=d
old=json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
result=compare(subjects['main'],subjects['candidate'],json.loads((root/'docs/qa/CRITICAL_SOFTWARE_CHECKS.json').read_text(encoding='utf-8')))
result['observed_transitions']=old['observed_transitions'];result['additional_source_review']=review
(folder/'locale-source-review.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
(folder/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({s:result[s]['known_confirmed_unresolved_defects'] for s in ['main','candidate']}))
