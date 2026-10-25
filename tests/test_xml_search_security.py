import _env
import asyncio
from contextlib import asynccontextmanager
import unittest
from unittest.mock import patch
import httpx
from defusedxml.common import EntitiesForbidden
from backend.knowledge import websearch


class XMLSearchSecurity(unittest.TestCase):
    def test_arxiv_rejects_external_entity_declarations(self):
        xml = '<!DOCTYPE feed [<!ENTITY injected "forged-source">]><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>&injected;</title></entry></feed>'
        @asynccontextmanager
        async def client(*_):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=xml))) as c:
                yield c
        with patch.object(websearch, '_client', client):
            with self.assertRaises(EntitiesForbidden):
                asyncio.run(websearch.arxiv('safe query', 2))
