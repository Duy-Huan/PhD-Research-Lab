"""Native adapter contracts after owner-authorized vendor retirement.

See docs/qa/test-retirement-native-migration.json. Model/retrieval boundaries are
MOCKED; filesystem and task-contract assertions execute locally. No live claims.
"""
import _env
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from backend.core import config
from backend.providers import research
from backend.research_engines import registry
from backend.research_engines.contracts import EngineTask,EngineFailure,EngineResult


class NativeConformance(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('native-engine-contract')
        self.engine=registry.get('phdlab')

    def task(self,**patches):
        return EngineTask(**({'operation_id':'RR-12345678:S1','project_id':config.data_dir().name,
            'workflow_id':'RR-12345678','step_id':'S1','question':'Compare the supplied evidence',
            'context':'Current constraints and evidence','output_dir':config.data_dir()/'engine-output',
            'capability':'analysis'}|patches))

    def test_common_result_contract_is_versioned_and_contains_actual_full_output(self):
        text='Detailed controlled result. '*100
        events=[]
        with patch.object(research,'app_complete',return_value=text):
            result=self.engine.execute(self.task(),events.append,lambda:False)
        self.assertEqual(EngineResult.model_validate(result.model_dump()),result)
        self.assertEqual(result.schema_version,'1.0')
        self.assertEqual(result.engine,'phdlab')
        self.assertEqual(result.text,text)
        self.assertEqual(''.join(e.data.get('text','') for e in events if e.type=='text_delta'),text)
        self.assertEqual(Path(result.artifact_refs[0]['path']).read_text('utf-8'),text)
        self.assertFalse(self.engine.descriptor.token_streaming)

    def test_common_cancel_before_dispatch_has_no_model_or_filesystem_execution(self):
        with patch.object(research,'app_complete') as model:
            with self.assertRaises(EngineFailure) as caught:
                self.engine.execute(self.task(),lambda e:None,lambda:True)
        self.assertEqual(caught.exception.kind,'cancelled');model.assert_not_called()
        self.assertFalse(self.task().output_dir.exists())

    def test_native_analysis_preserves_exact_context_and_does_not_force_search(self):
        context='Evidence and constraints. '*2000+' FINAL-CONSTRAINT-UNCHANGED'
        question='Explain this result; do not run an experiment. '+('detail '*1000)
        with patch.object(research,'app_complete',return_value='Scoped explanation') as model, \
             patch('backend.knowledge.websearch.search') as search:
            self.engine.execute(self.task(context=context,question=question),lambda e:None,lambda:False)
        self.assertIn(context,model.call_args.args[1])
        self.assertEqual(model.call_args.args[2],question)
        search.assert_not_called()

    def test_literature_outage_is_visible_and_cannot_become_verified_sources(self):
        events=[]
        with patch.object(research,'app_complete',return_value='Sources are unavailable'), \
             patch('backend.knowledge.websearch.search',new=AsyncMock(side_effect=OSError('Controlled outage'))):
            result=self.engine.execute(self.task(capability='literature'),events.append,lambda:False)
        self.assertEqual(result.provenance['retrieval'],'UNAVAILABLE')
        self.assertEqual(result.provenance['sources_count'],0)
        self.assertTrue(any(e.data.get('result')=='UNAVAILABLE' for e in events))
        self.assertFalse((self.task().output_dir/'sources.json').exists())

    def test_output_outside_project_is_refused_before_model_dispatch(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-outside-native-') as folder:
            target=Path(folder)/'forbidden-output'
            with patch.object(research,'app_complete') as model:
                with self.assertRaises(EngineFailure) as caught:self.engine.execute(self.task(output_dir=target),lambda e:None,lambda:False)
            self.assertEqual(caught.exception.kind,'policy');model.assert_not_called()
            self.assertFalse(target.exists())

    def test_deadline_cancels_the_actual_coroutine_instead_of_replaying(self):
        cancelled=[]
        async def slow(*args,**kwargs):
            try:await asyncio.sleep(10)
            finally:cancelled.append(True)
        with patch('backend.providers.models.call_agent',side_effect=slow) as model:
            with self.assertRaises(EngineFailure) as caught:self.engine.execute(self.task(time_limit_s=.02),lambda e:None,lambda:False)
        self.assertEqual(caught.exception.kind,'timeout')
        self.assertEqual(cancelled,[True]);self.assertEqual(model.call_count,1)
        self.assertFalse((self.task().output_dir/'phdlab_research_report.md').exists())

    def test_native_failure_does_not_publish_report_or_completion(self):
        events=[]
        with patch.object(research,'app_complete',side_effect=RuntimeError('Controlled model failure')):
            with self.assertRaises(EngineFailure):self.engine.execute(self.task(),events.append,lambda:False)
        self.assertFalse(any(e.data.get('state')=='completed' for e in events))
        self.assertFalse((self.task().output_dir/'phdlab_research_report.md').exists())


class Contracts(unittest.TestCase):
    def test_schema_versions_and_optional_adapters_keep_existing_boundary(self):
        with self.assertRaises(ValidationError):EngineResult(schema_version='2',engine='phdlab',text='controlled')
        for name in registry.FACTORIES:
            engine=registry.get(name)
            self.assertEqual(engine.descriptor.schema_version,'1.0')
            self.assertEqual(engine.descriptor.skills_owner,'engine')
            self.assertTrue(callable(engine.execute))
        self.assertEqual(registry.plan('auto','analysis'),['phdlab'])
        with self.assertRaises(EngineFailure):registry.plan('auto','prototype',preferred='opencode')
        self.assertEqual(registry.plan('paperorchestra','review'),['paperorchestra'])
        for retired in ('feynman','openscience','collaborative','unknown'):
            with self.assertRaises(EngineFailure):registry.plan(retired,'analysis')


if __name__=='__main__':unittest.main()
