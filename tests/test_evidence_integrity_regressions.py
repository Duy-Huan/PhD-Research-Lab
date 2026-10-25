"""UNIT/integration regressions: no provider inference or scientific certification."""
import json
import unittest
from pathlib import Path
from unittest import mock

import _env

from backend.execution import harness
from backend.intelligence import reproducibility as repro
from backend.knowledge import research_store as store


class EvidenceIntegrity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('evidence-integrity')

    def test_binary_presence_does_not_execute_benchmarks(self):
        for tool in harness.HARNESS_TOOL_MAP:
            with self.subTest(tool=tool), mock.patch.object(harness, '_is_tool_available', return_value=True):
                result = harness._execute_harness_tool(tool, {}, {})
                self.assertFalse(result['passed'], result)
                self.assertEqual(result['metrics'], {})
                self.assertIn(result['status'], ('blocked', 'unsupported'))

    def test_unknown_tool_cannot_pass_even_when_presence_probe_says_yes(self):
        with mock.patch.object(harness, '_is_tool_available', return_value=True):
            result = harness._execute_harness_tool('unknown-adapter', {}, {})
        self.assertFalse(result['passed'])
        self.assertEqual(result['status'], 'unsupported')

    def test_empty_graph_and_cycles_never_execute_or_pass(self):
        for graph in ({'nodes': [], 'edges': []}, {
            'nodes': [{'id': 'a'}, {'id': 'b'}],
            'edges': [{'source': 'a', 'target': 'b'}, {'source': 'b', 'target': 'a'}],
        }, {'nodes': [{'id': 'a'}, {'id': 'a'}], 'edges': []}, {
            'nodes': [{'id': 'a'}], 'edges': [{'source': 'missing', 'target': 'a'}],
        }):
            with self.subTest(graph=graph), mock.patch.object(harness, '_execute_harness_tool') as execute:
                result = harness.execute_workflow(graph)
                self.assertFalse(result['passed'])
                self.assertEqual(result['status'], 'failed')
                execute.assert_not_called()

    def test_export_has_no_invented_metrics_and_replay_never_copies_expected(self):
        topic = store.save_topic(store.TopicInput(title='No experiment has executed'))
        pack = repro.export_reproducibility_pack(topic['id'], 'no-such-mission')
        self.assertEqual(pack['manifest']['expected_metrics'], {})
        report = repro.replay_reproducibility_pack(topic['id'], 'no-such-mission')
        self.assertFalse(report['passed'])
        self.assertEqual(report['status'], 'unverified')
        self.assertEqual(report['replayed_metrics'], {})
        self.assertFalse(report['execution']['executed'])

    def test_empty_checksum_manifest_and_path_escape_fail_closed(self):
        topic = store.save_topic(store.TopicInput(title='Tamper fixture'))
        pack = repro.export_reproducibility_pack(topic['id'], 'tamper-fixture')
        path = Path(pack['pack_dir']) / 'checksums.sha256'
        for contents in ('', 'malformed\n', '0' * 64 + '  ../../outside.json\n'):
            with self.subTest(contents=contents):
                path.write_text(contents, encoding='utf-8')
                report = repro.replay_reproducibility_pack(topic['id'], 'tamper-fixture')
                self.assertFalse(report['passed'])
                self.assertEqual(report['status'], 'failed')
                self.assertTrue(report['checksum_mismatches'])

    def test_changed_export_file_fails_integrity(self):
        topic = store.save_topic(store.TopicInput(title='Modified data'))
        pack = repro.export_reproducibility_pack(topic['id'], 'modified')
        (Path(pack['pack_dir']) / 'manifest.json').write_text(json.dumps({'tampered': True}), encoding='utf-8')
        report = repro.replay_reproducibility_pack(topic['id'], 'modified')
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(report['checksum_mismatches'])

    def test_visual_nodes_never_invent_effects_and_approval_never_auto_passes(self):
        from backend.execution.workflow_nodes import NODE_REGISTRY
        from backend.execution.workflow_runtime import _execute_single_node
        for node_type in NODE_REGISTRY:
            with self.subTest(node_type=node_type):
                result = _execute_single_node({'id': 'node', 'type': node_type}, {})
                if node_type in ('start', 'end', 'condition'):
                    self.assertEqual(result['execution_mode'], 'CONTROL_FLOW')
                else:
                    self.assertFalse(result['passed'])
                    self.assertEqual(result['metrics'], {})
        waiting = _execute_single_node({'id': 'approval', 'type': 'human_approval'}, {}, 'L4')
        self.assertEqual(waiting['status'], 'waiting_approval')
        for actual in (None, float('nan'), float('inf'), True):
            result = _execute_single_node({'id': 'gate', 'type': 'evaluation_gate'}, {'latest_metrics': {'accuracy': actual}})
            self.assertFalse(result['passed'])

    def test_library_does_not_invent_authors_venue_year_or_ranking_from_hostname(self):
        from backend.api.library import _enrich_paper
        for host in ('ieeexplore.ieee.org', 'arxiv.org', 'sciencedirect.com', 'nature.com', 'acm.org', 'example.org'):
            with self.subTest(host=host):
                record = _enrich_paper({'title': 'Unverified source', 'url': f'https://{host}/unknown'})
                self.assertEqual(record['authors'], [])
                self.assertEqual(record['venue'], '')
                self.assertEqual(record['year'], '')
                self.assertEqual(record['rank']['tier'], '')
                self.assertEqual(record['ranking']['source'], '')
