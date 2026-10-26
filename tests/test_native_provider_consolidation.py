"""Actual local CPU/file/HTTP contracts; not remote GPU, live AI or scientific qualification."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import _env
from backend.core import config
from backend.execution import code_projects, remote_compute as compute
from backend.agent import launch, missions, runs
from backend.agent.mission_contracts import MissionSpec, Task
from backend.knowledge import research_store as store


class NativeCompute(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('native-compute')
        self.root=code_projects.active_dir()

    def make(self, source=None, **extra):
        source=source or "import os,json\nfrom pathlib import Path\nPath(os.environ['RUN_DIR'],'metrics.json').write_text(json.dumps({'loss':0.25}))\n"
        (self.root/'train.py').write_text(source,'utf-8')
        return compute.create({'files':['train.py'],'entrypoint':'train.py','compute_target':'docker',
                               'required_artifacts':['metrics.json'], **extra})

    def execute_fixture(self, record):
        compute.approve(record['run_id'])
        # Explicit local CPU execution of the portable launcher; no Docker/Colab claim.
        destination=config.data_dir()/('worker-'+record['run_id'])
        destination.mkdir()
        with zipfile.ZipFile(compute.bundle(record['run_id'])) as archive:
            archive.extractall(destination)
        result=subprocess.run([sys.executable,str(destination/'launch.py')],cwd=destination,
            capture_output=True,timeout=20,env={**__import__('os').environ,'PYTHONIOENCODING':'utf-8'})
        return result,destination

    def mutate(self, original, edit=None, append=None):
        target=original.with_name('mutated-'+str(len(list(original.parent.glob('mutated-*'))))+'.zip')
        with zipfile.ZipFile(original) as source,zipfile.ZipFile(target,'w') as destination:
            for name in source.namelist():
                raw=source.read(name)
                if edit:raw=edit(name,raw)
                destination.writestr(name,raw)
            if append:destination.writestr(*append)
        return target

    def test_native_worker_results_are_imported_with_exact_lineage_and_no_scientific_claim(self):
        record=self.make()
        result,worker=self.execute_fixture(record)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        actual=compute.import_results(record['run_id'],worker/'results.zip')
        self.assertEqual(actual['status'],'completed')
        self.assertEqual(actual['metrics'],{'loss':0.25})
        self.assertEqual(actual['verification'],{'transfer_integrity':'VERIFIED','remote_authenticity':'NOT_VERIFIED',
                                              'reproduction':'NOT_RUN','scientific_review':'pending'})
        digest=actual['imports'][0]['sha256']
        path=compute.imported_file(record['run_id'],digest,'metrics.json')
        self.assertEqual(json.loads(path.read_text()),{'loss':0.25})
        self.assertEqual(compute.import_results(record['run_id'],worker/'results.zip')['imports'],actual['imports'])
        with zipfile.ZipFile(compute.bundle(record['run_id'])) as archive:
            self.assertNotIn('from clearml',archive.read('launch.py').decode())

    def test_failed_process_is_preserved_as_failed(self):
        record=self.make("raise RuntimeError('controlled fixture failure')\n")
        result,worker=self.execute_fixture(record)
        self.assertNotEqual(result.returncode,0)
        actual=compute.import_results(record['run_id'],worker/'results.zip')
        self.assertEqual(actual['status'],'failed')
        self.assertNotEqual(json.loads((worker/'execution.json').read_text())['exit_code'],0)
        self.assertEqual(actual['metrics'],{})

    def test_source_change_after_review_prevents_bundle_download(self):
        record=self.make();compute.approve(record['run_id'])
        with (compute.folder(record['run_id'])/'bundle.zip').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):compute.bundle(record['run_id'])

    def test_tampered_output_is_rejected_without_changing_run_state(self):
        record=self.make();_,worker=self.execute_fixture(record)
        archive=self.mutate(worker/'results.zip',lambda name,raw:b'{"loss":99}' if name=='artifacts/metrics.json' else raw)
        with self.assertRaises(ValueError):compute.import_results(record['run_id'],archive)
        self.assertEqual(compute.get(record['run_id'])['status'],'ready_for_handoff')

    def test_wrong_manifest_or_completed_without_outputs_is_rejected(self):
        record=self.make();_,worker=self.execute_fixture(record)
        for mutation in ({'manifest_sha256':'0'*64},{'exit_code':1},{'artifacts':[]}, {'metrics':{'loss':99}}):
            def edit(name,raw):
                return json.dumps({**json.loads(raw),**mutation}).encode() if name=='execution.json' else raw
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                compute.import_results(record['run_id'],self.mutate(worker/'results.zip',edit))

    def test_traversal_or_unlisted_zip_entries_are_refused(self):
        record=self.make();_,worker=self.execute_fixture(record)
        with self.assertRaises(ValueError):
            compute.import_results(record['run_id'],self.mutate(worker/'results.zip',append=('../escape.py',b'never execute')))
        self.assertFalse((compute.folder(record['run_id'])/'escape.py').exists())

    def test_idempotent_reimport_rejects_later_local_artifact_or_receipt_tampering(self):
        record=self.make();_,worker=self.execute_fixture(record)
        actual=compute.import_results(record['run_id'],worker/'results.zip')
        digest=actual['imports'][0]['sha256']
        path=compute.imported_file(record['run_id'],digest,'metrics.json')
        path.write_text('{"loss":55}')
        with self.assertRaises(ValueError):compute.import_results(record['run_id'],worker/'results.zip')
        with self.assertRaises(ValueError):compute.imported_file(record['run_id'],digest,'metrics.json')

    def test_paths_approval_and_timeout_are_explicit(self):
        record=self.make()
        with self.assertRaisesRegex(ValueError,'approve'):compute.bundle(record['run_id'])
        for extra in ({'files':['../train.py']},{'required_artifacts':['CON.txt']},{'max_seconds':True}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.make(**extra)
        record=self.make('import time\ntime.sleep(30)\n',max_seconds=1)
        result,worker=self.execute_fixture(record)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(compute.import_results(record['run_id'],worker/'results.zip')['status'],'failed')

    def test_result_http_upload_roundtrip_and_wrong_content_type(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.api.compute import router
        record=self.make();_,worker=self.execute_fixture(record)
        app=FastAPI();app.include_router(router)
        with TestClient(app) as client:
            url='/api/compute/runs/'+record['run_id']+'/results'
            self.assertEqual(client.post(url,content=b'{}',headers={'Content-Type':'application/json'}).status_code,415)
            self.assertEqual(client.post(url,content=b'broken',headers={'Content-Type':'application/zip'}).status_code,422)
            response=client.post(url,content=(worker/'results.zip').read_bytes(),headers={'Content-Type':'application/zip'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['status'],'completed')


class NativeCodingDelegation(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project('native-code-delegation')

    def test_code_creation_preserves_full_goal_and_forces_real_write_approval(self):
        config.save_config({'runs':{'auto_approve_risk':3},'research_providers':{'coding_default':'app'}})
        goal='Important context. '*600+'Keep this final constraint.'
        record=launch.from_skill('code',goal)
        self.assertEqual(record['status'],'APPROVAL_PENDING')
        self.assertEqual(record['goal'],goal)
        self.assertEqual(record['inputs']['task'],goal)
        self.assertEqual(record['inputs']['code_project_id'],code_projects.active()['id'])
        self.assertEqual(record['approval']['status'],'pending')

    def mission(self):
        topic=store.save_topic(store.TopicInput(title='Native coding topic'))
        spec=MissionSpec(topic_id=topic['id'],objective='Implement a research baseline',permissions=['workspace_write'],
                         tasks=[Task(id='coding',capability='code.implement',args={'goal':'Write a bounded module'})])
        mission=missions.create(spec)
        return mission,spec.tasks[0]

    def test_coding_observation_never_completes_at_creation_or_replays_inference(self):
        mission,task=self.mission()
        first=asyncio.run(missions._native_code(mission,task))
        self.assertEqual(first.status,'interrupted')
        rid=first.output['run_id']
        self.assertEqual(runs.get(rid)['status'],'APPROVAL_PENDING')
        again=asyncio.run(missions._native_code(missions.get(mission['id']),task))
        self.assertEqual(again.output['run_id'],rid)
        self.assertEqual(len([r for r in runs.list_runs() if r['pipeline']=='code']),1)

    def test_completion_requires_exact_bound_files_and_their_hashes(self):
        mission,task=self.mission()
        first=asyncio.run(missions._native_code(mission,task));rid=first.output['run_id']
        root=code_projects.active_dir();path=root/'experiments'/'fixture.py';path.parent.mkdir();path.write_text('result = 42')
        name=path.relative_to(root).as_posix();digest=hashlib.sha256(path.read_bytes()).hexdigest()
        # Controlled durable executor fixture, not a live coding-agent invocation.
        def completed(record):
            record['status']='COMPLETED'
            step=next(item for item in record['steps'] if item['kind']=='code')
            step.update(status='done',result={'files':[name],'sha256':{name:digest},'command':'python '+name})
        runs.update(rid,completed)
        actual=asyncio.run(missions._native_code(missions.get(mission['id']),task))
        self.assertEqual(actual.status,'completed')
        self.assertEqual(actual.output['tests_status'],'NOT_RUN_BY_CODE_MATERIALIZATION')
        path.write_text('tampered = True')
        with self.assertRaisesRegex(ValueError,'hashes'):
            asyncio.run(missions._native_code(missions.get(mission['id']),task))

    def test_legacy_opencode_http_history_is_read_only_and_not_live(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.api.opencode import router
        topic=store.save_topic(store.TopicInput(title='Historical code'))
        with store.db() as connection:
            connection.execute('INSERT INTO opencode_sessions(id,topic_id,native_session_id,status,payload,created,updated) VALUES(?,?,?,?,?,?,?)',
                ('old-session',topic['id'],'native-old','running',store.dumps({'token':'secret-fixture','spec':{'goal':'old code'}}),store.now(),store.now()))
        index=store.store_dir()/'research.sqlite3';before=hashlib.sha256(index.read_bytes()).hexdigest()
        app=FastAPI();app.include_router(router)
        with TestClient(app) as client:
            url='/api/research/topics/'+topic['id']+'/opencode/sessions'
            value=client.get(url).json()['sessions'][0]
            self.assertEqual(value['status'],'running')
            self.assertFalse(value['native_execution_observed']);self.assertTrue(value['read_only'])
            self.assertNotIn('token',value['payload'])
            self.assertEqual(client.post(url,json={}).status_code,410)
        self.assertEqual(hashlib.sha256(index.read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
