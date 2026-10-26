"""MOCKED vendor/Docker boundaries, real RPC parsing and durable job files.

These contracts do not claim Nous authentication, inference or scientific validation.
Actual container/model observations are recorded separately with exact source hashes.
"""
import _env
import importlib.util
import io
import json
from contextlib import nullcontext
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from types import ModuleType
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from backend.core import config
from backend.providers import hermes
from backend.providers.cli import ProviderError

spec = importlib.util.spec_from_file_location('phdlab_hermes_service_contract',
    _env.ROOT / 'tools/hermes_runtime/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class HermesCatalog(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('hermes-catalog')
        self.state = config.data_dir() / 'rpc-fixture'
        self.addCleanup(patch.stopall)
        patch.object(service, 'STATE', self.state).start()

    def test_free_pricing_requires_both_exact_finite_zero_prices(self):
        prices = [({'prompt': '0', 'completion': '0'}, True),
                  ({'prompt': '0.000', 'completion': 0}, True),
                  ({'prompt': '1e-9999', 'completion': '0'}, False),
                  ({'prompt': '0', 'completion': '0.001'}, False),
                  ({'prompt': False, 'completion': False}, False),
                  ({'prompt': None, 'completion': '0'}, False),
                  ({'prompt': 'NaN', 'completion': '0'}, False),
                  ({'prompt': '-Infinity', 'completion': '0'}, False),
                  ({'prompt': '0'}, False), ([], False), (None, False)]
        rows = [{'id': 'model-'+str(i)+':free', 'pricing': price} for i,(price,_) in enumerate(prices)]
        with patch.object(service, 'nous_credentials', return_value={'base_url': 'https://inference-api.nousresearch.com/v1', 'api_key': 'fixture-only'}), \
             patch.object(service.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'data': rows}).encode())):
            result = service.catalog()
        self.assertEqual([m['free'] for m in result['models']], [free for _,free in prices])
        self.assertFalse(result['inference_verified'])
        self.assertNotIn('fixture-only', (self.state/'catalog.json').read_text('utf-8'))

    def test_credential_origin_is_official_https_without_redirect_credentials(self):
        auth = ModuleType('hermes_cli.auth')
        background = ModuleType('hermes_cli.anon_challenge')
        background.background_caller = nullcontext
        with patch.dict('sys.modules', {'hermes_cli.auth': auth, 'hermes_cli.anon_challenge': background}):
            for base in ('http://inference-api.nousresearch.com/v1', 'https://evil.example/v1',
                         'https://inference-api.nousresearch.com.evil.example/v1',
                         'https://user:secret@inference-api.nousresearch.com/v1',
                         'https://inference-api.nousresearch.com:444/v1',
                         'https://inference-api.nousresearch.com/v1?token=secret'):
                auth.resolve_nous_runtime_credentials = lambda **kw: {'base_url': base, 'api_key': 'fixture-only'}
                with self.subTest(base=base), self.assertRaises(ValueError): service.nous_credentials()
            auth.resolve_nous_runtime_credentials = lambda **kw: {'base_url': 'https://inference-api.nousresearch.com/v1', 'api_key': 'fixture-only'}
            self.assertEqual(service.nous_credentials()['api_key'], 'fixture-only')

    def test_unknown_or_nonzero_priced_model_never_constructs_agent(self):
        jid = 'a'*32
        service.save(service.job_path(jid), {'id': jid, 'status': 'running', 'model': 'paid:free'})
        with patch.object(service.Path, 'read_bytes', return_value=b'controlled-pinned-library'), \
             patch.object(service, 'AGENT_HASH', __import__('hashlib').sha256(b'controlled-pinned-library').hexdigest()), \
             patch.object(service, 'catalog', return_value={'models': [{'id': 'paid:free', 'free': False}]}):
            service.run_agent(jid)
        actual = service.read_job(jid)
        self.assertEqual(actual['status'], 'failed')
        self.assertEqual(actual['error_code'], 'ValueError')
        self.assertNotIn('answer', actual)

    def test_sensitive_vendor_errors_and_prompt_are_not_public(self):
        error = RuntimeError('https://vendor.invalid?token=private-super-secret')
        self.assertEqual(service.error_code(error), 'RuntimeError')
        view = service.public_job({'id':'a'*32, 'prompt':'private prompt', 'tools':['read'], 'answer':'observed'})
        self.assertEqual(view, {'id':'a'*32, 'answer':'observed'})

    def test_history_is_durable_and_reused_without_paid_or_framework_fallback(self):
        calls=[]
        history=[{'role':'user','content':'Synthetic retained context '+('detail '*500)},
                 {'role':'assistant','content':'Fixture answer; not a real model observation'}]
        runtime=ModuleType('run_agent')
        class FixtureAgent:
            def __init__(self,**kwargs):calls.append({'configuration':kwargs})
            def run_conversation(self,**kwargs):
                calls[-1]['conversation']=kwargs
                return {'final_response':'Fixture answer; not live inference','messages':history}
        runtime.AIAgent=FixtureAgent
        common={'session':'b'*32,'status':'running','model':'observed:free','prompt':'Synthetic question',
                'max_iterations':2,'deadline_s':5,'max_tokens':128}
        with patch.dict('sys.modules',{'run_agent':runtime}), \
             patch.object(service.Path,'read_bytes',return_value=b'fixture'), \
             patch.object(service,'AGENT_HASH',__import__('hashlib').sha256(b'fixture').hexdigest()), \
             patch.object(service,'catalog',return_value={'models':[{'id':'observed:free','free':True}]}), \
             patch.object(service,'nous_credentials',return_value={'api_key':'fixture-only','base_url':'https://inference-api.nousresearch.com/v1'}):
            for jid in ('a'*32,'c'*32):
                service.save(service.job_path(jid),{**common,'id':jid})
                service.run_agent(jid)
                self.assertEqual(service.read_job(jid)['status'],'completed')
        self.assertEqual(calls[0]['conversation']['conversation_history'],[])
        self.assertEqual(calls[1]['conversation']['conversation_history'],history)
        self.assertEqual(calls[1]['configuration']['fallback_model'],{})
        self.assertEqual(calls[1]['configuration']['model'],'observed:free')
        self.assertEqual(calls[1]['configuration']['enabled_toolsets'],['memory','skills','web'])
        self.assertIsNone(service.read_job('c'*32)['usage'])
        self.assertNotIn('fixture-only',service.job_path('c'*32).read_text('utf-8'))


