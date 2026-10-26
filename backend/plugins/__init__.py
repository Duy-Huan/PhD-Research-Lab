"""Skill plugins installed from GitHub — stored once under <data>/plugins/, switched on or off per research project.

    <data>/plugins/<id>/plugin.json    manifest: repository, ref, commit, install time, adapter, skills found
    <data>/plugins/<id>/repo/          the repository snapshot (codeload zip of one commit; nothing is ever executed)
    <project>/plugins.json             {"enabled": {id: bool}, "disabled_skills": [name, …]} of that project

A repository can bring skills in two formats:
    Agent Skills      any folder with a SKILL.md (front matter: name, description; body = instructions)
    PhD Lab skills    Markdown files with the front matter of backend/agent/skills.py (in skills/ or phdlab-skills/)
Repositories with a known adapter (backend/plugins/ai_scientist.py for SakanaAI/AI-Scientist-v2) add skills built from
the repository's own prompts. A plugin skill never grants rights: risk decides whether the researcher must accept.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath

from backend.agent import AIWSError

MAX_ZIP = 120 * 1024 * 1024        # compressed download
MAX_FILES = 6000
MAX_UNPACKED = 400 * 1024 * 1024
SKILL_CHARS = 16000                # instructions + inlined references of one skill
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")
GH_RE = re.compile(r"^(?:https?://github\.com/)?([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.+?))?)?/?$")
_lock = threading.RLock()


class PluginError(AIWSError):
    pass


def root() -> Path:
    from backend.core.config import GLOBAL_DIR
    d = GLOBAL_DIR / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dir(pid: str) -> Path:
    if not ID_RE.match(pid or "") or pid.startswith("_"):
        raise PluginError("Invalid plugin id")
    d = root() / pid
    if not (d / "plugin.json").is_file():
        raise PluginError(f"Plugin {pid} is not installed")
    return d


def parse_url(url: str) -> dict:
    """github.com/owner/repo[/tree/ref[/sub/dir]] or owner/repo → {owner, repo, ref, subdir}."""
    m = GH_RE.match((url or "").strip())
    if not m:
        raise PluginError("Enter a GitHub repository: https://github.com/owner/repo (optionally /tree/<branch>/<folder>)")
    owner, repo, ref, sub = m.groups()
    if "." in owner:  # a bare foreign hostname is not a GitHub owner/repo shorthand
        raise PluginError("Enter a GitHub repository URL or owner/repo")
    sub = str(PurePosixPath(sub)) if sub else ""
    if ".." in sub.split("/"):
        raise PluginError("Invalid folder in the repository URL")
    return {"owner": owner, "repo": repo, "ref": ref or "", "subdir": sub}


def plugin_id(owner: str, repo: str, subdir: str = "") -> str:
    base = f"{owner}-{repo}" + (f"-{subdir.replace('/', '-')}" if subdir else "")
    return re.sub(r"[^a-z0-9._-]+", "-", base.lower()).strip("-.")[:80]


# ------------------------------------------------------------------ download
def _http():
    import httpx
    return httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "PhD-Research-Lab", "Accept": "application/vnd.github+json"})


def _resolve(owner: str, repo: str, ref: str) -> tuple[str, str]:
    """(ref, commit sha) — the default branch when ref is empty. A missing API answer keeps the branch name."""
    with _http() as c:
        if not ref:
            r = c.get(f"https://api.github.com/repos/{owner}/{repo}")
            if r.status_code == 404:
                raise PluginError(f"GitHub repository {owner}/{repo} not found (or private)")
            r.raise_for_status()
            ref = r.json().get("default_branch") or "main"
        r = c.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}")
        sha = r.json().get("sha", "") if r.status_code == 200 else ""
    return ref, sha


def _download(owner: str, repo: str, rev: str) -> bytes:
    with _http() as c, c.stream("GET", f"https://codeload.github.com/{owner}/{repo}/zip/{rev}") as r:
        if r.status_code == 404:
            raise PluginError(f"{owner}/{repo}@{rev} not found on GitHub")
        r.raise_for_status()
        buf = io.BytesIO()
        for chunk in r.iter_bytes():
            buf.write(chunk)
            if buf.tell() > MAX_ZIP:
                raise PluginError(f"Repository archive is larger than {MAX_ZIP // 2**20} MB")
    return buf.getvalue()


def extract(data: bytes, dest: Path, subdir: str = "") -> int:
    """Unpack a GitHub archive (its single top folder stripped) into dest; zip-slip, links and size are checked."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PluginError("The download is not a zip archive")
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES:
        raise PluginError(f"Repository has more than {MAX_FILES} files")
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise PluginError(f"Repository is larger than {MAX_UNPACKED // 2**20} MB unpacked")
    prefix = (subdir.strip("/") + "/") if subdir else ""
    n = 0
    for i in infos:
        parts = PurePosixPath(i.filename).parts[1:]  # drop "<repo>-<rev>/"
        rel = "/".join(parts)
        if (i.external_attr >> 16) & 0o170000 == 0o120000 or not rel:  # symbolic link / top folder
            continue
        if prefix:
            if not rel.startswith(prefix):
                continue
            rel = rel[len(prefix):]
        target = (dest / rel).resolve()
        if dest.resolve() not in target.parents:
            raise PluginError(f"Unsafe path in archive: {i.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(i) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        n += 1
    if not n:
        raise PluginError(f"No files found{' in folder ' + subdir if subdir else ''}")
    return n


# ------------------------------------------------------------------ skill discovery
def _yaml(front: str) -> dict:
    """The small YAML subset of SKILL.md front matter: key: value, quoted strings, | and > blocks, [a, b] lists."""
    out, key, block, style = {}, None, [], ""
    for line in front.splitlines() + ["__end__: x"]:
        if key and (line.startswith((" ", "\t")) or not line.strip()):
            block.append(line.strip())
            continue
        if key:
            out[key] = ("\n" if style == "|" else " ").join(block).strip()
            key, block = None, []
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v in ("|", ">", "|-", ">-", "|+", ">+"):
            key, style = k, v[0]
        elif v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else:
            out[k] = v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in "'\"" else v
    out.pop("__end__", None)
    return out


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "-", str(name).lower()).strip("-_")
    s = re.sub(r"-{2,}", "-", s)
    if not s or not s[0].isalpha():
        s = "s-" + s
    return s[:31].rstrip("-_") or "skill"


