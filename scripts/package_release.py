"""Package a validated software commit and freshly built web assets; no deployment claims."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile


def package(root: Path, out: Path, sha: str) -> dict:
    root, out = root.resolve(), out.resolve()
    if not out.is_relative_to(root / 'output/release') or out.exists():
        raise ValueError('Use a new output/release/ directory within this checkout')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[a-f0-9]{40}', sha) or sha != head:
        raise ValueError('Release SHA must match this exact checkout')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', '.', ':(exclude)frontend/dist'], cwd=root).returncode:
        raise ValueError('Uncommitted source cannot be released under the committed SHA')
    version = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Expected a stable semantic version')
    for name in ['backend/core/config.py', 'start.py']:
        tree = ast.parse((root / name).read_text(encoding='utf-8-sig'))
        values = [n.value.value for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in n.targets)
                  and isinstance(n.value, ast.Constant)]
        if values != [version]:
            raise ValueError('Unsynchronized version: ' + name)
    dist = root / 'frontend/dist'
    if not (dist / 'index.html').is_file():
        raise ValueError('Fresh frontend build is required')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    stages = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root).decode('utf-8').split('\0')
    modes = {record.split('\t', 1)[1]: int(record.split(' ', 1)[0], 8) for record in stages if record}
    excluded = ('data/', 'projects/', 'output/', 'artifacts/', 'frontend/dist/', '.env')
    sources = [root / p for p in tracked if p and not p.startswith(excluded)]
    web = [p for p in dist.rglob('*') if p.is_file() or p.is_symlink()]
    # A compiled bundle is new/untracked until archived; include it explicitly.
    groups = {'source': (sources, root), 'web': (web, dist)}
    for files, parent in groups.values():
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(parent.resolve()) or not path.is_file():
                raise ValueError('Unsafe or missing release input: ' + str(path.relative_to(root)))
    out.mkdir(parents=True)
    assets = []
    for kind, (files, parent) in groups.items():
        path = out / f'phdlab-{version}-{kind}.zip'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(files):
                info = zipfile.ZipInfo(file.relative_to(parent).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (modes[file.relative_to(root).as_posix()] if kind == 'source' else 0o100644) << 16
                # Source bytes come from the commit, independent of checkout CRLF filters.
                data = subprocess.check_output(['git', 'show', sha + ':' + file.relative_to(root).as_posix()], cwd=root) if kind == 'source' else file.read_bytes()
                archive.writestr(info, data)
        assets.append({'name': path.name, 'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {'version': version, 'source_sha': sha, 'assets': assets,
              'scope': 'Software source and compiled web distribution; not hosted deployment or scientific certification'}
    (out / 'manifest.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = package(Path(__file__).resolve().parents[1], args.out, args.sha)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write('version=' + result['version'] + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
