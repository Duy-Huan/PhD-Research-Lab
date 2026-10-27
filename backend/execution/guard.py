"""Hardware guard: admission control for background research work on one consumer PC (RTX 3060 12 GB, 32 GB RAM).

Every step of a research run declares the resource class it needs. A class has a fixed number of slots; a step that
cannot get a slot waits (the run shows BLOCKED with the reason) instead of starting and crashing the machine.

    gpu        1   training / evaluation on the GPU — never two at once (VRAM)
    cpu        1   CPU-only experiment processes (one at a time keeps the UI responsive)
    local_llm  1   a local model answering (LM Studio / Ollama share the same VRAM)
    cli        2   CLI providers (Claude Code, Codex, Gemini, supported native apps) — subprocesses, little memory
    cloud      3   cloud API calls (network bound)
    none       ∞   bookkeeping steps (verification, reports)

Slot counts can only be LOWERED in Settings (runs.slot_<class>); a GPU class above 1 is refused. Before a gpu slot is granted
the VRAM gate of resources.py runs: local models still in VRAM block the step (or are unloaded first when
resources.auto_unload_for_gpu is on), so a training job never starts on a GPU that is already full.
"""
from __future__ import annotations

import threading
import time

CLASSES = {"gpu": 1, "cpu": 1, "local_llm": 1, "cli": 2, "cloud": 3, "none": 0}
_cond = threading.Condition()
_held: dict = {}  # class → {holder id: since}


class Busy(Exception):
    def __init__(self, cls: str, reason: str, holders: list | None = None):
        super().__init__(reason)
        self.cls, self.reason, self.holders = cls, reason, holders or []


def capacity(cls: str) -> int:
    if cls not in CLASSES:
        raise ValueError(f"unknown resource class {cls}")
    if cls == "none":
        return 10 ** 6
    from backend.core.config import load_config
    want = (load_config().get("runs") or {}).get(f"slot_{cls}")
    try:
        want = int(want)
    except (TypeError, ValueError):
        return CLASSES[cls]
    return max(1, min(CLASSES[cls], want))


def _vram_check() -> None:
    from backend.execution import resources as R
    try:
        R.vram_gate()
    except R.VramBusy as e:
        from backend.core.config import load_config
        if load_config()["resources"].get("auto_unload_for_gpu"):
            from backend.providers.lifecycle import free_vram_for_gpu
            if free_vram_for_gpu().get("ok"):
                return
        raise Busy("gpu", f"{e} — unload the local models (Settings → Models) or allow automatic unloading",
                   list(getattr(e, "models", []) or []))


def try_acquire(cls: str, holder: str, gpu_check: bool = True) -> None:
    """Take a slot now or raise Busy (never blocks). Re-entrant for the same holder."""
    with _cond:
        held = _held.setdefault(cls, {})
        if holder in held:
            return
        if len(held) >= capacity(cls):
            raise Busy(cls, f"waiting for a free {cls} slot (in use by {', '.join(sorted(held))})", sorted(held))
        if cls == "gpu" and gpu_check:
            _vram_check()
        held[holder] = time.time()


def acquire(cls: str, holder: str, timeout: float = 0, on_wait=None, cancelled=None, gpu_check: bool = True) -> None:
    """Block until a slot is free (timeout 0 = wait until cancelled). on_wait(reason) is called once per new reason."""
    end = time.time() + timeout if timeout else None
    last = ""
    while True:
        try:
            return try_acquire(cls, holder, gpu_check)
        except Busy as b:
            if b.reason != last and on_wait:
                on_wait(b.reason)
            last = b.reason
            if (end and time.time() >= end) or (cancelled and cancelled()):
                raise
        with _cond:
            _cond.wait(0.5)


def release(cls: str, holder: str) -> None:
    with _cond:
        (_held.get(cls) or {}).pop(holder, None)
        _cond.notify_all()


def release_all(holder: str) -> None:
    with _cond:
        for h in _held.values():
            h.pop(holder, None)
        _cond.notify_all()


def snapshot() -> dict:
    with _cond:
        return {c: {"capacity": capacity(c) if c != "none" else None, "held_by": sorted(_held.get(c) or {})}
                for c in CLASSES if c != "none"}


def reset() -> None:
    """Tests only."""
    with _cond:
        _held.clear()
        _cond.notify_all()


def pid_alive(pid) -> bool:
    """True when a process with this id still runs (read-only check — never signals the process)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    import os
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
