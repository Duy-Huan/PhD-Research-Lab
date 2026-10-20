"""Robust launcher for PhD Interactive Autonomous Research Lab (Windows / macOS / Linux).

    python start.py            -> checks environment, installs missing packages, starts server, opens browser
    python start.py --port 9000
    python start.py --no-browser
    python start.py --check     -> only verify the installation (files, version, packages)
"""
import importlib.util
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

HOST = "127.0.0.1"
APP_VERSION = "4.0.0"   # must match backend/config.py - a mismatch means files from two versions were mixed
# Files that must exist for this version (an incomplete copy or a partial upgrade is the most common failure)
REQUIRED_FILES = [
    "backend/__init__.py", "backend/app.py", "backend/config.py", "backend/llm.py", "backend/library.py",
    "backend/paper.py", "backend/prompts.py", "backend/chat_store.py", "backend/context_hub.py",
    "backend/attachments.py", "backend/fs_browse.py", "backend/review_ext.py", "backend/review_prompts.py", "backend/websearch.py", "backend/latex_build.py", "frontend/index.html", "frontend/vendor/marked.min.js",
    "frontend/vendor/purify.min.js", "frontend/vendor/katex/katex.min.js", "frontend/vendor/katex/katex.min.css",
    "frontend/vendor/hljs/highlight.min.js", "frontend/guide/en.md", "frontend/guide/vi.md", "frontend/i18n.js", "requirements.txt",
    # v3.0: Code IDE, Docker sandbox, memory, context graph, GitHub, MCP
    "backend/api_v3.py", "backend/local_ai.py", "backend/sysinfo.py", "backend/sandbox.py", "backend/ide_fs.py",
    "backend/gitops.py", "backend/memory/__init__.py", "backend/context_graph.py", "backend/coder.py", "backend/mcp_server.py",
    "mcp_stdio_bridge.py", "frontend/app/workspace.js", "frontend/app/docker.js", "frontend/app/context.js", "frontend/app/v3.css",
    "frontend/vendor/vis/vis-network.min.js",
    # v3.1: external results + writing briefs
    "backend/results.py", "backend/brief.py", "backend/api_v31.py", "frontend/app/results.js", "frontend/app/brief.js",
    # v3.2: Context Memory v2, integration layer, resource governor, provenance, live critic, LLM router, connectors
    "backend/api_v32.py", "backend/memory/store.py", "backend/memory/pages.py", "backend/memory/working.py",
    "backend/memory/research.py", "backend/memory/knowledge.py", "backend/memory/lod.py", "backend/memory/embeddings.py",
    "backend/memory/retrieval.py", "backend/memory/compiler.py", "backend/memory/compressor.py",
    "backend/integrations/__init__.py", "backend/integrations/base.py", "backend/integrations/workspace.py",
    "backend/integrations/experiment.py", "backend/integrations/clearml_worker.py", "backend/integrations/agents.py",
    "backend/resources.py", "backend/provenance.py",
    "backend/critic.py", "backend/llm_router.py", "backend/connectors/__init__.py", "backend/connectors/base.py",
    "backend/connectors/registry.py", "frontend/app/control.js",
    # v4.0: research-state-aware Context Memory, Context Gateway + MCP research tools, environments, app shell
    "backend/api_v33.py", "backend/telemetry.py", "backend/envs.py", "backend/deps.py", "backend/memory/state.py",
    "backend/memory/engine.py", "backend/memory/policy.py", "backend/memory/evidence.py", "backend/memory/trace.py",
    "backend/memory/lifecycle.py", "backend/memory/cache.py", "backend/gateway/__init__.py", "backend/gateway/connectors.py",
    "backend/gateway/events.py", "backend/gateway/context.py", "backend/gateway/service.py", "backend/gateway/policy.py",
    "backend/gateway/mcp_tools.py", "frontend/app/shell.css", "frontend/app/shell.js", "frontend/app/envpanel.js",
    "frontend/app/memory33.js", "frontend/app/gateway.js", "frontend/app/img/logo-64.png",
]
UPGRADE_HELP = """How to fix (takes 1 minute):
  1. Extract the WHOLE new zip into a NEW, empty folder (do not copy single files over an old version).
  2. Copy your user data from the old folder into the new one:
       data/        (settings, API keys, Default project)
       references/  (PDFs of the Default project)
       projects/    (other research projects, if you have any)
  3. Start the new folder:  Windows: run.bat    Linux/macOS: ./run.sh  (or: python3 start.py)"""
