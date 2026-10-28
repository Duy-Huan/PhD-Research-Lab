"""HTTP/RPC adapter for a separately managed, project-contained Hermes runtime.

Hermes is never imported in this process. Native PhD agents and CLI/API providers keep
their existing dispatch path. Docker socket/host source/PhD credentials are not mounted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from backend.providers.cli import ProviderConnector, ProviderError

IMAGE = 'phdlab-runtime/hermes:0.22.5-rpc1'
UPSTREAM = 'bf0203a794a07aac3ff764972ab9087baa4e4f4e'
PROTOCOL = 1
_lock = threading.RLock()


def adapter_digest() -> str:
    from backend.core.config import ROOT
    digest = hashlib.sha256()
    for name in ('tools/hermes_runtime/Dockerfile', 'tools/hermes_runtime/service.py',
                 'tools/hermes_runtime/proxy.mjs', 'tools/cli_egress_proxy.mjs'):
        digest.update(name.encode()); digest.update((ROOT / name).read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def docker(*args, timeout=20):
    from backend.execution.tools import NO_WINDOW
    result = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=timeout, creationflags=NO_WINDOW)
    if result.returncode: raise ProviderError('Owned Hermes Docker operation failed; inspect local runtime availability.', 'UNAVAILABLE')
    return result.stdout.strip()


def folder(profile='review') -> Path:
    from backend.core.config import data_dir, ROOT
    from backend.providers.cli_space import safe_path
    if profile not in ('review', 'assisted'): raise ProviderError('Unsupported Hermes permission profile')
    project = data_dir().resolve()
    if project == ROOT.resolve() or project in ROOT.resolve().parents:
        raise ProviderError('Hermes requires a dedicated research data project')
    value = safe_path(project, 'agent-runtimes', 'hermes', profile)
    value.mkdir(parents=True, exist_ok=True)
    if not value.resolve().is_relative_to(project) or ',' in str(value): raise ProviderError('Unsafe Hermes data mount')
    return value


def _owner(profile) -> str:
    return hashlib.sha256(str(folder(profile).resolve()).encode()).hexdigest()[:24]


# ------------------------------------------------------------------ v6.6.2 native environment
SHARED_SKILLS_IN_RUNTIME = '/opt/shared-skills'
SKILL_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
REGISTRY_TOOLS = ('phdlab_tools_search', 'phdlab_tools_describe', 'phdlab_tools_call', 'phdlab_tools_job')
LIVENESS_S = 120  # the runtime must answer at least once in this window; the job itself has no deadline


def runtime_profile() -> str:
    """The owner's profile for Hermes (tools.client_profiles.hermes): workspace_write -> writable workspace."""
    from backend.tools import profiles
    return 'assisted' if 'workspace_write' in profiles.client_grant('hermes', 'hermes').permissions else 'review'


def shared_root() -> Path:
    """App-wide Hermes data shared by every project: the Nous sign-in and the reviewed skill library."""
    from backend.core.config import GLOBAL_DIR
    root = GLOBAL_DIR / 'hermes-shared'
    for name in ('auth', 'skills'):
        (root / name).mkdir(parents=True, exist_ok=True)
    if ',' in str(root.resolve()): raise ProviderError('Unsafe Hermes shared data mount')
    return root


def link_shared_skills(home: Path) -> dict:
    """Create the project Hermes config with skills.external_dirs (Hermes' read-only skill sources). An existing
    config is never rewritten; the result says whether the shared library is linked."""
    path = home / 'config.yaml'
    if path.exists():
        return {'linked': SHARED_SKILLS_IN_RUNTIME in path.read_text('utf-8', 'replace'), 'config': str(path)}
    home.mkdir(parents=True, exist_ok=True)
    path.write_text('skills:\n  external_dirs:\n    - ' + SHARED_SKILLS_IN_RUNTIME + '\n', 'utf-8')
    return {'linked': True, 'config': str(path)}


