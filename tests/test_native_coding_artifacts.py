"""Real project files and gateway state; vendor transports are explicit software fixtures."""
import _env
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.core import config
from backend.providers import cli, gateway, research


class CodingArtifacts(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('coding-artifacts')
        self.workspace=config.data_dir()/'provider-workspace';self.workspace.mkdir()
        self.output=config.data_dir()/'collected-results'

    def test_changed_outputs_are_collected_and_existing_files_are_preserved(self):
        old=self.workspace/'previous.py';old.write_text('previous = True','utf-8')
        before=research._snapshot(self.workspace)
        new=self.workspace/'result.py';new.write_text('measured = 42','utf-8')
        self.assertEqual(research._collect(self.workspace,before,self.output),['result.py'])
        self.assertEqual((self.output/'result.py').read_text('utf-8'),'measured = 42')
        self.assertFalse((self.output/'previous.py').exists())
        self.assertEqual(old.read_text('utf-8'),'previous = True')

    def test_link_to_another_project_cannot_be_exported_as_a_research_artifact(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-other-output-') as folder:
            outside=Path(folder);(outside/'private.py').write_text('private fixture','utf-8')
            _env.directory_link(outside,self.workspace/'outside')
            with self.assertRaises(ValueError):research._collect(self.workspace,{},self.output)
            self.assertFalse((self.output/'outside/private.py').exists())

    def test_output_destination_outside_paper_project_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-outside-destination-') as folder:
            target=Path(folder)/'must-not-write'
            (self.workspace/'result.py').write_text('result = 1')
            with self.assertRaises(research.ProviderUnavailable):research._collect(self.workspace,{},target)
            self.assertFalse(target.exists())

    def test_artifact_count_limit_never_silently_truncates_or_deletes_originals(self):
        for i in range(201):(self.workspace/f'result-{i:03d}.py').write_text('result = 1')
        with self.assertRaisesRegex(research.ProviderUnavailable,'200files'):
            research._collect(self.workspace,{},self.output)
        self.assertEqual(len(list(self.workspace.glob('*.py'))),201)
        self.assertFalse(self.output.exists())

    def test_large_artifact_stays_in_workspace_without_unbounded_copy(self):
        source=self.workspace/'large.json'
        with source.open('wb') as stream:stream.truncate(32*1024*1024+1)
        with self.assertRaisesRegex(research.ProviderUnavailable,'byte budget'):
            research._collect(self.workspace,{},self.output)
        self.assertTrue(source.exists());self.assertFalse(self.output.exists())


class FixtureConnector(cli.ProviderConnector):
    provider_id='codex';label='Controlled coding fixture'
    def health(self,fresh=False):return {'state':'CONNECTED','detail':'Mocked vendor boundary'}
    def capabilities(self):return {'send':True,'cancel':True}
    def cancel(self,rid):return {'cancelled':True}


class CodingGateway(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project('coding-gateway')

    def test_session_identity_collision_cannot_overwrite_an_existing_conversation(self):
        folder=config.data_dir()/'gateway/sessions';folder.mkdir(parents=True)
        original=folder/'gs-aaaaaaaa.json';original.write_text('{"prior":"preserve this history"}','utf-8')
        before=original.read_bytes()
        with patch.object(gateway.secrets,'token_hex',side_effect=['aaaaaaaa','bbbbbbbb']):
            sid=gateway._session()
        self.assertEqual(sid,'gs-bbbbbbbb')
        self.assertEqual(original.read_bytes(),before)
        self.assertTrue((folder/'gs-bbbbbbbb.json').is_file())

    def test_coding_task_uses_gateway_and_returns_the_actual_project_output(self):
        class Fixture(FixtureConnector):
            def stream_message(self,message,context):
                (Path(context['cwd'])/'result.py').write_text('observed = 42','utf-8')
                yield {'type':'text_delta','text':'Controlled output'}
                yield {'type':'request_completed','exit_code':0}
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            result=research.run_coding('owned-step','codex','Create the controlled output','Scoped context',config.data_dir()/'outputs')
        self.assertEqual(result['text'],'Controlled output')
        self.assertIn('result.py',result['files'])
        self.assertEqual((config.data_dir()/'outputs/result.py').read_text('utf-8'),'observed = 42')
        self.assertEqual(gateway.get(result['gateway_request_id'])['status'],'completed')
        self.assertTrue(Path(result['workspace']).is_relative_to(config.data_dir()))

    def test_partial_answer_with_error_cannot_become_a_completed_research_step(self):
        class Fixture(FixtureConnector):
            def stream_message(self,message,context):
                yield {'type':'text_delta','text':'Retained partial observation'}
                yield {'type':'error','message':'Controlled provider quota failure'}
                yield {'type':'request_completed','exit_code':1}
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            with self.assertRaisesRegex(research.ProviderUnavailable,'quota'):
                research.run_coding('failing-step','codex','Controlled question','',config.data_dir()/'outputs')
        records=list((config.data_dir()/'gateway/requests').glob('gw-*.json'))
        self.assertEqual(len(records),1)
        import json
        actual=json.loads(records[0].read_text('utf-8'))
        self.assertEqual(actual['status'],'failed')
        self.assertEqual(actual['answer'],'Retained partial observation')
        self.assertFalse((config.data_dir()/'outputs').exists())

    def test_native_materialization_uses_actual_file_bytes_and_keeps_experiment_path_once(self):
        from backend.agent import runs
        from backend.execution import code_projects
        record=runs.create('code','Controlled materialization','Keep the actual code',
            {'task':'Keep the actual code','code_project_id':code_projects.active()['id']},
            risk=2,provider='codex',start=False,force_approval=True)
        runs.update(record['id'],lambda item:item['approval'].update(status='approved'))
        ctx=runs.Ctx(record['id'],record['steps'][0])
        name='experiments/'+record['id']+'/train.py'
        def collected(*args):
            destination=ctx.out/'codex'/name;destination.parent.mkdir(parents=True)
            destination.write_bytes(b'actual_bytes = 42\r\n')
            return {'text':f'```python path={name}\nstale_narration = 0\n```\n```phdlab-run\npython {name}\n```',
                    'files':[name],'gateway_request_id':'controlled-fixture'}
        with patch.object(research,'pick',return_value=('codex','')),patch.object(research,'run_coding',side_effect=collected),patch('backend.execution.gitops.commit'):
            result=runs._code(ctx)['result']
        self.assertEqual(result['files'],[name])
        actual=code_projects.active_dir()/name
        self.assertEqual(actual.read_bytes(),b'actual_bytes = 42\r\n')
        import hashlib
        self.assertEqual(result['sha256'][name],hashlib.sha256(actual.read_bytes()).hexdigest())
        self.assertFalse((code_projects.active_dir()/f'experiments/{record["id"]}/experiments').exists())


if __name__=='__main__':unittest.main()
