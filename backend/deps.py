"""Automatic project dependencies (v3.4): "set up the environment, press Run, it runs".

detect()   what the research code needs, from (in this order of trust)
              1. requirements*.txt, pyproject.toml [project.dependencies], environment.yml (pip + conda names)
              2. the imports of every .py / .ipynb in the code workspace (stdlib and the project's own modules excluded),
                 mapped to their pip names (cv2 → opencv-python, sklearn → scikit-learn, PIL → Pillow, …)
write()    code/.phdlab/deps.json + code/.phdlab/ensure_deps.py (the folder is git-ignored)
command()  the prefix the sandbox puts in front of a run:   python .phdlab/ensure_deps.py && <your command>

ensure_deps.py runs INSIDE the target environment (project venv, chosen interpreter or Docker container), so it checks
what is really importable there, installs only what is missing, and prints one line when everything is present. Pinned
requirement files are re-installed only when the file changed or a listed distribution is missing. PyTorch on an NVIDIA
machine is installed from the official CUDA wheel index (CPU wheels would silently run on the CPU).
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

# import name → pip distribution (only where they differ or the import is ambiguous)
PIP_NAME = {
    "cv2": "opencv-python", "sklearn": "scikit-learn", "skimage": "scikit-image", "PIL": "Pillow", "yaml": "PyYAML",
    "bs4": "beautifulsoup4", "Crypto": "pycryptodome", "dateutil": "python-dateutil", "dotenv": "python-dotenv",
    "attr": "attrs", "google.protobuf": "protobuf", "jwt": "PyJWT", "serial": "pyserial", "usb": "pyusb", "magic": "python-magic",
    "fitz": "PyMuPDF", "docx": "python-docx", "pptx": "python-pptx", "tensorboardX": "tensorboardX", "torch": "torch",
    "torchvision": "torchvision", "torchaudio": "torchaudio", "spectral": "spectral", "osgeo": "GDAL", "h5py": "h5py",
    "scipy": "scipy", "numpy": "numpy", "pandas": "pandas", "matplotlib": "matplotlib", "seaborn": "seaborn",
    "einops": "einops", "timm": "timm", "transformers": "transformers", "datasets": "datasets", "lightning": "lightning",
    "pytorch_lightning": "pytorch-lightning", "hydra": "hydra-core", "omegaconf": "omegaconf", "wandb": "wandb",
    "clearml": "clearml", "tqdm": "tqdm", "rasterio": "rasterio", "tifffile": "tifffile", "imageio": "imageio",
    "mat73": "mat73", "kornia": "kornia", "lpips": "lpips", "piq": "piq", "thop": "thop", "fvcore": "fvcore",
    "mmcv": "mmcv", "mamba_ssm": "mamba-ssm", "flash_attn": "flash-attn", "jax": "jax", "tensorflow": "tensorflow",
    "keras": "keras", "lightgbm": "lightgbm", "xgboost": "xgboost", "catboost": "catboost", "statsmodels": "statsmodels",
    "sympy": "sympy", "networkx": "networkx", "plotly": "plotly", "requests": "requests", "httpx": "httpx",
    "ipywidgets": "ipywidgets", "IPython": "ipython", "skopt": "scikit-optimize", "optuna": "optuna", "onnx": "onnx",
    "onnxruntime": "onnxruntime", "huggingface_hub": "huggingface_hub", "accelerate": "accelerate", "peft": "peft",
    "sentencepiece": "sentencepiece", "tokenizers": "tokenizers", "safetensors": "safetensors", "zarr": "zarr",
    "netCDF4": "netCDF4", "xarray": "xarray", "pywt": "PyWavelets", "numba": "numba", "cupy": "cupy-cuda12x",
}
GPU_FRAMEWORKS = {"torch", "torchvision", "torchaudio", "tensorflow", "jax", "cupy", "mamba_ssm", "flash_attn", "lightning",
                  "pytorch_lightning", "timm", "kornia"}
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".phdlab", ".devcontainer", "node_modules", ".ipynb_checkpoints",
             "runs", "data", "datasets", "build", "dist", ".mypy_cache", ".pytest_cache"}
MAX_FILES = 2000
REQ_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _files(root: Path, exts: tuple):
    n = 0
    for p in root.rglob("*"):
        if n >= MAX_FILES:
            return
        if p.suffix in exts and p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            n += 1
            yield p


def _imports_of(src: str) -> set:
    out = set()
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module)
    return out


def _notebook_source(p: Path) -> str:
    try:
        nb = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    lines = []
    for c in nb.get("cells", []):
        if c.get("cell_type") == "code":
            src = "".join(c.get("source") or [])
            lines.append("\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("%", "!"))))  # magics
    return "\n".join(lines)


def _local_modules(root: Path) -> set:
    names = set()
    for p in root.iterdir():
        if p.is_dir() and not p.name.startswith(".") and ((p / "__init__.py").exists() or any(p.glob("*.py"))):
            names.add(p.name)
        elif p.suffix == ".py":
            names.add(p.stem)
    for p in _files(root, (".py",)):  # sibling modules imported from scripts in sub-folders
        names.add(p.stem)
    return names


def _pip_name(module: str) -> str:
    if module in PIP_NAME:
        return PIP_NAME[module]
    top = module.split(".")[0]
    return PIP_NAME.get(top, top.replace("_", "-"))


def _req_files(root: Path) -> list:
    out = [p for p in sorted(root.glob("requirements*.txt")) if p.is_file()]
    return out


def _pyproject_deps(root: Path) -> list:
    p = root / "pyproject.toml"
    if not p.exists():
        return []
    try:
        import tomllib
        d = tomllib.loads(p.read_text("utf-8"))
    except Exception:
        return []
    return [str(x) for x in (d.get("project") or {}).get("dependencies") or []]


def _env_yml_deps(root: Path) -> list:
    p = next((root / n for n in ("environment.yml", "environment.yaml") if (root / n).exists()), None)
    if not p:
        return []
    deps, in_pip = [], False
    for line in p.read_text("utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("- pip:"):
            in_pip = True
            continue
        if s.startswith("- "):
            item = s[2:].strip()
            if item in ("pip", "python") or item.startswith("python="):
                continue
            deps.append(item.split("=")[0] if not in_pip else item)
        elif s and not s.startswith("#") and not line.startswith(" "):
            in_pip = False
    return [d for d in deps if d and not d.startswith("_")]


def detect(root: Path | None = None) -> dict:
    """The dependency plan of the code workspace (pure: nothing installed, nothing written)."""
    if root is None:
        from .sandbox import code_dir
        root = code_dir()
    std = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
    local = _local_modules(root)
    found: dict = {}
    for p in list(_files(root, (".py",))) + list(_files(root, (".ipynb",))):
        src = _notebook_source(p) if p.suffix == ".ipynb" else p.read_text("utf-8", errors="replace")
        for mod in _imports_of(src):
            top = mod.split(".")[0]
            if top in std or top in local or not top:
                continue
            key = mod if mod in PIP_NAME else top
            found.setdefault(key, set()).add(str(p.relative_to(root)).replace("\\", "/"))
    reqs = [str(p.relative_to(root)).replace("\\", "/") for p in _req_files(root)]
    extra = _pyproject_deps(root) + _env_yml_deps(root)
    imports = [{"module": m, "pip": _pip_name(m), "files": sorted(v)[:5]} for m, v in sorted(found.items())]
    return {"requirements_files": reqs, "declared": extra, "imports": imports,
            "gpu_frameworks": sorted({i["module"].split(".")[0] for i in imports} & GPU_FRAMEWORKS),
            "count": len(imports) + len(extra)}


ENSURE = r'''"""Generated by PhD Research Lab — installs what this project needs into THIS Python, then exits 0. Safe to re-run."""
import hashlib, importlib.metadata as md, importlib.util, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
plan = json.load(open(os.path.join(HERE, "deps.json"), encoding="utf-8"))
root = os.path.dirname(HERE)
stamp_dir = os.path.join(HERE, "stamps"); os.makedirs(stamp_dir, exist_ok=True)
env_id = hashlib.sha1((sys.executable + sys.version).encode()).hexdigest()[:12]
stamp_f = os.path.join(stamp_dir, env_id + ".json")
try:
    stamp = json.load(open(stamp_f, encoding="utf-8"))
except Exception:
    stamp = {}
def say(m): print("[deps] " + m, flush=True)
def pip(args):
    say("pip install " + " ".join(args))
    return subprocess.call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input"] + args)
def have_dist(name):
    try:
        md.distribution(name); return True
    except Exception:
        return False
def req_items(path):
    """(name, exact pin or None) of every requirement line; options (-r, -e, --index-url) make the file 'opaque'."""
    out, opaque = [], False
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.split("#")[0].strip()
        if not s: continue
        if s.startswith("-") or "://" in s or s.startswith("."):
            opaque = True; continue
        spec = s.split(";")[0].strip()
        name = spec
        for sep in ("===", "==", ">=", "<=", "~=", "!=", ">", "<", "["):
            name = name.split(sep)[0]
        pin = spec.split("==", 1)[1].split(",")[0].strip() if "==" in spec and "===" not in spec else None
        if name.strip(): out.append((name.strip(), pin))
    return out, opaque
def satisfied(path):
    items, opaque = req_items(path)
    if opaque: return False
    for name, pin in items:
        try:
            v = md.version(name)
        except Exception:
            return False
        if pin and v != pin: return False
    return True
if subprocess.call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
    say("pip missing — bootstrapping it with ensurepip"); subprocess.call([sys.executable, "-m", "ensurepip", "--upgrade"])
failed = []
for rel in plan.get("requirements_files", []):
    path = os.path.join(root, rel)
    h = hashlib.sha1(open(path, "rb").read()).hexdigest()
    if satisfied(path):  # every requirement present at its pinned version: no pip call (works offline)
        stamp[rel] = h
        continue
    if pip(["-r", path]) == 0: stamp[rel] = h
    else: failed.append(rel)
declared = [d for d in plan.get("declared", []) if not have_dist(d.split("=")[0].split(">")[0].split("<")[0].split("[")[0].strip())]
if declared and pip(declared) != 0: failed += declared
missing = []
for it in plan.get("imports", []):
    try:
        ok = importlib.util.find_spec(it["module"]) is not None
    except Exception:
        ok = False
    if not ok and it["pip"] not in missing: missing.append(it["pip"])
torch_like = [m for m in missing if m in ("torch", "torchvision", "torchaudio")]
if torch_like and shutil.which("nvidia-smi") and not os.environ.get("PHDLAB_IN_DOCKER"):
    idx = os.environ.get("PHDLAB_TORCH_INDEX", "https://download.pytorch.org/whl/cu124")
    say("NVIDIA GPU found — installing CUDA build of " + ", ".join(torch_like) + " from " + idx)
    if pip(torch_like + ["--index-url", idx]) != 0:
        say("CUDA wheel index failed (no wheel for this Python?) — trying the default index")
        if pip(torch_like) != 0: failed += torch_like
    missing = [m for m in missing if m not in torch_like]
if missing and pip(missing) != 0:
    for m in missing:  # one by one, so a single unknown name does not block the others
        if pip([m]) != 0: failed.append(m)
json.dump(stamp, open(stamp_f, "w", encoding="utf-8"))
if failed:
    say("could not install: " + ", ".join(failed) + " — add them (or their correct pip names) to requirements.txt")
    sys.exit(3)
say("all dependencies present (" + os.path.basename(sys.executable) + " " + sys.version.split()[0] + ")")
'''


def write(root: Path | None = None, plan: dict | None = None) -> dict:
    """Write .phdlab/deps.json + ensure_deps.py into the code workspace; returns the plan."""
    if root is None:
        from .sandbox import code_dir
        root = code_dir()
    plan = plan or detect(root)
    d = root / ".phdlab"
    d.mkdir(parents=True, exist_ok=True)
    body = json.dumps(plan, indent=1)
    f = d / "deps.json"
    if not f.exists() or f.read_text("utf-8") != body:
        f.write_text(body, "utf-8")
    e = d / "ensure_deps.py"
    if not e.exists() or e.read_text("utf-8") != ENSURE:
        e.write_text(ENSURE, "utf-8")
    gi = root / ".gitignore"
    try:
        cur = gi.read_text("utf-8") if gi.exists() else ""
        if ".phdlab/" not in cur:
            gi.write_text(cur + ("" if cur.endswith("\n") or not cur else "\n") + ".phdlab/\n", "utf-8")
    except OSError:
        pass
    return plan


_cache: dict = {}


def plan_cached(root: Path) -> dict:
    """detect() keyed by the newest mtime of the scanned files (cheap enough to call before every run)."""
    sig = []
    for p in list(_files(root, (".py", ".ipynb"))) + _req_files(root) + [root / "pyproject.toml", root / "environment.yml"]:
        try:
            sig.append((str(p), p.stat().st_mtime_ns))
        except OSError:
            pass
    key = (str(root), hashlib.sha1(repr(sorted(sig)).encode()).hexdigest())
    if _cache.get("key") != key:
        _cache.update(key=key, plan=detect(root))
    return _cache["plan"]


def command(python: str = "python") -> str:
    return f'{python} .phdlab/ensure_deps.py'
