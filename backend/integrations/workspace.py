"""Workspace adapter (v3.2, Milestone 3): VS Code is the editor, Dev Containers the reproducible environment, Jupyter the
notebook. PhD Lab only manages metadata and lifecycle — it never re-implements an editor or a terminal.

Security: actions take a TARGET NAME ("code" = the project's code workspace, "project" = its data folder), never an
arbitrary path from the browser; every resolved path is checked against that allow-list.
"""
from __future__ import annotations

import atexit
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx

from ..config import APP_VERSION, data_dir, load_config
from .base import NO_WINDOW, IntegrationError, IntegrationStatus, cached, run_cli, which

IS_WIN = sys.platform.startswith("win")
EXT_DEVCONTAINERS = "ms-vscode-remote.remote-containers"
EXT_PYTHON = "ms-python.python"
EXT_JUPYTER = "ms-toolsai.jupyter"
EXT_CODEX = "openai.chatgpt"  # "Codex – OpenAI's coding agent" (developers.openai.com/codex/ide)
INSTALLABLE = {EXT_CODEX, EXT_DEVCONTAINERS, EXT_JUPYTER, EXT_PYTHON}


# ------------------------------------------------------------------ allow-listed targets
def targets() -> dict:
    from ..sandbox import code_dir
    return {"code": code_dir().resolve(), "project": data_dir().resolve()}


def resolve_target(name: str) -> Path:
    t = targets()
    if name not in t:
        raise IntegrationError(f"Unknown workspace target '{name}' (allowed: {', '.join(t)})")
    p = t[name]
    if not p.is_dir():
        raise IntegrationError(f"{p} does not exist")
    return p


# ------------------------------------------------------------------ VS Code
def vscode_cli() -> str | None:
    custom = (load_config()["workspace"].get("vscode_path") or "").strip()
    if custom and Path(custom).is_file():
        return custom
    p = which("code", "code-insiders", "codium")
    if p:
        return p
    if IS_WIN:
        for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            for sub in ("Programs\\Microsoft VS Code\\bin\\code.cmd", "Microsoft VS Code\\bin\\code.cmd"):
                c = Path(base) / sub
                if base and c.is_file():
                    return str(c)
    return None


def _vscode_probe() -> dict:
    cli = vscode_cli()
    if not cli:
        return {"cli": None}
    code, out = run_cli([cli, "--version"], 20)
    ver = out.strip().splitlines()[0] if code == 0 and out.strip() else ""
    code2, ext = run_cli([cli, "--list-extensions"], 30)
    exts = [e.strip().lower() for e in ext.splitlines()] if code2 == 0 else []
    return {"cli": cli, "version": ver, "ok": code == 0, "extensions": exts, "error": "" if code == 0 else out.strip()[-200:]}


def vscode_status(force: bool = False) -> IntegrationStatus:
    if force:
        from .base import _cache
        _cache.pop("vscode", None)
    p = cached("vscode", 60, _vscode_probe)
    if not p["cli"]:
        return IntegrationStatus("vscode", "VS Code", "unavailable", "The `code` command was not found.",
                                 setup=["Install VS Code (https://code.visualstudio.com/)",
                                        "Windows: the installer adds `code` to PATH (restart the app afterwards)",
                                        "or set Control Center → Workspace → VS Code path to …\\bin\\code.cmd"])
    if not p["ok"]:
        return IntegrationStatus("vscode", "VS Code", "error", p["error"] or "`code --version` failed")
    exts = p["extensions"]
    caps = ["open_folder", "open_file", "deep_link"] + (["dev_container"] if EXT_DEVCONTAINERS in exts else []) + \
        (["jupyter"] if EXT_JUPYTER in exts else []) + (["codex"] if EXT_CODEX in exts else [])
    return IntegrationStatus("vscode", "VS Code", "available", f"CLI: {p['cli']}", version=p["version"], capabilities=caps,
                             extra={"dev_containers_ext": EXT_DEVCONTAINERS in exts, "python_ext": EXT_PYTHON in exts,
                                    "jupyter_ext": EXT_JUPYTER in exts, "codex_ext": EXT_CODEX in exts})


