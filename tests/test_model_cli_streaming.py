"""MOCKED CLI transport; assert actual async delivery and cancellation boundaries."""
import asyncio
import threading
import unittest
from unittest.mock import patch

import _env
from backend.core import config
from backend.providers import cli,models


class StreamingAuthority(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _env.isolate_config(self)

    async def test_first_delta_arrives_before_cli_finishes(self):
        release=threading.Event()
        class Fixture:
            def stream_message(self,prompt,context):
                context['request_id']='stream-fixture'
                yield {'type':'text_delta','text':'First observation.'}
                release.wait(8)
                yield {'type':'text_delta','text':'Final result.'}
            def cancel(self,rid):release.set()
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            stream=models._stream_cli(config.load_config(),'codex','Synthetic context',[{'role':'user','content':'Fixture'}])
            try:
                self.assertEqual(await asyncio.wait_for(anext(stream),2),'First observation.')
                self.assertFalse(release.is_set(),'First observation must be available before completion')
                release.set()
                self.assertEqual([part async for part in stream],['Final result.'])
            finally:
                release.set();await stream.aclose()

    async def test_partial_delta_is_delivered_before_later_provider_failure(self):
        class Fixture:
            def stream_message(self,prompt,context):
                yield {'type':'text_delta','text':'Partial observation.'}
                yield {'type':'error','message':'Controlled outage after partial text'}
            def cancel(self,rid):pass
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            stream=models._stream_cli(config.load_config(),'codex','',[])
            try:
                self.assertEqual(await anext(stream),'Partial observation.')
                with self.assertRaisesRegex(models.LLMError,'Controlled outage'):await anext(stream)
            finally:await stream.aclose()

    async def test_closing_reader_cancels_only_its_owned_cli_request(self):
        release=threading.Event();closed=threading.Event();cancelled=[]
        class Fixture:
            def stream_message(self,prompt,context):
                context['request_id']='owned-stream-fixture'
                try:
                    yield {'type':'text_delta','text':'First'}
                    release.wait(8)
                    if not context.get('_cancel',threading.Event()).is_set():
                        yield {'type':'text_delta','text':'Must not leak after close'}
                finally:closed.set()
            def cancel(self,rid):cancelled.append(rid);release.set()
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            stream=models._stream_cli(config.load_config(),'codex','',[])
            try:
                self.assertEqual(await asyncio.wait_for(anext(stream),2),'First')
                await stream.aclose()
                self.assertEqual(cancelled,['owned-stream-fixture'])
                self.assertTrue(closed.is_set())
            finally:release.set();await stream.aclose()

    async def test_completed_stream_does_not_cancel_an_already_finished_request(self):
        cancelled=[]
        class Fixture:
            def stream_message(self,prompt,context):
                context['request_id']='completed-stream-fixture'
                yield {'type':'text_delta','text':'Complete'}
            def cancel(self,rid):cancelled.append(rid)
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            self.assertEqual([p async for p in models._stream_cli(config.load_config(),'codex','',[])],['Complete'])
            self.assertEqual(cancelled,[])

    async def test_connector_startup_failure_is_reported_without_waiting_for_a_delta(self):
        class Fixture:
            def stream_message(self,prompt,context):raise OSError('Controlled connector startup failure')
            def cancel(self,rid):pass
        with patch.dict(cli.CONNECTORS,{'codex':Fixture()}):
            stream=models._stream_cli(config.load_config(),'codex','',[])
            try:
                with self.assertRaisesRegex(models.LLMError,'Controlled connector startup failure'):
                    await asyncio.wait_for(anext(stream),2)
            finally:await stream.aclose()
