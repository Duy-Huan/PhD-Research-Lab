"""Non-generating cloud connection preparation when a model selection is saved."""
from __future__ import annotations

import asyncio
import hashlib
import threading
import time

import httpx

from backend.core.config import PROVIDERS, load_config

_lock = threading.Lock()
_states: dict = {}
_tasks: dict = {}


def status() -> list[dict]:
    with _lock:
        return [{k: v for k, v in item.items() if k != 'identity'} for item in _states.values()]


async def _prepare(cfg: dict, pid: str, model: str, identity: str):
    from backend.providers import lifecycle as LC
    from backend.providers.models import (
        ANTHROPIC_VERSION,
        gateway_headers,
        provider_settings,
    )
    spec, key, _, base = provider_settings(cfg, pid)
    headers = gateway_headers(pid)
    headers.update({'x-api-key': key, 'anthropic-version': ANTHROPIC_VERSION} if spec['kind'] == 'anthropic'
                   else {'Authorization': f'Bearer {key}'} if key else {})
    state, code, listed = 'error', None, None
    try:
        async with LC.http_client(httpx.Timeout(10, connect=5)) as client:
            response = await client.get(base + '/models', headers=headers, timeout=10,
                                        params={'limit': 200} if spec['kind'] == 'anthropic' else None)
        code = response.status_code
        if code == 200:
            payload = response.json()
            items = payload.get('data', payload.get('models', [])) if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                raise ValueError('Unexpected models response')
            ids = {(x.get('id') or x.get('name') or '') if isinstance(x, dict) else x for x in items if isinstance(x, (dict, str))}
            listed = model in ids or 'models/' + model in ids
            state = 'connected' if listed else 'model_unconfirmed'
        elif code in (401, 403):
            state = 'auth_required'
        elif code == 429:
            state = 'rate_limited'
        elif code in (404, 405):
            state = 'reachable'  # Transport is warm, model/auth not proved by an unsupported list endpoint.
    except (httpx.HTTPError, ValueError):
        state = 'error'  # Never expose credential-bearing request URLs or vendor error bodies.
    finally:
        with _lock:
            if _states.get(pid, {}).get('identity') == identity:
                _states[pid].update(state=state, http_status=code, model_listed=listed, checked_at=time.time(),
                                    inference_verified=False)


def schedule(pid: str, model: str = '', cfg: dict | None = None):
    """Queue at most one bounded GET per identity. Does not load local models or generate tokens."""
    from backend.providers.models import LLMError, key_required, provider_settings
    cfg = cfg or load_config()
    if pid not in PROVIDERS or not cfg['lifecycle'].get('cloud_preconnect', True):
        return
    try:
        spec, key, default_model, base = provider_settings(cfg, pid)
    except LLMError:
        with _lock:
            _states[pid] = {'provider': pid, 'model': model, 'state': 'error', 'inference_verified': False}
        return
    model = model or default_model
    if not base or (not key and key_required(spec, pid, base)):
        with _lock:
            _states[pid] = {'provider': pid, 'model': model, 'state': 'auth_required', 'inference_verified': False}
        return
    identity = hashlib.sha256(repr((pid, model, base, key)).encode()).hexdigest()
    with _lock:
        current = _states.get(pid, {})
        if current.get('identity') == identity and (current.get('state') == 'connecting' or time.time() - current.get('checked_at', 0) < 300):
            return
        _states[pid] = {'provider': pid, 'model': model, 'identity': identity, 'state': 'connecting',
                        'model_listed': None, 'inference_verified': False}
    old = _tasks.get(pid)
    if old and not old.done():
        old.cancel()
    task = asyncio.create_task(_prepare(cfg, pid, model, identity))
    _tasks[pid] = task


async def selected(patch: dict | None = None):
    cfg = load_config()
    if not cfg['lifecycle'].get('cloud_preconnect', True):
        await shutdown()
        return
    patch = patch or {}
    from backend.providers.models import resolve_engine, resolve_model
    targets = {(resolve_engine(cfg, agent), resolve_model(cfg, agent) or '') for agent in cfg['agent_modes']}
    targets.update((pid, '') for pid in patch.get('providers', {}) if pid in PROVIDERS)
    targets.add((cfg['default_cloud'], ''))
    for pid, model in targets:
        schedule(pid, model, cfg)


def session_selected(session: dict):
    from backend.agent.policy import effective
    from backend.agent.policy import values as resolved_values
    values = resolved_values(effective(session))
    provider = values.get('provider', '').removeprefix('app:')
    if provider in PROVIDERS:
        schedule(provider, values.get('model') or '')


async def shutdown():
    tasks = [task for task in _tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()
