"""PaperOrchestra Research Writing Engine Adapter.

Implements the ResearchEngine Protocol (contracts.py) conforming to PhD Lab's
control-plane architecture without duplicating orchestration, memory, or routing.
Supports both official isolated CLI execution and capability-based skill execution.
"""
from __future__ import annotations

import os
from typing import Callable

from backend.core.config import load_config
from backend.paper import latex as LB
from backend.research_engines.contracts import (
    EngineDescriptor,
    EngineEvent,
    EngineFailure,
    EngineResult,
    EngineTask,
)
from backend.research_engines.paperorchestra.backends.cli_backend import (
    execute_cli,
    probe_cli_binary,
)
from backend.research_engines.paperorchestra.backends.skill_backend import (
    execute_skill,
)


class PaperOrchestraEngine:
    """Research Writing Engine Adapter for PaperOrchestra."""

    descriptor = EngineDescriptor(
        id="paperorchestra",
        capabilities=["literature", "analysis", "review"],
        transport="hybrid-cli-or-harness",
        token_streaming=True,
        native_sessions=False,
    )

    def health(self) -> dict:
        cfg = load_config().get("paperorchestra") or {}
        enabled = bool(cfg.get("enabled", True))
        cli_info = probe_cli_binary()
        tex_info = LB.engines()

        backend_mode = cfg.get("default_backend", "auto")
        if backend_mode == "cli" and not cli_info["installed"]:
            ready = False
            state = "CLI_NOT_INSTALLED"
            detail = "Official PaperOrchestra CLI not found on PATH; install it or set backend to 'auto'/'harness_skills'."
        else:
            ready = enabled
            state = "READY" if enabled else "DISABLED"
            detail = (
                f"PaperOrchestra writing engine ready ({backend_mode} mode; "
                f"CLI: {'installed' if cli_info['installed'] else 'fallback to harness skills'}; "
                f"TeX: {tex_info.get('default') or 'quick-shim'})."
            )

        return {
            "engine": "paperorchestra",
            "ready": ready,
            "state": state,
            "backend_mode": backend_mode,
            "detail": detail,
            "cli": cli_info,
            "latex_available": bool(tex_info.get("available")),
            "latex_engines": tex_info.get("available", []),
            "setup": ["pip install paper-orchestra"] if not cli_info["installed"] else [],
        }

    def execute(
        self,
        task: EngineTask,
        emit: Callable[[EngineEvent], None],
        cancelled: Callable[[], bool],
    ) -> EngineResult:
        if cancelled():
            raise EngineFailure("Task cancelled before PaperOrchestra dispatch", "cancelled")

        cfg = load_config().get("paperorchestra") or {}
        backend = cfg.get("default_backend", "auto")
        cli_info = probe_cli_binary()

        # Decide whether to use official CLI or harness skills
        use_cli = False
        if backend == "cli":
            use_cli = True
        elif backend == "auto":
            use_cli = cli_info["installed"]
        else:  # harness_skills
            use_cli = False

        if use_cli:
            try:
                return execute_cli(task, emit, cancelled)
            except EngineFailure as ef:
                if ef.kind == "capability" and backend == "auto":
                    # Fallback gracefully to harness skills if CLI unavailable in auto mode
                    emit(EngineEvent(engine="paperorchestra", type="status", data={"state": "fallback_to_harness_skills", "reason": str(ef)}))
                    return execute_skill(task, emit, cancelled)
                raise

        return execute_skill(task, emit, cancelled)

