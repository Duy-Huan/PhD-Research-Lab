"""Deterministic host and process failure contracts; no real Docker/Git/CLI side effects."""
import _env
import io
import json
import sys
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from backend.core import config
from backend.execution import sandbox as S, sysinfo as SI, gitops as G, deps, resources
from backend.execution import vscode as W, tools as B
from test_legacy_system import FakeDocker

class SystemFaults(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('system-faults')
        S.save_settings({'mode':'local','gpu':False,'image':'img:1','auto_deps':False,'python_mode':'direct','python_base':sys.executable})

    def test_sandbox_creation_failures_and_output_recovery(self):
        self.assertTrue(S._now())
        with mock.patch.object(deps,'plan_cached',side_effect=RuntimeError('unavailable')),mock.patch('backend.execution.envs.choose',return_value=('local','fallback')):
            self.assertEqual(S.choose_mode()[0],'local')
        with mock.patch.object(SI,'scan',side_effect=RuntimeError('unavailable')):self.assertEqual(S.effective_image({'image':''}),'python:3.11-slim')
        with mock.patch.object(resources,'clamp_sandbox',side_effect=RuntimeError('unavailable')):self.assertEqual(S._capped_settings()[1],[])
        f=FakeDocker()
        with mock.patch.object(S,'docker',f),mock.patch.object(S,'_capped_settings',return_value=(S.load_settings(),['clamped'])):
            self.assertIn('clamped',S.ensure_container()['warning'])
        with mock.patch.object(S,'container_state',return_value={'exists':True,'running':True,'name':'fake'}),mock.patch.object(S,'docker',return_value=(1,'denied')):
            with self.assertRaises(S.SandboxError):S.container_action('stop')
        job=S.Job('shell','test','test');job.run_dir=S.runs_dir()/job.id;job.run_dir.mkdir()
        with mock.patch('builtins.open',side_effect=OSError('disk')):job.add('out','measured')
        pipe=mock.Mock();pipe.readline.side_effect=OSError('closed');pipe.close.side_effect=OSError('closed');S._pump(job,pipe,'out')
        completed={str(i):SimpleNamespace(status='done') for i in range(201)}
        with mock.patch.dict(S.JOBS,completed,clear=True):S._register(job);self.assertLess(len(S.JOBS),201)
        with mock.patch.object(S,'_base_python',return_value='/different/python'):
            self.assertNotEqual(S._venv_dir({}),S.sb_dir()/'venv')
        with mock.patch.object(S,'_local_cmd',return_value=('fake',{})),mock.patch.object(S,'_local_python',return_value=sys.executable),mock.patch('subprocess.Popen',side_effect=OSError('missing')):
            with self.assertRaises(S.SandboxError):S.start_job('fake',kind='shell')
        job.started=0;job.status='done';job.run_dir=S.runs_dir()/job.id
        (S.code_dir()/'outputs').mkdir(exist_ok=True)
        (S.code_dir()/'metrics.json').write_text('{broken','utf-8')
        (S.code_dir()/'outputs'/'metrics.json').write_text('{"loss":0.2}','utf-8')
        (S.code_dir()/'outputs'/'curve.png').write_bytes(b'png')
        out=S.collect_run(job);self.assertEqual(out['metrics'],{'loss':0.2});self.assertTrue(out['figures'])
        with mock.patch.object(Path,'write_text',side_effect=OSError('disk')):S._write_run_meta(job)
        job.run_dir=None;S._write_run_meta(job)
        (S.runs_dir()/'run-broken').mkdir();(S.runs_dir()/'run-broken'/'run.json').write_text('{bad','utf-8');S.list_runs()
        with mock.patch.object(S,'list_runs',return_value=[{'id':'r','status':'done','metrics':{'label':'not number'}}]):self.assertEqual(S.best_metrics(),{})

    def test_waiter_timeout_stop_and_metrics_extraction_fault(self):
        job=S.Job('setup','fake','test');job.mode='local';job.status='running';job.started=1
        job.proc=mock.Mock(returncode=1);job.proc.poll.return_value=None;job.proc.wait.side_effect=RuntimeError('closed');job.proc.pid=123
        job.run_dir=S.runs_dir()/job.id;job.run_dir.mkdir();S.JOBS[job.id]=job
        def stop(*a):job.stop_requested=True
        with mock.patch.object(S.time,'time',side_effect=[1,3,4]),mock.patch.object(S,'stop_job',side_effect=stop),mock.patch.object(S,'collect_run',side_effect=RuntimeError('disk')),mock.patch.object(S,'_after_run'),mock.patch.object(S,'_write_run_meta'):
            S._waiter(job,mock.Mock(),mock.Mock(),1)
        self.assertEqual(job.status,'stopped')
        job.status='running';job.mode='docker'
        with mock.patch.object(S,'docker',return_value=(0,'')):self.assertEqual(S.stop_job(job.id)['id'],job.id)
        job.mode='local'
        with mock.patch.object(S,'IS_WIN',False),mock.patch.object(S.os,'getpgid',create=True,return_value=1),mock.patch.object(S.os,'killpg',create=True,side_effect=OSError('gone')):
            job.proc.kill.side_effect=OSError('gone');S.stop_job(job.id)
        S.JOBS.pop(job.id,None)

    def test_host_probe_failures_are_reported(self):
        with mock.patch.object(SI,'IS_WIN',False),mock.patch('builtins.open',mock.mock_open(read_data='model name : Test CPU\n')),mock.patch.object(SI.os.path,'exists',return_value=True):self.assertEqual(SI.cpu()['name'],'Test CPU')
        with mock.patch.object(SI,'IS_WIN',False),mock.patch('builtins.open',side_effect=OSError('unavailable')),mock.patch.object(SI.os.path,'exists',return_value=True):self.assertIn('name',SI.cpu())
        with mock.patch.object(SI,'IS_WIN',True),mock.patch.object(SI.platform,'processor',return_value=''):self.assertIn('name',SI.cpu())
        with mock.patch.object(SI,'IS_WIN',False),mock.patch.object(SI.sys,'platform','linux'),mock.patch('builtins.open',side_effect=OSError('unavailable')):self.assertIn('error',SI.memory())
        with mock.patch.object(SI.shutil,'which',return_value=None),mock.patch.object(SI,'IS_WIN',False):self.assertEqual(SI.gpus(),[])
        with mock.patch.object(SI,'run',return_value=(0,'not json')),mock.patch.object(SI.shutil,'which',return_value='docker'):self.assertIn('error',SI.docker_info())
        with mock.patch('backend.paper.latex.engines',side_effect=RuntimeError('unavailable')),mock.patch('backend.providers.local.lms_cli',side_effect=RuntimeError('unavailable')):self.assertEqual(SI.toolchain()['latex'],[])


