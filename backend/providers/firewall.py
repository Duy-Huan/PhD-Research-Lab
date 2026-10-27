"""Firewall for AI CLI providers (Claude Code, Codex, Gemini CLI and supported native coding tools).

An external agent may work with the research project — never with the application that runs it:

    allowed   its own session workspace (<data>/cli-space/…), the ACTIVE project's data folder and its references folder
    denied    the app's source tree (backend/, frontend/, tests/, tools/, docs/, .git, .venv, launchers …), other
              research projects, everything else on the disk

Five layers, each one enough to stop the common case, together fail-closed:
  1. cwd     the CLI process starts in its session workspace (cli_space.py), never in the repository
  2. env     an allowlisted environment: no API keys, no PhD-Lab paths (cli_space.minimal_env)
  3. rules   per-CLI native permissions written into the workspace before the process starts:
             Claude Code `--settings` with deny rules for every denied path; Gemini CLI / Antigravity workspace
             settings with the PhD-Lab MCP server only; Codex OS sandbox (writes only in the workspace)
  4. tools   the only sanctioned way to read project files or the internet is the PhD-Lab MCP server: files_list /
             files_read (allowlisted roots, path-checked) and web_search / web_fetch (public http(s) only — no
             localhost or private networks, so a page can never reach this app)
  5. audit   every tool call a CLI reports is checked; a call that names a denied path stops the process at once
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

SECRET = re.compile(r"(?i)^(config\.json.*|\.env.*|.*\.(key|pem|token)|mcp-audit.*|_trash)$")
PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/)(?:[^\s\"'<>|*?]+)")


class FirewallError(PermissionError):
    pass


def _norm(p) -> Path:
    return Path(p).expanduser().resolve()


def allowed_roots() -> dict:
    """name → folder the CLIs may read through MCP (the active project's data and references, the CLI space)."""
    from backend.core.config import data_dir, refs_dir
    from backend.providers.cli_space import root
    return {"data": _norm(data_dir()), "references": _norm(refs_dir()), "workspace": _norm(root())}


def _inside(p: Path, base: Path) -> bool:
    return p == base or base in p.parents


def denied_roots() -> list:
    """Every path next to the allowed roots inside the app folder (and the other projects of the data folder)."""
    from backend.core.config import GLOBAL_DIR, ROOT
    keep = list(allowed_roots().values())
    out = []

    def walk(base: Path, depth: int) -> None:
        try:
            children = sorted(base.iterdir())
        except OSError:
            return
        for c in children:
            c = _norm(c)
            if any(_inside(c, k) for k in keep):  # inside an allowed root
                continue
            if any(_inside(k, c) for k in keep):  # an allowed root is this folder or below it
                if c not in keep and depth < 6:
                    walk(c, depth + 1)
                continue
            out.append(c)
    for base in {_norm(ROOT), _norm(GLOBAL_DIR)}:
        if not any(_inside(base, k) for k in keep):  # (the data folder may itself be the active project)
            walk(base, 0)
    return sorted(set(out), key=str)


def check(path, root: str = "data") -> Path:
    """The resolved path when it lies inside the named allowed root (and outside every denied root), else FirewallError."""
    roots = allowed_roots()
    if root not in ("data", "references"):
        raise FirewallError("root must be data or references")
    base = roots[root]
    rel = str(path or "").replace("\\", "/").lstrip("/")
    if re.match(r"^[A-Za-z]:", rel) or any(seg == ".." for seg in rel.split("/")):
        raise FirewallError("use a path relative to the root, without ..")
    p = _norm(base / rel)
    if not _inside(p, base):
        raise FirewallError("path leaves the allowed folder")
    if root == "data" and any(_inside(p, d) for d in denied_roots()):
        raise FirewallError("this part of the data folder belongs to another project")
    rel_parts = p.relative_to(base).parts
    if any(SECRET.match(x) for x in rel_parts) or _inside(p, roots['workspace']):
        raise FirewallError("settings, credentials and other agents' workspaces are not readable")
    return p


def violation(text: str) -> str:
    """The first denied absolute path named in a tool call / command, or ''."""
    if not text:
        return ""
    denied = denied_roots()
    allowed = list(allowed_roots().values())
    for m in PATH_RE.finditer(str(text)):
        raw = m.group(0).rstrip(".,;:)]}")
        try:
            p = _norm(raw)
        except (OSError, ValueError):
            continue
        if SECRET.match(p.name):
            return raw
        if any(_inside(p, a) for a in allowed):
            continue
        if any(_inside(p, d) for d in denied):
            return raw
    return ""


# ------------------------------------------------------------------ per-CLI native rules (layer 3)
def _claude_path(p: Path) -> str:
    s = str(p).replace("\\", "/")
    return "//" + s.lstrip("/")


def prepare_workspace(provider: str, cwd: Path, mcp: dict | None = None) -> dict:
    """Write the provider's own permission / MCP settings into its session workspace. Returns argv additions."""
    cwd = Path(cwd)
    extra: list = []
    deny = denied_roots()
    if provider == "claude_code":
        rules = [f"{tool}({_claude_path(d)}/**)" for d in deny for tool in ("Read", "Edit", "Write", "Glob", "Grep")]
        rules += [f"Read({_claude_path(allowed_roots()['data'])}/{name})" for name in ("config.json*", ".env*")]
        settings = {"permissions": {"deny": rules + ["Bash", "WebFetch", "WebSearch"],
                                    "additionalDirectories": []}}
        f = cwd / ".claude" / "settings.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(settings, indent=1), "utf-8")
        extra += ["--settings", str(f)]
    elif provider in ("gemini_cli", "antigravity") and mcp:
        entry = {"httpUrl" if provider == "gemini_cli" else "serverUrl": mcp["url"],
                 "headers": {"Authorization": f"Bearer {mcp['token']}"}}
        name = ".gemini/settings.json" if provider == "gemini_cli" else ".agents/mcp_config.json"
        f = cwd / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"mcpServers": {"phd-research-lab": entry}}, indent=1), "utf-8")
    elif provider == "codex" and mcp:
        from backend.core.config import ROOT
        import sys
        bridge = str(ROOT / "mcp_stdio_bridge.py").replace("\\", "/")
        py = sys.executable.replace("\\", "/")
        extra += ["-c", f'mcp_servers.phdlab.command="{py}"', "-c", f'mcp_servers.phdlab.args=["{bridge}"]',
                  "-c", f'mcp_servers.phdlab.env={{PHDLAB_MCP_URL="{mcp["url"]}",PHDLAB_MCP_TOKEN="{mcp["token"]}"}}']
    (cwd / "FIREWALL.md").write_text(
        "You work inside this folder. Project files and the internet are available ONLY through the "
        "phd-research-lab MCP tools: files_list / files_read (roots: data, references) and web_search / web_fetch. "
        "Never read or write outside this folder; the application's source code is off limits.\n", "utf-8")
    return {"argv": extra}


# ------------------------------------------------------------------ web access for the CLIs (layer 4)
def public_url(url: str) -> str:
    """The URL when it is a public http(s) address; FirewallError for localhost, private networks, other schemes."""
    u = urlsplit(str(url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise FirewallError("only public http(s) URLs")
    host = u.hostname.strip("[]").lower()
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        raise FirewallError("local addresses are blocked")
    try:
        infos = socket.getaddrinfo(host, u.port or (443 if u.scheme == "https" else 80))
    except OSError:
        raise FirewallError(f"cannot resolve {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise FirewallError("private / local network addresses are blocked")
    return u.geturl()
