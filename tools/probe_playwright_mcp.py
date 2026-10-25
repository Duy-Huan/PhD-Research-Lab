"""Verify installed Playwright MCP with a real localhost browser navigation."""
import argparse
import json
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://localhost:8932/mcp')
    parser.add_argument('--url', default='http://127.0.0.1:8771/dist/react.html')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    history = []
    with httpx.Client(timeout=60, headers={'Accept': 'application/json, text/event-stream'}) as client:
        def rpc(method, params, ident=None):
            body = {'jsonrpc': '2.0', 'method': method, 'params': params}
            if ident is not None:
                body['id'] = ident
            response = client.post(args.endpoint, json=body)
            response.raise_for_status()
            if response.headers.get('mcp-session-id'):
                client.headers['Mcp-Session-Id'] = response.headers['mcp-session-id']
            messages = ([json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
                        if 'text/event-stream' in response.headers.get('content-type', '')
                        else [response.json()] if response.content else [])
            history.append({'method': method, 'response': messages})
            result = next((m for m in messages if m.get('id') == ident), {})
            if result.get('error') or result.get('result', {}).get('isError'):
                raise RuntimeError(json.dumps(result))
            return result.get('result', {})
        init = rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                 'clientInfo': {'name': 'phdlab-qa', 'version': '1.0'}}, 1)
        rpc('notifications/initialized', {})
        catalog = rpc('tools/list', {}, 2)
        names = {tool['name'] for tool in catalog['tools']}
        if not {'browser_navigate', 'browser_snapshot'} <= names:
            raise RuntimeError('Required Playwright browser tools are missing')
        rpc('tools/call', {'name': 'browser_navigate', 'arguments': {'url': args.url}}, 3)
        result = rpc('tools/call', {'name': 'browser_snapshot', 'arguments': {}}, 4)
        if 'PhD Research Lab' not in json.dumps(result):
            raise RuntimeError('Real application did not render through MCP')
        rpc('tools/call', {'name': 'browser_close', 'arguments': {}}, 5)
    (args.out / 'transcript.json').write_text(json.dumps(history, indent=2), 'utf-8')
    (args.out / 'report.json').write_text(json.dumps({'mode': 'INTEGRATION', 'status': 'PASSED',
        'server': init.get('serverInfo'), 'tool_count': len(names), 'url': args.url,
        'assertions': ['MCP initialized', 'Browser tools discovered', 'Local application rendered']}, indent=2), 'utf-8')
    print('PASS: installed MCP initialized and navigated real Chromium to the isolated app')


if __name__ == '__main__':
    main()
