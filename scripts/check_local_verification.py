"""CI independently checks the actual complete local software execution receipt."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.branch_policy import receipt_path,report_errors
from devtools.verification.runner import identity


def load_report(root: Path, report: Path | None = None) -> tuple[dict,list[str]]:
    try:
        if report is None:
            receipt=json.loads(receipt_path(root).read_text(encoding='utf-8'))
            report=Path(receipt['report']).resolve()
            if not report.is_relative_to((root/'output/playwright').resolve()):raise ValueError('Unowned local execution report')
            raw=report.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('Changed local receipt')
        else:
            report=report.resolve()
            if not report.is_relative_to(root.resolve()):raise ValueError('Report outside repository')
            raw=report.read_bytes()
        data=json.loads(raw)
        return data,report_errors(data,identity(root)['sha256'])
    except (OSError,ValueError,KeyError,TypeError,AttributeError,subprocess.SubprocessError) as exc:
        return {},['Missing, malformed or stale complete local execution evidence: '+type(exc).__name__]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'docs/qa/evidence/local-verification/report.json')
    args=parser.parse_args();report,errors=load_report(ROOT,args.report)
    print(json.dumps({'decision':'BLOCKED' if errors else 'PASS','errors':errors,
                      'source_sha256':report.get('source',{}).get('sha256'),'counts':report.get('counts'),
                      'scope':'Source-bound complete local software report, plus independent CI regression required'}))
    return 2 if errors else 0


if __name__=='__main__':raise SystemExit(main())