def _category(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(writ|paper|latex|manuscript|draft|citation|figure)", t):
        return "writing"
    if re.search(r"\b(experiment|train|code|benchmark|dataset|model)", t):
        return "experiment"
    return "research"


def _inline_refs(folder: Path, body: str, budget: int) -> str:
    """Append small Markdown files the skill links to ([x](references/y.md)) — the agent cannot open files itself."""
    extra = []
    for ref in dict.fromkeys(re.findall(r"\]\(([^)#\s]+\.md)\)", body)):
        f = (folder / ref).resolve()
        if folder.resolve() not in f.parents or not f.is_file():
            continue
        try:
            text = f.read_text("utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > budget:
            break
        budget -= len(text)
        extra.append(f"\n\n## Reference: {ref}\n{text.strip()}")
    return "".join(extra)


def agent_skill(path: Path, pid: str) -> dict:
    """One SKILL.md → a PhD Lab chat skill (origin plugin)."""
    text = path.read_text("utf-8", errors="replace")
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    meta, body = (_yaml(m.group(1)), m.group(2)) if m else ({}, text)
    name = slug(meta.get("name") or path.parent.name)
    desc = str(meta.get("description") or "").strip()
    body = body.strip()
    body += _inline_refs(path.parent, body, max(0, SKILL_CHARS - len(body)))
    title = str(meta.get("title") or meta.get("name") or path.parent.name).replace("-", " ").strip()
    return {"name": name, "title": title[:80], "description": desc[:300], "usage": "", "category": _category(name + " " + desc),
            "agent": "reviewer" if re.search(r"review|critique|referee", name + " " + desc[:120], re.I) else "research",
            "mode": "chat", "pipeline": "", "provider": "app", "risk": 0, "aliases": [],
            "origin": "plugin", "plugin": pid, "file": str(path), "instructions": body[:SKILL_CHARS]}


def discover(repo_dir: Path, pid: str) -> tuple[list, list]:
    """Every skill of an unpacked repository → (skills, errors). Depth-limited, never follows links."""
    from backend.agent.skills import parse
    found, errors, names = [], [], set()
    for f in sorted(repo_dir.rglob("*.md")):
        rel = f.relative_to(repo_dir)
        if len(rel.parts) > 6 or any(p.startswith(".") or p in ("node_modules", "_trash") for p in rel.parts):
            continue
        try:
            if f.name.lower() == "skill.md":
                s = agent_skill(f, pid)
            elif len(rel.parts) > 1 and rel.parts[-2] in ("skills", "phdlab-skills"):
                text = f.read_text("utf-8", errors="replace")
                if not text.lstrip("﻿").startswith("---"):
                    continue
                s = parse(text, "plugin")
                s.update(plugin=pid, file=str(f))
            else:
                continue
        except (AIWSError, OSError) as e:
            errors.append({"file": str(rel), "error": str(e)[:200]})
            continue
        base, i = s["name"], 2
        while s["name"] in names:  # two skills with one name in a repository: keep both
            s["name"] = f"{base[:28]}-{i}"
            i += 1
        names.add(s["name"])
        found.append(s)
    return found, errors


def _adapter_for(owner: str, repo: str):
    from backend.plugins import ai_scientist
    return ai_scientist if f"{owner}/{repo}".lower() == ai_scientist.REPO.lower() else None


def scan(pid: str) -> dict:
    """Re-read the skills of an installed plugin (after install / update) and store them in its manifest."""
    d = _dir(pid)
    man = json.loads((d / "plugin.json").read_text("utf-8"))
    skills, errors = discover(d / "repo", pid)
    adapter = _adapter_for(man["owner"], man["repo"])
    if adapter:
        skills = adapter.skills(d / "repo", pid) + skills
        man["adapter"] = adapter.NAME
    man["skills"] = [{k: v for k, v in s.items() if k != "instructions"} | {"chars": len(s["instructions"])} for s in skills]
    man["errors"] = errors
    _write(d / "plugin.json", man)
    _cache.clear()
    return man


def _write(path: Path, obj) -> None:
    from backend.memory.store import replace_retry
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")
    replace_retry(tmp, path)


# ------------------------------------------------------------------ install / update / remove
def install(url: str, enable: bool = True) -> dict:
    """Download a GitHub repository snapshot into <data>/plugins/<id>/ and enable it for the active project."""
    spec = parse_url(url)
    pid = plugin_id(spec["owner"], spec["repo"], spec["subdir"])
    ref, sha = _resolve(spec["owner"], spec["repo"], spec["ref"])
    data = _download(spec["owner"], spec["repo"], sha or ref)
    with _lock:
        d = root() / pid
        staging = root() / f"_staging-{pid}-{int(time.time() * 1000)}"
        try:
            n = extract(data, staging / "repo", spec["subdir"])
            man = {"id": pid, "owner": spec["owner"], "repo": spec["repo"], "subdir": spec["subdir"], "ref": ref, "commit": sha,
                   "url": f"https://github.com/{spec['owner']}/{spec['repo']}", "installed": time.time(), "files": n,
                   "skills": [], "errors": [], "adapter": ""}
            _write(staging / "plugin.json", man)
            if d.exists():
                _trash(d)
            staging.rename(d)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        man = scan(pid)
    if enable:
        set_enabled(pid, True)
    return describe(pid)


def update(pid: str) -> dict:
    man = json.loads((_dir(pid) / "plugin.json").read_text("utf-8"))
    url = man["url"] + (f"/tree/{man['ref']}" + (f"/{man['subdir']}" if man["subdir"] else "") if man.get("ref") else "")
    return install(url, enable=pid in enabled_ids())


def _trash(d: Path) -> None:
    t = root() / "_trash"
    t.mkdir(exist_ok=True)
    shutil.move(str(d), str(t / f"{d.name}-{int(time.time())}"))


def remove(pid: str) -> dict:
    with _lock:
        _trash(_dir(pid))
    _cache.clear()
    return {"removed": pid}


# ------------------------------------------------------------------ per-project switches
def _state_path() -> Path:
    from backend.core.config import data_dir
    return data_dir() / "plugins.json"


def _state() -> dict:
    try:
        st = json.loads(_state_path().read_text("utf-8"))
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def enabled_ids() -> set:
    return {k for k, v in (_state().get("enabled") or {}).items() if v}


def set_enabled(pid: str, on: bool) -> dict:
    _dir(pid)
    with _lock:
        st = _state()
        st.setdefault("enabled", {})[pid] = bool(on)
        _write(_state_path(), st)
    _cache.clear()
    return describe(pid)


def set_skill(name: str, on: bool) -> dict:
    with _lock:
        st = _state()
        off = set(st.get("disabled_skills") or [])
        (off.discard if on else off.add)(name)
        st["disabled_skills"] = sorted(off)
        _write(_state_path(), st)
    _cache.clear()
    return {"skill": name, "enabled": on}


def describe(pid: str) -> dict:
    man = json.loads((_dir(pid) / "plugin.json").read_text("utf-8"))
    off = set(_state().get("disabled_skills") or [])
    man["enabled"] = pid in enabled_ids()
    for s in man.get("skills") or []:
        s["enabled"] = s["name"] not in off
    man["path"] = str(_dir(pid))
    return man


def list_plugins() -> list:
    out = []
    for f in sorted(root().glob("*/plugin.json")):
        if f.parent.name.startswith("_"):
            continue
        try:
            out.append(describe(f.parent.name))
        except (OSError, ValueError, PluginError):
            continue
    return out


# ------------------------------------------------------------------ skills for backend/agent/skills.py
_cache: dict = {}


def stamp() -> tuple:
    """Changes whenever a plugin is installed / rescanned or the project's switches change (skills cache key)."""
    files = [f for f in root().glob("*/plugin.json") if not f.parent.name.startswith("_")]
    sp = _state_path()
    return tuple((str(f), f.stat().st_mtime_ns) for f in sorted(files)) + ((str(sp), sp.stat().st_mtime_ns) if sp.exists() else ("",))


def project_skills() -> list:
    """Full skill dicts (with instructions) of the plugins enabled in the active project, minus disabled skills."""
    key = stamp()
    if _cache.get("key") == key:
        return _cache["skills"]
    st = _state()
    on = {k for k, v in (st.get("enabled") or {}).items() if v}
    off = set(st.get("disabled_skills") or [])
    out = []
    for pid in sorted(on):
        try:
            d = _dir(pid)
            man = json.loads((d / "plugin.json").read_text("utf-8"))
        except (OSError, ValueError, PluginError):
            continue
        adapter = _adapter_for(man["owner"], man["repo"])
        skills = (adapter.skills(d / "repo", pid) if adapter else []) + discover(d / "repo", pid)[0]
        out += [s for s in skills if s["name"] not in off]
    _cache.update(key=key, skills=out)
    return out
