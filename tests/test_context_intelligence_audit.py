"""Behavior oracles for confirmed context loss; these do not certify general model intelligence."""
import hashlib
import unittest
from unittest.mock import patch

import _env

from backend.agent import context, orchestrator, policy, sessions
from backend.core import config
from backend.knowledge import library


class ContextIntelligenceAudit(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('context-intelligence-audit')
        context.clear_cache()

    def test_expanded_selected_paper_includes_results_after_page_three(self):
        from reportlab.pdfgen.canvas import Canvas
        path = config.refs_dir() / 'late-results.pdf'
        canvas = Canvas(str(path))
        for page in range(5):
            canvas.drawString(40, 700, f'Page {page + 1}: ' + ('THE MEASURED RESULT IS 7319' if page == 4 else 'Methodology'))
            canvas.showPage()
        canvas.save()
        library.save_library({'p': {'key': 'latepaper', 'key_locked': True, 'title': 'Late results research fixture',
                                     'file': path.name, 'include': True}})
        session = sessions.create(settings={'context_mode': 'expanded', 'context_budget_tokens': 6000})
        sessions.update(session['id'], lambda s: s.update(selected_sources=['ref:latepaper']))
        session = sessions.get(session['id'])
        packet = context.compile(session, 'What is the measured result on the final page?', policy.effective(session))
        self.assertIn('7319', packet['text'])
        source = next(s for s in packet['manifest']['sources'] if s['id'] == 'ref:latepaper')
        self.assertEqual(source['extraction']['pages_included'], 5)
        self.assertFalse(source['truncated'])

    def test_no_arbitrary_twenty_message_limit_and_large_history_is_declared(self):
        session = {'messages': [{'id': str(i), 'role': 'user' if i % 2 == 0 else 'assistant',
                                'content': f'Fact {i}', 'turn_id': str(i)} for i in range(30)]}
        messages, manifest = orchestrator._history_packet(session, 'new')
        self.assertEqual(len(messages), 30)
        self.assertFalse(manifest['omitted_messages'])
        config.save_config({'aiws': {'history_budget_tokens': 400}})
        session['messages'].append({'id': 'oversized', 'role': 'assistant', 'content': 'START' + 'x' * 10000 + 'END', 'turn_id': 'old'})
        messages, manifest = orchestrator._history_packet(session, 'new')
        self.assertEqual(manifest['truncated_messages'], ['oversized'])
        self.assertIn('middle omitted', messages[-1]['content'])
        self.assertIn('START', messages[-1]['content'])
        self.assertTrue(messages[-1]['content'].endswith('END'))
        self.assertLessEqual(manifest['estimated_tokens'], 400)

    def test_explicit_folder_memory_updates_even_after_many_unrelated_chats(self):
        group = sessions.create_chat_project('Shared research')
        old = sessions.create('Old shared memory')
        current = sessions.create('Current', settings={'context_mode': 'selected'})
        for item in (old, current):
            sessions.organize(item['id'], chat_project=group['id'])
        sessions.update(old['id'], lambda s: s.update(summary='Use three independent seeds.'))
        for i in range(12):
            sessions.create(f'Unrelated {i}')
        def build():
            s = sessions.get(current['id'])
            return context.compile(s, 'What are the constraints?', policy.effective(s))
        first = build()
        self.assertIn('three independent seeds', first['text'])
        sessions.update(old['id'], lambda s: s.update(summary='Use five independent seeds.'))
        second = build()
        self.assertNotEqual(first['manifest']['version'], second['manifest']['version'])
        self.assertIn('five independent seeds', second['text'])

    def test_budget_includes_source_framing_and_reports_original_hash(self):
        from backend.agent.project_context import src
        class Adapter:
            label = 'Fixture'
            def state(self, _):
                return [src('incidental', 'module_state', 'Long state', 'z' * 10000, 'state', 'fixture'),
                        src('state:pins', 'module_state', 'Pinned CPU budget', 'CPU budget is 2 seconds', 'user', 'pinned constraint')]
            def identity(self):
                return {'module': 'fixture'}
            def summary(self, _):
                return 'Fixture'
        s = sessions.create(settings={'context_mode': 'selected', 'context_budget_tokens': 600})
        long = src('ref:selected', 'reference', 'Selected document', 'x' * 10000, 'untrusted', 'selected')
        s['selected_sources'] = ['ref:selected']
        with patch('backend.agent.project_context.get', return_value=Adapter()), \
             patch('backend.agent.project_context.resolve_source', return_value=long):
            packet = context.compile(s, 'question', policy.effective(s))
        self.assertIn('CPU budget is 2 seconds', packet['text'])
        self.assertLessEqual(packet['manifest']['budget']['used_tokens'], 600)
        selected = next(item for item in packet['manifest']['sources'] if item['id'] == 'ref:selected')
        self.assertTrue(selected['truncated'])
        self.assertEqual(selected['full_sha256'], hashlib.sha256(('x' * 10000).encode()).hexdigest())
        self.assertNotEqual(selected['sha256'], selected['full_sha256'])