# module name(s) to probe -> pip package
REQUIRED = [
    (("fastapi",), "fastapi"),
    (("uvicorn",), "uvicorn"),
    (("httpx",), "httpx"),
    (("pypdf",), "pypdf"),
    (("python_multipart", "multipart"), "python-multipart"),
]


def fail(msg: str) -> None:
    print("\n[ERROR] " + msg)
    if sys.stdin and sys.stdin.isatty():
        input("\nPress Enter to close...")
    sys.exit(1)


def check_python() -> None:
    print(f"Python  : {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 9):
        fail("Python 3.9 or newer is required (3.11/3.12 recommended). Install from https://www.python.org/downloads/")


def check_files() -> None:
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(ROOT, f))]
    if missing:
        fail("The installation is incomplete or mixes files from different versions.\n"
             "Missing: " + ", ".join(missing) + "\n\n" + UPGRADE_HELP)
    try:
        cfg = open(os.path.join(ROOT, "backend", "config.py"), encoding="utf-8").read()
        found = re.search(r'APP_VERSION = "([^"]+)"', cfg).group(1)
    except Exception:
        found = "unknown"
    if found != APP_VERSION:
        fail(f"Version mismatch: start.py is v{APP_VERSION} but backend/config.py is v{found}.\n"
             "Files from two versions were mixed.\n\n" + UPGRADE_HELP)
    print(f"Files   : OK (v{APP_VERSION})")


