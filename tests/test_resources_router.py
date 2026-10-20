import _env  # noqa: F401  (must be first)
import copy
import unittest
from unittest import mock

from backend import llm, llm_router, resources as R
from backend.config import load_config

REF_SCAN = {"gpus": [{"name": "NVIDIA GeForce RTX 3060", "vram_total_mb": 12288}], "memory": {"total_gb": 32}, "cpu": {"cores": 16}}


class Policy(unittest.TestCase):
    def test_reference_machine_matches_the_hardware_document(self):
        p = R.policy(load_config(), REF_SCAN)
        self.assertEqual(p["vram_safety_cap_gb"], 11.0)
        self.assertEqual(p["local_ai_vram_gb"], 8.0)
        self.assertEqual(p["ram_safety_cap_gb"], 20.0)
        self.assertEqual(p["sandbox_memory_gb"], 16)
        self.assertEqual(p["sandbox_cpus"], 6)
        self.assertEqual(p["local_ai_threads"], 4)

    def test_small_machine_and_overrides(self):
        cfg = copy.deepcopy(load_config())
        p = R.policy(cfg, {"memory": {"total_gb": 8}, "cpu": {"cores": 4}, "gpus": []})
        self.assertEqual(p["vram_safety_cap_gb"], 0.0)
        self.assertGreaterEqual(p["sandbox_memory_gb"], 2)
        self.assertEqual(p["sandbox_cpus"], 2)
        cfg["resources"]["sandbox_cpus"] = 3
        p2 = R.policy(cfg, REF_SCAN)
        self.assertEqual(p2["sandbox_cpus"], 3)
        self.assertEqual(p2["source"]["sandbox_cpus"], "override")

    def test_clamp(self):
        cfg = load_config()
        with mock.patch.object(R, "_scan", return_value=REF_SCAN):
            s, warn = R.clamp_sandbox({"memory_gb": 0, "cpus": 12, "gpu": True}, cfg)
        self.assertEqual((s["memory_gb"], s["cpus"]), (16, 6))
        self.assertTrue(warn)

    def test_failure_classes(self):
        self.assertEqual(R.classify_failure("RuntimeError: CUDA error: unspecified launch failure"), "gpu_fault")
        self.assertEqual(R.classify_failure("torch.OutOfMemoryError: CUDA out of memory."), "gpu_oom")
        self.assertEqual(R.classify_failure("SyntaxError: invalid syntax"), "")

    def test_thermal_guard_forces_cpu(self):
        hot = [{"name": "g", "temp_c": 90, "vram_used_mb": 100}]
        with mock.patch.object(R, "gpus", return_value=hot):
            out = R.prepare_gpu_run({"gpu": True}, cfg=load_config())
        self.assertFalse(out["use_gpu"])
        self.assertEqual(out["env"], {"CUDA_VISIBLE_DEVICES": ""})

    def test_manual_unload_unloads_and_waits(self):
        calls = []
        seq = iter([[{"vram_used_mb": 9000}], [{"vram_used_mb": 9000}], [{"vram_used_mb": 800}]])

        async def unload(base, model):
            calls.append(model)
            return {"ok": True}
        cfg = copy.deepcopy(load_config())
        cfg["resources"]["unload_wait_s"] = 0
        with mock.patch.object(R, "loaded_local_models", return_value={"ollama": ["qwen2.5:7b"], "lmstudio": []}), \
                mock.patch("backend.local_ai.ollama_unload", side_effect=unload), \
                mock.patch.object(R, "gpus", side_effect=lambda *a: next(seq, [{"vram_used_mb": 800}])), \
                mock.patch("time.sleep"):
            rep = R.unload_local_models(cfg)
        self.assertEqual(calls, ["qwen2.5:7b"])
        self.assertEqual(rep["vram_after_mb"], 800)


class Router(unittest.TestCase):
    def cfg(self, **keys):
        c = copy.deepcopy(load_config())
        for pid, k in keys.items():
            c["providers"][pid]["api_key"] = k
        return c

    def test_chain_offline_keeps_only_local(self):
        c = self.cfg(groq="g", anthropic="a")
        with mock.patch.object(llm_router, "online", return_value=False), \
                mock.patch.object(llm_router, "local_up", side_effect=lambda cfg, e: e == "ollama"), \
                mock.patch.object(llm_router, "_reachable", return_value=False), mock.patch.object(R, "gpu_busy", return_value=False):
            p = llm_router.plan(c, "critic")
        self.assertEqual(p["candidates"], ["ollama"])
        self.assertEqual(p["skipped"]["groq"], "offline")

    def test_live_critic_prefers_groq_and_gpu_busy_moves_local_last(self):
        c = self.cfg(groq="g")
        with mock.patch.object(llm_router, "online", return_value=True), \
                mock.patch.object(llm_router, "local_up", return_value=True), \
                mock.patch.object(llm_router, "_reachable", return_value=False), mock.patch.object(R, "gpu_busy", return_value=True):
            p = llm_router.plan(c, "critic")
        self.assertEqual(p["candidates"][0], "groq")
        self.assertEqual(p["candidates"][-1], "ollama")
        self.assertNotIn("local", p["candidates"])  # LM Studio cannot offload to CPU

    def test_sequential_fallback(self):
        cfg = self.cfg()
        cfg["agent_modes"]["critic"] = "auto"
        tried = []

        async def cloud(cfg_, pid, *a, **k):
            tried.append(pid)
            if pid == "groq":
                raise llm.LLMError("429 quota")
            return "fine"
        plan = {"agent": "critic", "kind": "live_critic", "online": True, "gpu_busy": False, "candidates": ["groq", "deepinfra"], "skipped": {}}
        with mock.patch.object(llm, "load_config", return_value=cfg), mock.patch.object(llm_router, "plan", return_value=plan), \
                mock.patch.object(llm, "cloud_chat", side_effect=cloud):
            r = _env.run_async(llm.call_agent("critic", "sys", "hi"))
        self.assertEqual(tried, ["groq", "deepinfra"])
        self.assertEqual(r["engine"], "deepinfra")
        self.assertIn("fell back", r["note"])

    def test_no_engine_is_an_honest_error(self):
        cfg = self.cfg()
        cfg["agent_modes"]["critic"] = "auto"
        plan = {"agent": "critic", "kind": "live_critic", "online": False, "gpu_busy": False, "candidates": [], "skipped": {"groq": "offline"}}
        with mock.patch.object(llm, "load_config", return_value=cfg), mock.patch.object(llm_router, "plan", return_value=plan):
            with self.assertRaises(llm.LLMError):
                _env.run_async(llm.call_agent("critic", "sys", "hi"))

    def test_gateway_headers_are_sanitised(self):
        c = copy.deepcopy(load_config())
        c["routing"]["provider_headers"] = {"ninerouter": {"X-9Router-Skills": "rtk", "Authorization": "Bearer stolen",
                                                            "X-Bad": "a\nInjected: 1"}}
        with mock.patch.object(llm, "load_config", return_value=c):
            self.assertEqual(llm.gateway_headers("ninerouter"), {"X-9Router-Skills": "rtk"})


if __name__ == "__main__":
    unittest.main()
