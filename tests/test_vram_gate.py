"""Researcher's rule: a GPU training run is refused while local LLMs hold VRAM; unloading is a manual action."""
import _env  # noqa: F401  (must be first)
import os
import time
import unittest
import warnings
from unittest import mock

from backend.execution import resources as R, sandbox
from backend.core.config import load_config

LOADED = {"ollama": ["qwen2.5:7b"], "lmstudio": ["qwen2.5-coder-14b-instruct"]}
NONE = {"ollama": [], "lmstudio": []}


def wait(job, limit=120):
    t0 = time.time()
    while job.status == "running" and time.time() - t0 < limit:
        time.sleep(0.3)
    time.sleep(0.3)


class Gate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _env.fresh_project("vram-gate")
        sandbox.save_settings({"mode": "local", "gpu": True, "timeout_s": 120})

    def setUp(self):
        sandbox.save_settings({"mode": "local", "gpu": True, "timeout_s": 120})

    def test_gate_raises_with_the_models(self):
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED), mock.patch.object(R, "gpus", return_value=[{"vram_used_mb": 9100}]):
            with self.assertRaises(R.VramBusy) as cm:
                R.vram_gate()
        self.assertEqual(cm.exception.models, ["ollama:qwen2.5:7b", "lmstudio:qwen2.5-coder-14b-instruct"])
        self.assertIn("9100 MB", str(cm.exception))

    def test_gate_can_be_disabled(self):
        cfg = load_config()
        cfg["resources"]["require_unload"] = False
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED):
            R.vram_gate(cfg)  # no exception

    def test_gpu_run_refused_before_anything_is_created(self):
        before = set(p.name for p in sandbox.runs_dir().iterdir())
        n_jobs = len(sandbox.JOBS)
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED):
            with self.assertRaises(sandbox.VramBusyError) as cm:
                sandbox.start_job('python -c "print(1)"', "run", "gpu")
        self.assertTrue(cm.exception.models)
        self.assertEqual(set(p.name for p in sandbox.runs_dir().iterdir()), before)
        self.assertEqual(len(sandbox.JOBS), n_jobs)

    def test_nothing_is_unloaded_automatically(self):
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED), \
                mock.patch.object(R, "unload_local_models") as unload, mock.patch("backend.providers.local.ollama_unload") as ou, \
                mock.patch("backend.providers.local.lmstudio_unload") as lu:
            with self.assertRaises(sandbox.VramBusyError):
                sandbox.start_job('python -c "print(1)"', "run", "gpu")
        unload.assert_not_called()
        ou.assert_not_called()
        lu.assert_not_called()

    def test_cpu_run_and_shell_jobs_are_not_gated(self):
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED):
            job = sandbox.start_job("python -c \"import os;print('CVD=[%s]' % os.environ.get('CUDA_VISIBLE_DEVICES'))\"", "run", "cpu",
                                    extra_env={"CUDA_VISIBLE_DEVICES": ""})
            shell = sandbox.start_job('python -c "print(2)"', "shell", "pip-like")
        wait(job)
        wait(shell)
        self.assertEqual(job.status, "done", job.tail(20))
        self.assertIn("CVD=[]", job.tail(20, "out"))
        self.assertFalse(sandbox.get_run(job.id)["environment"]["gpu"])
        self.assertEqual(shell.status, "done")

    def test_free_vram_lets_the_gpu_run_start(self):
        with mock.patch.object(R, "loaded_local_models", return_value=NONE):
            job = sandbox.start_job('python -c "print(3)"', "run", "gpu ok")
        wait(job)
        self.assertEqual(job.status, "done", job.tail(20))

    def test_gpu_off_in_settings_is_not_gated(self):
        sandbox.save_settings({"gpu": False})
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED):
            job = sandbox.start_job('python -c "print(5)"', "run", "no gpu")
        wait(job)
        self.assertEqual(job.status, "done")



@unittest.skipUnless(os.environ.get("PHDLAB_LMSTUDIO_LIVE") == "1",
                     "set PHDLAB_LMSTUDIO_LIVE=1 (+ optional PHDLAB_LMSTUDIO_MODEL) to load/unload a real LM Studio model")
class LMStudioLive(unittest.TestCase):
    def test_real_gate_and_manual_unload(self):
        from backend.providers import local as local_ai
        cfg = load_config()
        model = os.environ.get("PHDLAB_LMSTUDIO_MODEL", "nvidia/nemotron-3-nano-4b")
        loaded = _env.run_async(local_ai.lmstudio_load(cfg["lmstudio_base_url"], model, 4096))
        if not local_ai.lms_cli():  # without the lms CLI everything must go through LM Studio's REST API
            self.assertIn(loaded["method"], ("rest", "jit"))
        try:
            loaded = R.loaded_local_models(cfg)["lmstudio"]
            self.assertTrue(any(model in m for m in loaded), loaded)
            with self.assertRaises(R.VramBusy):
                R.vram_gate(cfg)
        finally:
            rep = R.unload_local_models(cfg)
        self.assertTrue(rep["unloaded"], rep)
        if not local_ai.lms_cli():
            self.assertEqual(rep["lmstudio_method"], "rest-v1")
        R.vram_gate(cfg)  # free again → no exception
        self.assertEqual(R.loaded_local_models(cfg)["lmstudio"], [])
        print(f"\nLM Studio live: VRAM {rep['vram_before_mb']} → {rep['vram_after_mb']} MB in {rep['waited_s']} s")


if __name__ == "__main__":
    unittest.main()
