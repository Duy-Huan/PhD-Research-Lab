"""Local-first native GitHub promotion; never edits code or manufactures evidence."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

from .ci_repair import GitHub,REPOSITORY
from scripts.check_local_verification import load_report

TRUSTED_FILES=('devtools/verification/promotion.py','scripts/promote.py',
               '.github/scripts/automerge.cjs','.github/scripts/assess_promotion.cjs',
               '.github/required-ci-jobs.json','devtools/verification/ci_repair.py',
               '.github/workflows/quality.yml','.github/workflows/automerge.yml',
               '.github/workflows/research-live.yml','scripts/quality_gate.py',
               'scripts/live_qualification.py','scripts/uat_gate.py','scripts/publish_live_evidence.py','scripts/upload_live_evidence.py',
               'devtools/verification/contracts.py','devtools/verification/layers.py',
               'devtools/verification/evidence.py','devtools/verification/uat_gate.py',
               'devtools/verification/uat_authorization.py',
               'devtools/verification/runner.py','devtools/verification/branch_policy.py',
               'scripts/check_local_verification.py','scripts/development_guard.py')


def git(root: Path,*args) -> str:
    return subprocess.check_output(['git',*args],cwd=root,text=True,timeout=60).strip()


def sync_dev(root: Path,target: str,sha: str) -> dict:
    """Advance only dev across an observed same-tree native merge; never edit source."""
    if target not in ('qa','main') or git(root,'branch','--show-current')!='dev' or git(root,'status','--porcelain'):
        raise ValueError('History synchronization requires a clean dev worktree and a protected target')
    remote=git(root,'remote','get-url','origin').removesuffix('.git')
    if remote not in ('https://github.com/'+REPOSITORY,'git@github.com:'+REPOSITORY):raise ValueError('Unauthorized origin')
    before=git(root,'rev-parse','HEAD');tree=git(root,'rev-parse','HEAD^{tree}')
    git(root,'fetch','--no-tags','origin',target)
    actual=git(root,'rev-parse','origin/'+target)
    if actual!=sha or git(root,'rev-parse',sha+'^{tree}')!=tree:
        raise ValueError('Protected target changed or tree differs; preserve source and require dev integration/verification')
    subprocess.run(['git','merge-base','--is-ancestor',before,sha],cwd=root,check=True,capture_output=True,timeout=20)
    git(root,'merge','--ff-only',sha)
    if git(root,'rev-parse','HEAD^{tree}')!=tree or git(root,'status','--porcelain'):
        raise ValueError('Source changed during same-tree synchronization; do not push')
    git(root,'push','origin','dev')  # Installed source-bound pre-push guard remains authoritative.
    return {'from':before,'dev_head':sha,'tree_unchanged':True,'target':target}


def home(root: Path) -> Path:
    common=Path(git(root,'rev-parse','--git-common-dir'))
    if not common.is_absolute():common=root/common
    return common.resolve()/'auto-promotion'


def code_digests(root: Path) -> dict:
    hashes={}
    for name in TRUSTED_FILES:
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Controller source escapes authorized worktree')
        hashes[name]=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    return hashes


def policy_errors(root: Path,policy: dict) -> list[str]:
    if (policy.get('repository')!=REPOSITORY or policy.get('root')!=str(root.resolve())
            or policy.get('authorize_native_main') is not True):
        return ['Explicit external owner policy for this repository/worktree/main promotion is required']
    if policy.get('code')!=code_digests(root):return ['Trusted controller changed; explicit owner registration is required']
    return []


def save_state(path: Path,data: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');temp.replace(path)


def read_state(path: Path) -> dict:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or not isinstance(data.get('merges',[]),list):raise ValueError('Corrupt persistent promotion state')
    return data


def assess(root: Path,snapshot: dict,operation: str='promotion') -> dict:
    node=shutil.which('node.exe' if os.name=='nt' else 'node')
    if not node:raise ValueError('Trusted Node runtime unavailable')
    process=subprocess.run([node,str(root/'.github/scripts/assess_promotion.cjs')],cwd=root,
                           input=json.dumps({'operation':operation,'snapshot':snapshot}),capture_output=True,text=True,timeout=20)
    if process.returncode not in (0,2):raise ValueError('Shared promotion assessment did not complete')
    return json.loads(process.stdout)


def latest_run(runs: list,sha: str,branch: str,workflow: int,event='pull_request') -> dict | None:
    candidates=[r for r in runs if r.get('head_sha')==sha and r.get('head_branch')==branch
                and r.get('workflow_id')==workflow and r.get('event')==event
                and r.get('path')=='.github/workflows/quality.yml'
                and r.get('head_repository',{}).get('full_name')==REPOSITORY]
    return max(candidates,key=lambda r:(r.get('run_started_at',r.get('created_at','')),r.get('id',0),r.get('run_attempt',1))) if candidates else None


def execution(api: GitHub,sha: str,branch: str,event='pull_request') -> dict:
    workflow=api.request('/actions/workflows/quality.yml')
    runs=api.request('/actions/workflows/quality.yml/runs?head_sha='+sha+'&per_page=50')['workflow_runs']
    run=latest_run(runs,sha,branch,workflow['id'],event)
    jobs=api.pages('/actions/runs/'+str(run['id'])+'/jobs?filter=latest','jobs') if run else []
    return {'run':run,'jobs':jobs,'expected_head_sha':sha,'repository':REPOSITORY}


def mutate(api: GitHub,path: str,method: str,data: dict) -> dict:
    request=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+path,
                                   headers=api.headers,method=method,data=json.dumps(data).encode())
    with urllib.request.urlopen(request,timeout=40) as response:return json.load(response)


def find_pr(api: GitHub,head: str,base: str,create: bool=False) -> dict | None:
    prs=api.request('/pulls?state=open&base='+base+'&head=Duy-Huan:'+head+'&per_page=100')
    if len(prs)>1:raise ValueError('Ambiguous active promotion PR')
    if prs:return api.request('/pulls/'+str(prs[0]['number']))
    if not create:return None
    return api.request('/pulls',{'head':head,'base':base,'title':'Qualified promotion: '+head+' -> '+base,
        'body':'Contract: FQC-AUTO-PROMOTION-001\n\nOwner-authorized native forward promotion. Require actual current-source complete local software verification, independent complete software regression across backend/frontend/browser and policy/security. Live/provider/research and AI-UAT run separately and are not merge prerequisites under the owner2026-10-26 policy. No skipped/missing mandatory check is PASS.100%coverage is the desired informational target;95%was an estimate, never a waiver. Native GitHub alone may merge after all protected checks pass; no administrative bypass.'})


def ensure_native(api: GitHub,root: Path,pr: dict,policy: dict,apply: bool) -> dict:
    sha=pr['head']['sha'];snapshot=execution(api,sha,pr['head']['ref'])
    run=snapshot['run'];suite=run.get('check_suite_id') if run else None
    checks=api.pages('/commits/'+sha+'/check-runs?filter=latest','check_runs')
    snapshot.update(pr=pr,owner='Duy-Huan',allow_main_promotion=policy['authorize_native_main'],
                    protection=api.request('/branches/'+pr['base']['ref']+'/protection'),
                    checks=[c for c in checks if suite and c.get('check_suite',{}).get('id')==suite],
                    reviews=api.pages('/pulls/'+str(pr['number'])+'/reviews',None),
                    comparison=api.request('/compare/'+pr['base']['ref']+'...'+sha)['status'],
                    allow_auto_merge=api.request('')['allow_auto_merge'])
    assessment=assess(root,snapshot)
    # Repository flag is configured only under the explicit external owner policy,
    # after every other mandatory condition genuinely qualifies.
    flag='Repository auto-merge is disabled'
    if assessment['reasons']==[flag] and apply and policy.get('enable_repo_auto_merge') is True:
        mutate(api,'','PATCH',{'allow_auto_merge':True});snapshot['allow_auto_merge']=True
        assessment=assess(root,snapshot)
    result={'phase':'BLOCKED' if assessment['decision']!='ELIGIBLE' else 'ELIGIBLE',
            'pr':pr['number'],'head':sha,'target':pr['base']['ref'],'run_id':run.get('id') if run else None,
            'reasons':assessment['reasons']}
    if assessment['decision']!='ELIGIBLE' or not apply:return result
    fresh=api.request('/pulls/'+str(pr['number']))
    if (fresh['head']['sha']!=sha or fresh['base']['ref']!=pr['base']['ref']
            or fresh['base'].get('sha')!=pr['base'].get('sha') or fresh['head']['ref']!=pr['head']['ref']):
        return result | {'phase':'BLOCKED','reasons':['PR head or target changed before native request']}
    if not fresh.get('merged'):
        if (fresh.get('state')!='open' or fresh.get('draft') or fresh.get('mergeable') is not True
                or fresh.get('mergeable_state')!='clean'):
            return result | {'phase':'BLOCKED','reasons':['PR is no longer ready for protected native merge']}
        # GitHub rejects enablePullRequestAutoMerge for an already CLEAN PR. All
        # gates above still apply; this normal native mutation locks the head and
        # GitHub enforces the target's strict/admin-enforced branch protection.
        api.request('/graphql',{'query':'mutation($id:ID!,$sha:GitObjectID!){mergePullRequest(input:{pullRequestId:$id,expectedHeadOid:$sha,mergeMethod:MERGE}){pullRequest{number}}}',
                                'variables':{'id':fresh['node_id'],'sha':sha}})
    return result | {'phase':'NATIVE_PROTECTED_MERGE_REQUESTED'}


def tick(api: GitHub,root: Path,policy: dict,state: dict,apply: bool) -> dict:
    errors=policy_errors(root,policy)
    if errors:return {'phase':'BLOCKED','reasons':errors}
    if state.get('stopped'):return {'phase':'STOPPED','reasons':['Persistent stop requested']}
    if git(root,'branch','--show-current')!='dev' or git(root,'status','--porcelain'):
        return {'phase':'BLOCKED','reasons':['Only clean authorized dev worktree may promote']}
    report,errors=load_report(root)
    if errors:return {'phase':'BLOCKED','reasons':errors}
    head=git(root,'rev-parse','HEAD');tree=git(root,'rev-parse','HEAD^{tree}')
    if state.get('sync_pending'):
        if not apply:
            return {'phase': 'OBSERVE_SYNC_PENDING', 'synchronization': state['sync_pending']}
        task=state['sync_pending'];synchronized=sync_dev(root,task['target'],task['sha']);state.pop('sync_pending')
        return {'phase':'DEV_HISTORY_SYNCHRONIZED','synchronization':synchronized}
    remote=api.request('/branches/dev')['commit']['sha']
    if head!=remote:return {'phase':'BLOCKED','reasons':['Local dev HEAD differs from published dev']}
    # Record only observed native completion, never a queued request as MERGED.
    pending=state.get('pending')
    if pending:
        observed=api.request('/pulls/'+str(pending['pr']))
        if observed.get('merged'):
            merge=observed.get('merge_commit_sha')
            if not merge or api.request('/compare/'+merge+'...'+pending['target'])['status'] not in ('ahead','identical'):
                raise ValueError('Observed merge is not contained in target')
            record=pending | {'phase':'MERGED','merge_sha':merge,'observed_at':datetime.now(timezone.utc).isoformat()}
            if not any(x.get('merge_sha')==merge for x in state.setdefault('merges',[])):state['merges'].append(record)
            state.pop('pending',None)
            state['sync_pending']={'target':pending['target'],'sha':merge}
            if not apply:
                return record | {'phase': 'MERGE_OBSERVED_SYNC_PENDING', 'synchronization': state['sync_pending']}
            synchronized=sync_dev(root,pending['target'],merge);state.pop('sync_pending')
            if pending['target']=='main':return record | {'phase':'RELEASE_PROMOTION_VERIFIED','synchronization':synchronized}
            return record | {'phase':'QA_MERGE_VERIFIED','synchronization':synchronized}
    dev_run=execution(api,head,'dev','push');run=dev_run['run']
    software=[name for name in json.loads((root/'.github/required-ci-jobs.json').read_text())['qa']
              if name != 'QA gate']
    jobs={j['name']:j for j in dev_run['jobs']}
    dev_pass=bool(run and run['status']=='completed' and run['conclusion']=='success'
                  and all(jobs.get(name,{}).get('conclusion')=='success'
                          and jobs.get(name,{}).get('status')=='completed'
                          and jobs.get(name,{}).get('run_id')==run['id'] for name in software))
    qa=api.request('/branches/qa')['commit']['sha']
    qa_tree=api.request('/git/commits/'+qa)['tree']['sha']
    if qa_tree!=tree:
        if api.request('/compare/qa...'+head)['status'] not in ('ahead','identical'):
            return {'phase':'BLOCKED','reasons':['Dev must include current QA; integrate on dev, never rewrite protected branches']}
        pr=find_pr(api,'dev','qa',create=apply)
        if not pr:return {'phase':'READY_QA_PR','head':head,'reasons':['Observation only; no PR created']}
        if not dev_pass:return {'phase':'WAITING_DEV_CI','head':head,'pr':pr['number'],
                                'run_id':run.get('id') if run else None,
                                'reasons':['PR is reviewable/repairable; exact latest dev software CI must pass before native promotion']}
    else:
        if not dev_pass:return {'phase':'WAITING_DEV_CI','head':head,'run_id':run.get('id') if run else None,
                                'reasons':['Exact latest dev software CI has not genuinely passed']}
        history=api.request('/pulls?state=closed&base=qa&head=Duy-Huan:dev&per_page=100')
        provenance=next((p for p in history if p.get('merged_at') and p.get('merge_commit_sha')==qa),None)
        if not provenance:return {'phase':'BLOCKED','reasons':['QA tree matches but tested dev-to-QA merge provenance is absent']}
        tested=provenance['head']['sha']
        if api.request('/git/commits/'+tested)['tree']['sha']!=tree:
            return {'phase':'BLOCKED','reasons':['QA merge tree differs from the genuinely tested dev candidate']}
        qualified=assess(root,execution(api,tested,'dev'),'qualification')
        if qualified['decision']!='ELIGIBLE':return {'phase':'BLOCKED_UNQUALIFIED_QA','reasons':qualified['reasons']}
        main=api.request('/branches/main')['commit']['sha']
        if api.request('/git/commits/'+main)['tree']['sha']==tree:
            return {'phase':'MAIN_TREE_PRESENT','reasons':['No new promotion required; do not infer qualified release without an observed native completion record']}
        pr=find_pr(api,'qa','main',create=apply)
        if not pr:return {'phase':'READY_MAIN_PR','head':qa,'reasons':['Observation only; no PR created']}
    result=ensure_native(api,root,pr,policy,apply)
    if result['phase']=='NATIVE_PROTECTED_MERGE_REQUESTED':
        state['pending']=result | {'local_source_sha256':report['source']['sha256'],'local_tree':tree}
    return result
