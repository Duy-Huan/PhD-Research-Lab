"""REAL_E2E: actual terminal client, shared settings/locale and real local inference."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8771')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    client = httpx.Client(base_url=args.url, timeout=15)
    cfg = client.get('/api/config').raise_for_status().json()
    if not Path(cfg['project']['data_dir']).resolve().is_relative_to((ROOT / 'output/playwright').resolve()):
        raise RuntimeError('Refusing a non-disposable application profile')
    before = {s['id'] for s in client.get('/api/chat/sessions').json()['sessions']}
    commands = ['/settings', '/language en', '/help', '/settings appearance', '/language vi', '/help',
                '/language en', '/models', '/new', 'Calculate 17 times 23. Reply with the number. No tools.', '/quit']
    argv = [sys.executable, '-B', '-m', 'backend.cli', '--server', args.url]
    started = time.monotonic()
    result = subprocess.run(argv, input='\n'.join(commands)+'\n', capture_output=True, encoding='utf-8',
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, cwd=ROOT, timeout=150, check=False)
    (args.out / 'terminal.stdout.txt').write_text(result.stdout, 'utf-8')
    (args.out / 'terminal.stderr.txt').write_text(result.stderr, 'utf-8')
    sessions = [client.get(f"/api/chat/sessions/{s['id']}").json() for s in client.get('/api/chat/sessions').json()['sessions'] if s['id'] not in before]
    assertions = {
        'process_exit_zero': result.returncode == 0,
        'eight_settings_sections': all('/settings ' + key in result.stdout for key in ('models', 'research', 'search', 'experiments', 'memory', 'security', 'skills', 'appearance')),
        'english_help': '**Terminal commands:**' in result.stdout,
        'vietnamese_help': '**Lệnh terminal:**' in result.stdout,
        'shared_locale_persisted': client.get('/api/config').json()['ui']['language'] == 'en',
        'real_answer_saved': any(re.search(r'\b391\b', m.get('content', '')) for s in sessions for m in s['messages'] if m['role'] == 'assistant'),
        'turn_completed': any(s['turns'] and s['turns'][-1]['status'] == 'completed' for s in sessions),
    }
    report = {'mode': 'REAL_E2E', 'status': 'PASSED' if all(assertions.values()) else 'FAILED',
              'command': argv, 'assertions': assertions, 'elapsed_s': time.monotonic()-started,
              'model_requested': cfg.get('agent_models', {}).get('assistant'), 'sessions': sessions,
              'limitations': ['Scripted terminal input; prompt_toolkit interactive terminal rendering needs separate manual review']}
    (args.out / 'report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps({'status': report['status'], 'assertions': assertions}))
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
