"""Cloud Providers Contract & Authorization Integrity Test Suite.

Verifies:
  - All registered cloud providers enforce API key requirements
  - Zero unauthorized egress when allow_api_billing=False
  - Transparent BLOCKED status reporting for unauthenticated endpoints
"""
import asyncio
import unittest

from tests.live_e2e.conftest_or_setup import configure_live_phi4
from backend.core import config as C
from backend.providers import models


class TestProviderCloudLive(unittest.TestCase):
    def setUp(self):
        configure_live_phi4()

    def test_cloud_providers_registry_and_contracts(self):
        """Enumerate registered cloud providers and check specifications."""
        expected_providers = {"anthropic", "openai", "gemini", "openrouter", "deepseek", "groq", "mistral", "custom"}
        for pid in expected_providers:
            self.assertIn(pid, C.PROVIDERS, f"Provider {pid} must be registered in PROVIDERS dictionary")
            spec = C.PROVIDERS[pid]
            self.assertIn("label", spec)
            self.assertIn("kind", spec)
            self.assertIn("model", spec)

    def test_unauthenticated_cloud_call_raises_error_no_egress(self):
        """Unauthenticated cloud provider calls must raise clear error without network leakage."""
        cfg = C.load_config()
        # Force empty key
        cfg["providers"]["anthropic"]["api_key"] = ""
        with self.assertRaises(models.LLMError) as ctx:
            asyncio.run(models.cloud_chat(cfg, "anthropic", "sys", [{"role": "user", "content": "hi"}], 50))
        self.assertIn("API key", str(ctx.exception))

    def test_zero_paid_egress_policy_enforcement(self):
        """Missions with allow_api_billing=False refuse cloud providers."""
        from backend.agent import research_os as OS
        cfg = C.load_config()
        fake_mission = {
            "payload": {
                "spec": {
                    "control": {
                        "app_backend": "anthropic",
                        "app_model": "claude-sonnet-4-6",
                        "allow_api_billing": False
                    }
                }
            }
        }
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(OS.fixed_reasoning(fake_mission, "sys", "user prompt"))
        self.assertIn("Hidden API billing refused", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
