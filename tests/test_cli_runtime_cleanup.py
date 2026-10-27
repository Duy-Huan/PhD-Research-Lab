"""Real protocol processes, mocked Docker transport; actual Docker proof is separate."""
import sys
import json
import unittest
from unittest.mock import patch

import _env
from backend.providers import cli, isolated_cli
from backend.core import config

OWNER='a'*32


class RuntimeCleanup(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('runtime-cleanup-'+self._testMethodName[-12:])
        self.addCleanup(lambda:cli._last_error.pop('codex',None))

    def connector(self):
        class Fixture(cli.CodexConnector):
            def binary(self):return sys.executable
            def process_argv(self,args,context):
                context['_runtime_owner']=OWNER
                return args
            def _probe(self):
                return {'bin':sys.executable,'ok':True,'login_code':0,'login':'Logged in using ChatGPT'}
            def argv(self,context):
                records=[{'type':'item.completed','item':{'type':'agent_message','text':'Complete'}},
                         {'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}]
                return [sys.executable,'-c','import sys,json,time;sys.stdin.read();records='+repr(records)+
                        ';[print(json.dumps(r),flush=True) for r in records];time.sleep(1)']
        return Fixture()

    def test_completed_turn_releases_owned_runtime_before_reporting_completion(self):
        resources={OWNER:'running','another-request':'running'}
        with patch.object(isolated_cli,'cleanup_owned_runtime',create=True,
                          side_effect=lambda owner:resources.pop(owner)) as cleanup:
            events=self.connector().stream_message('Controlled protocol only',{})
            observed=[]
            for event in events:
                if event['type']=='request_completed':self.assertNotIn(OWNER,resources)
                observed.append(event)
            self.assertTrue(any(e['type']=='request_completed' and e['exit_code']==0 for e in observed))
            cleanup.assert_called_once_with(OWNER)
        self.assertEqual(resources,{'another-request':'running'})

    def test_consumer_close_releases_its_runtime_without_touching_other_requests(self):
        with patch.object(isolated_cli,'cleanup_owned_runtime',create=True) as cleanup:
            stream=self.connector().stream_message('Controlled process',{})
            self.assertEqual(next(stream)['type'],'request_started')
            stream.close()
            cleanup.assert_called_once_with(OWNER)

    def test_cleanup_failure_cannot_be_reported_as_a_successful_request(self):
        with patch.object(isolated_cli,'cleanup_owned_runtime',create=True,side_effect=OSError('Controlled cleanup outage')):
            events=list(self.connector().stream_message('Controlled failure',{}))
        self.assertTrue(any(e['type']=='error' and 'cleanup' in e.get('message','').lower() for e in events))
        self.assertFalse(any(e['type']=='request_completed' and e['exit_code']==0 for e in events))

    def test_docker_cleanup_uses_exact_owned_label_and_volume_only(self):
        calls=[];owned='b'*64
        def docker(*args,**kwargs):
            calls.append(args)
            return owned if len(calls)==1 else ''
        with patch.object(isolated_cli,'docker',side_effect=docker), \
             patch.object(isolated_cli.subprocess,'run') as run:
            isolated_cli.cleanup_owned_runtime(OWNER)
        self.assertIn(('ps','-aq','--filter','label=phdlab.cli='+OWNER),calls)
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [['docker','rm','-f',owned],['docker','volume','rm','phdlab-cli-ipc-'+OWNER]])

    def test_invalid_owner_cannot_start_docker_operations(self):
        with patch.object(isolated_cli,'docker') as docker,patch.object(isolated_cli.subprocess,'run') as run:
            with self.assertRaises(ValueError):isolated_cli.cleanup_owned_runtime('other; arbitrary')
            docker.assert_not_called();run.assert_not_called()

    def test_native_launch_shares_a_fresh_owner_with_the_runtime_wrapper(self):
        plan=config.data_dir()/'runtime-plan.json';plan.write_text('{}',encoding='utf-8')
        context={'cwd':str(config.data_dir()/'workspace')}
        with patch.object(isolated_cli,'prepare',return_value={'state':'PREPARED','plan':str(plan)}), \
             patch.object(cli.CodexConnector,'_prefix',return_value=['codex']):
            argv=cli.CodexConnector().process_argv(['codex','exec','-'],context)
        self.assertRegex(context['_runtime_owner'],r'^[a-f0-9]{32}$')
        self.assertEqual(argv[-2:],['--runtime-owner',context['_runtime_owner']])
        self.assertEqual(json.loads(plan.read_text(encoding='utf-8'))['command'],['codex','exec','-'])

    def test_remaining_owned_resource_is_a_cleanup_failure(self):
        owned='b'*64
        with patch.object(isolated_cli,'docker',side_effect=[owned,owned,'']), \
             patch.object(isolated_cli.subprocess,'run'):
            with self.assertRaisesRegex(ValueError,'cleanup did not complete'):
                isolated_cli.cleanup_owned_runtime(OWNER)

    def test_unexpected_resource_count_is_bounded_and_never_bulk_deleted(self):
        with patch.object(isolated_cli,'docker',return_value='\n'.join(['b'*64,'c'*64,'d'*64])), \
             patch.object(isolated_cli.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'resource count'):
                isolated_cli.cleanup_owned_runtime(OWNER)
            run.assert_not_called()

    def test_protocol_fixture_does_not_require_a_vendor_cli_on_path(self):
        from backend.execution.tools import _cache
        config.save_config({'codex':{'binary':''}})
        key='gw:codex:None';previous=_cache.get(key)
        with patch.object(cli,'which',return_value=None), \
             patch.object(isolated_cli,'cleanup_owned_runtime') as cleanup:
            try:
                self.assertEqual(cli.CodexConnector().health(fresh=True)['state'],'UNAVAILABLE')
                events=list(self.connector().stream_message('Python protocol fixture, no vendor CLI',{}))
            finally:
                if previous is None:_cache.pop(key,None)
                else:_cache[key]=previous
        self.assertTrue(any(e['type']=='request_completed' and e['exit_code']==0 for e in events))
        cleanup.assert_called_once_with(OWNER)


if __name__=='__main__':unittest.main()
