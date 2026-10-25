"""Load only the pinned, hash-verified official standard-library SDK for CI tests."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

COMMIT = 'd720862157d146d52b6faae1e5aff9d3973ed918'
DIGEST = '3dd47393f571cf124fcc0d69d3c2f5fc514cbe56121fecc80f9b6fa3d2a45c72'
URL = 'https://codeload.github.com/synthetic-sciences/openscience/tar.gz/' + COMMIT
PREFIX = 'openscience-' + COMMIT + '/tooling/sdk/python/openscience/'


def unpack(raw: bytes, out: Path, expected: str = DIGEST, prefix: str = PREFIX) -> dict:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Official SDK archive digest mismatch')
    if out.exists():
        raise ValueError('Use a fresh SDK output directory; never overwrite unknown files')
    selected = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for count, member in enumerate(archive):
            path = PurePosixPath(member.name)
            if count >= 50000 or path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('Unsafe or oversized archive inventory')
            if not member.name.startswith(prefix):
                continue
            relative = PurePosixPath('openscience') / member.name[len(prefix):]
            if member.isdir():
                continue
            if not member.isfile() or member.size > 1_000_000 or relative.as_posix() in selected:
                raise ValueError('Unsafe/duplicate SDK input')
            if relative.suffix != '.py':
                continue
            selected[relative.as_posix()] = archive.extractfile(member).read()
    if set(selected) != {'openscience/__init__.py', 'openscience/client.py'}:
        raise ValueError('Pinned SDK inventory differs from reviewed source')
    out.mkdir(parents=True)
    for name, data in selected.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report = {'commit': COMMIT, 'archive_sha256': expected, 'url': URL,
              'mode':'ACTUAL_OFFICIAL_SDK_SOURCE',
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in selected.items()},
              'license':'Apache-2.0; upstream license retained at pinned repository URL',
              'scope':'SDK socket regression only; no runtime/model or scientific qualification'}
    (out/'provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--archive', type=Path, help='Optional local cache; identical mandatory digest')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.out.resolve()
    if not out.is_relative_to((root/'output/playwright').resolve()):
        parser.error('SDK output must be inside disposable output/playwright/')
    if args.archive:
        if args.archive.stat().st_size > 50_000_000: raise ValueError('Archive download bound exceeded')
        raw = args.archive.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=60) as response: raw=response.read(50_000_001)
    if len(raw)>50_000_000: raise ValueError('Archive download bound exceeded')
    print(json.dumps(unpack(raw,out)))


if __name__ == '__main__': main()
