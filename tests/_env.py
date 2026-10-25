"""Import FIRST in every test module: points the app at a throw-away data folder, so tests never touch data/."""
import atexit
import os
import shutil
import sys
import tempfile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if not os.environ.get("PHDLAB_DATA_DIR"):
    _tmp = tempfile.mkdtemp(prefix="phdlab-test-")
    os.environ["PHDLAB_DATA_DIR"] = _tmp
    atexit.register(lambda: shutil.rmtree(_tmp, ignore_errors=True))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# notebook kernels registered by tests (ipykernel install --user) must not land in the researcher's real Jupyter folder
os.environ["JUPYTER_DATA_DIR"] = os.path.join(os.environ["PHDLAB_DATA_DIR"], "_jupyter")

from backend.core import config  # noqa: E402

if config.GLOBAL_DIR.resolve() == (ROOT / "data").resolve():
    raise SystemExit("tests must not run on the real data folder")
# no background ClearML subprocess after every sandbox run in the suite (test_clearml_offline turns it on itself)
config.save_config({"clearml": {"auto_record": False}, "memory": {"embed_engine": "hashing"},
                    "lifecycle": {"cloud_preconnect": False}})  # hermetic: connection tests opt into their local fixture


def _code_project(name: str = "main"):
    """v4.2: editor / sandbox actions need an open code project (code/<name>/); tests get one named "main"."""
    from backend.execution import code_projects
    if not code_projects.active():
        code_projects.create(name, git=False, vscode=False, seed=False)


_code_project()


def directory_link(target: Path, link: Path) -> str:
    """Exercise real filesystem reparse paths: symlink or unprivileged NTFS junction.

    No system Developer Mode setting is changed and failed creation is not a PASS.
    """
    temporary = Path(tempfile.gettempdir()).resolve()
    if not target.resolve().is_relative_to(temporary) or not link.parent.resolve().is_relative_to(temporary):
        raise ValueError('Directory-link fixture must remain inside owned temporary storage')
    try:
        os.symlink(target, link, target_is_directory=True)
        return 'SYMLINK'
    except OSError:
        if os.name != 'nt': raise
    env = dict(os.environ, PHDLAB_TEST_LINK=str(link), PHDLAB_TEST_TARGET=str(target))
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    'New-Item -ItemType Junction -Path $env:PHDLAB_TEST_LINK -Target $env:PHDLAB_TEST_TARGET -ErrorAction Stop | Out-Null'],
                   env=env, check=True, capture_output=True, timeout=20,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if link.resolve() != target.resolve():
        raise AssertionError('Created junction did not resolve to the actual fixture target')
    return 'NTFS_JUNCTION'


def fresh_project(name: str, code_project: str | None = "main"):
    """A new, empty, active research project (own memory/, runs/, code/) with an open code project (None: without)."""
    p = config.create_project(name)
    if code_project:
        _code_project(code_project)
    return p


def run_async(coro):
    import asyncio
    return asyncio.run(coro)


def isolate_config(tc) -> None:
    """v4.2 tests: the global config.json is restored when the test ends (settings changed by one test never leak)."""
    saved = config.CONFIG_PATH.read_text("utf-8") if config.CONFIG_PATH.exists() else None

    def restore():  # atomic like the app itself: background run threads may be reading the file right now
        if saved is None:
            config.CONFIG_PATH.unlink(missing_ok=True)
        else:
            from backend.memory.store import replace_retry
            tmp = config.CONFIG_PATH.with_suffix(".json.restore")
            tmp.write_text(saved, "utf-8")
            replace_retry(tmp, config.CONFIG_PATH)
    tc.addCleanup(restore)
