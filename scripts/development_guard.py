"""Install/enforce trusted local dev-only commits and complete-regression dev pushes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.branch_policy import development_errors, receipt_path, report_errors
from devtools.verification.runner import identity

ALLOWED_REMOTES = {'https://github.com/Duy-Huan/PhD-Research-Lab',
                   'git@github.com:Duy-Huan/PhD-Research-Lab',
                   'ssh://git@github.com/Duy-Huan/PhD-Research-Lab'}


def remote_errors(name: str, url: str) -> list[str]:
    return [] if name == 'origin' and url.removesuffix('.git') in ALLOWED_REMOTES else [
        'Push is allowed only to the authorized origin repository']


def reference_errors(updates: str) -> list[str]:
    errors=[]
    for line in updates.splitlines():
        fields=line.split()
        if len(fields)!=3:
            errors.append('Malformed Git reference transaction');continue
        _old,new,ref=fields
        if ref.startswith('refs/heads/') and ref!='refs/heads/dev' and new!='0'*40:
            errors.append('Only local dev may be created/updated; QA/main promotion belongs to protected GitHub PRs: '+ref)
    return errors


def git(root, *args):
    return subprocess.check_output(['git',*args],cwd=root,text=True).strip()


def push_errors(root: Path, updates: str) -> list[str]:
    errors=development_errors(git(root,'branch','--show-current'))
    head=git(root,'rev-parse','HEAD')
    lines=[line.split() for line in updates.splitlines() if line.strip()]
    if not lines or any(len(line)!=4 or line[0]!='refs/heads/dev' or line[1]!=head or line[2]!='refs/heads/dev' for line in lines):
        errors.append('Only the verified current dev HEAD may be pushed to origin/dev')
    if git(root,'status','--porcelain'):
        errors.append('Commit scoped changes and archive test-owned generated output before pushing')
    try:
        receipt=json.loads(receipt_path(root).read_text(encoding='utf-8'))
        path=Path(receipt['report']).resolve()
        if not path.is_relative_to((root/'output/playwright').resolve()):raise ValueError('Unowned report')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('Changed verification report')
        errors+=report_errors(json.loads(raw),identity(root)['sha256'])
    except (OSError,ValueError,KeyError,TypeError,AttributeError):errors.append('Local verification attestation is missing, stale or invalid')
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','pre-commit','pre-push','reference-transaction','check'])
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--remote-name',default='')
    parser.add_argument('--remote-url',default='')
    parser.add_argument('--transaction-phase',choices=['preparing','prepared','committed','aborted'])
    args=parser.parse_args();root=args.root.resolve()
    errors=development_errors(git(root,'branch','--show-current'))
    if args.action=='install' and not errors:
        subprocess.run(['git','config','--local','core.hooksPath',str(ROOT/'.githooks')],cwd=root,check=True)
        subprocess.run(['git','config','--local','phdlab.verifyPython',sys.executable],cwd=root,check=True)
    elif args.action=='pre-push':
        errors=remote_errors(args.remote_name,args.remote_url)+push_errors(root,sys.stdin.read())
    elif args.action=='reference-transaction':
        updates=sys.stdin.read()
        errors=reference_errors(updates) if args.transaction_phase in ('preparing','prepared') else []
        if not errors:return 0
    print(json.dumps({'decision':'BLOCKED' if errors else 'PASS','branch':git(root,'branch','--show-current'),'errors':errors}))
    return 1 if errors else 0


if __name__=='__main__':raise SystemExit(main())
