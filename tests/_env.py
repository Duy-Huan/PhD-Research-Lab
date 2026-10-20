"""Import FIRST in every test module: points the app at a throw-away data folder, so tests never touch data/."""
import atexit
import os
import shutil
import sys
import tempfile
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

from backend import config  # noqa: E402

if config.GLOBAL_DIR.resolve() == (ROOT / "data").resolve():
    raise SystemExit("tests must not run on the real data folder")
# no background ClearML subprocess after every sandbox run in the suite (test_clearml_offline turns it on itself)
config.save_config({"clearml": {"auto_record": False}})


def fresh_project(name: str):
    """A new, empty, active research project (own memory/, runs/, code/)."""
    return config.create_project(name)


def run_async(coro):
    import asyncio
    return asyncio.run(coro)