def share_skill(name: str, approved_by: str) -> dict:
    """Copy one skill the open project's Hermes learned into the shared library after the owner reviewed it."""
    from backend.providers.cli_space import safe_path
    if not (approved_by or '').strip(): raise ProviderError('Sharing a skill needs the reviewing owner')
    if not SKILL_NAME.fullmatch(name or '') or name in ('.', '..'): raise ProviderError('Invalid skill name')
    source = safe_path(folder(runtime_profile()), 'home', 'skills', name)
    if not source.is_dir() or not (source / 'SKILL.md').is_file(): raise ProviderError('Skill not found in this project')
    target = shared_root() / 'skills' / name
    staging = target.with_name(name + '.partial-' + secrets.token_hex(4))
    shutil.copytree(source, staging, symlinks=False)
    if target.exists(): shutil.rmtree(target)
    staging.rename(target)
    record = {'skill': name, 'approved_by': approved_by.strip()[:100], 'shared': time.time(),
              'source_project': str(folder(runtime_profile()).parent.parent.parent)}
    (target / '.phdlab-share.json').write_text(json.dumps(record), 'utf-8')
    return record


def skills() -> dict:
    """Skill names in the open project's Hermes home and in the shared library (names only, no contents)."""
    def names(root: Path) -> list[str]:
        return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / 'SKILL.md').is_file()) if root.is_dir() else []
    project = names(folder(runtime_profile()) / 'home' / 'skills')
    shared = names(shared_root() / 'skills')
    return {'project': project, 'shared': shared, 'shareable': [n for n in project if n not in shared]}


def _pause_other_projects(owner: str) -> list[str]:
    """Only the open project's Hermes runs; others are stopped (never removed), keeping their memory and data."""
    paused = []
    listing = docker('ps', '--filter', 'label=phdlab.hermes.owner', '--format', '{{.ID}} {{.Label "phdlab.hermes.owner"}}')
    for line in listing.splitlines():
        cid, _, other = line.strip().partition(' ')
        if cid and other and other != owner:
            docker('stop', '--time', '10', cid, timeout=25)
            paused.append(cid)
    return paused


def _read(profile) -> dict:
    path = folder(profile) / 'runtime.json'
    return json.loads(path.read_text('utf-8')) if path.is_file() else {}


def _write(profile, plan):
    from backend.memory.store import replace_retry
    path = folder(profile) / 'runtime.json'; temporary = path.with_suffix('.partial-' + secrets.token_hex(4))
    temporary.write_text(json.dumps(plan), encoding='utf-8'); temporary.chmod(0o600)
    replace_retry(temporary, path)


