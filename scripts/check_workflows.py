"""Run pinned official actionlint, verifying the binary before executing it."""
from __future__ import annotations
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.7.12'
ARCHIVES={'nt':('windows_amd64.zip','6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9'),
          'posix':('linux_amd64.tar.gz','8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8')}


def main() -> int:
    suffix,expected=ARCHIVES[os.name]
    name=f'actionlint_{VERSION}_{suffix}'
    request=urllib.request.Request(f'https://github.com/rhysd/actionlint/releases/download/v{VERSION}/{name}',headers={'User-Agent':'phdlab-workflow-validation'})
    with urllib.request.urlopen(request,timeout=60) as response: data=response.read(20_000_001)
    if len(data)>20_000_000 or hashlib.sha256(data).hexdigest()!=expected:
        raise RuntimeError('actionlint download size/digest verification failed')
    folder=ROOT/'output/playwright/ci-tools/actionlint';folder.mkdir(parents=True,exist_ok=True)
    exe=folder/('actionlint.exe' if os.name=='nt' else 'actionlint')
    if os.name=='nt':
        with zipfile.ZipFile(io.BytesIO(data)) as archive: exe.write_bytes(archive.read('actionlint.exe'))
    else:
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
            stream=archive.extractfile('actionlint')
            if stream is None: raise RuntimeError('actionlint executable absent')
            exe.write_bytes(stream.read());exe.chmod(0o755)
    return subprocess.run([str(exe),'-shellcheck=','-pyflakes='],cwd=ROOT).returncode


if __name__=='__main__':raise SystemExit(main())
