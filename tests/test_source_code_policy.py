"""FQC-SOURCE-POLICY-663: by owner decision (2026-10-28) agents may read project source and experiment results.

gateway.block_source_code defaults to off: code blocks leave unchanged and the MCP sandbox file read works unless the
researcher turns the firewall on in Settings. Credentials are always redacted, and an explicit opt-in still withholds."""
import unittest

import _env
from backend.core import config
from backend.execution import files as ide_fs
from backend.providers import mcp_server
from backend.providers.privacy import sanitize

CODE = "Result:\n```python\nprint(0.912)\n```"


class SourceCodePolicy(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('source-policy-663')

    def test_default_lets_agents_read_code_and_results(self):
        self.assertIs(config.DEFAULTS["gateway"]["block_source_code"], False)
        self.assertEqual(sanitize(CODE)[0], CODE)
        self.assertEqual(sanitize(CODE, {"gateway": {}})[0], CODE, "a missing key means no blocking")
        ide_fs.write('metrics.py', 'ACCURACY = 0.912')
        config.save_config({'mcp': {'expose_sandbox': True}})
        self.assertIn('0.912', str(mcp_server.call_tool('sandbox_manage_files', {'action': 'read', 'path': 'metrics.py'})))

    def test_large_results_pass_through_without_delay(self):
        import time
        big = ("| epoch | acc |\n```text\n" + "0.9 " * 50_000 + "\n```\n") * 10
        started = time.perf_counter()
        self.assertEqual(sanitize(big, {"gateway": {}})[0], big)
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_explicit_opt_in_still_withholds_and_credentials_are_always_redacted(self):
        text, notes = sanitize(CODE + "\nkey sk-ant-api03-" + "a" * 40, {"gateway": {"block_source_code": True}})
        self.assertNotIn("print(0.912)", text)
        self.assertIn("source code withheld", notes)
        self.assertNotIn("a" * 40, sanitize("key sk-ant-api03-" + "a" * 40, {"gateway": {}})[0])
        ide_fs.write('metrics.py', 'ACCURACY = 0.912')
        config.save_config({'gateway': {'block_source_code': True}, 'mcp': {'expose_sandbox': True}})
        with self.assertRaises(PermissionError):
            mcp_server.call_tool('sandbox_manage_files', {'action': 'read', 'path': 'metrics.py'})


if __name__ == "__main__":
    unittest.main()
