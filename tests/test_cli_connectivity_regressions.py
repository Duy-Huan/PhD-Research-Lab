"""Regressions found by real subscription CLI and UI probes (not entitlement tests)."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import _env
from fastapi.testclient import TestClient

from backend.agent import launch, runs, skills
from backend.app import app
from backend.core import config
from backend.providers import cli, models


class ConnectivityRegressions(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('cli-regressions-' + self._testMethodName[-18:])
        config.save_config({'runs': {'auto_approve_risk': -1}})

    def test_advertised_chat_commands_are_registered(self):
        from backend.agent.ui_actions import QUICK
        for file in ('Composer.tsx', 'MessageList.tsx'):
            source = (config.ROOT / 'frontend/src/features/chat' / file).read_text('utf-8')
            for name in set(re.findall(r"['\"]/([a-z][a-z0-9_-]*)(?=[\s'\"])", source)):
                with self.subTest(file=file, command=name):
                    if name not in QUICK:
                        skills.get(name)

    def test_external_commands_preserve_requested_engine_and_approval(self):
        config.save_config({'research_providers': {'engine_mode': 'collaborative'}})
        for command, provider, canonical in [('openscience', 'openscience', 'science'),
                                              ('science', 'openscience', 'science'),
                                              ('feynman', 'feynman', 'feynman'),
                                              ('opencode', 'opencode', 'opencode')]:
            with self.subTest(command=command):
                result = launch.from_skill(command, 'Design a bounded protocol')
                run = runs.get(result['id'])
                self.assertEqual(run['skill'], canonical)
                self.assertEqual(run['steps'][0]['provider'], provider)
                self.assertEqual(run['status'], 'APPROVAL_PENDING')

    def test_openscience_chat_endpoint_accepts_the_exact_ui_command(self):
        c = TestClient(app, headers={'X-PhDLab-Client': 'ui'})
        session = c.post('/api/chat/sessions', json={}).json()
        response = c.post(f"/api/chat/sessions/{session['id']}/turns", json={
            'text': '/openscience Design a controlled experimental protocol & ablation study.'})
        self.assertEqual(response.status_code, 200)
        message = c.get(f"/api/chat/sessions/{session['id']}").json()['messages'][-1]
        self.assertNotIn('Unknown command', message['content'])
        self.assertEqual(runs.get(message['run_id'])['status'], 'APPROVAL_PENDING')

    def test_cli_default_does_not_force_an_api_model(self):
        self.assertEqual(models.default_model_for(config.load_config(), 'codex'), '')

    def test_opencode_does_not_claim_manifest_creation_is_model_execution(self):
        from backend.research_engines.contracts import EngineFailure, EngineTask
        from backend.research_engines.opencode import OpenCodeEngine
        task = EngineTask(operation_id='RR-12345678:S1', project_id='qa', workflow_id='RR-12345678',
                          step_id='S1', question='Reply OK', output_dir=config.data_dir() / 'native-test', approved=True)
        with self.assertRaisesRegex(EngineFailure, 'native prompt dispatch is not connected'):
            OpenCodeEngine().execute(task, lambda e: None, lambda: False)
        self.assertFalse(task.output_dir.exists())

    def test_real_cli_failures_are_classified(self):
        self.assertEqual(cli.classify_error("You've hit your weekly limit"), 'RATE_LIMITED')
        self.assertEqual(cli.classify_error('Please set an Auth method in settings.json'), 'AUTH_EXPIRED')

    def test_opencode_html_fallback_is_not_api_readiness(self):
        from backend.research_engines import opencode
        with patch.object(opencode, 'probe_binary', return_value={'installed': True}), \
             patch.object(opencode.httpx, 'get', return_value=SimpleNamespace(status_code=200, json=dict)):
            self.assertFalse(opencode.health()['server_reachable'])

    def test_cli_connection_test_uses_real_connector_path_without_api_fallback(self):
        c = TestClient(app, headers={'X-PhDLab-Client': 'ui'})
        conn = cli.CONNECTORS['codex']
        with patch.object(conn, 'stream_message', return_value=iter([{'type': 'text_delta', 'text': 'OK'}])) as send:
            response = c.post('/api/models/test', json={'provider': 'cli:codex'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reply'], 'OK')
        self.assertEqual(send.call_args.args[1]['model'], '')

    def test_refresh_auth_does_not_hide_a_weekly_limit(self):
        conn = cli.ClaudeCodeConnector()
        cli._last_error['claude_code'] = ('RATE_LIMITED', 'weekly limit')
        self.addCleanup(lambda: cli._last_error.pop('claude_code', None))
        with patch.object(conn, '_probe', return_value={'bin': 'claude', 'ok': True}), \
             patch.object(conn, 'auth_state', return_value=('CONNECTED', 'signed in')):
            self.assertEqual(conn.health(True)['state'], 'RATE_LIMITED')

    def test_antigravity_print_flag_cannot_consume_output_format(self):
        argv = cli.AntigravityConnector().argv({})
        self.assertIn('--print=', argv)
        self.assertNotIn('-p', argv)
        self.assertIn('--sandbox', argv)

    def test_opencode_v2_npm_shim_resolves_to_native_executable(self):
        from backend.execution import tools
        with tempfile.TemporaryDirectory() as folder:
            shim = Path(folder) / 'opencode.cmd'
            native = Path(folder) / 'node_modules/@opencode/cli/bin/opencode.exe'
            native.parent.mkdir(parents=True)
            native.touch()
            with patch.object(tools.sys, 'platform', 'win32'):
                self.assertEqual(tools.node_argv(str(shim), 'opencode-ai/bin/opencode'), [str(native)])

    def test_result_only_stream_still_produces_an_answer_and_empty_exit_is_error(self):
        class ResultOnly(cli.AntigravityConnector):
            def process_argv(self, args, context):
                return args  # Controlled Python result-only fixture.
            def binary(self):
                return sys.executable

            def _probe(self):
                return {'bin': sys.executable, 'ok': True}

            def argv(self, context):
                return [sys.executable, '-c', 'import sys; sys.stdin.read(); ' + context['script']]

        conn = ResultOnly()
        record = {'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'OK'}}
        events = list(conn.stream_message('ping', {'script': 'print(' + repr(json.dumps(record)) + ')'}))
        self.assertEqual([e['text'] for e in events if e['type'] == 'text_delta'], ['OK'])
        self.assertFalse([e for e in events if e['type'] == 'error'])
        events = list(conn.stream_message('ping', {'script': 'pass'}))
        self.assertTrue([e for e in events if e['type'] == 'error' and 'no answer' in e['message']])

    def codex_protocol_fixture(self,records):
        class ControlledCodex(cli.CodexConnector):
            def process_argv(self,args,context):return args
            def binary(self):return sys.executable
            def _probe(self):return {'bin':sys.executable,'ok':True,'login_code':0,'login':'Logged in using ChatGPT'}
            def argv(self,context):
                script='import sys,json; sys.stdin.read(); records='+repr(records)+'; [print(json.dumps(r),flush=True) for r in records]'
                return [sys.executable,'-c',script]
        return list(ControlledCodex().stream_message('Protocol fixture only; no provider inference',{}))

    def test_codex_assistant_message_is_not_terminal_and_real_usage_event_is_retained(self):
        records=[{'type':'item.completed','item':{'type':'agent_message','text':'I will check the result.'}},
                 {'type':'item.completed','item':{'type':'agent_message','text':'The checked result is121.'}},
                 {'type':'turn.completed','usage':{'input_tokens':31,'output_tokens':12}}]
        events=self.codex_protocol_fixture(records)
        self.assertEqual([e['text'] for e in events if e['type']=='text_delta'],
                         ['I will check the result.','The checked result is121.'])
        self.assertEqual([e['usage'] for e in events if e.get('state')=='usage'],[{'input_tokens':31,'output_tokens':12}])
        self.assertFalse([e for e in events if e['type']=='error'])

    def test_codex_failure_after_partial_assistant_text_is_not_hidden_as_success(self):
        events=self.codex_protocol_fixture([
            {'type':'item.completed','item':{'type':'agent_message','text':'A partial observation.'}},
            {'type':'turn.failed','error':{'message':'Controlled provider failure after partial text'}}])
        self.assertTrue(any(e['type']=='error' and 'Controlled provider failure' in e['message'] for e in events))


if __name__ == '__main__':
    unittest.main()
