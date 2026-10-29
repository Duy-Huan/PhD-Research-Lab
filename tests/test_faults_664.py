"""FQC-FAULTS-664 (agent/PLAN_6.6.4_L3.md B3): every automated fault is caught by the check that must catch it.

A qualification case may count a detector only when it fires on a planted fault. Each fault is planted through the
app's own functions in a disposable research project: an edited result, an unsupported claim, an interrupted run, a
missing model and instructions inside a source. Faults without a deterministic detector are listed as campaign-only and
never counted."""
import importlib
import unittest

import _env
from backend.core import config
from backend.knowledge import research_store as S


class _Lazy:
    """Imported on use, so each test reports on its own (also on the commit before this module existed)."""

    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        return getattr(importlib.import_module(self.name), attr)


F = _Lazy("backend.agent.faults")


class Faults(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("fault suite tests", code_project=None)
        config.save_config({"research_os": {"enabled": True}})
        self.tid = _env.legacy_topic(S.TopicInput(title="Fault suite"))["id"]

    def check(self, fault):
        result = F.run_suite(self.tid, only=[fault])["results"][0]
        self.assertTrue(result["detected"], result)
        return result

    def test_an_edited_result_fails_independent_verification(self):
        self.assertIn("reported_gain_matches_raw", self.check("wrong_metric")["detail"])

    def test_a_claim_with_an_unmeasured_number_is_contested(self):
        self.assertEqual(self.check("unsupported_conclusion")["detail"], "claim status contested")

    def test_an_interrupted_run_is_marked_and_never_rerun(self):
        self.assertIn("status interrupted", self.check("interrupted_run")["detail"])

    def test_a_missing_model_pauses_the_mission_without_running_another(self):
        self.assertIn("cli:not-installed", self.check("provider_failure")["detail"])

    def test_instructions_inside_a_source_stay_untrusted_data(self):
        self.assertEqual(self.check("poisoned_source")["detail"], "trust untrusted")

    def test_the_suite_reports_denominators_and_never_counts_campaign_only_faults(self):
        suite = F.run_suite(self.tid)
        self.assertEqual((suite["automated"], suite["detected"]), (5, 5), suite["results"])
        self.assertEqual({c["fault"] for c in suite["campaign_only"]},
                         {"data_leakage", "stale_memory", "contradictory_memory", "poisoned_skill"})
        self.assertFalse({c["fault"] for c in suite["campaign_only"]} & {r["fault"] for r in suite["results"]})

    def test_a_broken_fixture_is_reported_as_not_detected(self):
        from unittest.mock import patch
        with patch("backend.knowledge.governance.evaluate", side_effect=RuntimeError("checker crashed")):
            result = F.run_suite(self.tid, only=["unsupported_conclusion"])["results"][0]
        self.assertFalse(result["detected"])
        self.assertIn("checker crashed", result["detail"])


if __name__ == "__main__":
    unittest.main()
