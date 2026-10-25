"""Start/stop the explicitly trusted local native dev -> qa -> main supervisor."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import subprocess
import time
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.promotion import home,read_state,save_state,code_digests,policy_errors,tick,git
from devtools.verification.ci_repair import GitHub
from scripts.check_local_verification import load_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['register','once','watch','status','stop','resume'])
    parser.add_argument('--authorize-native-main-merge',action='store_true')
    parser.add_argument('--enable-repo-auto-merge',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--interval',type=int,default=60)
    args=parser.parse_args();folder=home(ROOT);policy_path=folder/'policy.json';state_path=folder/'state.json'
    if args.interval<30:parser.error('Polling interval must be at least30seconds')
    if args.command=='register':
        report,errors=load_report(ROOT)
        if not args.authorize_native_main_merge:errors.append('Explicit owner authorization for native main promotion is required')
        if git(ROOT,'branch','--show-current')!='dev' or git(ROOT,'status','--porcelain'):errors.append('Register only a clean fully verified dev worktree')
        if errors:print(json.dumps({'decision':'BLOCKED','reasons':errors}));return 2
        if state_path.exists():read_state(state_path)  # Preserve/reject corrupt history, never reset it.
        policy={'repository':'Duy-Huan/PhD-Research-Lab','root':str(ROOT.resolve()),'authorize_native_main':True,
                'enable_repo_auto_merge':args.enable_repo_auto_merge,'code':code_digests(ROOT),
                'authorized_at':datetime.now(timezone.utc).isoformat(),'initial_source':report['source']['sha256']}
        save_state(policy_path,policy)
        if not state_path.exists():save_state(state_path,{'stopped':False,'merges':[]})
        print(json.dumps({'decision':'REGISTERED','policy':str(policy_path),'note':'External trust only; no merge or QA qualification is implied'}));return 0
    if args.command=='status':
        print(json.dumps(read_state(state_path) | {'stopped':(folder/'STOP').exists()},indent=2));return 0
    if args.command in ('stop','resume'):
        state=read_state(state_path);flag=folder/'STOP'
        if args.command=='stop':flag.touch()
        else:flag.unlink(missing_ok=True)
        print(json.dumps({'phase':'STOPPED' if flag.exists() else 'RESUMED','merges':len(state.get('merges',[]))}));return 0
    try:
        policy=json.loads(policy_path.read_text(encoding='utf-8'));errors=policy_errors(ROOT,policy)
        if errors:raise ValueError('; '.join(errors))
    except (OSError,ValueError,TypeError,AttributeError) as exc:
        print(json.dumps({'phase':'BLOCKED','reasons':[type(exc).__name__+': '+str(exc)[:300]]}));return 2
    # Reuse the existing cross-platform OS lock; no competing writer/supervisor.
    from devtools.verification.ci_repair import exclusive_lock
    with exclusive_lock(folder/'supervisor.lock'):
        previous=None
        while True:
            state=read_state(state_path)
            state['stopped']=(folder/'STOP').exists()
            try:result=tick(GitHub(),ROOT,policy,state,args.apply)
            except (OSError,ValueError,KeyError,TypeError,RuntimeError,AttributeError,subprocess.SubprocessError) as exc:
                result={'phase':'BLOCKED','reasons':[type(exc).__name__+': '+str(exc)[:400]]}
            state['latest']=result;state['observed_at']=datetime.now(timezone.utc).isoformat();save_state(state_path,state)
            compact=json.dumps(result,sort_keys=True)
            if compact!=previous:print(compact,flush=True);previous=compact
            if args.command=='once' or result['phase'] in ('STOPPED','RELEASE_PROMOTION_VERIFIED'):
                return 0 if result['phase'] in ('RELEASE_PROMOTION_VERIFIED','ELIGIBLE') else 2
            time.sleep(args.interval)


if __name__=='__main__':raise SystemExit(main())
