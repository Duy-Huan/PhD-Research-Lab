"""v4.1 Model Intelligence: analytic spec adapter, memory/feasibility vs. this PC, PyTorch profiling script (fixed, no
agent code) and result parsing, ONNX availability — every value carries a MEASURED / ESTIMATED / UNAVAILABLE label."""
import _env  # noqa: F401  (must be first)
import json
import unittest
from unittest import mock

from backend.workflow import model_intel as MI

HW = {"gpu": "RTX 3060", "vram_total_gb": 12.0, "vram_safety_cap_gb": 11.0, "ram_total_gb": 32}


class Spec(unittest.TestCase):
    def test_conv_net_counts(self):
        r = MI.analyze_spec({"input_shape": [3, 32, 32], "layers": [
            {"type": "conv2d", "in": 3, "out": 16, "k": 3, "padding": 1}, {"type": "batchnorm"}, {"type": "act"},
            {"type": "pool2d", "k": 2}, {"type": "conv2d", "out": 32, "k": 3, "stride": 2, "padding": 1, "bias": False, "groups": 2},
            {"type": "upsample2d", "scale": 2}, {"type": "pixel_shuffle", "scale": 2}, {"type": "dropout"}, {"type": "identity"},
            {"type": "flatten"}, {"type": "linear", "out": 10}, {"type": "layernorm"}]})
        conv1 = 16 * 3 * 9 + 16
        self.assertEqual(r["layers"][0]["params"], conv1)
        self.assertEqual(r["layers"][0]["macs"], 16 * 32 * 32 * 27)
        self.assertEqual(r["layers"][4]["params"], 32 * 8 * 9)
        self.assertEqual(r["layers"][4]["out_shape"], [32, 8, 8])
        self.assertEqual(r["layers"][6]["out_shape"], [8, 32, 32])
        self.assertEqual(r["output_shape"], [10])
        self.assertEqual(r["params"]["label"], "ESTIMATED")
        self.assertEqual(r["flops_per_sample"]["value"], 2 * r["macs_per_sample"]["value"])
        self.assertEqual(r["latency_ms"]["label"], "UNAVAILABLE")

    def test_3d_1d_attention_and_unsupported(self):
        r = MI.analyze_spec({"input_shape": [1, 8, 16, 16], "layers": [{"type": "conv3d", "out": 4, "k": 3, "padding": 1}]})
        self.assertEqual(r["params"]["value"], 4 * 27 + 4)
        r = MI.analyze_spec({"input_shape": [2, 50], "layers": [{"type": "conv1d", "out": 4, "k": 5}, {"type": "lstm"}]})
        self.assertEqual(r["unsupported_ops"], [{"index": 1, "type": "lstm"}])
        self.assertIn("partial", r["params"]["method"])
        r = MI.analyze_spec({"input_shape": [64, 4, 4], "layers": [{"type": "attention", "dim": 64}]})
        self.assertEqual(r["macs_per_sample"]["value"], 4 * 16 * 64 * 64 + 2 * 16 * 16 * 64)
        r = MI.analyze_spec({"input_shape": [64], "layers": [{"type": "attention", "dim": 64, "seq": 1}, {"type": "groupnorm"}]})
        self.assertEqual(r["layers"][1]["params"], 128)

    def test_spec_errors(self):
        bad = [None, {"input_shape": []}, {"input_shape": [0]}, {"input_shape": [3], "layers": []},
               {"input_shape": [3], "layers": ["x"]},
               {"input_shape": [3, 8, 8], "layers": [{"type": "conv1d", "out": 2, "k": 1}]},
               {"input_shape": [3, 8, 8], "layers": [{"type": "conv2d", "in": 4, "out": 2, "k": 1}]},
               {"input_shape": [3, 8, 8], "layers": [{"type": "conv2d", "out": 2, "k": 9}]},
               {"input_shape": [3, 8, 8], "layers": [{"type": "conv2d", "out": -1, "k": 1}]},
               {"input_shape": [3, 8, 8], "layers": [{"type": "conv2d", "out": True, "k": 1}]},
               {"input_shape": [8], "layers": [{"type": "linear", "in": 4, "out": 2}]},
               {"input_shape": [8], "layers": [{"type": "pool2d", "k": 2}]},
               {"input_shape": [8], "layers": [{"type": "upsample2d", "scale": 2}]},
               {"input_shape": [3, 4, 4], "layers": [{"type": "pixel_shuffle", "scale": 2}]}]
        for b in bad:
            with self.assertRaises(MI.ModelError, msg=b):
                MI.analyze_spec(b)


