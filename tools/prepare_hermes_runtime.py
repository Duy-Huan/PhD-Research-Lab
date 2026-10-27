"""Build a pinned Hermes adapter from a minimal context, never application source/data."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from backend.providers.hermes import IMAGE, adapter_digest
    with tempfile.TemporaryDirectory(prefix='phdlab-hermes-build-') as temporary:
        folder = Path(temporary)
        for name in ('Dockerfile', 'service.py', 'proxy.mjs'):
            shutil.copy2(ROOT / 'tools/hermes_runtime' / name, folder / name)
        shutil.copy2(ROOT / 'tools/cli_egress_proxy.mjs', folder / 'cli_egress_proxy.mjs')
        subprocess.run(['docker', 'build', '--label', 'phdlab.adapter.sha256=' + adapter_digest(), '--tag', IMAGE, str(folder)], check=True)
    print(json.dumps({'image': IMAGE, 'adapter_sha256': adapter_digest(), 'scope': 'Build only; no model or sign-in invoked'}))


if __name__ == '__main__': main()
