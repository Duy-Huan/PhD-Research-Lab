"""MOCKED transport: real chat state must preserve agent decision authority."""
import json
import time
import unittest
from unittest.mock import patch

import _env
from backend.agent import launch,orchestrator,sessions


class AgentDecisionAuthority(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('agent-decision-authority')

    def session(self):
        return sessions.create('Reasoning fixture',settings={
            'provider':'app:local','mcp_auto':False,'mcp_tools':['-'],
            'summaries':False,'collect_artifacts':False,'memory_mode':'off'})

    def test_plain_language_reaches_agent_without_keyword_workflow_interception(self):
        questions=[
            'How can I run an experiment that would falsify this hypothesis?',
            'Explain how to find papers that contradict the result.',
            'Tìm tài liệu về pruning, rồi cân nhắc có cần thay đổi hướng nghiên cứu không.',
            'Why did the literature review fail? Do not start a new workflow.',
            'Chạy thử ý tưởng này có giúp kiểm tra giả thuyết không?',
        ]
        for question in questions:
            with self.subTest(question=question):
                session=self.session()
                fixture={'id':'RR-unit-fixture','status':'RUNNING','steps':[]}
                with patch.object(orchestrator,'_spawn') as dispatch,patch.object(launch,'from_skill',return_value=fixture) as run:
                    turn=orchestrator.start(session['id'],question)
                self.assertFalse(run.called,'Plain language must not execute a keyword-selected research strategy')
                dispatch.assert_called_once_with(session['id'],turn['id'],'start')
                self.assertEqual(turn['question'],question)
                saved=sessions.get(session['id'])
                self.assertFalse(saved['approvals'],'The agent has not proposed any action yet')
                self.assertFalse(any(m.get('run_id') for m in saved['messages']))

    def test_long_research_request_is_not_rewritten_or_cut_into_keyword_run_arguments(self):
        session=self.session()
        question='Run a quick experiment only after assessing alternatives. '+('Preserve this scientific constraint. '*350)+'END-OF-CONSTRAINTS'
        with patch.object(orchestrator,'_spawn') as dispatch:
            turn=orchestrator.start(session['id'],question)
        dispatch.assert_called_once()
        self.assertEqual(turn['question'],question)
        self.assertTrue(turn['question'].endswith('END-OF-CONSTRAINTS'))
        self.assertFalse(sessions.get(session['id'])['approvals'])

    def test_explicit_slash_command_retains_its_existing_execution_contract(self):
        session=self.session();fixture={'id':'RR-unit-fixture','status':'RUNNING','steps':[]}
        with patch.object(launch,'from_skill',return_value=fixture) as run,patch.object(orchestrator,'_spawn') as dispatch:
            turn=orchestrator.start(session['id'],'/lit a deliberately explicit search')
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0:2],('lit','a deliberately explicit search'))
        dispatch.assert_not_called();self.assertEqual(turn['status'],'completed')

    def test_model_proposed_research_action_waits_for_real_approval(self):
        session=self.session()
        with patch.object(orchestrator,'_spawn'):
            turn=orchestrator.start(session['id'],'Consider the scientific question in this project.')
        block='```phdlab-action\n'+json.dumps({'action':'start_run','args':{'skill':'lit','input':'Contradictory prior art'}})+'\n```'
        with patch.object(launch,'from_skill') as execute:
            orchestrator._complete(session['id'],turn['id'],block,None,time.time(),'')
            execute.assert_not_called()
        actions=sessions.get(session['id'])['approvals']
        self.assertEqual(len(actions),1)
        self.assertEqual((actions[0]['name'],actions[0]['status']),('start_run','pending'))
        self.assertEqual(actions[0]['args']['input'],'Contradictory prior art')


class AgentProfileFidelity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('agent-profile-fidelity')

    def test_scientific_prompt_and_purpose_survive_save_and_reload_without_clipping(self):
        from backend.agent import workflow_architect
        purpose=('Keep null results, controls and rejected hypotheses. '*35)+'PURPOSE-END'
        prompt=('Preserve equation, assumptions and evidence before changing the method. '*90)+'PROMPT-END'
        saved=workflow_architect.save_agent_profile({'id':'fidelity-fixture','name':'Scientific profile fixture',
            'role':'researcher','purpose':purpose,'system_prompt':prompt,'permissions':['read']})
        self.assertEqual(saved['purpose'],purpose)
        self.assertEqual(saved['system_prompt'],prompt)
        persisted=json.loads(workflow_architect._agents_file().read_text(encoding='utf-8'))
        record=next(p for p in persisted if p['id']=='fidelity-fixture')
        self.assertEqual(record['purpose'],purpose)
        self.assertEqual(record['system_prompt'],prompt)


if __name__=='__main__':unittest.main()
