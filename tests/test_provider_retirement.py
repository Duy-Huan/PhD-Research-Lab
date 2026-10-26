"""Native migration contracts. Controlled fixtures are not live model qualification."""
import asyncio
import json
import os
import time
from pathlib import Path
import unittest
from unittest.mock import patch

import _env
from backend.agent import AIWSError, skills
from backend.core import config
from backend.providers import registry as providers, research
from backend.research_engines import registry, workspaces
from backend.research_engines.contracts import EngineTask, EngineFailure


class NativeRetirement(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('native-retirement')

    def test_retired_dispatch_is_absent_and_default_is_native(self):
        self.assertFalse({'feynman', 'openscience', 'opencode', 'clearml'} & registry.FACTORIES.keys())
        self.assertFalse({'feynman', 'openscience', 'opencode', 'clearml'} & research.CATALOG.keys())
        self.assertIn('paperorchestra', registry.FACTORIES)
        self.assertEqual(registry.get('paperorchestra').descriptor.id, 'paperorchestra')
        self.assertIn('paperorchestra', research.CATALOG)
        self.assertFalse(hasattr(research, 'run_feynman'))
        self.assertEqual(registry.plan('auto', 'literature'), ['phdlab'])
        for name in ('feynman', 'openscience', 'opencode', 'clearml'):
            with self.assertRaises(EngineFailure): registry.get(name)
            with self.assertRaises(EngineFailure): registry.plan(name, 'literature')

    def test_native_skills_preserve_literature_and_review(self):
        for name in ('lit', 'deepresearch', 'compare', 'science'):
            self.assertEqual(skills.get(name)['provider'], 'phdlab')
        for name in ('feynman', 'openscience', 'opencode'):
            with self.assertRaises(AIWSError): skills.get(name)

    def test_saved_retired_config_is_migrated_without_executing_it(self):
        raw = json.loads(config.CONFIG_PATH.read_text())
        raw.update(openscience={'enabled': True, 'token': 'controlled-old-secret'},
                   opencode={'enabled':True, 'old_session':'retained-session'},
                   clearml={'enabled':True, 'old_task':'retained-task'},
                   research_providers={'engine_mode': 'collaborative', 'engine_priority': ['feynman', 'openscience']})
        config.CONFIG_PATH.write_text(json.dumps(raw))
        migrated = config.load_config()
        self.assertNotIn('openscience', migrated)
        self.assertNotIn('opencode', migrated)
        self.assertNotIn('clearml', migrated)
        self.assertEqual(migrated['research_providers']['engine_mode'], 'phdlab')
        self.assertEqual(migrated['research_providers']['engine_priority'], ['phdlab'])
        self.assertEqual(json.loads(config.CONFIG_PATH.read_text())['openscience']['token'], 'controlled-old-secret')
        config.save_config({'ui':{'language':'en'}})
        persisted=json.loads(config.CONFIG_PATH.read_text())
        self.assertEqual(persisted['opencode']['old_session'],'retained-session')
        self.assertEqual(persisted['clearml']['old_task'],'retained-task')
        with self.assertRaises(ValueError): config.save_config({'openscience': {'enabled': True}})

    def test_native_output_is_complete_and_advertises_actual_execution(self):
        engine = registry.get('phdlab')
        text = 'Controlled full native response. ' * 70
        events = []
        async def search(*args): return {'sources': []}
        task = EngineTask(operation_id='RR-12345678:S1', attempt=1, project_id='fixture', workflow_id='wf',
                          step_id='S1', question='Compare supplied research evidence', capability='literature',
                          output_dir=config.data_dir() / 'native-output')
        with patch.object(research, 'app_complete', return_value=text), patch('backend.knowledge.websearch.search', search):
            result = engine.execute(task, events.append, lambda: False)
        self.assertEqual(result.text, text)
        self.assertEqual(''.join(e.data.get('text', '') for e in events if e.type == 'text_delta'), text)
        self.assertFalse(engine.descriptor.token_streaming)
        self.assertEqual(result.provenance['workflow'], 'native-role-response')
        self.assertEqual(Path(result.artifact_refs[0]['path']).read_text(encoding='utf-8'), text)

    def test_native_cancellation_and_empty_answer_do_not_publish_completion(self):
        engine = registry.get('phdlab')
        task = EngineTask(operation_id='RR-12345678:S1', attempt=1, project_id='fixture', workflow_id='wf',
                          step_id='S1', question='Review', capability='review', output_dir=config.data_dir() / 'cancel-output')
        with patch.object(research, 'app_complete') as model:
            with self.assertRaises(EngineFailure): engine.execute(task, lambda e: None, lambda: True)
            model.assert_not_called()
        with patch.object(research, 'app_complete', return_value=''):
            with self.assertRaises(EngineFailure): engine.execute(task, lambda e: None, lambda: False)
        self.assertFalse((task.output_dir / 'phdlab_review_report.md').exists())

    def test_retired_api_mutations_are_gone_and_history_is_read_only(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.api import research_engines, system
        app = FastAPI(); app.include_router(research_engines.router); app.include_router(system.router)
        folder = config.data_dir() / 'research-engines' / 'jobs'; folder.mkdir(parents=True)
        jid = 'ej-' + 'a' * 20
        (folder / (jid + '.json')).write_text(json.dumps({'id': jid, 'engine': 'openscience', 'token': 'never-return'}))
        with TestClient(app) as client:
            history = client.get('/api/research-engines/jobs/' + jid)
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json()['engine'], 'openscience')
            self.assertNotIn('never-return', history.text)
            for suffix in ('decisions', 'cancel', 'recover-admission'):
                self.assertEqual(client.post('/api/research-engines/jobs/' + jid + '/' + suffix, json={}).status_code, 410)
            for retired in ('feynman', 'openscience', 'opencode', 'clearml'):
                self.assertEqual(client.post('/api/providers/' + retired + '/launch', json={}).status_code, 404)

    def test_native_workspace_sync_and_historical_identity_survive(self):
        from backend.knowledge import research_store as store
        topic = store.save_topic(store.TopicInput(title='Native fixture'))
        workspace = workspaces.link(topic['id'], workspaces.WorkspaceInput(engine='phdlab'))
        file = Path(workspace['path']) / 'experiment.py'
        file.write_text('print(42)')
        self.assertFalse(workspaces.sync(workspace['id'])['complete'], 'A file still being written cannot be evidence of a complete scan')
        os.utime(file, (time.time()-20, time.time()-20))
        report = workspaces.sync(workspace['id'])
        self.assertTrue(report['complete'])
        self.assertTrue(workspaces.artifacts(topic['id']))
        for retired in ('feynman', 'openscience'):
            with self.assertRaises(ValueError): workspaces.WorkspaceInput(engine=retired)

    def test_legacy_workspace_relink_preserves_producer_without_reactivation(self):
        from backend.knowledge import research_store as store
        from fastapi.testclient import TestClient
        from backend.app import app
        topic=store.save_topic(store.TopicInput(title='Retained legacy files'))
        workspace=workspaces.link(topic['id'],workspaces.WorkspaceInput(engine='phdlab'))
        original=Path(workspace['path'])/'old.txt';original.write_text('Historical, unverified','utf-8')
        with store.db() as connection:
            connection.execute('UPDATE workspaces SET engine=? WHERE id=?',('openscience',workspace['id']))
        relocated=Path(workspace['path']).parent/'located-history';relocated.mkdir()
        (relocated/'old.txt').write_bytes(original.read_bytes())
        client=TestClient(app,headers={'X-PhDLab-Client':'ui'})
        with patch('subprocess.Popen',side_effect=AssertionError('Relink must never launch software')):
            response=client.put('/api/research/workspaces/'+workspace['id'],
                                 json={'path':str(relocated),'engine':'openscience'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['engine'],'openscience')
            self.assertEqual(response.json()['id'],workspace['id'])
            self.assertEqual(workspaces.open_workspace(workspace['id'])['status'],'retired')
            refused=client.put('/api/research/workspaces/'+workspace['id'],
                               json={'path':str(relocated),'engine':'phdlab'})
            self.assertEqual(refused.status_code,400,refused.text)
        self.assertEqual(workspaces.get(workspace['id'])['engine'],'openscience')
        self.assertEqual(original.read_bytes(),(relocated/'old.txt').read_bytes())

    def test_cli_descriptor_keeps_install_auth_isolation_and_inference_distinct(self):
        from backend.providers import cli, isolated_cli
        conn = cli.CONNECTORS['antigravity']
        with patch.object(conn, 'health', return_value={'state': 'UNKNOWN', 'detail': 'metadata only'}), \
             patch.object(conn, 'binary', return_value='C:/controlled/agy.exe'), \
             patch.object(conn, 'capabilities', return_value={'send': True, 'cancel': True}), \
             patch.object(isolated_cli, 'runtime_status', return_value={'state': 'BLOCKED', 'verified': False, 'detail': 'No verified Linux runtime'}):
            descriptor = providers.describe('cli:antigravity')
        self.assertEqual(descriptor['provider_id'], 'cli:antigravity')
        self.assertFalse(descriptor['available'])
        self.assertEqual(descriptor['readiness']['installation'], 'INSTALLED')
        self.assertEqual(descriptor['readiness']['authentication'], 'UNKNOWN')
        self.assertEqual(descriptor['readiness']['isolation'], 'BLOCKED')
        self.assertEqual(descriptor['readiness']['inference'], 'NOT_RUN')
        self.assertEqual(descriptor['model_catalog']['origin'], 'unavailable')
        self.assertEqual(descriptor['model_catalog']['models'], [])


if __name__ == '__main__': unittest.main()
