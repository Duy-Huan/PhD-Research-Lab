"""Source control & GitHub publishing (v3.0) for the project's code/ workspace.

Uses GitPython when installed (pip install GitPython), otherwise the git CLI directly — both need Git for Windows.
The GitHub Personal Access Token is stored only in data/config.json, is sent only to api.github.com / github.com,
and is passed to `git push` as a one-off HTTP header — it is never written into .git/config.
"""
from __future__ import annotations

import base64
import re
import shutil
import subprocess
from pathlib import Path

import httpx

from backend.core.config import load_config
from backend.execution.files import GITIGNORE
from backend.execution.sandbox import code_dir

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
API = "https://api.github.com"

try:
    import git as _gitpython  # GitPython
except Exception:  # not installed, or git executable missing
    _gitpython = None


class GitError(Exception):
    pass


def git_exe() -> str | None:
    return shutil.which("git")


def G(args: list, timeout: int = 120, extra_config: list | None = None, check: bool = True) -> str:
    """Run git in code/. extra_config: ['http.extraheader=…'] passed as -c options (never persisted)."""
    exe = git_exe()
    if not exe:
        raise GitError("Git is not installed. Install Git for Windows (https://git-scm.com/download/win) and restart the app.")
    pre = sum((["-c", c] for c in (extra_config or [])), [])
    cmd = [exe, *pre, *args]
    if _gitpython is not None:
        try:
            out = _gitpython.Git(str(code_dir())).execute(cmd, with_extended_output=True, with_exceptions=False,
                                                         kill_after_timeout=timeout, strip_newline_in_stdout=False)
            code, so, se = out
            if check and code != 0:
                raise GitError((se or so or f"git {args[0]} failed").strip()[-600:])
            return so or ""  # same contract as the subprocess path: stdout only
        except GitError:
            raise
        except Exception:
            pass  # fall back to subprocess
    r = subprocess.run(cmd, cwd=str(code_dir()), capture_output=True, text=True, errors="replace", timeout=timeout,
                       creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise GitError((r.stderr or r.stdout or f"git {args[0]} failed").strip()[-600:])
    return r.stdout


def is_repo() -> bool:
    return (code_dir() / ".git").exists()


def _identity():
    gh = load_config().get("github", {})
    name = gh.get("name") or gh.get("user") or "PhD Research Lab"
    email = gh.get("email") or (f"{gh['user']}@users.noreply.github.com" if gh.get("user") else "phdlab@localhost")
    return name, email


def init() -> dict:
    if is_repo():
        return status()
    G(["init"])
    try:
        G(["symbolic-ref", "HEAD", "refs/heads/main"])
    except GitError:
        pass
    gi = code_dir() / ".gitignore"
    if not gi.exists():
        gi.write_text(GITIGNORE, "utf-8")
    name, email = _identity()
    G(["config", "user.name", name])
    G(["config", "user.email", email])
    return status()


STATUS_MAP = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed", "C": "copied", "U": "conflict", "?": "untracked", "!": "ignored"}


def status() -> dict:
    out = {"git": bool(git_exe()), "gitpython": _gitpython is not None, "repo": False, "files": [], "branch": "",
           "remote": "", "ahead": 0, "behind": 0, "commits": []}
    if not git_exe() or not is_repo():
        return out
    out["repo"] = True
    txt = G(["status", "--porcelain=v1", "-b", "-uall"], check=False)
    for line in txt.splitlines():
        if line.startswith("## "):
            head = line[3:]
            out["branch"] = head.split("...")[0].replace("No commits yet on ", "")
            m = re.search(r"ahead (\d+)", head)
            out["ahead"] = int(m.group(1)) if m else 0
            m = re.search(r"behind (\d+)", head)
            out["behind"] = int(m.group(1)) if m else 0
            continue
        if len(line) < 4:
            continue
        x, y, path = line[0], line[1], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        code = y if y != " " else x
        out["files"].append({"path": path.strip('"'), "index": x, "worktree": y, "staged": x not in (" ", "?"),
                             "status": STATUS_MAP.get(code, code)})
    out["remote"] = G(["remote", "get-url", "origin"], check=False).strip() if "origin" in G(["remote"], check=False).split() else ""
    log = G(["log", "-n", "15", "--pretty=format:%h%x1f%an%x1f%ar%x1f%s"], check=False)
    for line in log.splitlines():
        p = line.split("\x1f")
        if len(p) == 4:
            out["commits"].append({"hash": p[0], "author": p[1], "when": p[2], "message": p[3]})
    return out


def head_info() -> dict:
    """Commit the code is at right now — recorded in every run (Experiment → Git commit traceability). {} if no repo."""
    if not git_exe() or not is_repo():
        return {}
    sha = G(["rev-parse", "HEAD"], check=False, timeout=20).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return {"sha": "", "branch": "", "dirty": True, "note": "no commit yet"}
    dirty = bool(G(["status", "--porcelain", "-uno"], check=False, timeout=20).strip())
    remotes = G(["remote"], check=False, timeout=20).split()
    return {"sha": sha, "short": sha[:10], "branch": G(["rev-parse", "--abbrev-ref", "HEAD"], check=False, timeout=20).strip(),
            "dirty": dirty, "remote": G(["remote", "get-url", "origin"], check=False, timeout=20).strip() if "origin" in remotes else ""}


def diff(path: str) -> dict:
    if not is_repo():
        raise GitError("Not a git repository yet — click Initialize")
    p = (code_dir() / path).resolve()
    if code_dir().resolve() not in p.parents:
        raise GitError("Path outside the workspace")
    head = G(["show", f"HEAD:{path}"], check=False) if G(["rev-parse", "--verify", "HEAD"], check=False).strip() else ""
    cur = p.read_text("utf-8", errors="replace") if p.exists() else ""
    return {"path": path, "original": head, "modified": cur}


def commit(message: str, paths: list | None = None) -> dict:
    if not message.strip():
        raise GitError("Write a commit message")
    if not is_repo():
        init()
    name, email = _identity()
    if paths:
        G(["add", "--", *paths])
    else:
        G(["add", "-A"])
    staged = G(["diff", "--cached", "--name-only"], check=False).strip()
    if not staged:
        raise GitError("Nothing to commit")
    G(["-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", message.strip()])
    return status()
