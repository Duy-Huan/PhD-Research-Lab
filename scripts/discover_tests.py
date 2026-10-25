"""Report dynamic test inventory; discovery never becomes execution evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from devtools.verification.selection import select
from devtools.verification.journeys import browser_plan


def inventory(root: Path) -> dict:
    backend=select(root,[],'pr')
    browser=browser_plan(root,[],[],'pr',all_offline=True)
    unit=[p.relative_to(root/'frontend').as_posix() for p in sorted((root/'frontend/src').rglob('*.test.*'))
          if p.suffix in ('.ts','.tsx')]
    return {'status':'NOT_RUN','scope':'Static dynamic inventory, not executed PASS or generated assertions',
            'python_modules':backend['backend_tests'],'frontend_unit_files':unit,'playwright_files':browser['tests'],
            'deferred_model_suites':browser['deferred_model_tests'],
            'errors':browser['errors']+['Unpackaged Python test: '+p for p in backend['blocked_tests']]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to((ROOT/'output/playwright').resolve()):parser.error('Inventory output must be disposable output/playwright/')
    report=inventory(ROOT);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'inventory':'NOT_RUN','errors':report['errors'],'python_modules':len(report['python_modules']),
                      'frontend_unit_files':len(report['frontend_unit_files']),'offline_e2e_files':len(report['playwright_files'])}))
    return 1 if report['errors'] else 0


if __name__=='__main__':raise SystemExit(main())