def open_file(rel: str, line: int = 1) -> dict:
    """Open one file of the code workspace in VS Code (inside the workspace window) at a line."""
    from .. import ide_fs
    cli = vscode_cli()
    if not cli:
        raise IntegrationError("VS Code CLI not found — install VS Code or set its path in the Control Center")
    try:
        p = ide_fs.safe(rel)
    except ide_fs.FsError as e:
        raise IntegrationError(str(e))
    if not p.is_file():
        raise IntegrationError(f"{rel} does not exist in the code workspace")
    root = resolve_target("code")
    code, out = run_cli([cli, str(root), "-g", f"{p}:{max(1, int(line or 1))}"], 30)
    if code != 0:
        raise IntegrationError(f"`code` exited with {code}: {out.strip()[-300:]}")
    return {"launched": True, "path": str(p), "note": f"Opened {rel} in VS Code."}


def install_extension(ext: str) -> dict:
    """Install one allow-listed VS Code extension (explicit researcher action)."""
    if ext not in INSTALLABLE:
        raise IntegrationError(f"Extension {ext} is not on the allow-list ({', '.join(sorted(INSTALLABLE))})")
    cli = vscode_cli()
    if not cli:
        raise IntegrationError("VS Code CLI not found")
    code, out = run_cli([cli, "--install-extension", ext], 300)
    from .base import _cache
    _cache.pop("vscode", None)
    if code != 0:
        raise IntegrationError(f"Installing {ext} failed ({code}): {out.strip()[-300:]}")
    return {"installed": ext, "output": out.strip()[-400:]}


def deep_link(target: str = "code") -> str:
    """vscode://file/… link the browser hands to VS Code (works without the backend launching anything)."""
    p = resolve_target(target).as_posix()
    return "vscode://file/" + (p if not p.startswith("/") else p[1:]) + "/"


def open_folder(target: str = "code") -> dict:
    cli = vscode_cli()
    if not cli:
        raise IntegrationError("VS Code CLI not found — install VS Code or set its path in the Control Center")
    p = resolve_target(target)
    code, out = run_cli([cli, str(p)], 30)
    if code != 0:
        raise IntegrationError(f"`code` exited with {code}: {out.strip()[-300:]}")
    return {"launched": True, "path": str(p), "note": "VS Code accepted the request (the window opens on this computer)."}


def devcontainer_uri(target: str = "code") -> str:
    p = resolve_target(target)
    return f"vscode-remote://dev-container+{str(p).encode('utf-8').hex()}/workspaces/{p.name}"


def open_devcontainer(target: str = "code", prepare: bool = True) -> dict:
    """v3.4 with prepare=True: installs the Dev Containers extension when missing and generates .devcontainer/ from the
    sandbox image when it does not exist yet — one click from nothing to VS Code inside the container."""
    st = vscode_status()
    if not st.ok:
        raise IntegrationError(f"VS Code is {st.state}: {st.detail}")
    steps = []
    if not st.extra.get("dev_containers_ext"):
        if not prepare:
            raise IntegrationError(f"Install the Dev Containers extension first: code --install-extension {EXT_DEVCONTAINERS}")
        install_extension(EXT_DEVCONTAINERS)
        steps.append("Dev Containers extension installed")
    p = resolve_target(target)
    if not (p / ".devcontainer" / "devcontainer.json").exists():
        if not prepare:
            raise IntegrationError("No .devcontainer/devcontainer.json yet — generate the environment first")
        from ..sandbox import effective_image, load_settings
        s = load_settings()
        img = effective_image(s)
        write_environment({"gpu": bool(s.get("gpu")) and "cuda" in img.lower(), "image": img})
        steps.append(f".devcontainer/ generated from the sandbox image {img}")
    from ..sandbox import docker_exe, docker_running
    if not (docker_exe() and docker_running(5)):
        raise IntegrationError("Docker is not running — start Docker Desktop first")
    code, out = run_cli([vscode_cli(), "--folder-uri", devcontainer_uri(target)], 30)
    if code != 0:
        raise IntegrationError(f"`code --folder-uri` exited with {code}: {out.strip()[-300:]}")
    return {"launched": True, "uri": devcontainer_uri(target), "steps": steps,
            "note": "VS Code is reopening the folder inside the dev container (first build can take minutes)."}


