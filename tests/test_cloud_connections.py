"""INTEGRATION HTTP fixture + UNIT policy tests; no live-cloud inference certification."""
import asyncio
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import AsyncMock, patch

import _env

from backend.core import config
from backend.providers import connections as C
from backend.providers import lifecycle as LC


class Connections(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        C._states.clear()
        LC.reset()

    def tearDown(self):
        LC.reset()

    def test_cloud_is_never_a_local_unload_target(self):
        config.save_config({'lifecycle': {'cloud': 'unload_after_task'}})
        self.assertEqual(LC.policy_for('cloud'), 'keep_loaded')
        with self.assertRaises(ValueError):
            asyncio.run(LC.unload('openai', 'cloud-model', force=True))

    def test_preconnect_off_local_and_missing_auth_do_not_make_network_calls(self):
        async def go():
            with patch.object(C, '_prepare', new_callable=AsyncMock) as prepare:
                config.save_config({'lifecycle': {'cloud_preconnect': False}})
                C.schedule('openai')
                config.save_config({'lifecycle': {'cloud_preconnect': True}, 'providers': {'openai': {'api_key': ''}}})
                C.schedule('local', 'spark-x2.5-4b')
                C.schedule('openai')
                prepare.assert_not_called()
                self.assertEqual(C.status()[-1]['state'], 'auth_required')
        asyncio.run(go())

    def test_actual_socket_is_reused_after_preconnect_and_worker_dispatch(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def do_GET(self):
                seen.append((self.path, self.client_address[1]))
                data = json.dumps({'data': [{'id': 'fixture-model'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}/v1'
        config.save_config({'lifecycle': {'cloud_preconnect': True},
                            'providers': {'custom': {'api_key': '', 'base_url': base, 'model': 'fixture-model'}}})

        async def go():
            LC._main['loop'] = asyncio.get_running_loop()
            C.schedule('custom')
            C.schedule('custom')  # Coalesced, no duplicate request.
            await C._tasks['custom']
            self.assertEqual(C.status()[0]['state'], 'connected')
            self.assertFalse(C.status()[0]['inference_verified'])

            async def request():
                async with LC.http_client(5) as client:
                    return (await client.get(base + '/reuse')).status_code

            result = await asyncio.to_thread(LC.run_on_app_loop, request())
            self.assertEqual(result, 200)
            await LC.release_due(10 ** 12)
            self.assertFalse(LC._pool['client'].is_closed)
            await C.shutdown()
            await LC._close_pool()
        asyncio.run(go())
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][1], seen[1][1], seen)
        self.assertEqual(seen[0][0], '/v1/models')  # Never a token-generating completion call.

    def test_session_selection_resolves_effective_provider(self):
        from backend.agent import sessions
        session = sessions.create(settings={'provider': 'app:openai', 'model': 'selected-model'})
        with patch.object(C, 'schedule') as schedule:
            C.session_selected(session)
            schedule.assert_called_once_with('openai', 'selected-model')