class Memory(unittest.TestCase):
    rep = MI.analyze_spec({"input_shape": [3, 64, 64], "layers": [{"type": "conv2d", "out": 64, "k": 3, "padding": 1}]})

    def test_memory_estimate(self):
        m = MI.memory_estimate(self.rep, 4, "fp16", "sgd_momentum")
        self.assertEqual(m["training_mb"]["label"], "ESTIMATED")
        self.assertGreater(m["training_mb"]["value"], m["inference_mb"]["value"])
        for bad in (dict(precision="fp8"), dict(optimizer="lion"), dict(batch_size=0)):
            with self.assertRaises(MI.ModelError):
                MI.memory_estimate(self.rep, **bad)
        self.assertEqual(MI.memory_estimate({}, 1)["training_mb"]["label"], "UNAVAILABLE")
        self.assertIn("note", MI.memory_estimate({"params": {"value": 1000}}, 1))

    def test_feasibility(self):
        f = MI.feasibility(self.rep, 8, hardware=HW)
        self.assertTrue(f["feasible"])
        self.assertGreater(f["max_batch_estimate"], 8)
        self.assertEqual(f["label"], "ESTIMATED")
        huge = {"params": {"value": 4e9}, "activation_elements_per_sample": {"value": 1e6}}
        self.assertFalse(MI.feasibility(huge, 1, hardware=HW)["feasible"])
        self.assertIsNone(MI.feasibility(self.rep, 1, hardware={"vram_safety_cap_gb": 0})["feasible"])
        self.assertIsNone(MI.feasibility({}, 1, hardware=HW)["feasible"])
        self.assertEqual(MI.feasibility(self.rep, 1, hardware=HW, max_gpu_memory_gb=2)["vram_budget_gb"], 2)
        self.assertEqual(MI.feasibility(self.rep, 1, hardware={"vram_safety_cap_gb": 0}, max_gpu_memory_gb=3)["vram_budget_gb"], 3)
        no_act = {"params": {"value": 10}}
        self.assertIsNone(MI.feasibility(no_act, 1, hardware=HW)["max_batch_estimate"])
        with mock.patch("backend.resources.policy", return_value=HW):
            self.assertTrue(MI.feasibility(self.rep, 1)["feasible"])


class Profiling(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("model-intel")
        from backend.sandbox import code_dir
        (code_dir() / "net.py").write_text("class Net: pass\n", "utf-8")

    def test_script_is_fixed_and_validated(self):
        s = MI.profiling_script("net.py", "Net", [3, 32, 32], 2, "fp16", False, 1, 3, {"width": 8})
        compile(s, "profile.py", "exec")  # valid Python
        self.assertIn("'Net'", s)
        self.assertIn("{'width': 8}", s)
        for kw in (dict(class_name="Net; import os"), dict(model_path="../x.py"), dict(model_path="missing.py"),
                   dict(precision="int4"), dict(input_shape=[0]), dict(batch_size=0)):
            args = dict(model_path="net.py", class_name="Net", input_shape=[3, 8, 8])
            args.update(kw)
            with self.assertRaises(MI.ModelError, msg=kw):
                MI.profiling_script(**args)
        with self.assertRaises(TypeError):
            MI.profiling_script("net.py", "Net", [3, 8, 8], kwargs={"f": object()})

    def test_parse_profile(self):
        gpu = {"params": 1000, "trainable": 900, "macs": 5000, "latency_ms_median": 2.0, "latency_ms_p95": 2.5, "peak_mb": 350.0,
               "device": "cuda", "torch": "2.5", "gpu": "RTX 3060"}
        r = MI.parse_profile("noise\n" + MI.PROFILE_TAG + json.dumps(gpu), 4, 5, 20, "fp32")
        self.assertEqual(r["params"]["label"], "MEASURED")
        self.assertEqual(r["macs_per_sample"]["label"], "ESTIMATED")
        self.assertEqual(r["throughput_per_s"]["value"], 2000.0)
        self.assertEqual(r["peak_memory_mb"]["label"], "MEASURED")
        cpu = dict(gpu, peak_mb=None, device="cpu", gpu="", latency_ms_median=0)
        r = MI.parse_profile(MI.PROFILE_TAG + json.dumps(cpu), 1, 0, 1, "fp32")
        self.assertEqual(r["peak_memory_mb"]["label"], "UNAVAILABLE")
        self.assertIsNone(r["throughput_per_s"]["value"])
        with self.assertRaises(MI.ModelError):
            MI.parse_profile("no result", 1, 0, 1, "fp32")

    def test_onnx_and_registry(self):
        with self.assertRaises(MI.ModelError):
            MI.analyze_onnx("m.onnx")
        ids = [a["id"] for a in MI.adapters()]
        self.assertEqual(ids, ["spec", "pytorch", "onnx"])
        self.assertTrue(MI.adapters()[1]["trusted_code"])


if __name__ == "__main__":
    unittest.main()
