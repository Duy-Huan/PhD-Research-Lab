"""FQC-TOOL-SHELL-664 (agent/PLAN_6.6.4_L3.md A5): the sandbox tool tells the agent which shell runs its commands.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): the description said nothing about the host, so
Codex wrote POSIX `VAR=1 python ...` and Windows cmd.exe failed. Local mode runs with shell=True (cmd.exe on Windows,
/bin/sh elsewhere); Docker mode runs `sh -c` in a Linux container."""
import time
import unittest
from unittest.mock import patch

import _env  # noqa: F401
from backend.execution import sandbox
from backend.providers import mcp_server
from backend.tools import registry


def run_code_description(mode: str, windows: bool) -> tuple[str, str]:
    with patch.object(sandbox, "IS_WIN", windows), \
            patch.object(sandbox, "load_settings", return_value={**sandbox.DEFAULT_SETTINGS, "mode": mode}):
        listed = next(t for t in mcp_server.tool_list() if t["name"] == "sandbox_run_code")["description"]
        spec = next(s for s in registry.builtin_specs() if s.id == "sandbox_run_code").description
    return listed, spec


class SandboxShellDescription(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)

    def test_local_windows_names_cmd_and_its_syntax(self):
        for text in run_code_description("local", True):
            self.assertIn("cmd.exe", text)
            self.assertIn("set VAR=1 && python", text)
            self.assertNotIn("POSIX sh inside", text)

    def test_local_posix_and_docker_name_sh(self):
        for mode, windows in (("local", False), ("docker", True), ("docker", False)):
            with self.subTest(mode=mode, windows=windows):
                for text in run_code_description(mode, windows):
                    self.assertIn("POSIX sh", text)
                    self.assertNotIn("cmd.exe", text)

    def test_auto_mode_describes_both_and_recommends_code(self):
        for text in run_code_description("auto", True):
            self.assertIn("cmd.exe", text)
            self.assertIn("POSIX sh", text)
            self.assertIn("code", text)

    def test_unknown_mode_falls_back_to_the_local_shell(self):
        listed, spec = run_code_description("something-else", True)
        self.assertIn("cmd.exe", listed)
        self.assertEqual(listed, spec)

    def test_other_tools_and_the_static_catalog_are_untouched(self):
        static = next(t for t in mcp_server.TOOLS if t["name"] == "sandbox_run_code")["description"]
        self.assertNotIn("cmd.exe", static)  # the note is added per call, never written into the shared list
        listed = {t["name"]: t["description"] for t in mcp_server.tool_list()}
        self.assertEqual(listed["sandbox_manage_files"],
                         next(t for t in mcp_server.TOOLS if t["name"] == "sandbox_manage_files")["description"])

    def test_describing_is_fast(self):
        # Built once per tool listing; reading the sandbox setting costs about 5 ms (project lookup).
        t0 = time.perf_counter()
        for _ in range(50):
            sandbox.shell_note()
        self.assertLess(time.perf_counter() - t0, 1.0)  # under 20 ms per listing


if __name__ == "__main__":
    unittest.main()
