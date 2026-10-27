"""Verify live evidence from a successful explicitly dispatched trusted GitHub run.

No AI is invoked here. Missing live infrastructure or evidence blocks QA/release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.runner import identity, validate_live


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def latest_owner_run(runs: list,workflow: int,repo: str,head: str) -> dict:
    candidates=[r for r in runs if r.get('workflow_id')==workflow
                and r.get('head_repository',{}).get('full_name')==repo
                and r.get('actor',{}).get('login')==repo.split('/')[0]
                and r.get('event')=='workflow_dispatch' and r.get('head_sha')==head
                and r.get('path')=='.github/workflows/research-live.yml']
    run=max(candidates,key=lambda r:(r.get('id',0),r.get('run_attempt',1))) if candidates else None
    if not run or run.get('status')!='completed' or run.get('conclusion')!='success':
        raise ValueError('Latest owner-dispatched live workflow on the exact PR head has not succeeded')
    return run


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true',required=True)
    parser.parse_args()
    out=ROOT/'output/playwright/ci/live';out.mkdir(parents=True,exist_ok=True)
    reasons=[]; manifest=None
    repo=os.environ.get('GITHUB_REPOSITORY','');token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN','')
    event_path=os.environ.get('GITHUB_EVENT_PATH')
    event=json.loads(Path(event_path).read_text(encoding='utf-8')) if event_path else {}
    head=event.get('pull_request',{}).get('head',{}).get('sha') or os.environ.get('GITHUB_SHA','')
    def api(path: str):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,headers={'User-Agent':'phdlab-live-qualification','Accept':'application/vnd.github+json','Authorization':'Bearer '+token})
        return json.load(urllib.request.urlopen(req,timeout=30))
    try:
        if not token or '/' not in repo or not head: raise ValueError('No authenticated GitHub run/evidence context; run the real local qualification and publish trusted artifacts')
        workflow=api('/actions/workflows/research-live.yml')
        runs=api('/actions/workflows/research-live.yml/runs?event=workflow_dispatch&head_sha='+head+'&per_page=100')['workflow_runs']
        run=latest_owner_run(runs,workflow['id'],repo,head)
        artifacts=api('/actions/runs/'+str(run['id'])+'/artifacts')['artifacts']
        name='live-qualification-'+str(run['id'])+'-'+str(run['run_attempt'])
        matching=[a for a in artifacts if a.get('name')==name and not a.get('expired', True)]
        if len(matching)!=1:raise ValueError('Exact latest-attempt live artifact is missing, ambiguous or expired')
        artifact=matching[0]
        if (artifact.get('workflow_run',{}).get('id')!=run['id']
                or artifact.get('workflow_run',{}).get('head_sha')!=head):
            raise ValueError('Live artifact belongs to a different run or commit')
        req=urllib.request.Request(artifact['archive_download_url'],headers={'User-Agent':'phdlab-live-qualification','Authorization':'Bearer '+token})
        try: response=urllib.request.build_opener(NoRedirect).open(req,timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301,302,307):raise
            # Signed artifact blob redirects must not receive the repository token.
            response=urllib.request.urlopen(exc.headers['Location'],timeout=60)
        data=response.read(50_000_001)
        if len(data)>50_000_000:raise ValueError('Live artifact exceeds bounded download size')
        from scripts.publish_live_evidence import unpack_bundle
        unpack_bundle(data,out/'evidence',hashlib.sha256(data).hexdigest())
        manifest=out/'evidence/manifest.json'
        reasons += validate_live(manifest,identity(ROOT)['sha256'],head)
    except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile) as exc:
        reasons.append(type(exc).__name__+': '+str(exc)[:400])
    report={'decision':'BLOCKED' if reasons else 'PASS','head_sha':head,'reasons':reasons,
            'scope':'Trusted real-local/provider/scientific artifact validation, not model execution',
            'manifest':str(manifest) if manifest else None}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
    return 2 if reasons else 0


if __name__=='__main__':raise SystemExit(main())
