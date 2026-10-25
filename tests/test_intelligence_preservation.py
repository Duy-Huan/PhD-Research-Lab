"""UNIT regression oracles for prompt capabilities and terminal failure provenance."""
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import _env

from backend.agent import context, mcp_policy, orchestrator, sessions
from backend.memory.retrieval import newest_first


class IntelligencePreservation(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('intelligence-preservation')

    def test_explicit_no_tools_never_performs_auto_memory_lookup(self):
        for question in ('Return 13 plus 29. Do not use any tools.', 'Calculate 17 * 23. No tools.',
                         'Không dùng công cụ. Hãy tính 13 cộng 29.'):
            with self.subTest(question=question):
                self.assertEqual(mcp_policy.propose(question, ['research_search_memory', 'web_search']), [])

    def test_reasoning_is_permitted_without_fabricating_empirical_measurements(self):
        instructions = orchestrator.instructions('global')
        self.assertIn('calculate', instructions)
        self.assertIn('empirical', instructions)
        self.assertNotIn('Answer from the compiled context,', instructions)

    def test_failed_gateway_with_partial_text_is_not_reconciled_to_completed(self):
        session = sessions.create('Failure fixture')
        sessions.update(session['id'], lambda s: s['turns'].append({'id': 'old', 'status': 'running',
            'gateway_request': 'request-fixture', 'answer_id': 'partial-answer'}))
        orchestrator._running['old'] = {'cancel': threading.Event(), 'rid': 'request-fixture'}
        self.addCleanup(lambda: orchestrator._running.pop('old', None))
        with patch('backend.providers.gateway.get', return_value={'status': 'failed', 'answer': 'partial'}), \
             patch.object(orchestrator, '_spawn'):
            orchestrator.start(session['id'], '/help')
        self.assertEqual(sessions.get(session['id'])['turns'][0]['status'], 'failed')

    def test_terminal_completion_waits_for_artifact_and_retention_writes(self):
        session = sessions.create(settings={'provider': 'app:local', 'keep_history': False, 'summaries': False})
        with patch.object(orchestrator, '_spawn'):
            turn = orchestrator.start(session['id'], 'A bounded fixture request')
        orchestrator._set(session['id'], turn['id'], status='running')
        reached, release = threading.Event(), threading.Event()
        def delayed(*args):
            reached.set()
            release.wait(3)
        with patch.object(orchestrator.artifacts, 'from_text', delayed):
            worker = threading.Thread(target=orchestrator._complete,
                args=(session['id'], turn['id'], 'Fixture answer', None, time.time(), ''))
            worker.start()
            try:
                self.assertTrue(reached.wait(2))
                self.assertEqual(sessions.get(session['id'])['turns'][-1]['status'], 'running')
            finally:
                release.set()
                worker.join(3)
        saved = sessions.get(session['id'])
        self.assertEqual(saved['turns'][-1]['status'], 'completed')
        self.assertTrue(saved['messages'][-1]['not_retained'])

    def test_unrelated_conversation_is_not_injected_as_default_project_context(self):
        other = sessions.create('Unrelated arithmetic')
        sessions.add_message(other['id'], 'user', 'Calculate 13 plus 29', 'old')
        sessions.add_message(other['id'], 'assistant', '42', 'old')
        current = sessions.create('Current arithmetic', settings={'mcp_auto': False})
        sessions.add_message(current['id'], 'user', 'Calculate 17 times 23', 'first')
        sessions.add_message(current['id'], 'assistant', '391', 'first')
        with patch.object(orchestrator, '_spawn'):
            turn = orchestrator.start(current['id'], 'Now multiply that previous result by 2')
        saved = sessions.get(current['id'])
        packet = context.ContextBuilder.build(saved, turn['question'], turn['effective'])
        self.assertNotIn('conv:' + other['id'], [s['id'] for s in packet['manifest']['sources']])
        self.assertEqual(orchestrator._history(saved, turn['id'])[-1]['content'], '391')
        self.assertIs(context.compile, context.ContextBuilder.build)

    def test_unowned_stale_turn_is_cancelled_and_cannot_block_new_work(self):
        session = sessions.create('Stale state fixture')
        sessions.update(session['id'], lambda s: s['turns'].append({'id': 'stale-no-worker', 'status': 'running', 'answer_id': ''}))
        new = orchestrator.start(session['id'], '/help')
        saved = sessions.get(session['id'])
        self.assertEqual(saved['turns'][0]['status'], 'cancelled')
        self.assertEqual(new['status'], 'completed')

    def test_temporal_context_orders_equal_instants_by_id_without_sampling_clock(self):
        nodes = [SimpleNamespace(id='B', ts='2026-10-25T07:00:00+07:00'),
                 SimpleNamespace(id='A', ts='2026-10-25T00:00:00Z'),
                 SimpleNamespace(id='new', ts='2026-10-26T00:00:00Z'),
                 SimpleNamespace(id='unknown', ts='invalid')]
        with patch('backend.memory.retrieval.datetime') as clock:
            # Parsing uses the real class; reading now would alter equal-age ordering.
            from datetime import datetime
            clock.fromisoformat.side_effect = datetime.fromisoformat
            clock.now.side_effect = AssertionError('Temporal order must use stored instants')
            self.assertEqual([n.id for n in sorted(nodes, key=newest_first)], ['new', 'A', 'B', 'unknown'])
            # Test the opposite input order to catch missing tie-breakers.
            self.assertEqual([n.id for n in sorted(reversed(nodes), key=newest_first)], ['new', 'A', 'B', 'unknown'])  # noqa: C414
