"""Configuration compatibility and alternate PDF engine contracts."""
import _env
import builtins
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace,ModuleType
from unittest import mock
from backend.core import config as C
from backend.knowledge import library as L

class ConfigPdf(unittest.TestCase):
    def setUp(self):_env.fresh_project('config-pdf')

    def test_pdf_font_and_text_engines_agree_on_contract(self):
        page=mock.Mock();page.rect.height=800
        page.get_text.side_effect=lambda kind=None: {'blocks':[{'lines':[{'spans':[{'text':'Evidence-based research','size':18,'bbox':[0,30]},{'text':'x','size':1,'bbox':[0,0]}]}]}]} if kind=='dict' else 'Evidence-based research\nMethods'
        doc=mock.MagicMock();doc.__enter__.return_value=doc;doc.page_count=1;doc.metadata={'title':'Evidence'};doc.__getitem__.return_value=page
        fitz=mock.Mock();fitz.open.return_value=doc
        with mock.patch.object(L,'PDF_BACKEND','pymupdf'),mock.patch.object(L,'fitz',fitz,create=True):
            self.assertEqual(L._read_pdf(Path('fake.pdf'))['pages'],1)
            self.assertTrue(L.pdf_pages(Path('fake.pdf'))[0])
            self.assertEqual(L._read_pdf(Path('fake.pdf'),want_title=False)['font_title'],'')
            doc.page_count=0;self.assertEqual(L._read_pdf(Path('fake.pdf'))['text'],'')
        p=mock.Mock();p.extract_text.return_value='IEEE Journal\nA sufficiently long research title\nMethods';p.mediabox.height=800
        reader=SimpleNamespace(is_encrypted=False,metadata={},pages=[p])
        with mock.patch.object(L,'PDF_BACKEND','pypdf'),mock.patch.object(L,'PdfReader',return_value=reader),mock.patch.object(L,'_pick_title',return_value=''):
            self.assertEqual(L._read_pdf(Path('fake.pdf'))['font_title'],'A sufficiently long research title')
        original=builtins.__import__
        for alternative in ('pymupdf','none'):
            def importing(name,*a,**kw):
                if name=='fitz':raise ImportError('missing')
                if name=='pymupdf':
                    if alternative=='none':raise ImportError('missing')
                    return fitz
                if name=='pypdf' and alternative=='none':raise ImportError('missing')
                return original(name,*a,**kw)
            spec=importlib.util.spec_from_file_location('backend._pdf_regression',L.__file__);module=importlib.util.module_from_spec(spec)
            with mock.patch('builtins.__import__',importing):spec.loader.exec_module(module)
            self.assertEqual(module.PDF_BACKEND,'pymupdf' if alternative=='pymupdf' else 'none')
