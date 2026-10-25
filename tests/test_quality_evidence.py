import unittest
from tools.quality_evidence import assess


class EvidenceTests(unittest.TestCase):
    def test_complete_regression_is_independent_of_coverage_percentages(self):
        tests = {'total_run': 2, 'passed': 2}
        for coverage in (None, {}, {'num_statements': 10},
                         {'num_statements': 10, 'covered_lines': 9, 'num_branches': 2, 'covered_branches': 1},
                         {'num_statements': 10, 'covered_lines': 10, 'num_branches': 2, 'covered_branches': 2}):
            self.assertEqual(assess(tests, coverage), 'CONDITIONAL')

    def test_failures_skips_and_zero_collection_never_pass(self):
        for summary, expected in [({"errors": 1}, "FAIL"), ({"failures": 1}, "FAIL"), ({"total_run": 2, "skipped": 1}, "BLOCKED"), ({}, "BLOCKED")]:
            self.assertEqual(assess(summary), expected)
