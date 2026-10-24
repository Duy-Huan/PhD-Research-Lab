"""Keep backend, npm package/lock and README release metadata synchronized."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='Semantic version MAJOR.MINOR.PATCH')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        parser.error('Expected MAJOR.MINOR.PATCH')
    updates = {}
    path = ROOT / 'backend/core/config.py'
    updates[path] = re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{args.version}"', path.read_text('utf-8'))
    for filename in ('package.json', 'package-lock.json'):
        path = ROOT / 'frontend' / filename
        obj = json.loads(path.read_text('utf-8'))
        obj['version'] = args.version
        if filename == 'package-lock.json':
            obj['packages']['']['version'] = args.version
        updates[path] = json.dumps(obj, indent=2) + '\n'
    path = ROOT / 'README.md'
    updates[path] = re.sub(r'^# PhD Research Lab - v[^\n]+', f'# PhD Research Lab - v{args.version}', path.read_text('utf-8'))
    different = [p for p, text in updates.items() if p.read_text('utf-8') != text]
    if args.check:
        for path in different:
            print('VERSION_METADATA_DRIFT: ' + str(path.relative_to(ROOT)))
        return 1 if different else 0
    for path, text in updates.items():
        path.write_text(text, 'utf-8')
    print('Version synchronized: ' + args.version)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
