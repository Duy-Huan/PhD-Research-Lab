"""UNIT/INTEGRATION negative oracles for project roots, grants and native launch containment."""
import unittest
from unittest.mock import patch

import _env

from backend.agent import mcp_policy
from backend.core import config
from backend.providers import cli_space as W
from backend.providers import firewall, isolated_cli, mcp_server, native


class ProjectSecurity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('provider-security')
        config.save_config({'gateway': {'cli_space_dir': ''}, 'mcp': {'token': '', 'rate_limit_per_min': 0}})

    def test_provider_workspaces_are_inside_current_project_and_private_to_mcp(self):
        a = W.open_session('codex', 'native-security-a')
        self.assertTrue(W.root().is_relative_to(config.data_dir()))
        self.assertNotEqual(a['cwd'], str(config.ROOT))
        with self.assertRaises(firewall.FirewallError):
            firewall.check('cli-space/codex/sessions/native-security-a/workspace/secret.txt')
        custom = config.data_dir() / 'custom-cli'
        config.save_config({'gateway': {'cli_space_dir': str(custom)}})
        with self.assertRaises(firewall.FirewallError):
            firewall.check('custom-cli/codex/secret.txt')

    def test_expired_revoked_and_cross_project_grants_cannot_become_anonymous(self):
        token = mcp_policy.issue('provider-test', ['research_get_current_state'])
        headers = {'authorization': 'Bearer ' + token}
        self.assertEqual(mcp_server.guard(headers, 'test')[0], 0)
        project = config.data_dir()
        _env.fresh_project('other-provider-security')
        self.assertIsNone(mcp_policy.lookup(token))
        self.assertEqual(mcp_server.guard(headers, 'test')[0], 401)
        with config.project_scope(project):
            self.assertIsNotNone(mcp_policy.lookup(token))
            mcp_policy.revoke(token)
            self.assertEqual(mcp_server.guard(headers, 'test')[0], 401)
        expired = mcp_policy.issue('provider-expired', [], ttl_s=-1)
        self.assertEqual(mcp_server.guard({'authorization': 'Bearer ' + expired}, 'test')[0], 401)

    def test_raw_host_launch_and_missing_isolation_fail_closed(self):
        with patch.object(native.subprocess, 'Popen') as spawn:
            self.assertFalse(native.launch_terminal('codex')['launched'])
            with patch.object(isolated_cli, 'docker', side_effect=OSError('unavailable')):
                self.assertEqual(native.launch_provider('codex')['state'], 'BLOCKED')
            self.assertEqual(native.launch_provider('antigravity')['state'], 'UNSUPPORTED')
            spawn.assert_not_called()

    def test_same_project_shared_context_is_provider_independent_and_read_only(self):
        first, second = isolated_cli.shared_context(), isolated_cli.shared_context()
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(first['path'], second['path'])
        self.assertTrue(first['path'].startswith(str(config.data_dir())))
