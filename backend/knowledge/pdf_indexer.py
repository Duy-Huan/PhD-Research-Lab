"""Reuse the existing PDF implementation with a hard process timeout and bounded output."""
import json
import subprocess
import sys
from pathlib import Path

from backend.knowledge import research_store as S


def pages(path: Path) -> tuple[list[str], int]:
    from backend.execution.tools import NO_WINDOW
    from backend.providers.cli_space import minimal_env
    env = minimal_env()
    env["PHDLAB_DATA_DIR"] = str(S.safe_child(S.store_dir(), "parser-scratch"))
    try:
        result = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).with_name("pdf_index_worker.py")), str(path)],
                                cwd=str(S.store_dir()), env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=45, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("PDF parsing timed out after 45 seconds; file preserved for retry") from exc
    if result.returncode or len(result.stdout) > 15 * 1024 * 1024:
        raise ValueError("PDF parsing failed or output exceeded its evidence budget; file preserved")
    try:
        parsed = json.loads(result.stdout)
        return parsed["pages"], parsed["total_pages"]
    except (ValueError, KeyError) as exc:
        raise ValueError("PDF parser returned invalid page evidence") from exc
