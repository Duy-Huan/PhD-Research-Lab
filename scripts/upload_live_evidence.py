"""Transfer actual local evidence without changing code/branches; dispatch trusted validation."""
from __future__ import annotations
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.ci_repair import GitHub,exclusive_lock
from scripts.check_local_verification import load_report
from scripts.publish_live_evidence import publish


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root',type=Path,required=True)
    parser.add_argument('--ref',choices=['dev','qa'],required=True)
    args=parser.parse_args();report,errors=load_report(ROOT)
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():errors.append('Preserve/commit scoped changes first; only a clean verified dev worktree may upload')
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='dev':errors.append('Develop and qualify from the single dev branch')
    if errors:print(json.dumps({'decision':'BLOCKED','reasons':errors}));return 2
    api=GitHub();head=api.request('/branches/'+args.ref)['commit']['sha']
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if actual!=head:raise ValueError('Local dev must include the exact qualified target commit; no misleading head relabeling')
    os.environ['GITHUB_REF']='refs/heads/'+args.ref
    owned=ROOT/'output/playwright/live-transfer';owned.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='upload-',dir=owned))
    with exclusive_lock(owned/'upload.lock'):
        publication=publish(ROOT,args.evidence_root.resolve(),folder/'evidence',head,report['source']['sha256'])
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((folder/'evidence').rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(folder/'evidence').as_posix())
        raw=buffer.getvalue()
        if len(raw)>50_000_000:raise ValueError('Actual evidence bundle exceeds bounded transport size')
        digest=hashlib.sha256(raw).hexdigest()
        blob=api.request('/git/blobs',{'content':base64.b64encode(raw).decode(),'encoding':'base64'})
        receipt={'scope':'Evidence transport only; no branch/ref/commit changed, no model invoked',
                 'head_sha':head,'source_sha256':report['source']['sha256'],'bundle_blob_sha':blob['sha'],
                 'bundle_sha256':digest,'bytes':len(raw),'publication':publication,'created_utc':datetime.now(timezone.utc).isoformat()}
        (folder/'transport.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        if api.request('/branches/'+args.ref)['commit']['sha']!=head:raise ValueError('Branch moved; do not dispatch stale evidence')
        body={'ref':args.ref,'inputs':{'expected_head_sha':head,'source_sha256':report['source']['sha256'],
                                      'bundle_blob_sha':blob['sha'],'bundle_sha256':digest}}
        request=urllib.request.Request('https://api.github.com/repos/Duy-Huan/PhD-Research-Lab/actions/workflows/research-live.yml/dispatches',
            headers=api.headers,method='POST',data=json.dumps(body).encode())
        with urllib.request.urlopen(request,timeout=40) as response:receipt['dispatch_http_status']=response.status
        receipt['state']='DISPATCH_REQUESTED_NOT_YET_VERIFIED'
        (folder/'transport.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'state':receipt['state'],'head_sha':head,'receipt':str(folder/'transport.json')}));return 0


if __name__=='__main__':raise SystemExit(main())