# ------------------------------------------------------------------ Environment Manager (Dockerfile + devcontainer.json)
GPU_IMAGES = {  # vetted official tags (pytorch/pytorch on Docker Hub)
    ("2.5.1", "12.4"): "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime",
    ("2.4.1", "12.4"): "pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime",
    ("2.4.1", "12.1"): "pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime",
}
CPU_PY = ("3.10", "3.11", "3.12")


def environment_options() -> dict:
    return {"gpu_images": [{"torch": k[0], "cuda": k[1], "image": v} for k, v in GPU_IMAGES.items()],
            "python_versions": list(CPU_PY)}


def build_environment(spec: dict) -> dict:
    """Render the files of a reproducible environment from a spec (pure function, nothing written).
    spec: {gpu: bool, torch, cuda, python, image?, datasets_dir?, shm_gb?, env: {K: V}}"""
    from ..resources import policy
    pol = policy()
    gpu = bool(spec.get("gpu", True))
    image = (spec.get("image") or "").strip()
    if not image:
        if gpu:
            key = (str(spec.get("torch") or "2.5.1"), str(spec.get("cuda") or "12.4"))
            if key not in GPU_IMAGES:
                raise IntegrationError(f"No vetted image for torch {key[0]} + CUDA {key[1]} — choose one of the list or give an image")
            image = GPU_IMAGES[key]
        else:
            py = str(spec.get("python") or "3.11")
            if py not in CPU_PY:
                raise IntegrationError(f"Python {py} not offered (choose {', '.join(CPU_PY)})")
            image = f"python:{py}-slim"
    if not re.fullmatch(r"[\w.\-/:@]+", image):
        raise IntegrationError("Invalid image name")
    env = {str(k): str(v) for k, v in (spec.get("env") or {}).items() if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(k))}
    mem, cpus, shm = pol["sandbox_memory_gb"], pol["sandbox_cpus"], int(spec.get("shm_gb") or 2)
    run_args = (["--gpus", "all"] if gpu else []) + [f"--memory={mem}g", f"--cpus={cpus}", f"--shm-size={shm}g"]
    mounts = ["source=${localWorkspaceFolder}/../runs,target=/runs,type=bind"]
    ds = (spec.get("datasets_dir") or "").strip()
    if ds:
        dp = Path(ds).expanduser()
        if not dp.is_absolute() or not dp.is_dir():
            raise IntegrationError("datasets_dir must be an existing absolute folder")
        mounts.append(f"source={dp.as_posix()},target=/datasets,type=bind,readonly")
        env.setdefault("DATASETS_DIR", "/datasets")
    from ..sandbox import code_dir
    has_req = (code_dir() / "requirements.txt").exists()
    dc = {"name": f"PhD Lab · {data_dir().name}",
          "build": {"dockerfile": "Dockerfile", "context": ".."},
          "runArgs": run_args, "mounts": mounts,
          "containerEnv": {"PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "RUN_DIR": "/runs/devcontainer", **env},
          "customizations": {"vscode": {"extensions": [EXT_PYTHON, EXT_JUPYTER]}}}
    try:  # v3.4: same automatic dependencies as sandbox runs (requirements files + imports of the code)
        from .. import deps
        deps.write(code_dir())
        dc["postCreateCommand"] = "python .phdlab/ensure_deps.py"
    except Exception:
        if has_req:
            dc["postCreateCommand"] = "pip install --no-cache-dir -r requirements.txt"
    dockerfile = "\n".join([
        f"# Generated by PhD Research Lab {APP_VERSION} — reproducible research environment",
        f"FROM {image}",
        "ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg PIP_DISABLE_PIP_VERSION_CHECK=1",
        "RUN mkdir -p /runs",
        *(["COPY requirements.txt /tmp/requirements.txt", "RUN pip install --no-cache-dir -r /tmp/requirements.txt"] if has_req else []),
        f'LABEL org.phdlab.version="{APP_VERSION}" org.phdlab.gpu="{str(gpu).lower()}"', ""])
    meta = {"generated_by": f"PhD Research Lab {APP_VERSION}", "image": image, "gpu": gpu, "memory_gb": mem, "cpus": cpus,
            "shm_gb": shm, "policy_source": pol["source"], "datasets_dir": ds, "requirements_pinned": has_req,
            "spec": {k: spec.get(k) for k in ("gpu", "torch", "cuda", "python", "image") if spec.get(k) not in (None, "")}}
    return {".devcontainer/devcontainer.json": json.dumps(dc, indent=2) + "\n", ".devcontainer/Dockerfile": dockerfile,
            ".devcontainer/environment.json": json.dumps(meta, indent=2) + "\n"}


def write_environment(spec: dict, overwrite: bool = False) -> dict:
    from .. import ide_fs
    files = build_environment(spec)
    existing = [p for p in files if ide_fs.safe(p).exists()]
    if existing and not overwrite:
        raise IntegrationError("Already exists: " + ", ".join(existing) + " — confirm overwrite to replace them")
    for rel, content in files.items():
        p = ide_fs.safe(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, "utf-8")
    return {"written": list(files), "overwritten": existing}


# ------------------------------------------------------------------ Jupyter
# JupyterLab runs from the Python that runs this app (python -m jupyterlab), so it is found even when that Python's
# Scripts folder is not on PATH. Kernels inherit the project context (PHDLAB_* variables) and, in ClearML offline mode,
# CLEARML_OFFLINE_MODE + CLEARML_CACHE_DIR=<project>/clearml: a notebook's Task.init lands in the project's sessions.
_JUP = {"proc": None, "port": None, "token": None, "started": None, "root": None}


def _project_python() -> str | None:
    try:
        from ..sandbox import local_python_info
        py = local_python_info()["python"]
        return py if Path(py).exists() else None
    except Exception:
        return None


def jupyter_argv() -> list | None:
    """v3.4: JupyterLab from (1) the project's Python environment, (2) the app's Python, (3) ANY Python found on this machine
    (envs.discover_pythons: system installs that are not on PATH, conda, py launcher) — e.g. `pip install jupyterlab` into
    the system Python while the app runs from its own .venv — then (4) a jupyter executable on PATH."""
    from ..envs import probe, python_with
    proj = _project_python()
    if proj and (probe(proj, 15) or {}).get("jupyterlab"):
        return [proj, "-m", "jupyterlab"]
    if importlib.util.find_spec("jupyterlab") is not None:
        return [sys.executable, "-m", "jupyterlab"]
    hit = python_with("jupyterlab")
    if hit:
        return [hit["path"], "-m", "jupyterlab"]
    p = which("jupyter-lab")
    if p:
        return [p]
    p = which("jupyter")
    return [p, "lab"] if p else None


def kernel_name() -> str:
    from ..sandbox import container_name
    return container_name().replace("phdlab-", "phdlab_")


def ensure_project_kernel(install: bool = True) -> dict:
    """Register the project's Python environment as a Jupyter kernel ("PhD-Lab · <project>"), so notebooks import the
    same packages as sandbox runs. Installs ipykernel into that environment first when it is missing."""
    from ..envs import probe
    py = _project_python()
    if not py:
        from ..sandbox import _local_python
        py = _local_python()  # creates the project venv on first use
    info = probe(py, 20) or {}
    notes = []
    if not info.get("ipykernel"):
        if not install:
            return {"registered": False, "python": py, "detail": "ipykernel missing in the project environment"}
        code, out = run_cli([py, "-m", "pip", "install", "--disable-pip-version-check", "ipykernel"], 600)
        if code != 0:
            return {"registered": False, "python": py, "detail": "pip install ipykernel failed: " + out.strip()[-300:]}
        notes.append("ipykernel installed into the project environment")
    name = kernel_name()
    code, out = run_cli([py, "-m", "ipykernel", "install", "--user", "--name", name, "--display-name", f"PhD-Lab · {data_dir().name}"], 120)
    if code != 0:
        return {"registered": False, "python": py, "detail": out.strip()[-300:]}
    return {"registered": True, "name": name, "python": py, "notes": notes}


def _jupyter_version() -> str:
    argv = jupyter_argv()
    if not argv:
        return ""
    code, out = run_cli(argv + ["--version"], 60)
    return out.strip().splitlines()[-1] if code == 0 and out.strip() else ""


def _running() -> bool:
    return _JUP["proc"] is not None and _JUP["proc"].poll() is None


def jupyter_status() -> IntegrationStatus:
    argv = jupyter_argv()
    if not argv:
        return IntegrationStatus("jupyter", "JupyterLab", "unavailable", "JupyterLab was not found in any Python on this machine.",
                                 setup=["python -m pip install jupyterlab ipykernel   (any Python — the app finds it)",
                                        "or open .ipynb files in VS Code with the Jupyter extension"])
    ver = cached("jupyter_version", 300, _jupyter_version)
    how = f"{argv[0]} -m jupyterlab" if len(argv) > 2 else argv[0]
    detail = f"running on port {_JUP['port']} · root {_JUP['root']}" if _running() else f"found: {how}"
    return IntegrationStatus("jupyter", "JupyterLab", "available", detail, version=f"JupyterLab {ver}" if ver else "",
                             capabilities=["launch", "stop", "notebook_template"],
                             extra={"running": _running(), "port": _JUP["port"] if _running() else None})


def _free_port(start: int) -> int:
    import socket
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
            try:
                sk.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise IntegrationError(f"No free port in {start}-{start + 19} for JupyterLab")


def _kernel_env() -> dict:
    """Context every notebook kernel inherits (no credentials)."""
    from ..sandbox import code_dir, runs_dir
    cfg = load_config()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLEARML_API_", "PHDLAB_DATA_DIR"))}
    env.update(PHDLAB_PROJECT=data_dir().name, PHDLAB_PROJECT_DIR=str(data_dir()), PHDLAB_CODE_DIR=str(code_dir()),
               PHDLAB_RUNS_DIR=str(runs_dir()), PYTHONIOENCODING="utf-8")
    c = cfg["clearml"]
    if c.get("enabled") and (c.get("mode") or "offline") == "offline":
        env.update(CLEARML_OFFLINE_MODE="1", CLEARML_CACHE_DIR=str(data_dir() / "clearml"))
    return env


def jupyter_launch(target: str = "code") -> dict:
    if _running():
        return {"url": f"http://127.0.0.1:{_JUP['port']}/lab?token={_JUP['token']}", "port": _JUP["port"], "root": _JUP["root"],
                "already_running": True}
    argv = jupyter_argv()
    if not argv:
        raise IntegrationError("JupyterLab is not installed (pip install jupyterlab ipykernel)")
    nb_dir = resolve_target(target)
    try:  # notebooks run in the project's environment (same packages as the sandbox runs)
        kern = ensure_project_kernel()
    except Exception as e:
        kern = {"registered": False, "detail": str(e)[:200]}
    port = _free_port(int(load_config()["workspace"].get("jupyter_port") or 8888))
    token = secrets.token_hex(24)
    logf = data_dir() / "jupyter" / "jupyterlab.log"
    logf.parent.mkdir(parents=True, exist_ok=True)
    args = argv + ["--no-browser", "--ServerApp.ip=127.0.0.1", f"--ServerApp.port={port}", "--ServerApp.port_retries=0",
                   f"--ServerApp.root_dir={nb_dir}", f"--IdentityProvider.token={token}"]
    with open(logf, "ab") as log:
        proc = subprocess.Popen(args, cwd=str(nb_dir), stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=_kernel_env(),
                                creationflags=NO_WINDOW | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = logf.read_text("utf-8", errors="replace")[-600:]
            raise IntegrationError(f"JupyterLab exited with code {proc.returncode}: {tail}")
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/status", params={"token": token}, timeout=2)
            if r.status_code == 200:
                _JUP.update(proc=proc, port=port, token=token, started=time.time(), root=str(nb_dir))
                return {"url": f"http://127.0.0.1:{port}/lab?token={token}", "port": port, "root": str(nb_dir),
                        "server_python": argv[0], "kernel": kern}
        except httpx.HTTPError:
            pass
        time.sleep(1)
    _kill_tree(proc)
    raise IntegrationError(f"JupyterLab did not answer within 90 s (log: {logf})")


def _kill_tree(proc) -> None:
    if proc is None or proc.poll() is not None:
        return
    if IS_WIN:  # kernels are child processes: stop the whole tree
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, creationflags=NO_WINDOW)
    else:
        proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()


def jupyter_stop() -> dict:
    if not _running():
        _JUP.update(proc=None, port=None, token=None, root=None)
        return {"stopped": False, "note": "not running"}
    _kill_tree(_JUP["proc"])
    _JUP.update(proc=None, port=None, token=None, root=None)
    return {"stopped": True}


atexit.register(lambda: _kill_tree(_JUP["proc"]))


def _cell(kind: str, src: str) -> dict:
    c = {"cell_type": kind, "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def create_notebook(name: str) -> dict:
    """notebooks/<name>.ipynb in the code workspace: project context, git commit, ClearML task — never overwrites."""
    from .. import ide_fs
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", (name or "experiment").strip()).strip("-")[:60] or "experiment"
    rel = f"notebooks/{slug}.ipynb"
    p = ide_fs.safe(rel)
    if p.exists():
        raise IntegrationError(f"{rel} already exists")
    cells = [
        _cell("markdown", f"""# {name or slug}
Research notebook of **PhD Research Lab** project. The notebook is a working surface, not the research record:
write conclusions, failed hypotheses and decisions into Context Memory (🧭 Control Center → Research timeline)."""),
        _cell("code", """import os, subprocess
print("project :", os.environ.get("PHDLAB_PROJECT"))
try:
    print("git     :", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())
except Exception:
    print("git     : (no commit yet — commit the code to make this notebook reproducible)")"""),
        _cell("markdown", """## Track with ClearML
In ClearML offline mode (the app default) the session is stored in the project (`clearml/offline/`) and appears in
🧭 Control Center → Integrations → ClearML; it can be imported into a ClearML Server later."""),
        _cell("code", f"""from clearml import Task
task = Task.init(project_name=os.environ.get("PHDLAB_PROJECT", "PhD Research Lab"), task_name="{slug}",
                 auto_connect_frameworks=False, reuse_last_task_id=False)
logger = task.get_logger()
print("ClearML task:", task.id, "(offline)" if Task.is_offline() else "")"""),
        _cell("code", """# example: log a curve and a final value (replace with your experiment)
for step, loss in enumerate([1.0, 0.6, 0.4, 0.3]):
    logger.report_scalar("loss", "train", value=loss, iteration=step)
logger.report_single_value("final_loss", 0.3)"""),
        _cell("code", """task.close()  # writes the offline session zip"""),
    ]
    try:
        kern = ensure_project_kernel()
    except Exception:
        kern = {"registered": False}
    spec = ({"display_name": f"PhD-Lab · {data_dir().name}", "language": "python", "name": kern["name"]} if kern.get("registered")
            else {"display_name": "Python 3", "language": "python", "name": "python3"})
    nb = {"cells": cells, "metadata": {"kernelspec": spec,
                                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(nb, indent=1), "utf-8")
    out = {"path": rel}
    if _running():
        out["url"] = f"http://127.0.0.1:{_JUP['port']}/lab/tree/{rel}?token={_JUP['token']}"
    return out
