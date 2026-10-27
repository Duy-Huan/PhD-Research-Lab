"""UNIT: native launcher transport is mocked; these are not live launch claims."""
import base64
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import _env
from fastapi.testclient import TestClient

from backend.app import app
from backend.providers import native


class NativeCLILaunch(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('native-cli-launch')

    def test_installed_executable_is_quoted_and_launched_without_a_website(self):
        with patch.object(native.sys, 'platform', 'win32'), patch.object(native.shutil, 'which', return_value=sys.executable), \
             patch.object(native.subprocess, 'Popen', return_value=SimpleNamespace(pid=123)) as launch:
            result = native._open_console(sys.executable, ["a'b", '$(untrusted)'], str(_env.config.data_dir()))
        argv = launch.call_args.args[0]
        command = base64.b64decode(argv[-1]).decode('utf-16le')
        self.assertIn("'a''b'", command)
        self.assertIn("'$(untrusted)'", command)
        self.assertTrue(result['launched'])
        self.assertEqual(result['pid'], 123)
        self.assertNotIn('http', command)

    def test_missing_binary_and_process_error_are_not_success(self):
        with patch.object(native.shutil, 'which', return_value=None), patch.object(native.subprocess, 'Popen') as launch:
            self.assertFalse(native.launch_terminal('missing')['launched'])
            launch.assert_not_called()
        with patch.object(native.sys, 'platform', 'win32'), patch.object(native.shutil, 'which', return_value=sys.executable), \
             patch.object(native.subprocess, 'Popen', side_effect=OSError):
            self.assertEqual(native._open_console('python', [], str(_env.config.data_dir()))['state'], 'ERROR')

    def test_forward_modes_and_launch_always_target_the_installed_app(self):
        client = TestClient(app)
        launched = {'launched': True, 'detail': 'Native test process', 'command': ['codex']}
        with patch('webbrowser.open') as browser, patch.object(native, 'launch_provider', return_value=launched) as launch:
            for mode in ('app', 'web'):
                response = client.post('/api/providers/cli:codex/connect', json={'mode': mode})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()['opened_web'])
            response = client.post('/api/providers/codex/launch', json={})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['terminal_launched'])
            self.assertEqual(launch.call_args.args, ('codex',))
            browser.assert_not_called()
        with patch.object(native, 'launch_provider', return_value={'launched': False, 'detail': 'Not installed'}):
            response = client.post('/api/providers/codex/launch')
            self.assertEqual(response.status_code, 503)
