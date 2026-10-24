"""Real chat HTTP -> gateway -> signed-in CLI -> SSE -> persisted answer smoke test."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8765')
    parser.add_argument('--out', required=True)
    parser.add_argument('--provider', choices=['codex', 'antigravity'], default='codex')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.base, headers={'X-PhDLab-Client': 'ui'}, timeout=120) as client:
        settings = {'provider': 'cli:' + args.provider, 'model': 'gpt-5' if args.provider == 'codex' else '',
                    'memory_mode': 'off', 'context_mode': 'none', 'mcp_tools': ['-'], 'mcp_auto': False,
                    'summaries': False, 'collect_artifacts': False, 'operating_mode': 'automation'}
        response = client.post('/api/chat/sessions', json={'title': 'QA real CLI connectivity ' + args.provider,
                                                          'settings': settings})
        response.raise_for_status()
        session = response.json()
        sid = session['id']
        start = time.monotonic()
        response = client.post(f'/api/chat/sessions/{sid}/turns', json={
            'text': 'Reply with the single word OK. Do not read files, use tools, or modify anything.',
            'overrides': {'provider': 'cli:' + args.provider, 'model': ''}})
        response.raise_for_status()
        turn = response.json()
        events = []
        with client.stream('GET', f'/api/chat/sessions/{sid}/stream', params={'timeout': 110}) as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if not line.startswith('data: '):
                    continue
                event = json.loads(line[6:])
                events.append(event)
                if event['type'] in ('turn.completed', 'turn.failed', 'turn.cancelled', 'stream.timeout'):
                    break
        response = client.get(f'/api/chat/sessions/{sid}')
        response.raise_for_status()
        final = response.json()
        actual = next(t for t in final['turns'] if t['id'] == turn['id'])
        answer = next((m['content'] for m in final['messages'] if m['role'] == 'assistant' and m['turn_id'] == turn['id']), '')
        deltas = ''.join(e['data'].get('text', '') for e in events if e['type'] == 'message.delta')
        passed = actual['status'] == 'completed' and answer.strip() == 'OK' and deltas.strip() == 'OK'
        report = {'passed': passed, 'real_cli': True, 'provider': args.provider, 'session_id': sid,
                  'turn_id': turn['id'], 'status': actual['status'], 'error': actual.get('error'),
                  'answer': answer, 'sse_answer': deltas, 'events': events,
                  'elapsed_s': round(time.monotonic() - start, 3)}
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        client.put(f'/api/chat/sessions/{sid}', json={'archived': True}).raise_for_status()
        print(json.dumps({k: v for k, v in report.items() if k != 'events'}))
        return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
