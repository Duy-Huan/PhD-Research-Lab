"""Container-only execution for grants with isolation="container" (v6.6.2, layer 1 of the ChatGPT connector).

Python tools run in the owner's validation image with the tool directory mounted read-only, the job directory as the
only writable mount, and no network unless the tool declares it (the Container adapter's existing hardening). Tools
that would execute on the host and cannot be moved into a container are refused: CLI tools (host binaries) and
native tools that need compute/process (they run code in this process or on the host). In-app native tools without
those permissions (reading project state, search) and remote MCP tools are unaffected.
"""
from __future__ import annotations

from backend.tools.spec import ToolSpec

HOST_PERMISSIONS = {"compute", "process"}


def containable(spec: ToolSpec) -> str:
    """Empty when the tool may run under container isolation, otherwise the refusal reason."""
    if spec.kind in ("container", "mcp", "python"):
        return ""
    if spec.kind == "cli":
        return f"{spec.id} runs a host program; refused for container-isolated clients"
    if spec.kind == "native" and HOST_PERMISSIONS & set(spec.permissions):
        return f"{spec.id} executes on the host ({', '.join(sorted(HOST_PERMISSIONS & set(spec.permissions)))}); refused for container-isolated clients"
    return ""


def containerize(spec: ToolSpec) -> ToolSpec:
    if spec.kind != "python":
        return spec
    from backend.core.config import load_config
    image = (load_config().get("tools") or {}).get("validation_image") or "python:3.12-slim"
    entry = str(spec.execution.get("entry", ""))
    return spec.model_copy(update={"kind": "container", "execution": {
        "image": image, "home": spec.execution.get("home", ""), "command": ["python", "-I", "/tool/" + entry]}})
