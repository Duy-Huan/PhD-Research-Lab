"""FQC-AUTONOMY-QA-664 (agent/PLAN_6.6.4_L3.md, phase A-QA): the Missions L1–L4 flows and Harness Studio are checked
by Playwright on every CI run, and the defects those specs found stay fixed.

Found by frontend/e2e/autonomy_levels.spec.ts and harness_levels.spec.ts: no L1–L4 flow ran in routine CI (both
existing specs need a model), the Harness Team tab and AI Architect showed Vietnamese in the English interface, and
the visual runtime reported blocked nodes in Vietnamese."""
import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _env  # noqa: F401
from backend.agent import workflow_architect as W
from backend.execution import workflow_runtime as R
from devtools.verification.journeys import browser_plan, execution_groups

ROOT = Path(__file__).resolve().parents[1]
VIETNAMESE = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)
GOAL = "Study label smoothing and calibration, then write a paper"


def fixture(root: Path):
    config = json.loads((ROOT / 'devtools/verification/uat_config.json').read_text(encoding='utf-8'))
    p = root / 'devtools/verification/uat_config.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(config))
    for name in set(config['smoke']) | {f for record in config['journeys'].values() for f in record['tests']}:
        p = root / 'frontend/e2e' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('// isolated selection fixture\n')


class AutonomyLevelsInCi(unittest.TestCase):
    def test_the_four_autonomy_levels_and_harness_run_on_every_ci_without_a_model(self):
        config = json.loads((ROOT / 'devtools/verification/uat_config.json').read_text(encoding='utf-8'))
        record = config['journeys']['autonomy-levels']
        self.assertEqual(record['tests'], ['autonomy_levels.spec.ts'])
        self.assertFalse(record['needs_model'])
        for spec in ('autonomy_levels.spec.ts', 'harness_levels.spec.ts'):
            self.assertTrue((ROOT / 'frontend/e2e' / spec).is_file(), spec)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / 'frontend/e2e/harness_levels.spec.ts').write_text('// no model\n')
            offline = browser_plan(root, [], [], 'pr', all_offline=True)['tests']
            self.assertIn('autonomy_levels.spec.ts', offline)
            self.assertIn('harness_levels.spec.ts', offline)
            self.assertEqual(dict(execution_groups(offline))['2d'].count('autonomy_levels.spec.ts'), 1)

    def test_a_missions_or_policy_change_selects_the_levels_outside_the_offline_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for changed in ('frontend/src/features/missions/AutonomyPanel.tsx', 'backend/agent/autonomy.py'):
                with self.subTest(changed=changed):
                    self.assertIn('autonomy_levels.spec.ts', browser_plan(root, [changed], [], 'pr')['tests'])
            self.assertNotIn('autonomy_levels.spec.ts', browser_plan(root, ['README.md'], [], 'pr')['tests'])


class HarnessLanguage(unittest.TestCase):
    def test_preset_agents_have_english_names_and_purposes(self):
        for agent in W.PRESET_AGENTS:
            with self.subTest(agent=agent['id']):
                for key in ('name_en', 'purpose_en'):
                    self.assertTrue(agent.get(key))
                    self.assertFalse(VIETNAMESE.search(agent[key]))
        self.assertEqual([a['id'] for a in W.list_agent_profiles()][:len(W.PRESET_AGENTS)], [a['id'] for a in W.PRESET_AGENTS])

    def test_architect_workflow_has_english_description_and_node_names(self):
        for level in ('L2', 'L3', 'L4'):
            wf = W.generate_workflow_from_objective(GOAL, level)
            with self.subTest(level=level):
                self.assertFalse(VIETNAMESE.search(wf['description_en']))
                self.assertIn(GOAL, wf['description_en'])
                for node in wf['nodes']:
                    self.assertTrue(node['data'].get('label_en'), node['id'])
                    self.assertFalse(VIETNAMESE.search(node['data']['label_en']))

    def test_runtime_reports_blocked_nodes_in_english_and_never_as_completed(self):
        wf = W.generate_workflow_from_objective(GOAL, 'L3')
        with mock.patch.object(R, 'save_execution_record'):
            report = R.execute_workflow_graph(workflow=wf, topic_id='', level='L3')
        results = list(report['node_results'].values())
        self.assertGreater(len(results), 2)
        for result in results:
            with self.subTest(node=result['node_id']):
                self.assertFalse(VIETNAMESE.search(result['summary']))
                self.assertTrue(result.get('label_en'))
                if not result.get('execution', {}).get('executed'):
                    self.assertNotEqual(result['status'], 'completed')

    def test_generating_and_running_is_fast(self):
        started = time.perf_counter()
        with mock.patch.object(R, 'save_execution_record'):
            for _ in range(50):
                R.execute_workflow_graph(workflow=W.generate_workflow_from_objective(GOAL, 'L4'), topic_id='', level='L4')
        self.assertLess(time.perf_counter() - started, 5.0)


if __name__ == '__main__':
    unittest.main()
