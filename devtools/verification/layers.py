"""Exact opt-in live identities; no wildcard exclusions or SKIP-to-PASS conversion."""
from __future__ import annotations
import unittest

LIVE_TESTS = frozenset({
    'test_live_integrations.ClearMLLive.test_create_log_read',
    'test_live_integrations.CodexLive.test_read_only_run',
    'test_vram_gate.LMStudioLive.test_real_gate_and_manual_unload',
})


class EmptyTestModule(unittest.TestCase):
    def __init__(self,module):
        super().__init__();self.module=module
    def id(self):return 'discovery.empty.'+self.module
    def runTest(self):
        self.fail('No executable unittest cases in '+self.module+'; use unittest.TestCase or explicitly register its runner')


def load_modules(loader: unittest.TestLoader,modules: list[str]) -> unittest.TestSuite:
    suites=[]
    for module in modules:
        suite=loader.loadTestsFromName(module)
        suites.append(suite if suite.countTestCases() else EmptyTestModule(module))
    return unittest.TestSuite(suites)


def live_ids() -> set[str]:
    return set(LIVE_TESTS)


def live_regression_errors(report: dict) -> list[str]:
    cases = report.get('cases', [])
    if (report.get('mode') not in ('REAL_LOCAL','REAL_INTEGRATION','LIVE_PROVIDER')
            or report.get('passed') is not True or not isinstance(cases,list)):
        return ['Real live-provider regression execution is incomplete']
    if not live_ids().issubset({c.get('id') for c in cases}):
        return ['Required deferred live-provider test identities are missing']
    if any(c.get('status')!='PASS' for c in cases):
        return ['Live-provider regressions include failed/skipped/unexecuted cases']
    return []


def partition(suite: unittest.TestSuite, layer: str, declared=None):
    if layer not in ('software', 'live', 'all'):
        raise ValueError('Unknown test layer')
    declared = live_ids() if declared is None else set(declared)
    selected, deferred = [], []
    def visit(item):
        if isinstance(item, unittest.TestSuite):
            for child in item: visit(child)
            return
        is_live = item.id() in declared
        if layer == 'all' or (layer == 'live') == is_live:
            selected.append(item)
        else:
            deferred.append({'id': item.id(), 'status': 'NOT_RUN',
                             'layer': 'LIVE_PROVIDER' if is_live else 'SOFTWARE',
                             'required_at': ['qa', 'main'] if is_live else ['dev', 'qa', 'main']})
    visit(suite)
    return unittest.TestSuite(selected), deferred
