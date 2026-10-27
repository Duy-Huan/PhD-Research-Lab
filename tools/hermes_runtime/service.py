"""Versioned local RPC around the official Hermes Python library, inside Docker only.

One container/home per paper and permission profile. Jobs and conversation history are
durable; a backend disconnect does not terminate a job or replay it. Interrupted runtime
jobs are reported, never silently re-executed. No PhD Lab modules are imported here.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
import http.server
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request

PROTOCOL = 1
UPSTREAM = 'bf0203a794a07aac3ff764972ab9087baa4e4f4e'
AGENT_HASH = '33c7195fc6efa9122f1a6700d416fd283f9634712189af3fd72feb01bcea054f'
HOME = Path(os.environ.get('HERMES_HOME', '/opt/data'))
STATE = HOME / 'phdlab'
LOCK = threading.RLock()
ACTIVE: dict = {}
ID = re.compile(r'^[a-f0-9]{32}$')


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.partial-' + os.urandom(4).hex())
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def job_path(jid: str) -> Path:
    if not ID.fullmatch(jid): raise ValueError('Invalid job identity')
    return STATE / 'jobs' / (jid + '.json')


def read_job(jid: str) -> dict:
    return load(job_path(jid))


def public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in ('prompt', 'tools', 'conversation_history')}


def error_code(error: Exception) -> str:
    value = str(getattr(error, 'code', '') or type(error).__name__)
    return value if re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', value) else type(error).__name__


def connect_proxy(client):
    remote = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        remote.connect('/ipc/egress.sock')
        def copy(source, destination):
            try:
                while chunk := source.recv(65536): destination.sendall(chunk)
            except OSError: pass
            finally:
                try: destination.shutdown(socket.SHUT_RDWR)
                except OSError: pass
        other = threading.Thread(target=copy, args=(client, remote), daemon=True)
        other.start(); copy(remote, client); other.join(timeout=1)
    finally: remote.close(); client.close()


def start_proxy():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 3128)); server.listen(16)
    def accept():
        while True:
            client, _ = server.accept()
            threading.Thread(target=connect_proxy, args=(client,), daemon=True).start()
    threading.Thread(target=accept, daemon=True).start()
    # Owner2026-10-26 explicitly grants direct unrestricted Internet to Hermes.
    # This local listener is used ONLY by the separately scoped native-tool bridge.
    # Do not install proxy environment variables or domain restrictions on model/web traffic.


def nous_credentials() -> dict:
    """Resolve official sign-in inside this home; never return it through RPC."""
    from hermes_cli.auth import resolve_nous_runtime_credentials
    from urllib.parse import urlsplit
    from hermes_cli.anon_challenge import background_caller
    with background_caller():
        credentials = resolve_nous_runtime_credentials(timeout_seconds=15)
    base = credentials.get('base_url', '').rstrip('/')
    target = urlsplit(base)
    if (target.scheme != 'https' or target.hostname != 'inference-api.nousresearch.com'
            or target.port not in (None, 443) or target.username or target.password or target.query or target.fragment):
        raise ValueError('Only the official Nous inference service is authorized')
    return credentials


def catalog() -> dict:
    # Catalog lookup may refresh Nous sign-in; it never invokes a model.
    credentials = nous_credentials()
    base = credentials['base_url'].rstrip('/')
    request = urllib.request.Request(base + '/models', headers={'Authorization': 'Bearer ' + credentials['api_key']})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000: raise ValueError('Model catalog exceeds limit')
    rows = json.loads(raw).get('data')
    if not isinstance(rows, list): raise ValueError('Nous returned an invalid catalog')
    result = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str): continue
        pricing = row.get('pricing') if isinstance(row.get('pricing'), dict) else {}
        # Missing prices, discounts rounded to zero and a suggestive name are NOT free evidence.
        free = False
        try:
            raw_prices = [pricing[k] for k in ('prompt', 'completion')]
            if any(type(p) not in (str, int, float) for p in raw_prices): raise ValueError('Invalid price')
            prices = [Decimal(str(p)) for p in raw_prices]
            free = all(p.is_finite() and p == 0 for p in prices)
        except (KeyError, TypeError, ValueError, InvalidOperation): pass
        result.append({'id': row['id'], 'free': free, 'pricing': {k: pricing.get(k) for k in ('prompt', 'completion')}})
    value = {'protocol': PROTOCOL, 'provider': 'nous', 'origin': 'live-account-catalog',
             'queried_at': time.time(), 'inference_verified': False, 'models': result}
    save(STATE / 'catalog.json', value)
    return value


def mcp(job: dict, method: str, params: dict) -> dict:
    import http.client
    connection = http.client.HTTPConnection('127.0.0.1', 3128, timeout=30)
    try:
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
        connection.request('POST', '/mcp', body, {'Content-Type': 'application/json', 'X-Phdlab-Job': job['id']})
        response = connection.getresponse(); raw = response.read(2_000_001)
        if response.status != 200 or len(raw) > 2_000_000: raise ValueError('Scoped PhD Lab tools are unavailable')
        value = json.loads(raw)
        if value.get('error'): raise ValueError('PhD Lab rejected the tool request')
        return value.get('result') or {}
    finally: connection.close()


def register_tools(job: dict):
    if not job.get('tools'): return
    from tools.registry import registry
    from toolsets import TOOLSETS
    allowed = set(job['tools'])
    result = mcp(job, 'tools/list', {})
    for tool in result.get('tools', []):
        name = tool.get('name')
        if name not in allowed: continue
        def execute(args, _name=name, **kwargs):
            # The native server independently enforces scope, approval and project identity.
            return json.dumps(mcp(job, 'tools/call', {'name': _name, 'arguments': args}), ensure_ascii=False)
        registry.register(name='phdlab_' + name, toolset='phdlab',
                          schema={'name': 'phdlab_' + name, 'description': tool.get('description', ''),
                                  'parameters': tool.get('inputSchema') or {'type': 'object', 'properties': {}}}, handler=execute)
    TOOLSETS['phdlab'] = {'description': 'Project-scoped native PhD Lab tools; original approval rules apply',
                         'tools': registry.get_tool_names_for_toolset('phdlab'), 'includes': []}


def run_agent(jid: str):
    job = read_job(jid)
    if job.get('status') != 'running': return
    try:
        actual = hashlib.sha256(Path('/opt/hermes/run_agent.py').read_bytes()).hexdigest()
        if actual != AGENT_HASH: raise ValueError('Pinned Hermes library compatibility check failed')
        available = catalog()
        if not any(row['id'] == job['model'] and row['free'] for row in available['models']):
            raise ValueError('Selected model is not currently verified free in the live Nous catalog')
        # The adapter writes a minimal isolated configuration: no auxiliary/fallback paid models.
        # Persistent Hermes memory, skills and auth files are otherwise retained across restarts.
        from run_agent import AIAgent
        register_tools(job)
        history_path = STATE / 'sessions' / (job['session'] + '.json')
        history = load(history_path).get('messages', []) if history_path.exists() else []
        if len(json.dumps(history).encode()) > 4_000_000:
            raise ValueError('Session history exceeds the explicit RPC budget; archive/review it before continuing')
        credentials = nous_credentials()
        if read_job(jid).get('status') != 'running': return
        agent = AIAgent(provider='nous', requested_provider='nous', api_key=credentials['api_key'],
                        base_url=credentials['base_url'], model=job['model'], quiet_mode=True,
                        enabled_toolsets=['memory', 'skills', 'web'] + (['phdlab'] if job.get('tools') else []),
                        skip_context_files=True, skip_background_review=True, skip_memory=False,
                        max_iterations=job['max_iterations'], run_budget_seconds=job['deadline_s'],
                        fallback_model={}, session_id=job['session'], cwd='/workspace', max_tokens=job['max_tokens'])
        result = agent.run_conversation(user_message=job['prompt'], conversation_history=history, task_id=jid)
        text = result.get('final_response')
        if not isinstance(text, str) or not text.strip(): raise ValueError('Hermes returned no final response')
        if result.get('error') or result.get('interrupted'): raise ValueError('Hermes did not complete the conversation')
        messages = result.get('messages')
        if not isinstance(messages, list): raise ValueError('Hermes returned no recoverable conversation history')
        save(history_path, {'messages': messages, 'last_job': jid, 'model': job['model'], 'updated': time.time()})
        # Usage remains unknown unless the pinned runtime actually supplies it.
        job.update(status='completed', answer=text, usage=result.get('usage') if isinstance(result.get('usage'), dict) else None,
                   ended=time.time(), history_messages=len(messages))
    except Exception as error:
        # Never persist an arbitrary vendor exception: it can contain keys/URLs or secret file contents.
        job.update(status='failed', error_code=error_code(error),
                   error='Hermes runtime could not complete this job; check sign-in, free-model catalog and scoped tools.', ended=time.time())
    save(job_path(jid), job)


def supervise(job: dict):
    jid = job['id']
    log = STATE / 'jobs' / (jid + '.log')
    with log.open('wb') as output:
        with LOCK:
            if read_job(jid).get('status') != 'running':
                ACTIVE.pop(jid, None)
                return
            process = subprocess.Popen([sys.executable, __file__, '--worker', jid], stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            ACTIVE[jid] = process
        try: process.wait(timeout=job['deadline_s'] + 15)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
            value = read_job(jid); value.update(status='failed', error='Hermes exceeded its execution deadline', ended=time.time())
            save(job_path(jid), value)
        finally:
            ACTIVE.pop(jid, None)
            value = read_job(jid)
            if value['status'] == 'running':
                value.update(status='failed', error='Hermes worker exited without a final result', ended=time.time())
                save(job_path(jid), value)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def reply(self, status, value):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        try:
            if self.path == '/v1/health':
                return self.reply(200, {'protocol': PROTOCOL, 'runtime': 'hermes', 'upstream': UPSTREAM,
                                      'library_sha256': AGENT_HASH, 'state': 'READY', 'free_only': True,
                                      'persistence': 'project-home-and-explicit-conversation-history', 'streaming': False,
                                      'network': 'unrestricted-internet'})
            if self.path == '/v1/models': return self.reply(200, catalog())
            if self.path.startswith('/v1/jobs/'): return self.reply(200, public_job(read_job(self.path.split('/')[-1])))
            return self.reply(404, {'state': 'NOT_FOUND'})
        except FileNotFoundError: return self.reply(404, {'state': 'NOT_FOUND'})
        except Exception as error:
            code = error_code(error)
            state = 'AUTH_REQUIRED' if code.startswith('nous_auth') else 'UNAVAILABLE'
            return self.reply(503, {'state': state, 'error_code': code,
                                    'detail': 'Complete official Nous sign-in in this project runtime; model access and free pricing are checked separately.'
                                              if state == 'AUTH_REQUIRED' else 'Runtime catalog or job unavailable; no inference was verified.'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 1_048_576: raise ValueError('RPC body exceeds budget')
            data = json.loads(self.rfile.read(length) or '{}')
            if not isinstance(data, dict): raise ValueError('RPC body must be an object')
            if re.fullmatch(r'/v1/jobs/[a-f0-9]{32}/cancel', self.path):
                jid = self.path.split('/')[-2]
                with LOCK:
                    job = read_job(jid); process = ACTIVE.get(jid)
                    if process and process.poll() is None:
                        import signal
                        os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
                    if job['status'] == 'running':
                        job.update(status='cancelled', ended=time.time()); save(job_path(jid), job)
                return self.reply(200, public_job(job))
            if self.path != '/v1/jobs': return self.reply(404, {'state': 'NOT_FOUND'})
            if set(data) - {'id', 'session', 'model', 'prompt', 'tools', 'deadline_s', 'max_iterations', 'max_tokens'}:
                raise ValueError('Unsupported RPC fields')
            jid = data['id']; path = job_path(jid)
            if not ID.fullmatch(data['session']): raise ValueError('Invalid session')
            if not isinstance(data['prompt'], str) or not data['prompt'].strip(): raise ValueError('Empty prompt')
            if not isinstance(data['model'], str) or not re.fullmatch(r'[\w.:/@+-]{1,160}', data['model']): raise ValueError('Invalid model')
            for name, low, high in (('deadline_s', 5, 1800), ('max_iterations', 1, 50), ('max_tokens', 128, 16384)):
                if type(data.get(name)) is not int or not low <= data[name] <= high: raise ValueError('Invalid execution budget')
            tools = data.get('tools') or []
            if not isinstance(tools, list) or len(tools) > 64 or any(not isinstance(t, str) or not re.fullmatch(r'[\w.-]{1,100}', t) for t in tools):
                raise ValueError('Invalid tool grant')
            with LOCK:
                if path.exists():
                    previous = read_job(jid)
                    if any(previous.get(k) != data.get(k) for k in ('prompt', 'session', 'model', 'tools', 'deadline_s', 'max_iterations', 'max_tokens')):
                        return self.reply(409, {'state': 'IDEMPOTENCY_CONFLICT'})
                    return self.reply(200, public_job(previous))
                if ACTIVE: return self.reply(409, {'state': 'BUSY', 'detail': 'One job at a time protects persistent memory/skills'})
                data.update(status='running', created=time.time(), protocol=PROTOCOL)
                save(path, data)
                ACTIVE[jid] = None
                threading.Thread(target=supervise, args=(data,), daemon=True).start()
            return self.reply(202, public_job(data))
        except (ValueError, TypeError, KeyError): return self.reply(400, {'state': 'INVALID_REQUEST'})
        except FileNotFoundError: return self.reply(404, {'state': 'NOT_FOUND'})


def main():
    if not hasattr(socketserver, 'UnixStreamServer'):
        raise RuntimeError('Hermes RPC service requires its Linux Docker runtime; host execution is unsupported')
    class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True
    STATE.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker': return run_agent(sys.argv[2])
    # A runtime restart is distinguishable from a backend restart. Never auto-replay model calls.
    for path in (STATE / 'jobs').glob('*.json'):
        value = load(path)
        if value.get('status') == 'running':
            value.update(status='interrupted', ended=time.time(), error='Runtime restarted; resume with an explicit new job')
            save(path, value)
    start_proxy()
    actual = hashlib.sha256(Path('/opt/hermes/run_agent.py').read_bytes()).hexdigest()
    if actual != AGENT_HASH: raise ValueError('Pinned Hermes library compatibility check failed')
    path = Path('/ipc/hermes/rpc.sock')
    for _ in range(40):
        if path.parent.is_dir(): break
        time.sleep(.1)
    path.unlink(missing_ok=True)
    with Server(str(path), Handler) as server:
        path.chmod(0o666); server.serve_forever()


if __name__ == '__main__': main()
