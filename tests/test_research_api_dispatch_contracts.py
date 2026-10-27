"""UNIT: exact topic/task/revision dispatch with mocked domain I/O, not research execution."""
import _env
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,patch

from fastapi import HTTPException,UploadFile
from backend.api import research as api
from backend.agent import teams,collaboration,decision_ledger
from backend.knowledge import verification
from backend.plugins import local_research


class ResearchDispatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project('dispatch-contract')

    async def test_topic_scoped_dispatch_preserves_identifiers_and_argument_order(self):
        cases=[
            (api.team_capabilities,(),teams.registry,()),
            (api.team_monitor,('topic','mission'),teams.monitor,('topic','mission')),
            (api.workstream_monitor,('topic','mission'),collaboration.monitor,('topic','mission')),
            (api.audit,('topic',),decision_ledger.export,('topic',)),
            (api.experiment_verification,('topic','run'),verification.verify_run,('topic','run')),
            (api.mission_cancel,('topic','mission'),api.missions.cancel,('topic','mission')),
            (api.import_library,('topic',),api.corpus.import_legacy,('topic',)),
            (api.citation_graph,('topic',),api.corpus.citation_graph,('topic',)),
            (api.cancel,('job',),api.J.cancel,('job',)),
            (api.retry,('job',),api.J.retry,('job',)),
            (api.open_workspace,('workspace',),api.W.open_workspace,('workspace',)),
            (api.workspace_editor,('workspace',),api.W.open_editor,('workspace',)),
            (api.sync_status,('workspace',),api.W.get,('workspace',)),
        ]
        for handler,args,target,expected in cases:
            with self.subTest(route=handler.__name__),patch.object(api,'call',new=AsyncMock(return_value={'fixture':'value'})) as dispatch:
                self.assertEqual(await handler(*args),{'fixture':'value'})
                dispatch.assert_awaited_once_with(target,*expected)

    async def test_explicit_approval_digests_and_retry_notes_are_not_dropped(self):
        cases=[
            (api.protocol_approve,('topic','protocol',{'digest':'digest','note':'owner note'}),api.protocols.approve,('topic','protocol','digest','owner note')),
            (api.mission_approve,('topic','mission',{'plan_digest':'plan','note':'owner','expires_minutes':15}),api.missions.approve,('topic','mission','plan','owner',15)),
            (api.mission_retry,('topic','mission',{'task_id':'task','reconcile_note':'verified interruption'}),api.missions.retry,('topic','mission','task','verified interruption')),
            (api.discover,('topic',{'dry_run':True}),api.J.enqueue,('topic','discover',{'dry_run':True})),
            (api.review_finding,('topic','finding',{'approve':False,'note':'insufficient evidence'}),api.C.review_finding,('topic','finding',False,'insufficient evidence')),
        ]
        for handler,args,target,expected in cases:
            with self.subTest(route=handler.__name__),patch.object(api,'call',new=AsyncMock(return_value={'fixture':True})) as dispatch:
                self.assertEqual(await handler(*args),{'fixture':True});dispatch.assert_awaited_once_with(target,*expected)
        for value in (None,'yes',1,{}):
            with self.subTest(approval=value),patch.object(api,'call',new=AsyncMock()) as dispatch:
                with self.assertRaises(HTTPException) as error:await api.review_finding('topic','finding',{'approve':value})
                self.assertEqual(error.exception.status_code,400);dispatch.assert_not_awaited()

    async def test_citation_network_permission_and_error_redaction(self):
        with patch.object(api.G,'resolve_citation',new=AsyncMock()) as resolver:
            for body in ({},{'allow_network':False},{'allow_network':'true'}):
                with self.assertRaises(HTTPException) as error:await api.citation_resolve('topic',body)
                self.assertEqual(error.exception.status_code,400)
            resolver.assert_not_awaited()
        with patch.object(api.G,'resolve_citation',new=AsyncMock(side_effect=TimeoutError('private fixture diagnostic'))) as resolver:
            with self.assertRaises(HTTPException) as error:await api.citation_resolve('topic',{'allow_network':True,'doi':'10.1000/fixture'})
            self.assertEqual(error.exception.detail,'Citation unresolved: TimeoutError')
            resolver.assert_awaited_once_with('topic','10.1000/fixture')

    async def test_zotero_import_parses_json_and_enforces_upload_bound_before_dispatch(self):
        for raw in (b'[{"title":"fixture"}]',b'{"items":[{"title":"fixture"}]}'):
            with patch.object(api,'call',new=AsyncMock(return_value={'imported':1})) as dispatch:
                result=await api.zotero_import('topic',UploadFile(file=io.BytesIO(raw),filename='fixture.json'))
                self.assertEqual(result,{'imported':1})
                dispatch.assert_awaited_once_with(local_research.import_zotero,'topic',[{'title':'fixture'}])
        for raw,code in [(b'invalid',400),(b'x'*(5*1024*1024+1),413)]:
            with patch.object(api,'call',new=AsyncMock()) as dispatch:
                with self.assertRaises(HTTPException) as error:await api.zotero_import('topic',UploadFile(file=io.BytesIO(raw)))
                self.assertEqual(error.exception.status_code,code);dispatch.assert_not_awaited()

    async def test_pdf_missing_versions_and_missing_objects_are_not_fake_downloads(self):
        for versions in ([],[{'id':'v','document':None}]):
            with patch.object(api,'call',new=AsyncMock(return_value={'versions':versions})):
                with self.assertRaises(HTTPException) as error:await api.pdf('topic','paper','v')
                self.assertEqual(error.exception.status_code,404)
        with tempfile.TemporaryDirectory(prefix='phdlab-pdf-route-') as directory:
            path=Path(directory)/'fixture.pdf'
            with patch.object(api,'call',new=AsyncMock(return_value={'versions':[{'id':'v','document':{'sha256':'digest'}}]})),patch.object(api.corpus,'object_path',return_value=path):
                with self.assertRaises(HTTPException) as error:await api.pdf('topic','paper','v')
                self.assertEqual(error.exception.status_code,404)
                path.write_bytes(b'%PDF-1.4\n% bounded route fixture\n')
                response=await api.pdf('topic','paper','v')
                self.assertEqual(response.path,path);self.assertEqual(response.media_type,'application/pdf')