def _inspect(container: str, owner: str, role: str, image: str | None = None) -> dict:
    if not re.fullmatch(r'[a-f0-9]{64}', container or ''): raise ProviderError('Invalid runtime container identity')
    value = json.loads(docker('inspect', container))[0]
    labels = value.get('Config', {}).get('Labels') or {}
    if labels.get('phdlab.hermes.owner') != owner or labels.get('phdlab.hermes.role') != role:
        raise ProviderError('Runtime ownership mismatch; no resources changed')
    if image and value.get('Image') != image: raise ProviderError('Runtime image identity changed')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def rpc(path: str, body: dict | None = None, *, profile='review', timeout=40) -> dict:
    if not re.fullmatch(r'/v1/(?:health|models|jobs(?:/[a-f0-9]{32}(?:/cancel)?)?)', path):
        raise ProviderError('Unsupported Hermes RPC path')
    plan = _read(profile); owner = _owner(profile)
    if plan.get('owner') != owner or plan.get('adapter_sha256') != adapter_digest():
        raise ProviderError('Hermes runtime is not prepared for this adapter version', 'UNAVAILABLE')
    inspect = _inspect(plan.get('proxy', ''), owner, 'proxy', plan.get('image'))
    bindings = inspect.get('NetworkSettings', {}).get('Ports', {}).get('8080/tcp') or []
    if len(bindings) != 1 or bindings[0].get('HostIp') != '127.0.0.1':
        raise ProviderError('Hermes RPC must bind exclusively to loopback')
    port = int(bindings[0]['HostPort'])
    request = urllib.request.Request(f'http://127.0.0.1:{port}' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + plan['rpc_token'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000: raise ProviderError('Hermes RPC response exceeds the explicit size limit')
        value = json.loads(raw)
        if not isinstance(value, dict): raise ProviderError('Invalid Hermes RPC response')
        return value
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read(4096))
            if not isinstance(detail, dict): raise ValueError('Invalid RPC error body')
            state = detail.get('state', 'UNAVAILABLE'); code = detail.get('error_code', '')
            if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{0,100}', code): code = ''
            message = 'Hermes requires official Nous sign-in in this project runtime.' if state == 'AUTH_REQUIRED' else 'Hermes rejected the RPC request; no automatic replay occurred.'
            raise ProviderError(message + (' [' + code + ']' if code else ''), 'AUTH_EXPIRED' if state == 'AUTH_REQUIRED' else 'UNAVAILABLE') from error
        except (ValueError, TypeError):
            raise ProviderError('Hermes RPC failed; no automatic job replay occurred.', 'UNAVAILABLE') from error
    except (OSError, ValueError, KeyError) as error:
        raise ProviderError('Hermes RPC unavailable; no fallback or automatic job replay occurred.', 'UNAVAILABLE') from error


def status(profile='review') -> dict:
    result = {'state': 'UNAVAILABLE', 'ready': False, 'protocol': PROTOCOL, 'runtime': 'hermes',
              'upstream': UPSTREAM, 'free_only': True, 'inference': 'NOT_RUN',
              'detail': 'Prepare the pinned Hermes image and start this project runtime.',
              'setup': ['python tools/prepare_hermes_runtime.py', 'python tools/manage_hermes_runtime.py start']}
    try:
        value = rpc('/v1/health', profile=profile, timeout=5)
        if value.get('protocol') != PROTOCOL or value.get('upstream') != UPSTREAM or value.get('runtime') != 'hermes':
            return {**result, 'state': 'INCOMPATIBLE', 'detail': 'Hermes RPC/library version is incompatible; explicit upgrade required.'}
        return {**result, 'state': 'READY', 'ready': True, 'authentication': 'UNKNOWN',
                'detail': 'Container runtime responds with unrestricted Internet access. Refresh models to verify Nous access; inference is separate.',
                'network': 'unrestricted-internet',
                'persistence': value.get('persistence'), 'streaming': False}
    except (ProviderError, OSError, ValueError, KeyError, subprocess.SubprocessError): return result


def start(profile=None) -> dict:
    from backend.providers.cli_space import safe_path
    profile = profile or runtime_profile()
    with _lock:
        current = status(profile)
        if current['ready']: return current
        root = folder(profile); owner = _owner(profile)
        image = json.loads(docker('image', 'inspect', IMAGE))[0]
        labels = image.get('Config', {}).get('Labels') or {}
        if (labels.get('phdlab.runtime') != 'hermes' or labels.get('phdlab.rpc.version') != str(PROTOCOL)
                or labels.get('phdlab.adapter.sha256') != adapter_digest()):
            raise ProviderError('Rebuild the pinned Hermes adapter image before starting', 'UNAVAILABLE')
        previous = _read(profile)
        if previous:
            history = root / 'lifecycle-history'; history.mkdir(exist_ok=True)
            record = {key: value for key, value in previous.items() if key != 'rpc_token'}
            record['containers'] = []
            # Stop/restart is an explicit operator action. Remove only verified owned containers.
            for role in ('runtime', 'proxy'):
                container = previous.get(role)
                if container:
                    observed = _inspect(container, owner, role)
                    record['containers'].append({'role': role, 'id': container, 'mounts': observed.get('Mounts')})
                    (history / (str(time.time_ns()) + '.json')).write_text(json.dumps(record), 'utf-8')
                    docker('rm', '-f', container)
        home = safe_path(root, 'home'); home.mkdir(exist_ok=True)
        workspace = safe_path(root, 'workspace'); workspace.mkdir(exist_ok=True)
        shared = shared_root(); link_shared_skills(home)
        _pause_other_projects(owner)
        volume = 'phdlab-hermes-ipc-' + owner
        docker('volume', 'create', '--label', 'phdlab.hermes.owner=' + owner, volume)
        token = secrets.token_hex(32)
        env_file = safe_path(root, '.rpc.env'); env_file.write_text('PHDLAB_RPC_TOKEN=' + token + '\n', 'utf-8'); env_file.chmod(0o600)
        common = ['--detach', '--restart=unless-stopped', '--read-only', '--cap-drop=ALL',
                  '--security-opt=no-new-privileges:true', '--pids-limit=128', '--cpus=1',
                  '--label', 'phdlab.hermes.owner=' + owner]
        proxy = docker('run', *common, '--memory=256m', '--user=0:0', '--tmpfs=/opt/data:rw,nosuid,noexec,size=16m',
                       '--label', 'phdlab.hermes.role=proxy',
                       '--env-file', str(env_file),
                       '--publish', '127.0.0.1::8080', '--mount', f'type=volume,source={volume},target=/ipc',
                       '--entrypoint', 'node', image['Id'], '/opt/phdlab-runtime/proxy.mjs')
        plan = {'owner': owner, 'proxy': proxy, 'image': image['Id'], 'rpc_token': token,
                'profile': profile, 'adapter_sha256': adapter_digest(), 'created': time.time()}
        _write(profile, plan)
        try:
            runtime = docker('run', *common, '--memory=2g', '--network=bridge', '--label', 'phdlab.hermes.role=runtime',
                         '--tmpfs=/tmp:rw,nosuid,noexec,size=256m', '--mount', f'type=volume,source={volume},target=/ipc',
                         '--mount', f'type=bind,source={home.resolve()},target=/opt/data',
                         # v6.6.2: one Nous sign-in for all projects (Hermes' own shared auth store) and the
                         # owner-reviewed skill library, read-only (skills.external_dirs in the project config).
                         '--mount', f"type=bind,source={(shared / 'auth').resolve()},target=/opt/shared-auth",
                         '--env', 'HERMES_SHARED_AUTH_DIR=/opt/shared-auth',
                         '--mount', f"type=bind,source={(shared / 'skills').resolve()},target={SHARED_SKILLS_IN_RUNTIME},readonly",
                         '--mount', f'type=bind,source={workspace.resolve()},target=/workspace' + (',readonly' if profile == 'review' else ''),
                         image['Id'])
            plan['runtime'] = runtime; _write(profile, plan)
            for _ in range(40):
                value = status(profile)
                if value['ready']: return value
                time.sleep(.25)
            raise ProviderError('Hermes started but did not become compatible/healthy; persistent data retained', 'UNAVAILABLE')
        except BaseException:
            # Retain launch identities and all durable data for diagnosis/restart.
            plan['start_failed'] = True; _write(profile, plan)
            raise


def stop(profile='review') -> dict:
    with _lock:
        plan = _read(profile); owner = _owner(profile)
        for role in ('runtime', 'proxy'):
            container = plan.get(role)
            if container:
                _inspect(container, owner, role); docker('stop', '--time', '10', container, timeout=25)
        return {'state': 'STOPPED', 'data_preserved': True, 'detail': 'Runtime stopped. Memory, skills, history and workspaces are retained.'}


def refresh_models(profile='review') -> dict:
    value = rpc('/v1/models', profile=profile)
    if value.get('origin') != 'live-account-catalog' or value.get('provider') != 'nous':
        raise ProviderError('Unverified Hermes model catalog')
    models = [row['id'] for row in value.get('models', []) if isinstance(row, dict) and row.get('free') is True]
    plan = _read(profile); plan['catalog'] = value; _write(profile, plan)
    return {'models': models, 'catalog': value, 'entitlement_verified': False, 'inference_verified': False, 'free_only': True}


def describe(cfg: dict | None = None) -> dict:
    from backend.core.config import load_config
    cfg = cfg or load_config(); profile = runtime_profile()
    health = status(profile); plan = _read(profile); catalog = plan.get('catalog') or {}
    models = [row['id'] for row in catalog.get('models', []) if row.get('free') is True]
    return {'id': 'runtime:hermes', 'provider_id': 'runtime:hermes', 'label': 'Hermes Agent (Nous free models)',
            'transport': 'runtime', 'state': health['state'], 'available': health['ready'] and bool(cfg.get('hermes', {}).get('enabled')),
            'detail': health['detail'], 'setup': health['setup'], 'billing': 'Free models only; no paid fallback',
            'runtime': health, 'readiness': {'installation': 'DOCKER_IMAGE', 'authentication': 'UNKNOWN',
                'isolation': health['state'], 'catalog': catalog.get('origin', 'unavailable'), 'inference': 'NOT_RUN'},
            'model_catalog': {'origin': catalog.get('origin', 'unavailable'), 'models': models, 'verified': False,
                              'queried_at': catalog.get('queried_at')},
            'capabilities': {'streaming': False, 'native_session_resume': True, 'conversation': 'persisted-history',
                'reasoning_controls': [], 'image_or_file_inputs': False, 'structured_tool_events': False,
                'usage_reporting': False, 'cancellation': True, 'model_override': True, 'models': models,
                'sandbox_options': [{'profile': p, 'level': 'os-container', 'enforced': True} for p in ('review', 'assisted')],
                'approval_options': ['phdlab'], 'mcp': 'session-scoped'}}


class HermesConnector(ProviderConnector):
    provider_id = 'hermes'
    label = 'Hermes Agent'
    supports_resume = True

    def capabilities(self):
        return {**super().capabilities(), 'connect': True, 'send': True, 'stream': False, 'cancel': True, 'mcp_client': True}

    def health(self, fresh=False):
        from backend.core.config import load_config
        value = status(runtime_profile())
        return {'provider': 'hermes', 'state': 'UNKNOWN' if value['ready'] else 'UNAVAILABLE',
                'detail': value['detail'], 'billing': 'Nous free-only, independently verified before each job'}

    def connect(self, launch=False):
        from backend.core.config import load_config
        profile = runtime_profile(); start(profile)
        plan = _read(profile)
        args = ['exec', '-it', plan['runtime'], '/opt/hermes/.venv/bin/hermes', 'auth', 'add', 'nous', '--type', 'oauth']
        result = {'action': 'official_nous_sign_in', 'command': ['docker', *args],
                  'detail': 'Complete Nous official authentication in the isolated runtime. PhD Lab does not collect your login.'}
        if launch:
            from backend.providers.native import _open_console
            result.update(_open_console(shutil.which('docker'), args, str(folder(profile))))
        return result

    def stream_message(self, message, context):
        from backend.core.config import load_config
        from backend.providers.events import ev
        cfg = load_config().get('hermes') or {}; profile = runtime_profile()  # owner's profile, not the CLI one
        if not cfg.get('enabled'): raise ProviderError('Hermes runtime is disabled', 'DISCONNECTED')
        context.setdefault('request_id', 'req-' + secrets.token_hex(6))
        jid = context.get('runtime_job_id') or secrets.token_hex(16)
        resume = str(context.get('resume_session') or '')
        session = resume if re.fullmatch(r'[a-f0-9]{32}', resume) else hashlib.sha256(str(context.get('cwd') or jid).encode()).hexdigest()[:32]
        model = str(context.get('model') or cfg.get('model') or '').strip()
        if not model: raise ProviderError('Select a currently free Nous model first')
        job = {'id': jid, 'session': session, 'model': model, 'prompt': message}
        # v6.6.2: no work budget by default; a positive value is an explicit owner limit.
        job.update({k: int(cfg[k]) for k in ('deadline_s', 'max_iterations', 'max_tokens') if int(cfg.get(k) or 0) > 0})
        if context.get('mcp_url') and context.get('mcp_token'):
            url = urlsplit(context['mcp_url'])
            if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1') or url.path != '/mcp' or url.query or url.fragment:
                raise ProviderError('Hermes tools must use the scoped local PhD Lab MCP endpoint')
            tools = sorted(set(context.get('mcp_tools') or []) | set(REGISTRY_TOOLS))  # Hermes always sees the registry
            job['mcp'] = {'port': url.port or 80, 'token': context['mcp_token'], 'tools': tools}
        # Persist correlation before POST, so a backend restart can inspect the same id without replay.
        correlation = folder(profile) / 'requests' / (jid + '.json'); correlation.parent.mkdir(exist_ok=True)
        correlation.write_text(json.dumps({'job': jid, 'session': session, 'profile': profile, 'model': model,
                                           'request_id': context.get('request_id'), 'created': time.time()}), 'utf-8')
        request_key = hashlib.sha256(context['request_id'].encode()).hexdigest()
        (correlation.parent / ('request-' + request_key + '.json')).write_text(
            json.dumps({'job': jid, 'profile': profile, 'request_id': context['request_id']}), 'utf-8')
        value = rpc('/v1/jobs', job, profile=profile)
        yield ev('status', state='session', session_id=session, runtime_job_id=jid, model=model)
        yield ev('request_started', provider='hermes', runtime_job_id=jid)
        # No observation deadline: Hermes works as long as it needs. Only a runtime that stops answering for
        # LIVENESS_S is an error (the durable job is kept for inspection; nothing is replayed).
        last_seen = time.monotonic()
        while value.get('status') == 'running':
            if context.get('_cancel') and context['_cancel'].is_set():
                rpc('/v1/jobs/' + jid + '/cancel', {}, profile=profile)
                yield ev('request_cancelled', runtime_job_id=jid); return
            time.sleep(.25)
            try:
                value = rpc('/v1/jobs/' + jid, profile=profile); last_seen = time.monotonic()
            except ProviderError:
                if time.monotonic() - last_seen > LIVENESS_S:
                    raise ProviderError('Hermes runtime is not responding; the durable job is retained for inspection')
        if value.get('status') != 'completed':
            raise ProviderError(value.get('error') or 'Hermes job did not complete; no automatic replay occurred')
        yield ev('text_delta', text=value['answer'], final=True)
        yield ev('status', state='result', final_text=value['answer'], usage=value.get('usage'), model=model, runtime_job_id=jid)
        yield ev('request_completed', exit_code=0, runtime_job_id=jid)

    def cancel(self, request_id: str) -> dict:
        from backend.core.config import load_config
        key = hashlib.sha256(request_id.encode()).hexdigest()
        configured = runtime_profile()
        for profile in (configured, 'assisted' if configured == 'review' else 'review'):
            path = folder(profile) / 'requests' / ('request-' + key + '.json')
            if path.is_file():
                entry = json.loads(path.read_text('utf-8'))
                if entry.get('request_id') != request_id or entry.get('profile') != profile:
                    raise ProviderError('Hermes cancellation identity mismatch')
                job = rpc('/v1/jobs/' + entry['job'] + '/cancel', {}, profile=profile)
                return {'provider': 'hermes', 'cancelled': job.get('status') == 'cancelled', 'runtime_job_id': entry['job']}
        return {'provider': 'hermes', 'cancelled': False, 'detail': 'No request in the current project; no other runtime was affected.'}
