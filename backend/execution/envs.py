"""Execution environments (v3.4): one place that knows every Python and every Docker image the research code can run in.

    Python environment   a) "venv"      a private virtual environment of the project, created from a base interpreter
                                         you choose (any Python found on this machine)
                         b) "existing"  run directly in an interpreter you already maintain (system Python, conda env,
                                         a venv you created) — packages you installed there are used as they are
    Docker               any image: the recommended one for this machine, a vetted catalog (PyTorch/CUDA, TensorFlow,
                         Hugging Face, NGC, CPU Python, Jupyter), images already on this machine, or a Docker Hub search
    Auto                 per run: Docker when the code needs a GPU framework and Docker is running, else the Python env

discover_pythons() finds interpreters that are NOT on PATH too (the Windows python.org/Store installs, the py launcher's
list, conda environments) — that is how a JupyterLab installed with `pip install jupyterlab` into the system Python is
found even though the app itself runs from its own .venv.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IS_WIN = sys.platform.startswith("win")
IMAGE_RE = re.compile(r"^[a-z0-9]([a-z0-9._/-]*[a-z0-9])?(:[\w][\w.-]{0,127})?(@sha256:[0-9a-f]{64})?$")
_cache: dict = {}

PROBE = r"""
import importlib.util as u, json, sys, os
def has(m):
    try: return u.find_spec(m) is not None
    except Exception: return False
info = {"version": sys.version.split()[0], "executable": sys.executable, "prefix": sys.prefix,
        "venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix), "conda": os.path.isdir(os.path.join(sys.prefix, "conda-meta")),
        "pip": has("pip"), "jupyterlab": has("jupyterlab"), "notebook": has("notebook"), "ipykernel": has("ipykernel"),
        "torch": has("torch"), "tensorflow": has("tensorflow"), "numpy": has("numpy")}