class HermesJobProtocol(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('hermes-rpc')
        self.addCleanup(patch.stopall)
        patch.object(service, 'STATE', config.data_dir() / 'rpc-fixture').start()
        patch.dict(service.ACTIVE, {}, clear=True).start()
        # No model worker is invoked. HTTP validation/idempotency and filesystem writes are real.
        self.actual_supervise=service.supervise
        patch.object(service, 'supervise', lambda job: None).start()
        self.server = ThreadingHTTPServer(('127.0.0.1',0), service.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.body = {'id':'a'*32, 'session':'b'*32, 'model':'observed:free', 'prompt':'Controlled private question',
                     'tools':['research_get_current_state'], 'deadline_s':5, 'max_iterations':1, 'max_tokens':128}

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)

    def post(self, value, path='/v1/jobs'):
        request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}'+path,
            data=json.dumps(value).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=5) as response: return response.status, json.load(response)
        except urllib.error.HTTPError as error: return error.code, json.load(error)

    def test_repeated_job_is_idempotent_and_does_not_rewrite_durable_record(self):
        first, body = self.post(self.body)
        self.assertEqual(first, 202)
        self.assertNotIn('prompt', body)
        before = service.job_path(self.body['id']).read_bytes()
        self.assertEqual(self.post(self.body)[0], 200)
        self.assertEqual(service.job_path(self.body['id']).read_bytes(), before)

    def test_changed_prompt_model_permissions_or_budgets_conflict(self):
        self.assertEqual(self.post(self.body)[0], 202)
        before = service.job_path(self.body['id']).read_bytes()
        for key,value in (('prompt','another'), ('model','other:free'), ('session','c'*32),
                          ('tools',['sandbox_run_code']), ('deadline_s',6), ('max_iterations',2), ('max_tokens',129)):
            with self.subTest(field=key): self.assertEqual(self.post({**self.body,key:value})[0],409)
        self.assertEqual(service.job_path(self.body['id']).read_bytes(), before)

    def test_one_project_job_at_a_time_preserves_memory_and_skills(self):
        self.assertEqual(self.post(self.body)[0],202)
        self.assertEqual(self.post({**self.body,'id':'c'*32})[0],409)
        self.assertFalse(service.job_path('c'*32).exists())

    def test_invalid_identity_types_tools_and_budget_are_rejected_before_admission(self):
        for key,value in (('id','../secret'), ('session','outside'), ('prompt',''), ('model','bad model'),
                          ('deadline_s',True), ('deadline_s',1801), ('max_tokens',127), ('max_iterations',0),
                          ('tools',['../../host']), ('tools','read'), ('unknown','value')):
            with self.subTest(field=key,value=value): self.assertEqual(self.post({**self.body,key:value})[0],400)
        self.assertEqual(self.post([])[0],400)
        self.assertFalse(service.job_path(self.body['id']).exists())

    def test_cancel_before_worker_spawn_prevents_model_execution(self):
        self.assertEqual(self.post(self.body)[0],202)
        code, body = self.post({}, '/v1/jobs/'+self.body['id']+'/cancel')
        self.assertEqual((code,body['status']), (200,'cancelled'))
        with patch.object(service.subprocess,'Popen') as spawn:
            self.actual_supervise(self.body)
            self.assertEqual(service.read_job(self.body['id'])['status'],'cancelled')
            spawn.assert_not_called()
            self.assertNotIn(self.body['id'],service.ACTIVE)

    def test_cancel_missing_job_is_not_completion(self):
        self.assertEqual(self.post({}, '/v1/jobs/'+'a'*32+'/cancel')[0],404)


