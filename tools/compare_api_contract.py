"""Compare current OpenAPI operations and schemas with a supplied baseline."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
METHODS = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'trace'}


def compare(before: dict, after: dict) -> dict:
    def structural(value):
        if isinstance(value, dict):
            return {k: structural(v) for k, v in value.items() if k not in {'description', 'summary'}}
        if isinstance(value, list):
            return [structural(v) for v in value]
        return value
    def operations(document):
        return {(method, path): operation for path, methods in document['paths'].items()
                for method, operation in methods.items() if method in METHODS}
    old, new = operations(before), operations(after)
    changed = [f'{m.upper()} {p}' for m, p in sorted(old.keys() & new.keys()) if structural(old[m, p]) != structural(new[m, p])]
    docs = [f'{m.upper()} {p}' for m, p in sorted(old.keys() & new.keys())
            if old[m, p] != new[m, p] and structural(old[m, p]) == structural(new[m, p])]
    removed = [f'{m.upper()} {p}' for m, p in sorted(old.keys() - new.keys())]
    added = [f'{m.upper()} {p}' for m, p in sorted(new.keys() - old.keys())]
    old_schemas = before.get('components', {}).get('schemas', {})
    new_schemas = after.get('components', {}).get('schemas', {})
    changed_schemas = [name for name in sorted(old_schemas) if old_schemas[name] != new_schemas.get(name)]
    return {'baseline_operations': len(old), 'current_operations': len(new), 'removed': removed,
            'changed': changed, 'added': added, 'changed_or_removed_schemas': changed_schemas,
            'documentation_only_changes': docs,
            'compatible_snapshot': not (removed or changed or changed_schemas),
            'limitations': ['Static OpenAPI comparison does not prove every runtime JSON/SSE response compatible']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'artifacts/backend-qa/openapi_snapshot.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='phdlab-openapi-') as data:
        os.environ['PHDLAB_DATA_DIR'] = data
        from backend.app import app
        current = app.openapi()
        result = compare(json.loads(args.baseline.read_text('utf-8')), current)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), 'utf-8')
    args.out.with_name('openapi-current.json').write_text(json.dumps(current, indent=2), 'utf-8')
    print(json.dumps(result))
    return 0 if result['compatible_snapshot'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