def in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def reexec_in_venv() -> None:
    """Linux/macOS system Pythons often refuse 'pip install' (PEP 668 'externally-managed-environment').
    Create ./.venv once, install the requirements there and restart this script inside it."""
    venv_dir = os.path.join(ROOT, ".venv")
    vpy = os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(vpy):
        print(f"Creating a private virtual environment in {venv_dir} ...")
        if subprocess.call([sys.executable, "-m", "venv", venv_dir]) != 0:
            fail("Could not create a virtual environment. On Ubuntu/Debian install it with:\n"
                 f"  sudo apt install python3-venv   (or python{sys.version_info.major}.{sys.version_info.minor}-venv)\n"
                 "then run this script again.")
    probe = "import fastapi, uvicorn, httpx, pypdf, multipart"
    if subprocess.call([vpy, "-c", probe], stderr=subprocess.DEVNULL) == 0:
        print("Using existing .venv\n")
        os.execv(vpy, [vpy, os.path.abspath(__file__)] + sys.argv[1:])
    print("Installing packages into .venv ...\n")
    if subprocess.call([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"]) != 0 or \
            subprocess.call([vpy, "-m", "pip", "install", "-r", os.path.join(ROOT, "requirements.txt")]) != 0:
        fail("pip install into .venv failed. Check your internet connection and try again.")
    print("\nRestarting inside .venv ...\n")
    os.execv(vpy, [vpy, os.path.abspath(__file__)] + sys.argv[1:])


def missing_packages() -> list:
    return [pkg for mods, pkg in REQUIRED if not any(importlib.util.find_spec(m) for m in mods)]


def ensure_packages() -> None:
    miss = missing_packages()
    if not miss:
        print("Packages: OK")
        return
    print(f"Missing packages for THIS Python ({sys.executable}): {', '.join(miss)}")
    venv_py = os.path.join(ROOT, ".venv", "bin", "python")
    if os.name != "nt" and not in_venv():
        if os.path.exists(venv_py) or not os.access(sys.prefix, os.W_OK):
            reexec_in_venv()  # system Python (PEP 668) -> use/create ./.venv
    print("Installing now...\n")
    cmd = [sys.executable, "-m", "pip", "install", "-r", os.path.join(ROOT, "requirements.txt")]
    if subprocess.call(cmd) != 0:
        if os.name != "nt" and not in_venv():
            reexec_in_venv()  # e.g. "externally-managed-environment" on Ubuntu 23.04+/Debian 12+
        fail("pip install failed. Check your internet connection, then run:\n  " + " ".join(cmd))
    importlib.invalidate_caches()
    if missing_packages():
        fail("Packages still missing after install: " + ", ".join(missing_packages()))


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def running_lab(port: int) -> dict | None:
    """{'version', 'root'} of a PhD Research Lab already listening on this port, else None."""
    import json
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/config", timeout=2) as r:
            cfg = json.loads(r.read().decode("utf-8", "replace"))
        if "agent_modes" not in cfg:
            return None
    except Exception:
        return None
    info = {"version": str(cfg.get("version") or "older"), "root": ""}
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/version", timeout=2) as r:
            info.update(json.loads(r.read().decode("utf-8", "replace")))
    except Exception:
        pass
    return info


def same_folder(a: str, b: str) -> bool:
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except Exception:
        return False


def open_when_ready(url: str, port: int) -> None:
    for _ in range(120):
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.5)
    print(f"\n>>> Open in your browser:  {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass


def report_tools() -> None:
    """Optional tools for v3 (Code IDE sandbox, Source Control, PDF preview). Missing ones only disable that feature;
    the 🐳 Docker & System tab scans everything in detail and recommends a setup."""
    import shutil
    def has(*names):
        return next((n for n in names if shutil.which(n)), None)
    items = [("Docker", has("docker")), ("Git", has("git")), ("NVIDIA GPU", has("nvidia-smi")), ("VS Code", has("code")),
             ("ClearML SDK", importlib.util.find_spec("clearml") is not None),
             ("LaTeX", has("latexmk", "pdflatex", "tectonic", "xelatex")), ("Ollama", has("ollama")), ("LM Studio CLI", has("lms"))]
    print("Tools   : " + ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in items) + "  (details: Docker & System tab)")


def main() -> None:
    args = sys.argv[1:]
    port = int(args[args.index("--port") + 1]) if "--port" in args else 8765
    browser = "--no-browser" not in args

    print("=" * 64)
    print(" PhD Interactive Autonomous Research Lab")
    print("=" * 64)
    print(f"Folder  : {ROOT}")
    if not os.path.isfile(os.path.join(ROOT, "backend", "app.py")):
        fail("backend/app.py not found. Extract the whole zip (right-click > Extract All) before running.")
    check_python()
    check_files()
    ensure_packages()
    report_tools()
    if "--check" in args:
        print("\nInstallation OK.")
        return

    # port handling
    if not port_free(port):
        info = running_lab(port)
        if info and info["version"] == APP_VERSION and (not info.get("root") or same_folder(info["root"], ROOT)):
            url = f"http://{HOST}:{port}"
            print(f"The lab (v{APP_VERSION}) is already running at {url} - opening it.")
            if browser:
                webbrowser.open(url)
            return
        old = port
        port = next((p for p in range(port + 1, port + 50) if port_free(p)), None)
        if port is None:
            fail(f"Port {old} and the next 49 ports are busy.")
        if info:
            where = f" from {info['root']}" if info.get("root") else ""
            print("!" * 64)
            print(f"!! Another copy of the lab (v{info['version']}{where}) is still running on port {old}.")
            print(f"!! This is v{APP_VERSION}: it starts on port {port} instead.")
            print("!! Close the OLD black window so your browser never opens the old version.")
            print("!" * 64)
        else:
            print(f"Port {old} is used by another program -> using port {port}")

    # import the app first so errors are shown clearly
    try:
        from backend.app import app  # noqa: F401
    except Exception:
        traceback.print_exc()
        fail("The application failed to load (see the traceback above).")

    import uvicorn
    from backend.library import PDF_BACKEND, PDF_BACKEND_ERROR
    print(f"PDF lib : {PDF_BACKEND}" + (f"   (note: {PDF_BACKEND_ERROR.split(':')[0]} - using fallback)" if PDF_BACKEND_ERROR and PDF_BACKEND != "none" else ""))
    if PDF_BACKEND == "none":
        print("WARNING : no PDF library - PDF ingestion disabled. Run: pip install pypdf")

    url = f"http://{HOST}:{port}"
    print(f"Server  : {url}   (keep this window open; Ctrl+C to stop)")
    if browser:
        threading.Thread(target=open_when_ready, args=(url, port), daemon=True).start()
    try:
        # pure-Python HTTP stack: avoids native extensions that Application Control may block
        uvicorn.run(app, host=HOST, port=port, log_level="info", http="h11", loop="asyncio", ws="none")
    except Exception:
        traceback.print_exc()
        fail("Server crashed (see the traceback above).")


if __name__ == "__main__":
    main()
