"""System scan (v3.0): hardware, Docker / WSL2 / GPU, local AI servers, toolchain — and a recommended setup.

Pure Python (no native extensions — Windows Smart App Control friendly). Results are cached in data/system/.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx

from .config import GLOBAL_DIR, load_config

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IS_WIN = sys.platform.startswith("win")
CACHE = GLOBAL_DIR / "system" / "system_scan.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd: list, timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as e:
        return 126, str(e)
    raw = (r.stdout or b"") + (r.stderr or b"")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or (len(raw) > 4 and raw[1:2] == b"\x00"):  # wsl.exe prints UTF-16
        try:
            return r.returncode, raw.decode("utf-16-le", errors="replace").replace("\x00", "")
        except Exception:
            pass
    return r.returncode, raw.decode("utf-8", errors="replace")


# ------------------------------------------------------------------ hardware
def memory() -> dict:
    try:
        if IS_WIN:
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullExtended", ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return {"total_gb": round(m.ullTotalPhys / 2**30, 1), "available_gb": round(m.ullAvailPhys / 2**30, 1), "used_pct": m.dwMemoryLoad}
        if sys.platform == "darwin":
            _, out = run(["sysctl", "-n", "hw.memsize"])
            tot = int(out.strip() or 0)
            return {"total_gb": round(tot / 2**30, 1), "available_gb": None, "used_pct": None}
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0]) * 1024
        tot, av = info.get("MemTotal", 0), info.get("MemAvailable", 0)
        return {"total_gb": round(tot / 2**30, 1), "available_gb": round(av / 2**30, 1), "used_pct": round(100 * (1 - av / tot)) if tot else None}
    except Exception as e:
        return {"error": str(e)}


def cpu() -> dict:
    name = platform.processor() or ""
    if not IS_WIN and os.path.exists("/proc/cpuinfo"):
        try:
            m = re.search(r"model name\s*:\s*(.+)", open("/proc/cpuinfo").read())
            name = m.group(1).strip() if m else name
        except Exception:
            pass
    if IS_WIN and not name.strip():
        name = os.environ.get("PROCESSOR_IDENTIFIER", "")
    load = None
    try:
        load = round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):
        pass
    return {"name": name.strip(), "cores": os.cpu_count(), "load_1m": load}


def gpus() -> list:
    smi = shutil.which("nvidia-smi") or (r"C:\Windows\System32\nvidia-smi.exe" if IS_WIN and os.path.exists(r"C:\Windows\System32\nvidia-smi.exe") else None)
    if not smi:
        return []
    code, out = run([smi, "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,driver_version",
                     "--format=csv,noheader,nounits"], 10)
    res = []
    if code != 0:
        return res
    for line in out.strip().splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) < 8:
            continue
        num = lambda x: float(x) if re.match(r"^[\d.]+$", x or "") else None
        res.append({"index": int(num(p[0]) or 0), "name": p[1], "vram_total_mb": num(p[2]), "vram_used_mb": num(p[3]),
                    "util_pct": num(p[4]), "temp_c": num(p[5]), "power_w": num(p[6]), "driver": p[7]})
    if res:
        code, out = run([smi], 10)
        m = re.search(r"CUDA Version:\s*([\d.]+)", out)
        for g in res:
            g["cuda"] = m.group(1) if m else ""
    return res


def disk(path) -> dict:
    try:
        u = shutil.disk_usage(path)
        return {"path": str(path), "free_gb": round(u.free / 2**30, 1), "total_gb": round(u.total / 2**30, 1)}
    except Exception as e:
        return {"error": str(e)}


# ------------------------------------------------------------------ docker / wsl
def docker_info() -> dict:
    exe = shutil.which("docker")
    if not exe:
        return {"installed": False, "running": False}
    out = {"installed": True, "running": False, "path": exe}
    code, txt = run([exe, "version", "--format", "{{json .}}"], 20)
    try:
        v = json.loads(txt.strip().splitlines()[-1]) if txt.strip() else {}
    except Exception:
        v = {}
    out["client_version"] = (v.get("Client") or {}).get("Version", "")
    if v.get("Server"):
        out["server_version"] = v["Server"].get("Version", "")
    code, txt = run([exe, "info", "--format", "{{json .}}"], 25)
    if code == 0 and txt.strip().startswith("{"):
        try:
            i = json.loads(txt.strip())
            out.update(running=True, os=i.get("OperatingSystem", ""), kernel=i.get("KernelVersion", ""),
                       ncpu=i.get("NCPU"), mem_gb=round((i.get("MemTotal") or 0) / 2**30, 1),
                       runtimes=sorted((i.get("Runtimes") or {}).keys()), default_runtime=i.get("DefaultRuntime", ""),
                       containers_running=i.get("ContainersRunning"), images=i.get("Images"),
                       root_dir=i.get("DockerRootDir", ""), server_version=i.get("ServerVersion", out.get("server_version", "")),
                       wsl2="WSL" in (i.get("KernelVersion", "") + i.get("OperatingSystem", "")) or "microsoft" in i.get("KernelVersion", "").lower(),
                       desktop="Docker Desktop" in i.get("OperatingSystem", ""))
            out["gpu_runtime"] = "nvidia" in out["runtimes"] or out.get("desktop", False)  # Docker Desktop: --gpus all via WSL2
        except Exception as e:
            out["error"] = str(e)
    else:
        out["error"] = (txt.strip().splitlines() or ["Docker daemon not running"])[-1][:300]
    return out


def wsl_info() -> dict:
    if not IS_WIN:
        return {"applicable": False}
    exe = shutil.which("wsl")
    if not exe:
        return {"applicable": True, "installed": False}
    code, txt = run([exe, "-l", "-v"], 15)
    distros = []
    for line in txt.splitlines()[1:]:
        p = line.replace("*", " ").split()
        if len(p) >= 3:
            distros.append({"name": p[0], "state": p[1], "version": p[2]})
    return {"applicable": True, "installed": code == 0, "distros": distros,
            "wsl2": any(d["version"] == "2" for d in distros)}


# ------------------------------------------------------------------ toolchain & local AI
def toolchain() -> dict:
    tools = {}
    for name, args in (("git", ["git", "--version"]), ("python", [sys.executable, "--version"]), ("nvcc", ["nvcc", "--version"]),
                       ("conda", ["conda", "--version"]), ("ollama", ["ollama", "--version"])):
        exe = shutil.which(args[0]) if args[0] != sys.executable else sys.executable
        if not exe:
            tools[name] = None
            continue
        code, out = run([exe] + args[1:], 10)
        line = (out.strip().splitlines() or [""])[-1]
        tools[name] = line[:120] if code == 0 else None
    try:
        from .latex_build import engines
        tools["latex"] = engines()["available"]
    except Exception:
        tools["latex"] = []
    try:
        from .local_ai import lms_cli
        tools["lms_cli"] = bool(lms_cli())
    except Exception:
        tools["lms_cli"] = False
    for mod in ("git", "docker"):
        try:
            __import__(mod)
            tools[f"py_{mod}"] = True
        except Exception:
            tools[f"py_{mod}"] = False
    return tools


def _ping(url: str) -> bool:
    try:
        return httpx.get(url, timeout=3).status_code < 500
    except Exception:
        return False


def local_ai_servers(cfg: dict) -> dict:
    from .local_ai import lms_root, ollama_root
    return {"lmstudio": _ping(lms_root(cfg.get("lmstudio_base_url")) + "/v1/models"),
            "ollama": _ping(ollama_root(cfg.get("ollama_base_url")) + "/api/tags")}


# ------------------------------------------------------------------ recommendations
GPU_IMAGE = "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime"
CPU_IMAGE = "python:3.11-slim"


def recommend(s: dict) -> dict:
    g = (s.get("gpus") or [None])[0]
    vram = (g or {}).get("vram_total_mb") or 0
    ram = (s.get("memory") or {}).get("total_gb") or 0
    d, w = s.get("docker") or {}, s.get("wsl") or {}
    items, sandbox = [], {}
    if d.get("running"):
        gpu_ok = bool(g) and (d.get("gpu_runtime") or d.get("desktop"))
        sandbox = {"mode": "docker", "gpu": gpu_ok, "image": GPU_IMAGE if gpu_ok else CPU_IMAGE,
                   "memory_gb": max(2, int(ram * 0.5)) if ram else 8, "cpus": max(1, (s["cpu"].get("cores") or 4) - 2),
                   "shm_gb": 2 if gpu_ok else 1, "network": True}
        items.append({"level": "ok", "area": "Sandbox", "text": f"Docker {d.get('server_version', '')} is running"
                      + (" with WSL2" if d.get("wsl2") else "") + (" — GPU passthrough available" if gpu_ok else " — CPU only")})
        if g and not gpu_ok:
            items.append({"level": "warn", "area": "GPU", "text": "An NVIDIA GPU was found but Docker has no GPU runtime. "
                          "Docker Desktop: Settings → Resources → WSL integration; Linux: install nvidia-container-toolkit."})
    elif d.get("installed"):
        sandbox = {"mode": "local", "gpu": bool(g), "image": "", "memory_gb": 0, "cpus": 0, "network": True}
        items.append({"level": "warn", "area": "Sandbox", "text": "Docker is installed but not running — start Docker Desktop. "
                      "Until then code runs in a local Python process (less isolated)."})
    else:
        sandbox = {"mode": "local", "gpu": bool(g), "image": "", "memory_gb": 0, "cpus": 0, "network": True}
        items.append({"level": "info", "area": "Sandbox", "text": "Docker not found: code runs in a local Python process with a time limit. "
                      "For isolation and GPU containers install Docker Desktop (WSL2 backend)."})
    if w.get("applicable") and not w.get("wsl2"):
        items.append({"level": "warn", "area": "WSL2", "text": "WSL2 not detected — Docker Desktop needs it for Linux containers + GPU (wsl --install)."})
    # local model sizing (Q4_K_M ≈ 0.6 GB per billion parameters + KV cache)
    if vram >= 22000:
        lm = ("32B (Q4_K_M) — e.g. Qwen2.5-Coder-32B-Instruct", 16384)
    elif vram >= 15000:
        lm = ("14B (Q6_K) or 22-24B (Q4_K_M)", 16384)
    elif vram >= 11000:
        lm = ("14B (Q4_K_M, ≈ 9 GB) — e.g. Qwen2.5-Coder-14B-Instruct for coding, Qwen2.5-14B-Instruct / Phi-4 for summaries", 8192)
    elif vram >= 7000:
        lm = ("7-8B (Q4_K_M/Q6_K) — e.g. Qwen2.5-Coder-7B-Instruct", 8192)
    elif vram:
        lm = ("3-4B (Q4_K_M)", 4096)
    else:
        lm = ("CPU only: 3-7B (Q4_K_M), expect slow generation", 4096)
    items.append({"level": "info", "area": "Local AI", "text": f"GPU {g['name']} with {int(vram / 1024)} GB VRAM → recommended local model size: {lm[0]}; context length ≈ {lm[1]}."
                  if g else f"No NVIDIA GPU detected → {lm[0]}."})
    if g and vram and vram < 13000:
        items.append({"level": "warn", "area": "VRAM", "text": "A 14B model and a CUDA training job do not fit in 12 GB together: unload the LM Studio/Ollama model "
                      "before long GPU training runs (one click in the sidebar), or run the coder agent on the cloud model."})
    ai = s.get("local_ai") or {}
    if not ai.get("lmstudio") and not ai.get("ollama"):
        items.append({"level": "warn", "area": "Local AI", "text": "Neither LM Studio nor Ollama is running — local agents fall back to the cloud model."})
    if not (s.get("tools") or {}).get("git"):
        items.append({"level": "warn", "area": "Git", "text": "Git is not installed — Source Control / Publish to GitHub need it (https://git-scm.com/download/win)."})
    if not (s.get("tools") or {}).get("latex"):
        items.append({"level": "info", "area": "LaTeX", "text": "No LaTeX engine — the PDF preview needs Tectonic or MiKTeX/TeX Live."})
    dsk = s.get("disk") or {}
    if dsk.get("free_gb") is not None and dsk["free_gb"] < 20:
        items.append({"level": "warn", "area": "Disk", "text": f"Only {dsk['free_gb']} GB free where data/ lives — Docker images (≈ 8 GB for PyTorch+CUDA) and checkpoints need space."})
    agents = {"coder": "local" if ai.get("lmstudio") or ai.get("ollama") else "cloud", "summarizer": "local" if ai.get("lmstudio") or ai.get("ollama") else "cloud"}
    return {"sandbox": sandbox, "items": items, "local_model": {"size": lm[0], "context": lm[1]}, "agents": agents}


def scan(force: bool = False) -> dict:
    if not force and CACHE.exists() and time.time() - CACHE.stat().st_mtime < 600:
        try:
            return json.loads(CACHE.read_text("utf-8"))
        except Exception:
            pass
    cfg = load_config()
    s = {"time": _now(), "os": {"system": platform.system(), "release": platform.release(), "version": platform.version(),
                                "machine": platform.machine(), "python": sys.version.split()[0]},
         "cpu": cpu(), "memory": memory(), "gpus": gpus(), "disk": disk(GLOBAL_DIR), "docker": docker_info(), "wsl": wsl_info(),
         "tools": toolchain(), "local_ai": local_ai_servers(cfg)}
    s["recommendation"] = recommend(s)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(s, indent=1), "utf-8")
    return s


def live() -> dict:
    """Fast, frequently polled numbers for the monitor: RAM, CPU load, GPUs."""
    return {"time": _now(), "memory": memory(), "cpu": cpu(), "gpus": gpus()}
