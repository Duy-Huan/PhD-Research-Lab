"""Build pinned vendor CLI runtimes without sending the application repository to Docker."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PACKAGES = {'codex': ('@openai/codex', '0.163.0'), 'gemini_cli': ('@google/gemini-cli', '0.64.0'),
            'claude_code': ('@anthropic-ai/claude-code', '2.1.304')}


def main():
    from backend.providers.isolated_cli import adapter_digest
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=sorted(PACKAGES), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    package, version = PACKAGES[args.provider]
    tag = f'phdlab-cli/{args.provider}:{version}'
    with tempfile.TemporaryDirectory(prefix='phdlab-cli-build-') as tmp:
        build = Path(tmp)
        for name in ('cli_egress_proxy.mjs', 'cli_network_forwarder.mjs'):
            shutil.copy2(ROOT / 'tools' / name, build / name)
        (build / 'Dockerfile').write_text(
            'FROM node:24-bookworm-slim\n'
            'RUN apt-get update\n'
            'RUN apt-get install -y --no-install-recommends ca-certificates\n'
            f'RUN npm install --global {package}@{version} && npm cache clean --force\n'
            'COPY cli_egress_proxy.mjs cli_network_forwarder.mjs /opt/phdlab/\n'
            f'LABEL phdlab.cli.provider="{args.provider}" phdlab.cli.version="{version}"\n'
            'WORKDIR /workspace\n', 'utf-8')
        subprocess.run(['docker', 'build', '--label', 'phdlab.cli.adapter.sha256=' + adapter_digest(), '--tag', tag, str(build)], check=True)
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', tag], text=True))[0]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({'provider': args.provider, 'package': package, 'version': version,
                                   'tag': tag, 'image_id': image['Id']}, indent=2), 'utf-8')
    print(json.dumps({'provider': args.provider, 'image_id': image['Id']}))


if __name__ == '__main__':
    main()
