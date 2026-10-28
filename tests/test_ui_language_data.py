"""FQC-UI-QA-663: names the backend sends to the interface exist in English as well as Vietnamese.

Found by the 6.6.3 full-app Playwright QA (frontend/e2e/qa_screens.spec.ts, rule VIS-MIXED-LANG): agent descriptions,
Harness template blocks and the Docker / Python engine details appeared in Vietnamese in the English interface."""
import re
import time
import unittest
from unittest import mock

import _env  # noqa: F401
from backend.core import config
from backend.execution import harness
from backend.providers import research

VIETNAMESE = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)


def template_nodes():
    for template in harness._get_preset_workflows():
        for node in template.get("nodes", []):
            yield template, node.get("data", {})


class UiLanguageData(unittest.TestCase):
    def test_every_agent_has_an_english_description(self):
        for agent, spec in config.AGENTS.items():
            with self.subTest(agent=agent):
                self.assertTrue(spec.get("label_en"), "the English interface shows label_en")
                self.assertFalse(VIETNAMESE.search(spec["label_en"]))
        self.assertIn("label_en", config.public_config(config.load_config())["agents"]["assistant"])

    def test_every_vietnamese_template_block_has_an_english_name(self):
        seen = 0
        for template, data in template_nodes():
            label = data.get("label", "")
            if VIETNAMESE.search(label):
                seen += 1
                with self.subTest(template=template.get("id"), label=label):
                    self.assertTrue(data.get("label_en"))
                    self.assertFalse(VIETNAMESE.search(data["label_en"]))
        self.assertGreater(seen, 0, "the presets still carry Vietnamese names, each with an English one")

    def test_engine_names_and_details_are_english_like_the_other_engines(self):
        self.assertFalse(VIETNAMESE.search(research.CATALOG["docker"][1]))
        self.assertFalse(VIETNAMESE.search(research._exec_health("python", {})["detail"]))
        with mock.patch("backend.execution.sandbox.docker_exe", return_value=None):
            self.assertFalse(VIETNAMESE.search(research._exec_health("docker", {})["detail"]))
        with mock.patch("backend.execution.sandbox.docker_exe", return_value="docker"), \
                mock.patch("backend.execution.sandbox.docker_running", return_value=False):
            self.assertFalse(VIETNAMESE.search(research._exec_health("docker", {})["detail"]))

    def test_checking_the_catalog_is_fast(self):
        started = time.perf_counter()
        for _ in range(200):
            list(template_nodes())
            config.public_config(config.load_config())
        self.assertLess(time.perf_counter() - started, 5.0)


if __name__ == "__main__":
    unittest.main()
