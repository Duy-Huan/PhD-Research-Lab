"""Receipt parsing cannot turn stale, empty or contradictory software evidence into PASS."""
import _env
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validation_report import render_receipt


class ReceiptReader(unittest.TestCase):
    def record(self):
        return {'schema_version':1,'decision':'PASS','profile':'targeted','component':'backend',
                'mode':'MOCKED','source':{'sha256':'fixture','files':{}},'source_stable':True,
                'cases':[{'id':'fixture.case','status':'PASS'}],
                'counts':{'PASS':1,'FAIL':0,'ERROR':0,'SKIP':0,'NOT_RUN':0,'BLOCKED':0,'UNVERIFIED':0},
                'steps':[{'id':'backend','status':'PASS'}]}

    def render(self, record, current=None):
        with tempfile.TemporaryDirectory(prefix='phdlab-receipt-') as temporary:
            path=Path(temporary)/'report.json';path.write_text(json.dumps(record),'utf-8')
            with patch('tools.validation_report.identity',return_value=current or record.get('source')):
                return render_receipt(path)

    def test_current_scoped_receipt_keeps_its_mode_and_scope(self):
        raw,status=self.render(self.record())
        actual=json.loads(raw)
        self.assertEqual(status,0)
        self.assertEqual((actual['profile'],actual['mode']),('targeted','MOCKED'))
        self.assertNotIn('release_ready',actual)
        self.assertIn('not another test runner',str(actual['limitations']))

    def test_stale_or_unstable_source_cannot_return_success(self):
        record=self.record()
        for current, stable in (({'sha256':'changed','files':{}},True),(record['source'],False)):
            with self.subTest(stable=stable):
                record['source_stable']=stable
                self.assertEqual(self.render(record,current)[1],2)

    def test_empty_inconsistent_and_failed_pass_claims_are_rejected(self):
        for mutation in ('empty','counts','failure','gate','skip'):
            with self.subTest(mutation=mutation):
                record=self.record()
                if mutation=='empty':record['cases']=[];record['counts']['PASS']=0
                elif mutation=='counts':record['counts']['PASS']=2
                elif mutation=='gate':record['steps'][0]['status']='FAIL'
                else:
                    status='FAIL' if mutation=='failure' else 'SKIP'
                    record['cases'][0]['status']=status
                    record['counts']['PASS']=0;record['counts'][status]=1
                with self.assertRaises(ValueError):self.render(record)

    def test_unknown_provider_logs_never_enter_a_canonical_result(self):
        with self.assertRaisesRegex(ValueError,'canonical'):
            self.render({'codex_log':'OK','scientific_review':'verified','passed':True})
