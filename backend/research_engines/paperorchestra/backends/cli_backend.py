"""Official PaperOrchestra CLI Backend (Isolated Sandbox Execution).

Integrates Google Cloud AI Research / official `paper-orchestra` CLI:
- Runs in an isolated session workspace (never directly in the user repository).
- Sanitizes environment variables to prevent accidental API leak.
- Handles timeouts, external process signals, cancellation, and error codes.
- Extracts generated artifacts, converts them into versioned `WritingArtifact`s,
  and syncs accepted files to PhD Lab's `project.json` and build workspace.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from backend.agent import decision_ledger as L
from backend.core.config import data_dir, load_config
from backend.execution.tools import NO_WINDOW, run_cli, which
from backend.research_engines.contracts import EngineEvent, EngineFailure, EngineResult, EngineTask
from backend.research_engines.paperorchestra.artifact_store import save_artifact
from backend.research_engines.paperorchestra.contracts import WritingArtifact


def probe_cli_binary() -> dict:
    cfg = load_config().get("paperorchestra") or {}
    custom_bin = cfg.get("cli_binary") or "paper-orchestra"
    bin_path = which(custom_bin) or which("paper-orchestra")
    installed = bool(bin_path)
    version = "not_installed"
    if bin_path:
        try:
            res = subprocess.run(
                [bin_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=NO_WINDOW,
            )
            version = (res.stdout or res.stderr).strip().splitlines()[0][:80] if res.returncode == 0 else "installed-unverified"
        except Exception:
            version = "installed-unverified"

    return {
        "binary": bin_path,
        "installed": installed,
        "version": version,
        "framework": "Google Cloud AI Research / PaperOrchestra",
    }


def make_isolated_session_workspace(operation_id: str) -> Path:
    safe_op = operation_id.replace(":", "-").replace("/", "_")
    ws = data_dir() / "research-engines" / "paperorchestra" / safe_op / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def execute_cli(
    task: EngineTask,
    emit: Callable[[EngineEvent], None],
    cancelled: Callable[[], bool],
) -> EngineResult:
    """Execute task via official PaperOrchestra CLI in an isolated sandbox."""
    probe = probe_cli_binary()
    bin_path = probe["binary"]
    if not bin_path:
        raise EngineFailure("Official `paper-orchestra` CLI is not installed on PATH", "capability")

    if cancelled():
        raise EngineFailure("Task cancelled before CLI launch", "cancelled")

    ws = make_isolated_session_workspace(task.operation_id)
    emit(EngineEvent(engine="paperorchestra", type="status", data={"state": "launching_cli", "workspace": str(ws)}))

    # Prepare inputs in isolated workspace
    input_file = ws / "input_task.json"
    input_file.write_text(
        json.dumps({
            "operation_id": task.operation_id,
            "project_id": task.project_id,
            "workflow_id": task.workflow_id,
            "step_id": task.step_id,
            "capability": task.capability,
            "question": task.question,
            "context": task.context,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Sanitize environment: only permit minimal variables, deny external billing unless explicit
    from backend.providers.cli_space import minimal_env
    env = minimal_env()
    env["PAPERORCHESTRA_WORKSPACE"] = str(ws)

    # Build command arguments
    # `paper-orchestra run --input input_task.json --output-dir .`
    cmd = [bin_path, "run", "--input", str(input_file), "--output-dir", str(ws)]

    started = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ws),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=NO_WINDOW,
        )

        # Polling loop checking cancellation and timeout
        while proc.poll() is None:
            if cancelled():
                proc.kill()
                raise EngineFailure("Task cancelled during CLI execution", "cancelled")
            if time.time() - started > task.time_limit_s:
                proc.kill()
                raise EngineFailure(f"PaperOrchestra CLI timed out after {task.time_limit_s}s", "timeout")
            time.sleep(0.5)

        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            err_msg = (stderr or stdout or f"Process exited with code {proc.returncode}")[:500]
            raise EngineFailure(f"PaperOrchestra CLI execution failed: {err_msg}", "execution")

    except OSError as e:
        raise EngineFailure(f"Failed to spawn PaperOrchestra process: {e}", "execution") from e

    # Discover generated outputs
    out_tex = ws / "main.tex"
    out_md = ws / "output.md"
    result_text = ""
    if out_tex.exists():
        result_text = out_tex.read_text(encoding="utf-8", errors="ignore")
    elif out_md.exists():
        result_text = out_md.read_text(encoding="utf-8", errors="ignore")
    else:
        result_text = stdout[:10000]

    # Save to shared versioned artifact store
    art = WritingArtifact.create(
        task_id=task.step_id,
        parent_workflow_id=task.workflow_id,
        content=result_text,
        section_id=task.native_workflow or "manuscript",
        title=f"CLI Output: {task.question[:60]}",
        agent_id="paperorchestra_cli",
        provider_id="paperorchestra",
        execution_metrics={"duration_s": round(time.time() - started, 2)},
    )
    saved = save_artifact(art, sync_paper_section=True)

    emit(EngineEvent(engine="paperorchestra", type="status", data={"state": "completed", "artifact_id": saved.artifact_id}))

    return EngineResult(
        engine="paperorchestra",
        text=result_text,
        artifact_refs=[{
            "id": saved.artifact_id,
            "path": saved.storage_path,
            "sha256": saved.content_hash,
            "bytes": len(result_text.encode("utf-8")),
        }],
        native_run_id=task.operation_id,
        provenance={"backend": "official_cli", "version": probe["version"], "workspace": str(ws)},
    )

