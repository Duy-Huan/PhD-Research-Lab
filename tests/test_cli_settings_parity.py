"""INTEGRATION: terminal settings share the actual web config API; no AI calls."""
import io
import unittest
from types import SimpleNamespace

import _env
from fastapi.testclient import TestClient

from backend.app import app
from backend.cli import Client, CLIError
from backend.cli.repl import Repl
from backend.core import config


class CLISettingsParity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('cli-settings-parity')
        self.http = TestClient(app)
        self.output = io.StringIO()
        self.repl = Repl(SimpleNamespace(c=Client(http=self.http), out=self.output, inp=lambda _: ''))

    def test_menu_matches_all_web_settings_categories_in_both_languages(self):
        for locale, expected in [('en', 'Models & AI Agents'), ('vi', 'Mô hình & Tác nhân AI')]:
            config.save_config({'ui': {'language': locale}})
            self.output.seek(0)
            self.output.truncate()
            self.repl.handle('/settings')
            text = self.output.getvalue()
            self.assertIn(expected, text)
            for section in ('models', 'research', 'search', 'experiments', 'memory', 'security', 'skills', 'appearance'):
                self.assertIn('/settings ' + section, text)
                self.repl.handle('/settings ' + section)

    def test_language_switch_persists_in_web_and_new_terminal_and_keeps_session(self):
        self.repl.handle('/new')
        sid = self.repl.sid
        self.repl.handle('/language en')
        self.assertEqual(self.http.get('/api/config').json()['ui']['language'], 'en')
        self.assertIn('Language saved', self.output.getvalue())
        self.assertEqual(self.repl.sid, sid)
        self.repl.handle('/language ai vi')
        self.assertEqual(self.http.get('/api/config').json()['ui']['ai_language'], 'vi')
        config.save_config({'ui': {'language': 'vi'}})
        self.repl.handle('/help')
        self.assertEqual(self.repl.language, 'vi')
        second = Repl(SimpleNamespace(c=Client(http=self.http), out=io.StringIO(), inp=lambda _: ''))
        second.refresh_language()
        self.assertEqual(second.language, 'vi')

    def test_settings_roundtrip_rejects_invalid_input_and_never_echoes_secret(self):
        self.repl.handle('/settings set runs.max_minutes 37')
        self.assertEqual(config.load_config()['runs']['max_minutes'], 37)
        self.repl.handle('/settings set providers.openai.api_key "fixture-private-value"')
        self.assertNotIn('fixture-private-value', self.output.getvalue())
        self.repl.handle('/settings models')
        self.assertNotIn('fixture-private-value', self.output.getvalue())
        for command in ('/language invalid', '/language ai invalid', '/settings absent', '/settings set x {broken', '/settings set ui.language 5'):
            with self.subTest(command=command), self.assertRaises(CLIError):
                self.repl.handle(command)

    def test_english_help_has_translated_command_descriptions(self):
        config.save_config({'ui': {'language': 'en'}})
        self.repl.handle('/help')
        text = self.output.getvalue()
        self.assertIn('**Terminal commands:**', text)
        self.assertIn('conversation provider', text)
        self.assertNotIn('cuộc trò chuyện', text)
