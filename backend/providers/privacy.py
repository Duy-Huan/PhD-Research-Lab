"""Privacy / sensitivity policy of everything that leaves the machine (v3.4 §11, §18).

    PUBLIC      always allowed (papers, concepts by default)
    INTERNAL    allowed when gateway.allow_internal (default: yes — research records are INTERNAL by default)
    SENSITIVE   blocked unless gateway.allow_sensitive
    RESTRICTED  never leaves

Applied BEFORE a provider request (Context Gateway) and to every MCP research-tool result (MCP clients are external
models). Classification is per memory node (lod.MemoryNode.classification: type default or the researcher's override in
the context-graph overlay). On top: credential redaction (telemetry.redact) and the "never send proprietary source code"
project rule (gateway.block_source_code) which removes fenced code blocks and blocks the sandbox file-read MCP tools.
"""
from __future__ import annotations

import re

from backend.memory.lod import SENSITIVITY

CODE_FENCE = re.compile(r"```.*?```", re.S)


def gw(cfg: dict | None = None) -> dict:
    from backend.core.config import load_config
    return (cfg or load_config())["gateway"]


def allowed_classes(cfg: dict | None = None) -> tuple:
    g = gw(cfg)
    out = ["PUBLIC"]
    if g.get("allow_internal", True):
        out.append("INTERNAL")
    if g.get("allow_sensitive", False):
        out.append("SENSITIVE")
    return tuple(out)


def sanitize(text: str, cfg: dict | None = None) -> tuple[str, list]:
    """Outgoing text → (text, notes): credentials redacted, code blocks removed under block_source_code."""
    from backend.core.telemetry import redact
    notes = []
    t = redact(text or "")
    if t != (text or ""):
        notes.append("credentials redacted")
    if gw(cfg).get("block_source_code", True):
        t2 = CODE_FENCE.sub("[source code withheld by project policy]", t)
        if t2 != t:
            notes.append("source code withheld")
        t = t2
    return t, notes


def set_sensitivity(node_id: str, level: str) -> dict:
    """The researcher's classification of one memory record. RESTRICTED records never leave this computer: they are
    left out of every context sent to a cloud model or a CLI agent and out of every MCP answer."""
    if level not in SENSITIVITY and level != "":
        raise ValueError(f"level must be one of {', '.join(SENSITIVITY)} (or empty for the default)")
    if not re.fullmatch(r"[\w:.@/+-]{1,120}", node_id or ""):
        raise ValueError("Invalid record id")
    from backend.memory.graph import load_overlay, save_overlay
    ov = load_overlay()
    node = ov["nodes"].setdefault(node_id, {})
    if level:
        node["sensitivity"] = level
    else:
        node.pop("sensitivity", None)
    save_overlay(ov)
    return {"id": node_id, "sensitivity": level or "(type default)"}
