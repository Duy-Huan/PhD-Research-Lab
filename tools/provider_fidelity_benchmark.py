"""Bounded native-vs-HTTP-wrapped local-provider evaluation with deterministic oracles."""
import argparse
import json
import re
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8771')
    parser.add_argument('--model', default='spark-x2.5-4b')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=2, choices=range(1, 4))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    client = httpx.Client(timeout=100)
    cfg = client.get(args.url + '/api/config').raise_for_status().json()
    if 'output' not in Path(cfg['project']['data_dir']).parts:
        raise RuntimeError('Refusing to benchmark against non-disposable state')
    cases = [('arithmetic', 'Return just the result of 13 plus 29. Do not use any tools.', r'^\s*42\s*[.!]?\s*$'),
             ('supplied-value', 'Synthetic fixture input: power=0.125 mW. Repeat only the numeric value. No tools.', r'^\s*0\.125\s*[.!]?\s*$'),
             ('missing-measurement', 'No experiment has been executed and no accuracy has been measured. Reply UNKNOWN. No tools.', r'\bUNKNOWN\b')]
    rows = []
    for repeat in range(args.repeats):
        for case, question, oracle in cases:
            for path in ('native', 'wrapped'):
                start = time.monotonic()
                row = {'id': f'{case}-{repeat}-{path}', 'case': case, 'repeat': repeat, 'path': path, 'model_requested': args.model}
                try:
                    if path == 'native':
                        response = client.post('http://127.0.0.1:1234/v1/chat/completions', json={
                            'model': args.model, 'messages': [{'role': 'system', 'content': 'Answer the user directly. Do not invent measurements.'}, {'role': 'user', 'content': question}],
                            'max_tokens': 6000, 'temperature': 0.3}).raise_for_status().json()
                        row.update(text=response['choices'][0]['message']['content'], model_returned=response.get('model'), usage=response.get('usage'), cost=None)
                        if response.get('model') != args.model:
                            raise RuntimeError('Native response model differs from the requested model')
                    else:
                        session = client.post(args.url + '/api/chat/sessions', json={'title': row['id'],
                            'settings': {'provider': 'app:local', 'model': args.model, 'context_mode': 'none', 'mcp_auto': False, 'reasoning': 'auto'}}).raise_for_status().json()
                        turn = client.post(args.url + f"/api/chat/sessions/{session['id']}/turns", json={'text': question}).raise_for_status().json()
                        deadline = time.monotonic()+100
                        while time.monotonic() < deadline:
                            saved = client.get(args.url + f"/api/chat/sessions/{session['id']}").raise_for_status().json()
                            actual = next(t for t in saved['turns'] if t['id'] == turn['id'])
                            if actual['status'] not in ('queued', 'running'):
                                break
                            time.sleep(0.1)
                        else:
                            client.post(args.url + f"/api/chat/sessions/{session['id']}/cancel")
                            raise TimeoutError('Wrapped inference exceeded the benchmark deadline')
                        if actual['status'] != 'completed' or actual.get('error'):
                            raise RuntimeError(json.dumps(actual))
                        row.update(text=saved['messages'][-1]['content'], model_returned=None, usage=None, cost=None,
                                   session_id=session['id'], manifest=actual['manifest'])
                    row['passed'] = bool(re.search(oracle, row['text'], re.IGNORECASE))
                    row['status'] = 'PASSED' if row['passed'] else 'FAILED'
                except Exception as exc:  # noqa: BLE001 - preserve each unexpected live failure as ERROR evidence
                    row.update(passed=False, status='ERROR', error=f'{type(exc).__name__}: {exc}')
                row['elapsed_s'] = time.monotonic()-start
                rows.append(row)
                (args.out / 'rows.json').write_text(json.dumps(rows, indent=2), 'utf-8')
    summary = {path: {'passed': sum(r['passed'] for r in rows if r['path'] == path),
                      'executed': sum(r['path'] == path for r in rows)} for path in ('native', 'wrapped')}
    report = {'model': args.model, 'rows': rows, 'summary': summary, 'status': 'PASSED' if all(r['passed'] for r in rows) else 'FAILED',
              'limitations': ['Three deterministic tasks; no general provider intelligence parity certification',
                  'Native minimal system prompt differs from application instructions by design',
                  'Wrapped API does not expose authoritative provider-returned model ID or token usage; those fields stay unknown',
                  'Small repeated sample is insufficient for sustained reliability or subjective scientific-quality conclusions']}
    (args.out / 'report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps({'status': report['status'], 'summary': summary}))
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