class HermesBoundary(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('hermes-boundary')

    def test_runtime_profile_is_not_a_path_and_no_host_source_is_mounted(self):
        for profile in ('../host','C:/Windows','admin'):
            with self.assertRaises(ProviderError): hermes.folder(profile)
        path = hermes.folder('review')
        self.assertTrue(path.is_relative_to(config.data_dir()))
        dockerfile = (_env.ROOT/'tools/hermes_runtime/Dockerfile').read_text('utf-8')
        self.assertIn('@sha256:',dockerfile)
        self.assertNotIn('COPY . ',dockerfile)

    def test_rpc_refuses_nonloopback_publish_before_sending_credentials(self):
        plan={'owner':hermes._owner('review'),'adapter_sha256':hermes.adapter_digest(),'proxy':'a'*64,'image':'pinned','rpc_token':'private'}
        with patch.object(hermes,'_read',return_value=plan), \
             patch.object(hermes,'_inspect',return_value={'NetworkSettings':{'Ports':{'8080/tcp':[{'HostIp':'0.0.0.0','HostPort':'9000'}]}}}), \
             patch.object(hermes.urllib.request,'build_opener') as network:
            with self.assertRaisesRegex(ProviderError,'loopback'):hermes.rpc('/v1/health')
            network.assert_not_called()

    def test_error_payload_list_and_vendor_secret_are_safely_normalized(self):
        plan={'owner':hermes._owner('review'),'adapter_sha256':hermes.adapter_digest(),'proxy':'a'*64,'image':'pinned','rpc_token':'private'}
        for body in ([], {'state':'UNAVAILABLE','detail':'private-secret'}, {'state':'UNAVAILABLE','error_code':[]},
                     {'state':'AUTH_REQUIRED','error_code':'nous_auth_missing'}):
            error=urllib.error.HTTPError('http://127.0.0.1',503,'unavailable',{},io.BytesIO(json.dumps(body).encode()))
            with patch.object(hermes,'_read',return_value=plan), \
                 patch.object(hermes,'_inspect',return_value={'NetworkSettings':{'Ports':{'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'9000'}]}}}), \
                 patch.object(hermes.urllib.request,'build_opener') as network:
                network.return_value.open.side_effect=error
                with self.assertRaises(ProviderError) as caught:hermes.rpc('/v1/health')
                self.assertNotIn('private-secret',str(caught.exception))

    def test_model_config_cannot_enable_paid_fallback_or_escape_budget(self):
        result=config.save_config({'hermes':{'free_only':False,'deadline_s':9999,'max_tokens':100000,'max_iterations':1000}})
        self.assertTrue(result['hermes']['free_only'])
        self.assertEqual(result['hermes']['deadline_s'],1800)
        self.assertEqual(result['hermes']['max_tokens'],16384)
        self.assertEqual(result['hermes']['max_iterations'],50)
        with self.assertRaises(ValueError):config.save_config({'hermes':{'model':'model with spaces'}})


if __name__ == '__main__':unittest.main()
