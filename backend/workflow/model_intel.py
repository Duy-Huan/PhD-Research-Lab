"""Model Intelligence Engine (v4.1 M4): inspect a model, estimate its cost, check it against this PC's hardware.

Adapter registry — support comes from tested adapters, never from assuming formats are interchangeable:
    spec      architecture described as JSON layers (no code runs). Analytic counts, labelled ESTIMATED
              (method "analytic-spec"); latency / measured memory are UNAVAILABLE.            tested here
    pytorch   a model class in the project's code folder, profiled by a fixed script inside the sandbox (trusted
              code = the researcher's own model file). Parameter count, latency (warm-up + repeats) and CUDA peak
              memory are MEASURED; MACs come from forward hooks (ESTIMATED). Needs torch in the sandbox environment.
    onnx      parameter count from the file's initializers (MEASURED); needs the optional `onnx` package.

Every value carries {value, unit, label, method}. Conventions: 1 MAC = one multiply-add = 2 FLOPs; activation memory
counts each layer output once (inference) and keeps every output for backward (training, ×1 plus gradients ×1).
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

from .hpo import ESTIMATED, MEASURED, UNAVAILABLE

BYTES = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1}
OPTIMIZER_STATES = {"adam": 2, "adamw": 2, "sgd": 0, "sgd_momentum": 1, "rmsprop": 1}
LAYERS = ("conv1d", "conv2d", "conv3d", "linear", "batchnorm", "layernorm", "groupnorm", "act", "pool2d", "upsample2d",
          "attention", "flatten", "identity", "dropout", "pixel_shuffle")


class ModelError(ValueError):
    pass


def val(value, unit: str, label: str, method: str) -> dict:
    return {"value": value, "unit": unit, "label": label, "method": method}


def unavailable(unit: str, why: str) -> dict:
    return {"value": None, "unit": unit, "label": UNAVAILABLE, "method": why}


# ------------------------------------------------------------------ spec adapter (analytic)
def _conv_out(n: int, k: int, s: int, p: int, d: int = 1) -> int:
    return (n + 2 * p - d * (k - 1) - 1) // s + 1


def _int(layer: dict, key: str, default=None) -> int:
    v = layer.get(key, default)
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise ModelError(f"layer {layer.get('type')}: {key} must be a non-negative integer")
    return v


def analyze_spec(spec: dict) -> dict:
    """spec = {"input_shape": [C, H, W] | [C, D, H, W] | [F], "layers": [{"type": ..., ...}]} (batch excluded)."""
    if not isinstance(spec, dict) or not isinstance(spec.get("input_shape"), list) or not spec["input_shape"]:
        raise ModelError("spec needs input_shape (list, batch excluded) and layers")
    shape = list(spec["input_shape"])
    if not all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in shape):
        raise ModelError("input_shape entries must be positive integers")
    layers = spec.get("layers")
    if not isinstance(layers, list) or not layers or len(layers) > 2000:
        raise ModelError("layers must be a non-empty list (≤ 2000)")
    params = macs = act_elems = 0
    unsupported, per_layer = [], []
    for i, L in enumerate(layers):
        if not isinstance(L, dict):
            raise ModelError(f"layer {i}: must be an object")
        t = L.get("type")
        p = m = 0
        if t in ("conv1d", "conv2d", "conv3d"):
            dims = int(t[4])
            if len(shape) != dims + 1:
                raise ModelError(f"layer {i} ({t}): input has shape {shape}")
            cin, cout, k = _int(L, "in", shape[0]), _int(L, "out"), _int(L, "k")
            s, pad, g = _int(L, "stride", 1), _int(L, "padding", 0), _int(L, "groups", 1)
            if cin != shape[0] or g < 1 or cin % g or cout % g or k < 1 or s < 1:
                raise ModelError(f"layer {i} ({t}): in={cin} must match {shape[0]} channels; groups must divide in/out")
            spatial = [_conv_out(n, k, s, pad) for n in shape[1:]]
            if any(x <= 0 for x in spatial):
                raise ModelError(f"layer {i} ({t}): output size ≤ 0 for input {shape}")
            kvol = k ** dims
            p = cout * (cin // g) * kvol + (cout if L.get("bias", True) else 0)
            m = cout * math.prod(spatial) * (cin // g) * kvol
            shape = [cout] + spatial
        elif t == "linear":
            fin, fout = _int(L, "in", shape[-1]), _int(L, "out")
            if fin != shape[-1]:
                raise ModelError(f"layer {i} (linear): in={fin} but input features are {shape[-1]}")
            tokens = math.prod(shape[:-1]) if len(shape) > 1 else 1
            p = fin * fout + (fout if L.get("bias", True) else 0)
            m = tokens * fin * fout
            shape = shape[:-1] + [fout]
        elif t in ("batchnorm", "groupnorm"):
            p = 2 * shape[0]
        elif t == "layernorm":
            p = 2 * shape[-1]
        elif t in ("act", "dropout", "identity"):
            pass
        elif t == "pool2d":
            k, s = _int(L, "k"), _int(L, "stride", L.get("k"))
            if len(shape) != 3 or k < 1 or s < 1:
                raise ModelError(f"layer {i} (pool2d): needs a [C, H, W] input and k ≥ 1")
            shape = [shape[0], _conv_out(shape[1], k, s, 0), _conv_out(shape[2], k, s, 0)]
        elif t == "upsample2d":
            sc = _int(L, "scale")
            if len(shape) != 3 or sc < 1:
                raise ModelError(f"layer {i} (upsample2d): needs a [C, H, W] input and scale ≥ 1")
            shape = [shape[0], shape[1] * sc, shape[2] * sc]
        elif t == "pixel_shuffle":
            r = _int(L, "scale")
            if len(shape) != 3 or r < 1 or shape[0] % (r * r):
                raise ModelError(f"layer {i} (pixel_shuffle): channels must be divisible by scale²")
            shape = [shape[0] // (r * r), shape[1] * r, shape[2] * r]
        elif t == "flatten":
            shape = [math.prod(shape)]
        elif t == "attention":
            dim, seq = _int(L, "dim"), _int(L, "seq", None) if "seq" in L else (math.prod(shape[1:]) if len(shape) > 1 else 1)
            p = 4 * dim * dim + 4 * dim
            m = 4 * seq * dim * dim + 2 * seq * seq * dim
        else:
            unsupported.append({"index": i, "type": t})
            per_layer.append({"index": i, "type": t, "params": None, "macs": None, "out_shape": shape})
            continue
        params += p
        macs += m
        act_elems += math.prod(shape)
        per_layer.append({"index": i, "type": t, "params": p, "macs": m, "out_shape": list(shape)})
    method = "analytic-spec" + (" (partial: unsupported layers counted as 0)" if unsupported else "")
    return {"adapter": "spec", "output_shape": shape, "unsupported_ops": unsupported, "layers": per_layer,
            "params": val(params, "count", ESTIMATED, method), "trainable_params": val(params, "count", ESTIMATED, method),
            "macs_per_sample": val(macs, "MAC", ESTIMATED, method),
            "flops_per_sample": val(2 * macs, "FLOP", ESTIMATED, method + "; 1 MAC = 2 FLOPs"),
            "activation_elements_per_sample": val(act_elems, "elements", ESTIMATED, method),
            "latency_ms": unavailable("ms", "needs a measured run (pytorch adapter)"),
            "throughput_per_s": unavailable("samples/s", "needs a measured run (pytorch adapter)"),
            "peak_memory_mb": unavailable("MB", "needs a measured run (pytorch adapter)")}


def memory_estimate(report: dict, batch_size: int = 1, precision: str = "fp32", optimizer: str = "adam") -> dict:
    """Training/inference memory from a report (screening estimate, never a guarantee)."""
    if precision not in BYTES:
        raise ModelError(f"precision must be one of {', '.join(BYTES)}")
    if optimizer not in OPTIMIZER_STATES:
        raise ModelError(f"optimizer must be one of {', '.join(OPTIMIZER_STATES)}")
    if not isinstance(batch_size, int) or batch_size < 1:
        raise ModelError("batch_size must be a positive integer")
    P = (report.get("params") or {}).get("value")
    A = (report.get("activation_elements_per_sample") or {}).get("value")
    if not isinstance(P, (int, float)):
        return {"training_mb": unavailable("MB", "parameter count unknown"), "inference_mb": unavailable("MB", "parameter count unknown")}
    b = BYTES[precision]
    master = 4 if precision in ("fp16", "bf16") else 0  # mixed precision keeps fp32 master weights
    weights = P * (b + master)
    grads = P * b
    opt = P * 4 * OPTIMIZER_STATES[optimizer]
    acts = (A or 0) * batch_size * b
    mb = 2 ** 20
    method = f"estimate: weights+grads+{optimizer} states+activations×2 (batch {batch_size}, {precision})"
    out = {"training_mb": val(round((weights + grads + opt + 2 * acts) / mb, 1), "MB", ESTIMATED, method),
           "inference_mb": val(round((P * b + acts) / mb, 1), "MB", ESTIMATED, f"estimate: weights + activations (batch {batch_size})"),
           "checkpoint_mb": val(round(P * 4 / mb, 1), "MB", ESTIMATED, "fp32 weights"),
           "batch_size": batch_size, "precision": precision, "optimizer": optimizer}
    if A is None:
        out["note"] = "activation size unknown: memory excludes activations"
    return out


def feasibility(report: dict, batch_size: int = 1, precision: str = "fp32", optimizer: str = "adam",
                hardware: dict | None = None, max_gpu_memory_gb: float = 0) -> dict:
    """Compare the training estimate with this PC (resources.policy) and the workflow's GPU-memory budget."""
    if hardware is None:
        from ..resources import policy
        hardware = policy()
    mem = memory_estimate(report, batch_size, precision, optimizer)
    need = mem["training_mb"]["value"]
    cap_gb = hardware.get("vram_safety_cap_gb") or 0
    if max_gpu_memory_gb:
        cap_gb = min(cap_gb, max_gpu_memory_gb) if cap_gb else max_gpu_memory_gb
    reasons = []
    if need is None:
        feasible = None
        reasons.append("training memory unknown")
    elif not cap_gb:
        feasible = None
        reasons.append("no NVIDIA GPU detected — CPU training only (slow)")
    else:
        feasible = need <= cap_gb * 1024
        reasons.append(f"training needs ≈{need:.0f} MB, GPU budget {cap_gb * 1024:.0f} MB "
                       f"({'fits' if feasible else 'does NOT fit'})")
    max_batch = None
    if need is not None and cap_gb:
        per = memory_estimate(report, 1, precision, optimizer)["training_mb"]["value"]
        fixed = memory_estimate(report, 2, precision, optimizer)["training_mb"]["value"] - per
        if fixed > 0:
            max_batch = max(0, int((cap_gb * 1024 - (per - fixed)) // fixed))
    return {"feasible": feasible, "reasons": reasons, "memory": mem, "vram_budget_gb": cap_gb,
            "max_batch_estimate": max_batch, "hardware": {k: hardware.get(k) for k in ("gpu", "vram_total_gb",
                                                                                         "vram_safety_cap_gb", "ram_total_gb")},
            "label": ESTIMATED, "caveat": "Screening estimate: confirm with a short dry run before an expensive study."}


# ------------------------------------------------------------------ pytorch adapter (sandbox, measured)
PROFILE_TAG = "PHDLAB_PROFILE "
_SCRIPT = r'''
import importlib.util, json, sys, time
spec = importlib.util.spec_from_file_location("phdlab_model", {path!r})
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import torch
model = getattr(mod, {cls!r})(**{kwargs!r})
dev = "cuda" if torch.cuda.is_available() and {gpu!r} else "cpu"
dtype = {{"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}}[{precision!r}]
model = model.to(dev).to(dtype).eval()
x = torch.randn({batch}, *{shape!r}, device=dev, dtype=dtype)
P = sum(p.numel() for p in model.parameters()); T = sum(p.numel() for p in model.parameters() if p.requires_grad)
macs = [0]
def hook(m, i, o):
    if isinstance(m, (torch.nn.Conv1d, torch.nn.Conv2d, torch.nn.Conv3d)):
        macs[0] += o.numel() // o.shape[0] * (m.in_channels // m.groups) * int(torch.tensor(m.kernel_size).prod())
    elif isinstance(m, torch.nn.Linear):
        macs[0] += o.numel() // o.shape[0] * m.in_features
hs = [m.register_forward_hook(hook) for m in model.modules()]
with torch.no_grad():
    model(x)
for h in hs: h.remove()
if dev == "cuda": torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
with torch.no_grad():
    for _ in range({warmup}): model(x)
    if dev == "cuda": torch.cuda.synchronize()
    ts = []
    for _ in range({repeats}):
        t0 = time.perf_counter(); model(x)
        if dev == "cuda": torch.cuda.synchronize()
        ts.append((time.perf_counter() - t0) * 1000)
ts.sort()
out = {{"params": P, "trainable": T, "macs": macs[0], "latency_ms_median": ts[len(ts) // 2], "latency_ms_p95": ts[int(len(ts) * 0.95) - 1 if len(ts) > 1 else 0],
       "peak_mb": (torch.cuda.max_memory_allocated() / 2**20) if dev == "cuda" else None, "device": dev,
       "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0) if dev == "cuda" else ""}}
print("PHDLAB_PROFILE " + json.dumps(out), flush=True)
'''


def profiling_script(model_path: str, class_name: str, input_shape: list, batch_size: int = 1, precision: str = "fp32",
                     gpu: bool = True, warmup: int = 5, repeats: int = 20, kwargs: dict | None = None) -> str:
    """The fixed profiling program (parameters are data inserted with repr — nothing from an agent is executed)."""
    from ..sandbox import code_dir
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,80}", class_name or ""):
        raise ModelError("class_name must be a Python identifier")
    root = code_dir().resolve()
    p = (root / model_path).resolve()
    if root not in p.parents or p.suffix != ".py" or not p.is_file():
        raise ModelError("model_path must be an existing .py file inside the project's code folder")
    if precision not in ("fp32", "fp16", "bf16"):
        raise ModelError("precision must be fp32, fp16 or bf16")
    if not (isinstance(input_shape, list) and input_shape and all(isinstance(x, int) and x > 0 for x in input_shape)):
        raise ModelError("input_shape must be a list of positive integers (batch excluded)")
    if not (1 <= int(batch_size) <= 4096 and 0 <= int(warmup) <= 100 and 1 <= int(repeats) <= 1000):
        raise ModelError("batch_size 1–4096, warmup 0–100, repeats 1–1000")
    kw = kwargs or {}
    json.dumps(kw)  # constructor kwargs must be plain JSON data
    return _SCRIPT.format(path=str(p), cls=class_name, kwargs=kw, gpu=bool(gpu), precision=precision, batch=int(batch_size),
                          shape=list(input_shape), warmup=int(warmup), repeats=int(repeats))


def parse_profile(stdout: str, batch_size: int, warmup: int, repeats: int, precision: str) -> dict:
    line = next((l for l in reversed((stdout or "").splitlines()) if l.startswith(PROFILE_TAG)), None)
    if line is None:
        raise ModelError("the profiling run printed no result (is torch installed in the sandbox environment?)")
    d = json.loads(line[len(PROFILE_TAG):])
    how = f"measured on {d.get('device')} {d.get('gpu') or ''}, torch {d.get('torch')}, batch {batch_size}, {precision}, " \
          f"{warmup} warm-up + {repeats} repeats".replace("  ", " ")
    lat = d.get("latency_ms_median")
    return {"adapter": "pytorch", "params": val(d["params"], "count", MEASURED, "sum(p.numel())"),
            "trainable_params": val(d["trainable"], "count", MEASURED, "requires_grad parameters"),
            "macs_per_sample": val(d["macs"], "MAC", ESTIMATED, "forward hooks on Conv/Linear only"),
            "flops_per_sample": val(2 * d["macs"], "FLOP", ESTIMATED, "forward hooks; 1 MAC = 2 FLOPs"),
            "latency_ms": val(lat, "ms", MEASURED, how + " (median)"),
            "latency_p95_ms": val(d.get("latency_ms_p95"), "ms", MEASURED, how),
            "throughput_per_s": val(round(batch_size * 1000 / lat, 2) if lat else None, "samples/s", MEASURED, how),
            "peak_memory_mb": val(d["peak_mb"], "MB", MEASURED, how) if d.get("peak_mb") is not None
            else unavailable("MB", "CPU run: CUDA peak memory not measurable"),
            "environment": {k: d.get(k) for k in ("device", "gpu", "torch")}}


# ------------------------------------------------------------------ onnx adapter
def analyze_onnx(path: str) -> dict:
    if importlib.util.find_spec("onnx") is None:
        raise ModelError("the ONNX adapter needs the optional 'onnx' package (pip install onnx)")
    import onnx  # pragma: no cover - not installed in this environment
    from onnx import numpy_helper  # pragma: no cover
    m = onnx.load(str(Path(path)))  # pragma: no cover
    P = sum(int(numpy_helper.to_array(t).size) for t in m.graph.initializer)  # pragma: no cover
    return {"adapter": "onnx", "params": val(P, "count", MEASURED, "sum of ONNX initializer sizes"),  # pragma: no cover
            "macs_per_sample": unavailable("MAC", "not computed for ONNX graphs"),
            "latency_ms": unavailable("ms", "run the pytorch adapter or an ONNX runtime benchmark")}


def adapters() -> list:
    return [{"id": "spec", "format": "JSON layer list", "available": True, "trusted_code": False,
             "operations": ["params", "macs", "flops", "activations", "memory_estimate", "feasibility"],
             "limitations": "analytic only — no latency, no measured memory; unsupported layers are listed"},
            {"id": "pytorch", "format": "PyTorch nn.Module (.py in the project code folder)", "available": "checked on run",
             "trusted_code": True, "operations": ["params (measured)", "latency", "throughput", "peak CUDA memory", "macs (hooks)"],
             "limitations": "runs the researcher's model file in the sandbox; needs torch in that environment"},
            {"id": "onnx", "format": "ONNX file", "available": importlib.util.find_spec("onnx") is not None, "trusted_code": False,
             "operations": ["params (from initializers)"], "limitations": "optional 'onnx' package"}]
