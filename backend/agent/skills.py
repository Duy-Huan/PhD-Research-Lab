"""Skills: the "/" commands of the research chat (UI and CLI share them).

A skill is a Markdown file with a small front matter block and the instructions the agent follows:

    ---
    name: lit
    title: Literature review
    description: Tìm, lọc và tổng hợp tài liệu về một chủ đề
    usage: <chủ đề>
    category: research          research | experiment | writing | system
    agent: research             research | reviewer   (the two agents of the app)
    mode: run                   chat (one answer in the conversation) | run (a background research run)
    pipeline: research          run pipeline (see runs.PIPELINES); ignored for chat skills
    provider: feynman           preferred research provider: feynman | coding | app (falls back to app)
    feynman: lit                Feynman workflow used when the provider is Feynman
    risk: 0                     0 read · 1 writes inside the project · 2 compute / code / research state
    aliases: [literature]
    ---
    Instructions for the agent (Markdown).

Lookup order (a later layer overrides an earlier one with the same name):
    backend/agent/skills/*.md     built-in skills
    <data>/plugins/<id>/          skills of GitHub plugins enabled in this project (backend/plugins; never override a
                                  built-in skill — a clashing plugin skill is renamed <plugin>-<name>)
    <data>/skills/*.md            the researcher's skills for every project
    <project>/skills/*.md         skills of the active research project
A skill never grants rights: risk only decides whether the researcher must accept before anything runs.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.agent import AIWSError

BUILTIN = Path(__file__).with_name("skills")
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
CATEGORIES = ("research", "experiment", "writing", "system")
AGENTS = ("research", "reviewer")
MODES = ("chat", "run")
PROVIDERS = ("app", "feynman", "coding", "openscience")
CMD_RE = re.compile(r"^/([a-z][a-z0-9_-]{0,30})(?:\s+([\s\S]*))?$")
_cache: dict = {}


def _scalar(v: str, as_list: bool = False):
    v = v.strip()
    if as_list and v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v.strip("'\"")


def parse(text: str, origin: str = "builtin") -> dict:
    """Front matter + body → a validated skill dict (AIWSError on anything invalid)."""
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*\n?(.*)$", text or "", re.S)
    if not m:
        raise AIWSError("A skill starts with a front matter block between two '---' lines")
    meta = {}
    for line in m.group(1).splitlines():
        line = line.split(" #", 1)[0].rstrip() if not line.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        k, sep, v = line.partition(":")
        if not sep:
            raise AIWSError(f"Invalid front matter line: {line[:60]}")
        meta[k.strip()] = _scalar(v, k.strip() == "aliases")
    name = str(meta.get("name", ""))
    if not NAME_RE.match(name):
        raise AIWSError("name: 2–31 lowercase letters, digits, '-' or '_', starting with a letter")
    s = {"name": name, "title": str(meta.get("title") or name)[:80], "description": str(meta.get("description") or "")[:300],
         "usage": str(meta.get("usage") or "")[:120], "category": meta.get("category") or "research",
         "agent": meta.get("agent") or "research", "mode": meta.get("mode") or "chat",
         "pipeline": str(meta.get("pipeline") or ""), "provider": meta.get("provider") or "app",
         "feynman": str(meta.get("feynman") or ""), "risk": meta.get("risk", 0),
         "aliases": [a for a in (meta.get("aliases") or []) if NAME_RE.match(str(a))], "origin": origin,
         "title_en": str(meta.get("title_en") or "")[:80], "description_en": str(meta.get("description_en") or "")[:300],
         "instructions": m.group(2).strip()}
    for key, allowed in (("category", CATEGORIES), ("agent", AGENTS), ("mode", MODES), ("provider", PROVIDERS)):
        if s[key] not in allowed:
            raise AIWSError(f"{key} must be one of {', '.join(allowed)}")
    if not isinstance(s["risk"], int) or not 0 <= s["risk"] <= 3:
        raise AIWSError("risk must be 0, 1, 2 or 3")
    if s["mode"] == "run":
        from backend.agent.runs import PIPELINES
        if s["pipeline"] not in PIPELINES:
            raise AIWSError(f"pipeline must be one of {', '.join(PIPELINES)}")
    return s


def _dirs() -> list:
    from backend.core.config import GLOBAL_DIR, data_dir
    return [(BUILTIN, "builtin"), (GLOBAL_DIR / "skills", "user"), (data_dir() / "skills", "project")]


def _stamp(dirs: list) -> tuple:
    out = []
    for d, _ in dirs:
        if d.is_dir():
            out += [(str(f), f.stat().st_mtime_ns) for f in sorted(d.glob("*.md"))]
    return tuple(out)


def _plugin_skills(skills: dict, errors: list) -> None:
    from backend import plugins
    try:
        found = plugins.project_skills()
    except Exception as e:  # a damaged plugin folder never disables the built-in commands
        errors.append({"file": "plugins", "origin": "plugin", "error": str(e)[:200]})
        return
    for s in found:
        s = dict(s)
        if skills.get(s["name"], {}).get("origin") == "builtin":
            short = re.sub(r"[^a-z0-9]", "", s["plugin"].split("-")[-1])[:8] or "plugin"
            s["name"] = f"{short}-{s['name']}"[:31].rstrip("-_")
        skills[s["name"]] = s


def load() -> dict:
    """name → skill (aliases resolved separately). Files that do not parse are reported, never fatal."""
    from backend import plugins
    dirs = _dirs()
    key = (_stamp(dirs), plugins.stamp())
    if _cache.get("key") == key:
        return _cache["skills"]
    skills, errors = {}, []
    for d, origin in dirs:
        if origin == "user":
            _plugin_skills(skills, errors)
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                s = parse(f.read_text("utf-8"), origin)
            except (AIWSError, OSError, UnicodeDecodeError) as e:
                errors.append({"file": f.name, "origin": origin, "error": str(e)[:200]})
                continue
            s["file"] = f.name
            skills[s["name"]] = s
    _cache.update(key=key, skills=skills, errors=errors)
    return skills


def errors() -> list:
    load()
    return list(_cache.get("errors") or [])


def get(name: str) -> dict:
    skills = load()
    if name in skills:
        return skills[name]
    for s in skills.values():
        if name in s["aliases"]:
            return s
    raise AIWSError(f"Unknown command /{name} — type /help to see every command")


def catalog() -> list:
    """For the "/" menu and `phdlab skills`: what each command does, without the instructions."""
    order = {c: i for i, c in enumerate(CATEGORIES)}
    out = [{k: v for k, v in s.items() if k != "instructions"} for s in load().values()]
    return sorted(out, key=lambda s: (order[s["category"]], s["name"]))


def match(text: str) -> tuple[dict, str] | None:
    """'/lit vision transformers' → (skill, 'vision transformers'); None for a normal message."""
    m = CMD_RE.match((text or "").strip())
    if not m:
        return None
    return get(m.group(1)), (m.group(2) or "").strip()


def save_user(text: str, scope: str = "project") -> dict:
    """Create or replace a skill of the researcher (never a built-in file)."""
    if scope not in ("project", "user"):
        raise AIWSError("scope must be project or user")
    s = parse(text, scope)
    from backend.core.config import GLOBAL_DIR, data_dir
    d = (data_dir() if scope == "project" else GLOBAL_DIR) / "skills"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{s['name']}.md").write_text(text, "utf-8")
    _cache.clear()
    return get(s["name"])


def delete_user(name: str) -> dict:
    from backend.core.config import GLOBAL_DIR, data_dir
    for d in (data_dir() / "skills", GLOBAL_DIR / "skills"):
        f = d / f"{name}.md"
        if NAME_RE.match(name) and f.is_file():
            f.unlink()
            _cache.clear()
            return {"deleted": name}
    raise AIWSError(f"/{name} is not a skill you created (built-in skills cannot be deleted)")
