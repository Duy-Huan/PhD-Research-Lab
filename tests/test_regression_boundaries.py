"""Failure-injection contracts for optional data services, storage retries, and telemetry."""
import _env
import json
import os
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import httpx
from backend.core import config, telemetry as T
from backend.memory import store as S, cache
from backend.execution import tools as B
from backend.providers import events as EV, privacy as policy

class BoundaryRegression(unittest.TestCase):
    def setUp(self):_env.fresh_project('boundary-regression')



    def test_normalizer_unknown_events_are_observable(self):
        cases={'codex':[{'type':'item.started','item':{'type':'mcp_tool_call','tool':'read'}},{'type':'item.completed','item':{'type':'command_execution','status':'done'}},{'type':'turn.failed','error':'offline'},{'type':'turn.failed','error':{'message':'offline'}}],
            'claude':[{'type':'system','subtype':'api_retry','attempt':2},{'type':'system','subtype':'other'},{'type':'stream_event','event':{}},{'type':'assistant','message':{'content':[{'type':'text'}]}},{'type':'user','message':{'content':['text',{'type':'tool_result','tool_use_id':'x'}]}}],
            'agy':[{'event':'step_update','step_update':{'step_type':'tool','state':'DONE','tool_name':'read'}},{'event':'step_update','step_update':{}},{'event':'result','result':{'status':'ERROR','error':'offline'}}],
            'gemini':[{'type':'message','role':'user','content':'ignore'},{'type':'message','content':''},{'type':'result','status':'error','error':'offline'}]}
        for name,events in cases.items():
            for event in events:
                with self.subTest(name=name,event=event):self.assertIsInstance(EV.NORMALIZERS[name](event),list)
            self.assertEqual(EV.NORMALIZERS[name]({}),[])
            key='event' if name=='agy' else 'type'
            self.assertEqual(EV.NORMALIZERS[name]({key:'unknown'})[0]['type'],'status')

