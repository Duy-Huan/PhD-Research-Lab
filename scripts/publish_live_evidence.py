"""Publish existing genuine local qualification; never generates model/scientific evidence."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.runner import identity,validate_live
from devtools.verification.selection import changed_files
from devtools.verification.journeys import relevant_contracts
from devtools.verification.uat_gate import requirements,validate_manifest


def unpack_bundle(raw: bytes,out: Path,digest: str) -> None:
    if len(raw)>50_000_000 or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Evidence archive size/digest mismatch')
    if out.exists():raise ValueError('Preserve existing incoming evidence')
    contents={};total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for count,item in enumerate(archive.infolist()):
            name=PurePosixPath(item.filename)
            if (count>=1000 or item.orig_filename!=item.filename or name.is_absolute() or '..' in name.parts or chr(92) in item.filename
                    or ':' in item.filename or (item.external_attr>>16)&0o170000==0o120000):
                raise ValueError('Unsafe incoming artifact path or symlink')
            if item.is_dir():continue
            if name.as_posix() in contents or item.file_size>50_000_000:raise ValueError('Duplicate/oversized incoming artifact')
            total+=item.file_size
            if total>200_000_000:raise ValueError('Incoming evidence expansion bound exceeded')
            contents[name.as_posix()]=archive.read(item)
    if 'manifest.json' not in contents:raise ValueError('Actual qualification manifest missing')
    for name,data in contents.items():
        path=(out/name).resolve()
        if not path.is_relative_to(out.resolve()):raise ValueError('Incoming path escapes owned storage')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def receive(root: Path,head: str) -> Path:
    blob=os.environ.get('BUNDLE_BLOB_SHA','');digest=os.environ.get('BUNDLE_SHA256','')
    if not re.fullmatch('[0-9a-f]{40}',blob) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Actual owner archive identifiers required')
    token=os.environ.get('GITHUB_TOKEN','')
    if not token:raise ValueError('Read-only GitHub artifact transport context is missing')
    request=urllib.request.Request('https://api.github.com/repos/Duy-Huan/PhD-Research-Lab/git/blobs/'+blob,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github.raw+json','User-Agent':'phdlab-live-publisher'})
    with urllib.request.urlopen(request,timeout=60) as response:raw=response.read(50_000_001)
    owned=root/'output/playwright/live-transfer';owned.mkdir(parents=True,exist_ok=True)
    incoming=Path(tempfile.mkdtemp(prefix='received-',dir=owned))
    unpack_bundle(raw,incoming/head,digest)
    return incoming


def uat_files(root: Path,folder: Path,source: str) -> dict[str,str]:
    base='origin/main' if os.environ.get('GITHUB_REF')=='refs/heads/qa' else 'origin/qa'
    paths=changed_files(root,base)
    contracts=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'docs/qa/contracts').glob('*.json')]
    policy=requirements(paths,relevant_contracts(paths,contracts))
    path=folder/'uat/manifest.json';errors=validate_manifest(path,source,policy)
    if errors:raise ValueError('; '.join(errors))
    if not policy['required']:return {}
    raw=path.read_bytes();data=json.loads(raw)
    return {'uat/manifest.json':hashlib.sha256(raw).hexdigest(),
            **{'uat/'+item['path']:item['sha256'] for item in data['artifacts']}}


def collect_files(manifest: dict) -> dict[str,str | None]:
    records={'manifest.json':None}
    for layer in manifest.get('layers',{}).values():
        for item in layer.get('artifacts',[]):
            name=item['path'];digest=item['sha256']
            if name in records and records[name]!=digest:raise ValueError('Conflicting artifact digest')
            records[name]=digest
    live=manifest['live_regression'];records[live['path']]=live['sha256']
    if len(records)>1000:raise ValueError('Too many qualification artifacts')
    return records


def publish(root: Path,evidence_root: Path,out: Path,head: str,source: str) -> dict:
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if actual!=head or identity(root)['sha256']!=source:raise ValueError('Checkout does not match approved actual source/head')
    folder=(evidence_root/head).resolve()
    if not folder.is_relative_to(evidence_root.resolve()):raise ValueError('Unowned evidence input')
    manifest_path=folder/'manifest.json'
    errors=validate_live(manifest_path,source,head)
    if errors:raise ValueError('; '.join(errors))
    manifest_raw=manifest_path.read_bytes();records=collect_files(json.loads(manifest_raw))
    records.update(uat_files(root,folder,source))
    if out.exists():raise ValueError('Use a fresh output directory; preserve prior evidence')
    # Read/hash everything before writing anything. Only explicitly declared raw
    # artifacts are copied; no private environment or arbitrary directory upload.
    content={};total=0
    for name,digest in records.items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder) or not path.is_file():raise ValueError('Artifact escapes evidence root or is missing')
        if path.stat().st_size>50_000_000:raise ValueError('Individual artifact size bound exceeded')
        raw=path.read_bytes();total+=len(raw)
        if total>200_000_000:raise ValueError('Qualification archive size bound exceeded')
        if name=='manifest.json' and raw!=manifest_raw:raise ValueError('Manifest changed during publication')
        if digest and hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Artifact changed during publication')
        target=(out/name).resolve()
        if not target.is_relative_to(out.resolve()):raise ValueError('Unsafe artifact output path')
        content[name]=raw
    for name,raw in content.items():
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return {'operation':'PUBLISH_EXISTING_VERIFIED_EVIDENCE','head_sha':head,'source_sha256':source,
            'files':len(content),'bytes':total,'model_invoked':False,
            'scope':'Integrity/provenance packaging only; original actual execution and independent scientific review remain required'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    head=os.environ.get('EXPECTED_HEAD_SHA','');source=os.environ.get('EXPECTED_SOURCE_SHA256','')
    try:
        if (os.environ.get('GITHUB_EVENT_NAME')!='workflow_dispatch'
                or os.environ.get('GITHUB_ACTOR')!='Duy-Huan'
                or os.environ.get('GITHUB_REPOSITORY')!='Duy-Huan/PhD-Research-Lab'
                or os.environ.get('GITHUB_REF') not in ('refs/heads/dev','refs/heads/qa')):
            raise ValueError('Only an explicit owner dispatch on trusted dev/QA may publish')
        if not re.fullmatch('[0-9a-f]{40}',head) or not re.fullmatch('[0-9a-f]{64}',source):raise ValueError('Exact approved head/source inputs required')
        if os.environ.get('GITHUB_SHA')!=head:raise ValueError('Dispatched branch moved from the approved commit')
        if not out.is_relative_to((ROOT/'output/playwright').resolve()):raise ValueError('Unowned output directory')
        configured=os.environ.get('PHDLAB_LIVE_EVIDENCE_ROOT')
        evidence=Path(configured).resolve() if configured else receive(ROOT,head)
        report=publish(ROOT,evidence,out,head,source)
        print(json.dumps(report));return 0
    except (OSError,ValueError,KeyError,TypeError,AttributeError,subprocess.SubprocessError,zipfile.BadZipFile) as exc:
        print(json.dumps({'decision':'BLOCKED','model_invoked':False,'reason':str(exc)[:800]}));return 2


if __name__=='__main__':raise SystemExit(main())
