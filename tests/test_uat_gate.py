"""Acceptance-policy tests use explicit metadata fixtures, never live UAT claims."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import struct
import zlib
import zipfile
from devtools.verification.uat_gate import requirements,validate_manifest


class UATGate(unittest.TestCase):
    def test_malformed_browser_contract_cannot_bypass_journey_policy(self):
        from devtools.verification.contracts import validate_contract
        root=Path(__file__).resolve().parents[1]
        contract=json.loads((root/'docs/qa/contracts/FQC-UAT-001.json').read_text(encoding='utf-8'))
        for acceptance in [{'required':'yes','journeys':['settings-language']},
                           {'required':True,'journeys':'settings-language'},
                           {'required':True,'journeys':[]},
                           {'required':True,'journeys':['settings-language'],'applies_to':'*'},
                           {'required':True,'journeys':['settings-language'],'independent_review':'approved'}]:
            with self.subTest(acceptance=acceptance):
                self.assertTrue(validate_contract({**contract,'browser_acceptance':acceptance},root))

    def test_low_risk_docs_do_not_require_paid_or_local_llm(self):
        policy=requirements(['docs/README.md'],[])
        self.assertFalse(policy['required'])
        self.assertEqual(validate_manifest(Path('absent.json'),'source',policy),[])

    def test_contract_order_cannot_lower_critical_risk(self):
        contracts=[{'risk':r,'browser_acceptance':{'required':True}} for r in ['CRITICAL','HIGH']]
        for order in [contracts,list(reversed(contracts))]:
            policy=requirements(['frontend/src/App.tsx','backend/api/chat.py'],order)
            self.assertEqual(policy['risk'],'CRITICAL')
            self.assertTrue(policy['independent_review'])

    def test_required_missing_exploration_blocks(self):
        policy=requirements(['frontend/src/App.tsx','backend/providers/models.py'],[])
        self.assertTrue(policy['required'])
        self.assertTrue(validate_manifest(Path('absent.json'),'source',policy))

    def test_stale_mocked_pending_and_modified_evidence_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            files=['final.png','trace.zip','agent-history.json','browser-evidence.json','agent-result.json']
            artifacts=[]
            for name in files:
                if name=='final.png':
                    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
                    raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',640,480,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\xff\xff\xff'*640)*480))+chunk(b'IEND',b'')
                    (folder/name).write_bytes(raw)
                elif name=='trace.zip':
                    with zipfile.ZipFile(folder/name,'w') as trace:trace.writestr('trace.trace','{"fixture":true}')
                    raw=(folder/name).read_bytes()
                else:
                    payload={'history':[{'fixture':True}]} if name=='agent-history.json' else {'confirmation':'PASS','events':[]} if name=='browser-evidence.json' else {'ai_success':True,'steps':3}
                    raw=json.dumps(payload).encode();(folder/name).write_bytes(raw)
                artifacts.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest()})
            valid={'decision':'PASS','mode':'REAL_LOCAL','source_sha256':'exact-source',
                   'verified_journeys':['settings-language'],'artifacts':artifacts,'review':{'status':'APPROVED'}}
            policy={'required':True,'journeys':['settings-language'],'independent_review':True}
            path=folder/'manifest.json'
            path.write_text(json.dumps(valid),encoding='utf-8')
            self.assertEqual(validate_manifest(path,'exact-source',policy),[])
            for key,value in [('decision','BLOCKED'),('mode','MOCKED'),('source_sha256','old'),
                              ('verified_journeys',[]),('review',{'status':'PENDING'}),('release_blocking_defects',1)]:
                with self.subTest(key=key):
                    changed={**valid,key:value};path.write_text(json.dumps(changed),encoding='utf-8')
                    self.assertTrue(validate_manifest(path,'exact-source',policy))
            path.write_text(json.dumps(valid),encoding='utf-8');(folder/'final.png').write_bytes(b'changed')
            self.assertTrue(validate_manifest(path,'exact-source',policy))


if __name__=='__main__':unittest.main()
