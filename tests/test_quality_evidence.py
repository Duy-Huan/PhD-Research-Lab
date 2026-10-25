import unittest
from tools.quality_evidence import assess


class EvidenceTests(unittest.TestCase):
    def test_suite_success_cannot_hide_missing_or_partial_coverage(self):
        tests = {"total_run": 2}
        self.assertEqual(assess(tests), "BLOCKED")
        self.assertEqual(assess(tests, {"num_statements": 10}), "BLOCKED")
        self.assertEqual(assess(tests, {"num_statements": 10, "covered_lines": 9, "num_branches": 2, "covered_branches": 2}), "FAIL")
        self.assertEqual(assess(tests, {"num_statements": 10, "covered_lines": 10, "num_branches": 2, "covered_branches": 1}), "FAIL")
        self.assertEqual(assess(tests, {"num_statements": 10, "covered_lines": 10, "num_branches": 2, "covered_branches": 2}), "CONDITIONAL")

    def test_failures_skips_and_zero_collection_never_pass(self):
        for summary, expected in [({"errors": 1}, "FAIL"), ({"failures": 1}, "FAIL"), ({"total_run": 2, "skipped": 1}, "BLOCKED"), ({}, "BLOCKED")]:
            self.assertEqual(assess(summary), expected)
