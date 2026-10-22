import _env  # noqa: F401
import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from backend.core import config as C
from backend.agent import sessions as S, orchestrator as O


class ChatOrganization(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.project = _env.fresh_project('chat organization', code_project=None)

    def test_groups_assignments_pins_are_durable_and_project_scoped(self):
        group = S.create_chat_project('Literature notes')
        a, b = S.create('A'), S.create('B')
        S.organize(a['id'], pinned=True, chat_project=group['id'])
        S.organize(b['id'], pinned=True)
        S.update(a['id'], lambda s: s.update(updated=1))
        S.create('Unpinned newest')
        self.assertTrue(S.list_sessions(limit=1)[0]['pinned'])
        self.assertEqual(S.get(a['id'])['chat_project'], group['id'])
        self.assertEqual(S.chat_projects()[0]['name'], 'Literature notes')
        S.organize(a['id'], pinned=False, chat_project='')
        self.assertFalse(S.get(a['id'])['pinned'])
        self.assertEqual(S.get(a['id'])['chat_project'], '')
        with self.assertRaisesRegex(ValueError, 'not found'):
            S.organize(a['id'], chat_project='cg-unknown')
        with self.assertRaisesRegex(ValueError, 'boolean'):
            S.organize(a['id'], pinned='true')
        for name in ('', ' ' * 8, 'a' * 81):
            with self.assertRaises(ValueError):
                S.create_chat_project(name)
        _env.fresh_project('other isolated chats', code_project=None)
        self.assertEqual(S.chat_projects(), [])
        with self.assertRaises(ValueError):
            S.organize(a['id'], chat_project=group['id'])
        with C.project_scope(self.project['data_dir']):
            self.assertEqual(len(S.chat_projects()), 1)

    def test_concurrent_pins_keep_all_messages(self):
        session = S.create('Many pins')
        S.update(session['id'], lambda s: s.update(messages=[{'id': 'm' + str(i), 'role': 'user', 'content': str(i), 'ts': i} for i in range(20)]))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: S.pin_message(session['id'], 'm' + str(i), True), range(20)))
        self.assertEqual(sum(m.get('pinned', False) for m in S.get(session['id'])['messages']), 20)

    def test_assistant_is_separate_and_catalog_contains_only_its_provider(self):
        from backend.api import system
        cfg = C.save_config({'agent_modes': {'assistant': 'openai', 'research': 'anthropic', 'reviewer': 'ollama', 'utility': 'mcp'},
                             'agent_models': {'assistant': 'my-openai'}, 'mcp_agent': {'models': ['mcp-only']}})
        self.assertEqual(O._agent({}), 'assistant')
        with patch('backend.agent.skills.get', return_value={'agent': 'reviewer'}):
            self.assertEqual(O._agent({'skill': 'review'}), 'reviewer')
        descriptor = {'id': 'app:openai', 'label': 'OpenAI', 'transport': 'api', 'state': 'NO_KEY', 'available': False, 'detail': '',
                      'capabilities': {'models': ['gpt-one'], 'reasoning_controls': []}}
        with patch('backend.providers.registry.registry', return_value=[descriptor]):
            result = asyncio.run(system.models())
        catalog = result['agent_catalog']['assistant']
        self.assertEqual(catalog['models'], ['gpt-one', 'my-openai'])
        self.assertEqual(catalog['engine'], 'openai')
        self.assertEqual(result['agent_catalog']['utility']['models'], ['mcp-only'])
        self.assertNotEqual(cfg['agent_modes']['assistant'], cfg['agent_modes']['research'])

    def test_api_creates_and_assigns_groups_without_crossing_topics(self):
        from backend.api import chat
        group = asyncio.run(chat.chat_project_create({'name': 'Discussion'}))
        session = asyncio.run(chat.create({'title': 'Grouped', 'chat_project': group['id']}))
        self.assertEqual(session['chat_project'], group['id'])
        self.assertEqual(asyncio.run(chat.chat_projects())['projects'][0]['id'], group['id'])
        changed = asyncio.run(chat.update(session['id'], {'pinned': True, 'chat_project': ''}))
        self.assertTrue(changed['pinned'])
        self.assertEqual(changed['chat_project'], '')
        before = len(S.list_sessions())
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            asyncio.run(chat.create({'chat_project': 'cg-unknown'}))
        self.assertEqual(len(S.list_sessions()), before)
