"""Context serialization regression; remote records are explicit fixtures, not scientific evidence."""
import json
import unittest
from unittest.mock import patch

import _env
from backend.agent.project_context import Adapter


class LatestIntegration(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('latest-integration')

    def test_remote_compute_context_preserves_record_identity_and_unverified_status(self):
        record={'run_id':'fixture-run','hypothesis_id':'fixture-hypothesis','status':'pending',
                'metrics':None,'artifact_refs':[],'evaluation':{'scientific_review':'pending'}}
        with patch('backend.execution.remote_compute.list_runs',return_value=[record]):
            item=next(x for x in Adapter()._runs() if x['id']=='state:compute_runs')
        self.assertEqual(json.loads(item['text'])[0]['run_id'],'fixture-run')
        self.assertIsNone(json.loads(item['text'])[0]['metrics'])
        self.assertEqual(json.loads(item['text'])[0]['evaluation']['scientific_review'],'pending')
        self.assertEqual(item['trust'],'state')


if __name__=='__main__':unittest.main()
