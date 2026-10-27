"""MOCKED artifact/policy fixtures; no model or product acceptance is asserted."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

from devtools.verification.uat_gate import validate_manifest
from devtools.verification.uat_journeys import JOURNEYS, CHECKS, CHAT_PROMPT, allowed_write, task, execution_key


def write_fixture(folder, journey='settings-language', source='source'):
    folder.mkdir(parents=True, exist_ok=True)
    def chunk(kind, data):
        return struct.pack('!I', len(data))+kind+data+struct.pack('!I', zlib.crc32(kind+data)&0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('!2I5B', 640, 480, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress((b'\0'+b'\xff'*1920)*480))+chunk(b'IEND', b'')
    (folder/'final.png').write_bytes(png)
    with zipfile.ZipFile(folder/'trace.zip', 'w') as archive:
        archive.writestr('trace.trace', '{"fixture":true}')
    payloads = {'agent-history.json': {'history': [{'fixture': True, 'journey':journey}]},
                'agent-result.json': {'journey': journey, 'source_sha256': source, 'ai_success': True, 'steps': 3,
                    'mode':'REAL_LOCAL','adapter':'browser-use','version':'UNIT_FIXTURE','model_requested':'spark-x2.5-4b'},
                'browser-evidence.json': {'journey': journey, 'source_sha256': source, 'confirmation': 'PASS',
                    'oracle_version': 1, 'checks': [{'id': 'fixture-only', 'passed': True}], 'events': []}}
    for name, value in payloads.items():
        (folder/name).write_text(json.dumps(value), encoding='utf-8')
    return [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir())]


class JourneyEvidence(unittest.TestCase):
    def test_individually_packaged_runs_keep_review_pending_and_require_each_journey(self):
        from scripts.package_uat_evidence import collect_reports
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);reports=[]
            for journey in JOURNEYS:
                run=root/journey;folder=run/'uat';write_fixture(folder,journey)
                browser=folder/'browser-evidence.json';data=json.loads(browser.read_text())
                data['checks']=[{'id':key,'passed':True} for key in sorted(CHECKS[journey])]
                browser.write_text(json.dumps(data))
                (folder/'uat-report.json').write_text(json.dumps({'journey':journey,'decision':'PASS','mode':'REAL_LOCAL',
                    'deterministic_confirmation':'PASS','source_sha256':'source','scope':'MOCKED packaging fixture only'}))
                report=run/'report.json';report.write_text(json.dumps({'profile':'uat','decision':'PASS','source_stable':True,
                    'source':{'sha256':'source'},'head_sha':'head'}));reports.append(report)
            manifest,content=collect_reports(reports,'source','head')
            self.assertEqual(manifest['review']['status'],'PENDING')
            out=root/'package';out.mkdir()
            for name,raw in content.items():
                p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            path=out/'manifest.json';path.write_text(json.dumps(manifest))
            policy={'required':True,'journeys':list(JOURNEYS),'independent_review':True}
            self.assertIn('Independent critical acceptance review is pending',validate_manifest(path,'source',policy))
            self.assertEqual(validate_manifest(path,'source',{**policy,'independent_review':False}),[])
            with self.assertRaisesRegex(ValueError,'duplicate'):collect_reports([reports[0],reports[0]],'source','head')
            with self.assertRaisesRegex(ValueError,'exact head'):collect_reports(reports,'source','other-head')
            agent_path=reports[0].parent/'uat/agent-result.json';agent=json.loads(agent_path.read_text())
            for patch in [{'mode':'MOCKED'},{'status':'BLOCKED'},{'steps':True},{'adapter':'fixture'}]:
                agent_path.write_text(json.dumps({**agent,**patch}))
                with self.assertRaises(ValueError):collect_reports(reports,'source','head')
            agent_path.write_text(json.dumps(agent))
            (out/'journeys/project-and-chat/agent-history.json').write_text('{}')
            self.assertTrue(validate_manifest(path,'source',{**policy,'independent_review':False}))

    def test_expected_fault_phase_cannot_hide_unrelated_errors(self):
        from devtools.verification.uat_gate import unexpected_events
        fault={'id':'UAT-CONFIG-503','method':'GET','path':'/api/config','status':503}
        good={'expected_fault_id':'UAT-CONFIG-503','path':'/api/config','kind':'http','status':503}
        unrelated={'phase':'EXPECTED_FAULT_INJECTION','kind':'pageerror','text':'real app exception'}
        self.assertEqual(unexpected_events({'controlled_fault':fault,'events':[good,unrelated]}),[unrelated])
        self.assertEqual(unexpected_events({'events':[good]}),[good])
        self.assertEqual(unexpected_events({'controlled_fault':None,'events':[unrelated]}),[unrelated])

    def test_one_settings_run_cannot_qualify_three_unexecuted_journeys(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            artifacts=write_fixture(folder)
            data={'decision':'PASS','mode':'REAL_LOCAL','source_sha256':'source',
                  'verified_journeys':['settings-language','project-and-chat','workflow-operations','failure-recovery'],
                  'artifacts':artifacts,'review':{'status':'APPROVED'}}
            path=folder/'manifest.json';path.write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(validate_manifest(path,'source',{'required':True,'journeys':data['verified_journeys'],'independent_review':True}),
                            'A settings action history must not qualify copied journey names')

    def test_raw_journey_identity_must_match_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);artifacts=write_fixture(folder,journey='failure-recovery')
            data={'decision':'PASS','mode':'REAL_LOCAL','source_sha256':'source','verified_journeys':['settings-language'],
                  'artifacts':artifacts,'review':{'status':'APPROVED'}}
            path=folder/'manifest.json';path.write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(validate_manifest(path,'source',{'required':True,'journeys':['settings-language'],'independent_review':True}))


    def test_false_deterministic_assertion_cannot_be_overridden_by_ai_success(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);artifacts=write_fixture(folder)
            browser=folder/'browser-evidence.json';data=json.loads(browser.read_text())
            data['checks']=[{'id':'persisted-state','passed':False}];browser.write_text(json.dumps(data))
            artifacts=[{**a,'sha256':hashlib.sha256((folder/a['path']).read_bytes()).hexdigest()} for a in artifacts]
            data={'decision':'PASS','mode':'REAL_LOCAL','source_sha256':'source','verified_journeys':['settings-language'],
                  'artifacts':artifacts,'review':{'status':'APPROVED'}}
            path=folder/'manifest.json';path.write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(validate_manifest(path,'source',{'required':True,'journeys':['settings-language'],'independent_review':True}))


class JourneyCapabilities(unittest.TestCase):
    def test_settings_task_identity_cannot_evade_exhausted_original_budget(self):
        self.assertEqual(execution_key('settings-language',None),'TASK-UAT-LOCAL-ADAPTER')
        for key in ['FQC-UAT-JOURNEYS-001','fresh-task']:
            with self.assertRaises(ValueError):execution_key('settings-language',key)
        for journey in JOURNEYS[1:]:
            self.assertEqual(execution_key(journey,'FQC-UAT-JOURNEYS-001'),'FQC-UAT-JOURNEYS-001')
            with self.assertRaises(ValueError):execution_key(journey,'fresh-task')

    def test_mission_review_note_schema_remains_strict(self):
        import _env  # noqa: F401 -- disposable backend state before API imports
        from backend.api.research import ReviewNote
        self.assertEqual(ReviewNote.model_validate({'note':'Technical fixture review'}).note,'Technical fixture review')
        with self.assertRaises(ValueError):ReviewNote.model_validate({'note':'Technical fixture review','decision':'accept'})
        from fastapi.testclient import TestClient
        from backend.app import app
        response=TestClient(app).post('/api/research/topics/missing/missions/missing/review',
            json={'note':'Technical fixture review','decision':'accept'})
        self.assertEqual(response.status_code,422)
        self.assertTrue(any(error['loc'][-1]=='decision' and error['type']=='extra_forbidden' for error in response.json()['detail']))

    def test_project_capability_rejects_paths_provider_overrides_and_unknown_sessions(self):
        lease={'project_name':'UAT owned','in_owned_project':True,'session_ids':['owned']}
        self.assertTrue(allowed_write('project-and-chat','POST','/api/projects',{'name':'UAT owned'},lease))
        self.assertFalse(allowed_write('project-and-chat','POST','/api/projects',{'name':'UAT owned','data_dir':'C:/private'},lease))
        self.assertFalse(allowed_write('project-and-chat','POST','/api/projects/open',{'data_dir':'C:/private'},lease))
        self.assertTrue(allowed_write('project-and-chat','POST','/api/chat/sessions/owned/turns',{'text':CHAT_PROMPT,'overrides':{}},lease))
        for path,body in [('/api/chat/sessions/foreign/turns',{'text':CHAT_PROMPT}),
                          ('/api/chat/sessions/owned/turns',{'text':CHAT_PROMPT,'overrides':{'provider':'app:openai'}}),
                          ('/api/chat/sessions/owned/turns',{'text':'Use a terminal'}),
                          ('/api/terminal/execute',{'command':'echo unsafe'})]:
            self.assertFalse(allowed_write('project-and-chat','POST',path,body,lease))
        self.assertFalse(allowed_write('project-and-chat','POST','/api/chat/sessions/owned/turns',{'text':CHAT_PROMPT},{**lease,'turn_started':True}))

    def test_workflow_capability_binds_native_mission_digest_and_strict_review_note(self):
        lease={'topic_id':'topic','mission_id':'mission','plan_digest':'a'*64}
        base='/api/research/topics/topic/missions/mission'
        self.assertTrue(allowed_write('workflow-operations','POST',base+'/approve',{'plan_digest':'a'*64,'note':'Synthetic fixture only'},lease))
        self.assertTrue(allowed_write('workflow-operations','POST',base+'/review',{'note':'Technical fixture review only'},lease))
        for path,body in [(base+'/approve',{'plan_digest':'b'*64,'note':'Bad'}),
                          (base+'/review',{'note':'Bad','decision':'accept'}),
                          (base.replace('/missions/mission','/missions/foreign')+'/review',{'note':'Bad'}),
                          ('/api/harness/execute',{}),('/api/research/topics/topic/missions',{})]:
            self.assertFalse(allowed_write('workflow-operations','POST',path,body,lease))

    def test_task_and_boundary_rules_preserve_all_four_scopes(self):
        self.assertEqual(len(JOURNEYS),4)
        for name in JOURNEYS:
            self.assertTrue(task(name,{'project_name':'UAT owned','topic_title':'UAT topic'}))
            self.assertFalse(allowed_write(name,'DELETE','/api/projects',{},{}))
        with self.assertRaises(ValueError):task('research-evidence',{})
        self.assertFalse(allowed_write('failure-recovery','POST','/api/config',{'ui':{'language':'en','theme':'dark'}},{}))

if __name__=='__main__':unittest.main()
