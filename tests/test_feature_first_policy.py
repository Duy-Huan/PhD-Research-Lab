"""MOCKED evidence fixtures test the owner-scoped chronology policy, not live execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from devtools.verification.contracts import validate_tdd


class OwnerFeatureFirst(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='phdlab-order-policy-')
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.report={'passed':True,'total':1,'cases':[{'id':'test_behavior.Contract.test_observation','status':'PASS'}]}
        self.contract={'id':'FQC-HERMES-RUNTIME-001','scenarios':[{'test':'tests/test_behavior.py::Contract.test_observation'}],
                       'tdd':{'status':'IMPLEMENTATION_FIRST_OWNER_AUTHORIZED','authorization':'OWNER-20261026-HERMES-FEATURE-FIRST',
                              'red':None,'green':{'path':'actual.json','exit_code':0}}}
        self.write()

    def write(self):
        raw=json.dumps(self.report).encode();(self.root/'actual.json').write_bytes(raw)
        self.contract['tdd']['green']['sha256']=hashlib.sha256(raw).hexdigest()

    def test_exact_owner_campaign_accepts_executed_traced_green_without_fabricated_red(self):
        self.assertEqual(validate_tdd(self.contract,self.root),[])

    def test_arbitrary_contract_or_authorization_cannot_waive_tdd(self):
        for key,value in (('id','FQC-ARBITRARY'),('id',[])):
            current=copy.deepcopy(self.contract);current[key]=value
            self.assertTrue(validate_tdd(current,self.root))
        self.contract['tdd']['authorization']='AI-says-owner-approved'
        self.assertTrue(validate_tdd(self.contract,self.root))

    def test_missing_failed_skipped_or_empty_suites_are_never_green(self):
        for status in ('FAIL','ERROR','SKIP','BLOCKED','NOT_RUN'):
            self.report['cases'][0]['status']=status;self.write()
            self.assertTrue(validate_tdd(self.contract,self.root))
        self.report.update(cases=[],total=0);self.write()
        self.assertTrue(validate_tdd(self.contract,self.root))

    def test_missing_traced_assertion_or_duplicate_case_ids_are_rejected(self):
        self.report['cases'][0]['id']='test_other.Unrelated.test_pass';self.write()
        self.assertTrue(validate_tdd(self.contract,self.root))
        self.report['cases']=[{'id':'test_behavior.Contract.test_observation','status':'PASS'}]*2
        self.report['total']=2;self.write()
        self.assertTrue(validate_tdd(self.contract,self.root))

    def test_changed_bytes_exit_codes_or_fake_red_are_rejected(self):
        (self.root/'actual.json').write_text('{}','utf-8')
        self.assertTrue(validate_tdd(self.contract,self.root))
        self.write();self.contract['tdd']['green']['exit_code']=1
        self.assertTrue(validate_tdd(self.contract,self.root))
        self.contract['tdd']['green']['exit_code']=0;self.contract['tdd']['red']={'status':'invented'}
        self.assertTrue(validate_tdd(self.contract,self.root))

    def test_other_features_still_require_actual_red_green(self):
        self.assertTrue(validate_tdd({'id':'FQC-ORDINARY'},self.root))
        self.assertTrue(validate_tdd({'tdd':[]},self.root))


if __name__=='__main__':unittest.main()