print(json.dumps(info))
"""


def _candidates() -> list:
    out = [(sys.executable, "PhD-Lab app")]
    base = getattr(sys, "_base_executable", "")
    if base and Path(base).exists():
        out.append((base, "base of the app"))
    for n in ("python", "python3"):
        p = shutil.which(n)
        if p:
            out.append((p, "PATH"))
    if IS_WIN:
        try:  # the py launcher lists every registered CPython
            r = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
            for line in r.stdout.splitlines():
                m = re.search(r"([A-Za-z]:\\.+?python(?:w)?\.exe)\s*$", line.strip(), re.I)
                if m:
                    out.append((m.group(1), "py launcher"))
        except (OSError, subprocess.SubprocessError):
            pass
        la, home = os.environ.get("LOCALAPPDATA", ""), str(Path.home())
        for pat in (rf"{la}\Python\pythoncore-*\python.exe", rf"{la}\Programs\Python\Python3*\python.exe",
                    r"C:\Program Files\Python3*\python.exe", rf"{home}\miniconda3\python.exe", rf"{home}\anaconda3\python.exe",
                    rf"{home}\miniforge3\python.exe", rf"{home}\miniconda3\envs\*\python.exe", rf"{home}\anaconda3\envs\*\python.exe",
                    rf"{home}\miniforge3\envs\*\python.exe", r"C:\ProgramData\miniconda3\python.exe", r"C:\ProgramData\anaconda3\python.exe"):
            out += [(p, "installed") for p in glob.glob(pat)]
    else:
        for pat in ("/usr/bin/python3*", "/usr/local/bin/python3*", str(Path.home() / "miniconda3/envs/*/bin/python"),
                    str(Path.home() / "anaconda3/envs/*/bin/python"), str(Path.home() / "miniconda3/bin/python")):
            out += [(p, "installed") for p in glob.glob(pat) if re.search(r"python3?(\.\d+)?$", p)]
    conda = shutil.which("conda")
    if conda:
        try:
            r = subprocess.run([conda, "env", "list", "--json"], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
            for e in json.loads(r.stdout or "{}").get("envs", []):
                p = Path(e) / ("python.exe" if IS_WIN else "bin/python")
                if p.exists():
                    out.append((str(p), "conda"))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    try:
        from backend.execution.sandbox import sb_dir
        for v in sb_dir().glob("venv*"):
            p = v / ("Scripts/python.exe" if IS_WIN else "bin/python")
            if p.exists():
                out.append((str(p), "project venv"))
    except Exception:
        pass
    seen, res = set(), []
    for p, src in out:
        if not p or "WindowsApps" in p:  # Store "app execution alias" stubs open the Store instead of running Python
            continue
        try:
            key = str(Path(p).resolve()).lower() if IS_WIN else str(Path(p).resolve())
        except OSError:
            continue
        if key not in seen and Path(p).exists():
            seen.add(key)
            res.append((str(Path(p)), src))
    return res


def probe(python: str, timeout: float = 20) -> dict | None:
    try:
        r = subprocess.run([python, "-c", PROBE], capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                           stdin=subprocess.DEVNULL)
        line = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else ""
        return json.loads(line) if line else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def discover_pythons(force: bool = False) -> list:
    hit = _cache.get("pythons")
    if hit and not force and time.time() - hit[0] < 300:
        return hit[1]
    res = []
    for p, src in _candidates():
        info = probe(p)
        if info:
            res.append({"path": p, "source": src, **info,
                        "label": f"Python {info['version']} · {'conda' if info['conda'] else 'venv' if info['venv'] else 'system'} · {p}"})
    res.sort(key=lambda d: (d["source"] == "PhD-Lab app", [-int(x) for x in re.findall(r"\d+", d["version"])[:2]], d["path"]))
    _cache["pythons"] = (time.time(), res)
    return res


def python_with(module: str) -> dict | None:
    """First discovered interpreter that has `module` importable (e.g. jupyterlab)."""
    return next((p for p in discover_pythons() if p.get(module)), None)


# ------------------------------------------------------------------ Docker images
CATALOG = [
    {"image": "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime", "gpu": True, "size_gb": 7.5, "group": "PyTorch",
     "note": "PyTorch 2.5.1 · CUDA 12.4 · cuDNN 9 — default for NVIDIA GPUs (RTX 30/40)"},
    {"image": "pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime", "gpu": True, "size_gb": 7.4, "group": "PyTorch",
     "note": "PyTorch 2.4.1 · CUDA 12.4"},
    {"image": "pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime", "gpu": True, "size_gb": 7.0, "group": "PyTorch",
     "note": "PyTorch 2.4.1 · CUDA 12.1 — older NVIDIA drivers"},
    {"image": "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel", "gpu": True, "size_gb": 14, "group": "PyTorch",
     "note": "devel: nvcc + headers to compile CUDA extensions (mamba-ssm, flash-attn, custom ops)"},
    {"image": "nvcr.io/nvidia/pytorch:24.10-py3", "gpu": True, "size_gb": 21, "group": "NVIDIA NGC",
     "note": "NVIDIA-optimised PyTorch + Apex, DALI, TensorRT — large"},
    {"image": "tensorflow/tensorflow:2.17.0-gpu", "gpu": True, "size_gb": 7.0, "group": "TensorFlow", "note": "TensorFlow 2.17 with GPU"},
    {"image": "huggingface/transformers-pytorch-gpu:latest", "gpu": True, "size_gb": 12, "group": "Hugging Face",
     "note": "transformers + PyTorch + CUDA, for LLM / ViT fine-tuning"},
    {"image": "nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04", "gpu": True, "size_gb": 3.5, "group": "CUDA base",
     "note": "bare CUDA + cuDNN (no Python packages) — build your own stack"},
    {"image": "python:3.12-slim", "gpu": False, "size_gb": 0.15, "group": "CPU Python", "note": "small CPU image, Python 3.12"},
    {"image": "python:3.11-slim", "gpu": False, "size_gb": 0.15, "group": "CPU Python", "note": "small CPU image, Python 3.11"},
    {"image": "quay.io/jupyter/scipy-notebook:latest", "gpu": False, "size_gb": 1.6, "group": "Jupyter",
     "note": "CPU · NumPy/SciPy/pandas/matplotlib/scikit-learn preinstalled"},
]


# ------------------------------------------------------------------ smart choice
def gpu_present() -> bool:
    return bool(shutil.which("nvidia-smi"))


def choose(settings: dict, plan: dict | None = None) -> tuple[str, str]:
    """(mode, reason) for one run. Explicit choices win; 'auto' looks at the code and the machine."""
    from backend.execution.sandbox import docker_exe, docker_running
    mode = settings.get("mode", "auto")
    if mode in ("docker", "local"):
        return mode, "chosen in the environment settings"
    docker_ok = bool(docker_exe()) and docker_running()
    needs_gpu = bool((plan or {}).get("gpu_frameworks")) and bool(settings.get("gpu"))
    if not docker_ok:
        return "local", "Docker is not running"
    if needs_gpu and gpu_present():
        return "docker", f"the code uses {', '.join(plan['gpu_frameworks'][:3])} and an NVIDIA GPU is available (reproducible CUDA image)"
    return "local", "no GPU framework in the code — the Python environment starts faster than a container"


def summary() -> dict:
    """What the Workspace panel shows: the active choice, interpreters, Docker state and the dependency plan."""
    from backend.execution import deps
    from backend.execution.sandbox import code_dir, docker_exe, docker_running, effective_image, load_settings, local_python_info
    s = load_settings()
    plan = deps.plan_cached(code_dir())
    mode, why = choose(s, plan)
    return {"settings": {k: s.get(k) for k in ("mode", "image", "gpu", "python_mode", "python_base", "auto_deps", "torch_index")},
            "effective": {"mode": mode, "reason": why, "image": effective_image(s) if mode == "docker" else "",
                          "python": local_python_info() if mode == "local" else None},
            "docker": {"installed": bool(docker_exe()), "running": bool(docker_exe()) and docker_running()},
            "gpu": gpu_present(), "deps": plan}
