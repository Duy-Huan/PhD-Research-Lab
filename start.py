"""Robust launcher for PhD Interactive Autonomous Research Lab (Windows / macOS / Linux).

    python start.py            -> checks environment, installs missing packages, starts server, opens browser
    python start.py --port 9000
    python start.py --no-browser
"""
import importlib.util
import os
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


def missing_packages() -> list:
    return [pkg for mods, pkg in REQUIRED if not any(importlib.util.find_spec(m) for m in mods)]


def ensure_packages() -> None:
    miss = missing_packages()
    if not miss:
        print("Packages: OK")
        return
    print(f"Missing packages for THIS Python ({sys.executable}): {', '.join(miss)}")
    print("Installing now...\n")
    cmd = [sys.executable, "-m", "pip", "install", "-r", os.path.join(ROOT, "requirements.txt")]
    if subprocess.call(cmd) != 0:
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


def lab_already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/config", timeout=2) as r:
            return b"agent_modes" in r.read()
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
    ensure_packages()

    # port handling
    if not port_free(port):
        if lab_already_running(port):
            url = f"http://{HOST}:{port}"
            print(f"The lab is already running at {url} - opening it.")
            if browser:
                webbrowser.open(url)
            return
        old = port
        port = next((p for p in range(port + 1, port + 50) if port_free(p)), None)
        if port is None:
            fail(f"Port {old} and the next 49 ports are busy.")
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
