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

from .config import load_config
from .ide_fs import GITIGNORE
from .sandbox import code_dir

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


def discard(path: str) -> dict:
    G(["checkout", "--", path])
    return status()


def _token() -> str:
    tok = load_config().get("github", {}).get("token", "")
    if not tok:
        raise GitError("Add a GitHub Personal Access Token first (Source Control → ⚙ GitHub settings). "
                       "Fine-grained token with 'Contents: read & write' and 'Administration: read & write' (to create repos), "
                       "or a classic token with the 'repo' scope.")
    return tok


def _auth_header(tok: str) -> str:
    b = base64.b64encode(f"x-access-token:{tok}".encode()).decode()
    return f"http.https://github.com/.extraheader=AUTHORIZATION: basic {b}"


def gh_user(tok: str | None = None) -> dict:
    tok = tok or _token()
    r = httpx.get(f"{API}/user", headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28"}, timeout=20)
    if r.status_code == 401:
        raise GitError("GitHub rejected the token (401) — check it has not expired")
    r.raise_for_status()
    d = r.json()
    return {"login": d.get("login"), "name": d.get("name"), "html_url": d.get("html_url")}


def publish(repo: str, private: bool = True, description: str = "") -> dict:
    """Create the GitHub repository (or reuse an existing one you own) and push the current branch."""
    tok = _token()
    repo = re.sub(r"[^A-Za-z0-9._-]+", "-", repo.strip()).strip("-.") or "research-code"
    if not is_repo():
        init()
    if not G(["rev-parse", "--verify", "HEAD"], check=False).strip():
        commit("Initial commit (PhD Research Lab)")
    user = gh_user(tok)
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    r = httpx.post(f"{API}/user/repos", headers=h, json={"name": repo, "private": bool(private), "description": description[:300],
                                                         "auto_init": False}, timeout=30)
    created = r.status_code == 201
    if r.status_code == 422:  # already exists
        r2 = httpx.get(f"{API}/repos/{user['login']}/{repo}", headers=h, timeout=20)
        if r2.status_code != 200:
            raise GitError(f"GitHub: {r.json().get('message', r.text)[:300]}")
        info = r2.json()
    elif r.status_code in (401, 403):
        raise GitError("The token cannot create repositories (needs 'Administration: write' or classic 'repo' scope).")
    elif not created:
        raise GitError(f"GitHub error {r.status_code}: {r.text[:300]}")
    else:
        info = r.json()
    url = f"https://github.com/{user['login']}/{repo}.git"
    remotes = G(["remote"], check=False).split()
    G(["remote", "set-url" if "origin" in remotes else "add", "origin", url])
    branch = G(["rev-parse", "--abbrev-ref", "HEAD"]).strip() or "main"
    G(["push", "-u", "origin", f"HEAD:{branch}"], timeout=600, extra_config=[_auth_header(tok)])
    return {"created": created, "html_url": info.get("html_url") or url[:-4], "private": info.get("private", private),
            "branch": branch, "status": status()}


def push() -> dict:
    tok = _token()
    if "origin" not in G(["remote"], check=False).split():
        raise GitError("No GitHub remote yet — use Publish to GitHub first")
    branch = G(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    G(["push", "-u", "origin", f"HEAD:{branch}"], timeout=600, extra_config=[_auth_header(tok)])
    return status()


def pull() -> dict:
    tok = _token()
    G(["pull", "--ff-only"], timeout=600, extra_config=[_auth_header(tok)])
    return status()
