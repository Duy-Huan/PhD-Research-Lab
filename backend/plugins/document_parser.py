"""Optional Docling process; explicit local model cache, no implicit downloads or remote inference."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.knowledge import research_store as S


def pages(path: Path) -> tuple[list[str], int]:
    cache = S.safe_child(S.store_dir(), "models", "docling")
    if not cache.is_dir():
        raise ValueError("Docling requires pre-provisioned local artifacts in workspace/research/models/docling; use existing parser meanwhile")
    from backend.execution.tools import NO_WINDOW
    from backend.providers.cli_space import minimal_env
    env = minimal_env()
    env.update(HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    worker = Path(__file__).with_name("document_parser_worker.py")
    try:
        result = subprocess.run([sys.executable, "-I", "-B", str(worker), str(path), str(cache)],
                                cwd=str(S.store_dir()), env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=180, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Docling parse timed out after 180 seconds; PDF preserved") from exc
    if result.returncode:
        raise ValueError("Docling unavailable or failed with local artifacts; PDF preserved, switch parser or retry")
    if len(result.stdout) > 3 * 1024 * 1024:
        raise ValueError("Docling output exceeds evidence budget")
    try:
        data = json.loads(result.stdout)
        return data["pages"], data["total_pages"]
    except (ValueError, KeyError) as exc:
        raise ValueError("Docling returned invalid structured page evidence") from exc
