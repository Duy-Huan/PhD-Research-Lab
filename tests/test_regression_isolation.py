"""Regression tests for project-bound background tasks and MCP source policy."""
import _env
import asyncio
import json
import threading
import unittest
from pathlib import Path
from unittest import mock
from backend.core import config
from backend.execution import files as ide_fs
from backend.providers import mcp_server
from backend.providers import gateway as GS, cli as GC
from providers.fakes import fake

class ProjectIsolation(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('isolation-A')
        self.a=config.data_dir()


    def test_mcp_read_respects_policy_and_explicit_opt_in(self):
        ide_fs.write('private.py','def confidential(): return 42')
        config.save_config({'gateway':{'block_source_code':True},'mcp':{'expose_sandbox':True}})
        with self.assertRaises(PermissionError):mcp_server.call_tool('sandbox_manage_files',{'action':'read','path':'private.py'})
        config.save_config({'gateway':{'block_source_code':False}})
        self.assertIn('confidential',str(mcp_server.call_tool('sandbox_manage_files',{'action':'read','path':'private.py'})))

