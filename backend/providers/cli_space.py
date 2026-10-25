"""Secure CLI space (v4.1, Firewall spec §5): every CLI provider request runs in a dedicated per-session workspace.

    <cli_space_dir or <data>/cli-space>/
      <provider>/sessions/<gateway session id>/
          workspace/   the provider's working directory (the only place a profile may let it write)
          context/     compiled context bundle + manifest (sha256 per item) — written read-only
          input/ output/ artifacts/ logs/   staged attachments, answers, deliverables, redacted stderr
          session.json policy snapshot (profile, isolation level, provider) — never secrets

Rules enforced here
  • A CLI is never started in the app folder or in the research project: cwd is always a session workspace.
  • Paths are canonicalised; traversal (`..`, absolute / drive / UNC parts) and symlinks that leave the root are refused.
  • The environment is rebuilt from an allowlist (system + the CLI's own sign-in/config locations). Credentials, cloud
    keys, tokens and unrelated variables are dropped; a provider's own API-key variables are kept only when the
    researcher enabled <provider>_api_fallback (cost guard, v3.4).
  • Profiles are only offered as far as the provider can enforce them. `review` = no writes; `assisted` = the session
    workspace is writable. A profile the provider enforces only through its own permission system (not an OS sandbox)
    is a visibly weaker mode and needs the researcher's explicit consent per request; an unsupported one is refused.
    A directory is not a sandbox: the isolation level is reported honestly in session.json and the UI.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import time
from pathlib import Path

SUBDIRS = ("workspace", "context", "input", "output", "artifacts", "logs")
PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")
PROFILES = {
    "review": "Read-only / Review — reads the staged context only; no file writes, no shell commands",
    "assisted": "Assisted — may write inside its own session workspace only; the project and memory stay read-only",
}
# (provider, profile) → (supported, level, enforced, how)
#   level: os-sandbox (the vendor's OS-level sandbox) · provider-permission (the CLI's own permission rules in headless
#   mode, no OS isolation) · none
ISOLATION = {
    ("codex", "review"): (True, "os-sandbox", True, "codex exec --sandbox read-only (Codex OS sandbox)"),
    ("codex", "assisted"): (True, "os-sandbox", True, "codex exec --sandbox workspace-write, cwd = session workspace"),
    ("claude_code", "review"): (True, "provider-permission", True,
                                "claude -p: only the read-only PhD-Lab MCP tools allowed; Bash/Edit/Write disallowed"),
    ("claude_code", "assisted"): (True, "provider-permission", False,
                                  "claude -p --permission-mode acceptEdits: edits limited to the working directory by "
                                  "Claude Code's permission rules (no OS sandbox on Windows) — needs your consent"),
    ("antigravity", "review"): (True, "provider-permission", True, "agy -p --sandbox (headless: approvals are soft-denied)"),
    ("gemini_cli", "review"): (True, "provider-permission", True, "gemini -p (headless: tool approvals are denied)"),
    ("feynman", "assisted"): (True, "provider-permission", False,
                              "feynman runs one research workflow with cwd = its session workspace; the files it writes stay "
                              "there until you accept them (no OS sandbox on Windows)"),
}
ENV_ALLOW = {
    # Windows system
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "PATH", "TEMP", "TMP", "OS", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "ALLUSERSPROFILE", "PUBLIC",
    # user profile: the CLIs keep their own sign-in in these folders (never read by PhD-Lab)
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME", "APPDATA", "LOCALAPPDATA", "USERNAME", "USER", "LOGNAME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR",
    # locale / terminal
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "PYTHONIOENCODING",
    # node-based CLIs
    "NVM_HOME", "NVM_SYMLINK", "NODE_PATH", "NPM_CONFIG_PREFIX",
    # the CLIs' own (non-secret) configuration locations
    "CODEX_HOME", "CLAUDE_CONFIG_DIR", "GEMINI_CLI_HOME",
}
SECRET_NAME = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|COOKIE|SESSION)")
_pruned = {"t": 0.0}


class WorkspaceError(ValueError):
    pass


def root(cfg: dict | None = None) -> Path:
    from backend.core.config import data_dir, load_config
    project = data_dir().resolve()
    d = ((cfg or load_config())["gateway"].get("cli_space_dir") or "").strip()
    r = (Path(d).expanduser() if d else project / "cli-space").resolve()
    if not r.is_relative_to(project) or r == project:
        raise WorkspaceError('CLI workspace root must be a dedicated folder inside the active project data directory')
    r.mkdir(parents=True, exist_ok=True)
    return r.resolve()


def _forbidden_roots() -> list:
    from backend.core.config import ROOT, data_dir
    out = [ROOT.resolve()]
    try:
        out.append(data_dir().resolve())
    except Exception:  # pragma: no cover - no active project
        pass
    return out


def safe_path(base: Path, *parts: str) -> Path:
    """base/parts after canonicalisation; refuses traversal, absolute/drive/UNC parts and symlink escapes."""
    base = Path(base).resolve()
    for p in parts:
        s = str(p)
        if not s or s in (".", "..") or "\x00" in s or re.match(r"^([A-Za-z]:|[\\/]{1,2})", s) or \
                any(seg == ".." for seg in re.split(r"[\\/]+", s)):
            raise WorkspaceError(f"unsafe path component: {s!r}")
    target = base.joinpath(*parts)
    resolved = target.resolve()
    if resolved != base and base not in resolved.parents:
        raise WorkspaceError(f"path escapes its root: {target}")
    cur = base
    for seg in Path(*parts).parts if parts else ():
        cur = cur / seg
        if cur.is_symlink():
            real = cur.resolve()
            if real != base and base not in real.parents:
                raise WorkspaceError(f"symlink leaves the workspace: {cur}")
    return resolved


def isolation(provider: str, profile: str) -> dict:
    sup, level, enforced, how = ISOLATION.get((provider, profile), (False, "none", False, "not supported by this provider"))
    return {"provider": provider, "profile": profile, "supported": sup, "level": level, "enforced": enforced, "how": how,
            "profile_label": PROFILES.get(profile, profile)}


def check_profile(provider: str, profile: str, allow_weaker: bool = False) -> dict:
    """Fail closed: unknown/unsupported → refused; weaker (not enforced) → refused without explicit consent."""
    if profile not in PROFILES:
        raise WorkspaceError(f"Unknown security profile '{profile}' (known: {', '.join(PROFILES)})")
    iso = isolation(provider, profile)
    if not iso["supported"]:
        raise WorkspaceError(f"Profile '{profile}' cannot be provided for {provider}: {iso['how']}. Use 'review'.")
    if not iso["enforced"] and not allow_weaker:
        raise WorkspaceError(f"Profile '{profile}' is only a weaker, permission-based isolation for {provider} "
                             f"({iso['how']}). Confirm 'accept weaker isolation' to use it, or choose 'review'.")
    iso["consented_weaker"] = not iso["enforced"]
    return iso


def open_session(provider: str, session_id: str, profile: str = "review", iso: dict | None = None,
                 cfg: dict | None = None) -> dict:
    """Create (or reopen) the dedicated workspace of one provider session."""
    if not PROVIDER_RE.match(provider or ""):
        raise WorkspaceError("invalid provider id")
    if not SESSION_RE.match(session_id or ""):
        raise WorkspaceError("invalid session id")
    base = safe_path(root(cfg), provider, "sessions", session_id)
    for fr in _forbidden_roots():
        if base == fr or base in fr.parents:  # a session folder may never BE (or contain) the app or project folder
            raise WorkspaceError("the CLI space must not be the app or project folder")
    for sub in SUBDIRS:
        safe_path(base, sub).mkdir(parents=True, exist_ok=True)
    meta_f = base / "session.json"
    meta = {}
    if meta_f.exists():
        try:
            meta = json.loads(meta_f.read_text("utf-8"))
        except ValueError:
            meta = {}
    meta.update({"provider": provider, "session_id": session_id, "profile": profile, "updated": time.time(),
                 "isolation": iso or isolation(provider, profile)})
    meta.setdefault("created", time.time())
    meta_f.write_text(json.dumps(meta, indent=1), "utf-8")
    return {"dir": str(base), "cwd": str(base / "workspace"), **{s: str(base / s) for s in SUBDIRS}, "meta": meta}


def _ro(p: Path) -> None:
    try:
        os.chmod(p, stat.S_IREAD)
    except OSError:  # pragma: no cover - filesystem without permission bits
        pass


def _rw(p: Path) -> None:
    try:
        os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    except OSError:  # pragma: no cover
        pass


def stage_context(sess: dict, request_id: str, prompt: str, manifest: dict) -> dict:
    """Write the (already sanitised) context bundle and a provenance manifest read-only into context/."""
    if not re.fullmatch(r"[\w-]{3,64}", request_id or ""):
        raise WorkspaceError("invalid request id")
    ctx = Path(sess["context"])
    pf = safe_path(ctx, f"{request_id}.prompt.md")
    mf = safe_path(ctx, f"{request_id}.manifest.json")
    for f in (pf, mf):
        if f.exists():
            _rw(f)
    pf.write_text(prompt, "utf-8")
    man = {"request_id": request_id, "created": time.time(), "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
           "prompt_chars": len(prompt), "access_mode": "read-only snapshot", **manifest}
    mf.write_text(json.dumps(man, indent=1, default=str), "utf-8")
    _ro(pf)
    _ro(mf)
    return man


def write_output(sess: dict, request_id: str, text: str, stderr_lines: list | None = None) -> None:
    from backend.providers.privacy import sanitize
    try:
        safe_path(Path(sess["output"]), f"{request_id}.md").write_text(text or "", "utf-8")
        if stderr_lines:
            red = [sanitize(l)[0] for l in stderr_lines]
            with open(safe_path(Path(sess["logs"]), "stderr.log"), "a", encoding="utf-8") as f:
                f.write("\n".join(f"[{request_id}] {l}" for l in red) + "\n")
    except (OSError, WorkspaceError):  # pragma: no cover - output capture must never fail a request
        pass


def minimal_env(keep: tuple | set = (), base: dict | None = None) -> dict:
    """Allowlisted environment for a CLI process (names in `keep` are passed through as well)."""
    src = os.environ if base is None else base
    allow = {n.upper() for n in ENV_ALLOW}
    keep_u = {n.upper() for n in keep}
    out = {}
    for k, v in src.items():
        ku = k.upper()
        if ku in keep_u or (ku in allow and not SECRET_NAME.search(ku)):
            out[k] = v
    out["NO_COLOR"] = "1"
    return out


def sessions(limit: int = 100, cfg: dict | None = None) -> list:
    r = root(cfg)
    out = []
    for f in r.glob("*/sessions/*/session.json"):
        try:
            d = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        d["dir"] = str(f.parent)
        d["files"] = {s: sum(1 for _ in (f.parent / s).glob("*")) for s in ("context", "output", "artifacts")}
        out.append(d)
    out.sort(key=lambda d: d.get("updated", 0), reverse=True)
    return out[:limit]


def prune(cfg: dict | None = None, force: bool = False) -> int:
    """Bounded retention: sessions older than cli_retention_days, and the oldest beyond cli_max_sessions."""
    from backend.core.config import load_config
    if not force and time.time() - _pruned["t"] < 600:
        return 0
    _pruned["t"] = time.time()
    g = (cfg or load_config())["gateway"]
    days, keep = int(g.get("cli_retention_days", 14) or 14), int(g.get("cli_max_sessions", 300) or 300)
    all_s = sessions(10 ** 6, cfg)
    cutoff = time.time() - days * 86400
    victims = [s for s in all_s if s.get("updated", 0) < cutoff] + all_s[keep:]
    n = 0
    r = root(cfg)
    for s in {v["dir"]: v for v in victims}.values():
        d = Path(s["dir"]).resolve()
        if r not in d.parents:  # pragma: no cover - sessions() only yields children of the root
            continue
        for f in d.rglob("*"):
            if f.is_file():
                _rw(f)
        shutil.rmtree(d, ignore_errors=True)
        n += 1
    return n
