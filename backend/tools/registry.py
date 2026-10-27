"""Central tool capability registry: one place where an agent discovers what it can do in this environment.

Sources (merged into one versioned index):
  builtin    the application's research/sandbox MCP tools, wrapped as kind=native (no behavior change to /mcp)
  manifests  <project data>/tools/<id>/<version>/tool.json (python | cli | mcp | container); an `active.json` pointer
             selects the active version per id (promotion/rollback, backend.tools.proposals). Manifests can never be
             kind=native: only application code defines native tools.
  mcp        tools discovered from configured external MCP servers (<project data>/tools/mcp_servers.json), snapshotted
             by an explicit discover call so listing never performs network I/O.

Discovery returns compact summaries; full input/output schemas are loaded only by describe() (lazy specification).
Search ranks by relevance to free text and filters by capability/kind/permission/availability. It never selects or
executes a tool: choosing is the agent's decision.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from pathlib import Path

from backend.tools.spec import ToolError, ToolSpec, parse_version, satisfies

_lock = threading.Lock()
_probe_cache: dict = {}
APP_ONLY_EXECUTION = ("home", "python", "callable", "mcp_tool", "stdio", "auth", "guard")  # only application code sets these
PROBE_TTL = 10.0
WORD = re.compile(r"[a-z0-9]+")


def tools_root() -> Path:
    from backend.core.config import data_dir
    return data_dir() / "tools"


# ------------------------------------------------------------------ builtin native tools
def _builtin_permissions(name: str, group: str) -> list:
    if name == "sandbox_run_code":
        return ["compute", "process", "workspace_write"]
    if name == "sandbox_manage_files":
        return ["workspace_write"]
    if name in ("web_search", "web_fetch"):
        return ["network", "read"]
    return ["workspace_write"] if group == "write" else ["read"]


def builtin_specs() -> list[ToolSpec]:
    from backend.providers.mcp_server import TOOLS as SANDBOX
    from backend.providers.mcp_tools import TOOLS as RESEARCH
    out = []
    for t in RESEARCH:
        caps = ["research", t["group"], *t["name"].split("_")[1:3]]
        if t["name"].startswith("web_"):
            caps = ["web", "literature", "network"]
        out.append(ToolSpec(id=t["name"], version="1.0.0", kind="native", description=t["description"],
                            capabilities=caps, input_schema=t["inputSchema"], mutates=t["group"] == "write",
                            permissions=_builtin_permissions(t["name"], t["group"]), source="builtin",
                            execution={"mcp_tool": t["name"]}))
    for t in SANDBOX:
        mutates = t["name"] != "sandbox_get_metrics"
        out.append(ToolSpec(id=t["name"], version="1.0.0", kind="native", description=t["description"],
                            capabilities=["sandbox", "compute", "experiment", "code"], input_schema=t["inputSchema"],
                            mutates=mutates, idempotent=not mutates, permissions=_builtin_permissions(t["name"], ""),
                            budget={"timeout_s": 3700}, source="builtin", execution={"mcp_tool": t["name"]}))
    return out


# ------------------------------------------------------------------ manifests
def load_manifest(path: Path, source: str = "manifest") -> ToolSpec:
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as e:
        raise ToolError("invalid_spec", f"Unreadable tool manifest {path.name}") from e
    if not isinstance(raw, dict):
        raise ToolError("invalid_spec", "Tool manifest must be a JSON object")
    if raw.get("kind") == "native":
        raise ToolError("invalid_spec", "Manifests cannot declare native tools")
    execution = {k: v for k, v in dict(raw.get("execution") or {}).items() if k not in APP_ONLY_EXECUTION}
    if raw.get("kind") == "python":
        execution["home"] = str(path.parent.resolve())  # always derived, never trusted from the manifest
    raw = {**raw, "execution": execution, "source": source}
    try:
        return ToolSpec.model_validate(raw)
    except ValueError as e:
        raise ToolError("invalid_spec", f"Invalid tool manifest {path.parent.name}: {str(e)[:600]}") from e


def active_version(tool_dir: Path) -> str:
    try:
        return json.loads((tool_dir / "active.json").read_text("utf-8")).get("version", "")
    except (OSError, ValueError, AttributeError):
        return ""


def _manifest_specs() -> tuple[list[ToolSpec], dict, list]:
    specs, active, problems = [], {}, []
    root = tools_root()
    if not root.is_dir():
        return specs, active, problems
    for tool_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        for vdir in sorted(p for p in tool_dir.iterdir() if p.is_dir()):
            manifest = vdir / "tool.json"
            if not manifest.is_file():
                continue
            try:
                spec = load_manifest(manifest)
                if spec.id != tool_dir.name or spec.version != vdir.name:
                    raise ToolError("invalid_spec", f"{manifest.parent} must match its id/version directories")
                specs.append(spec)
            except ToolError as e:
                problems.append({"path": str(manifest.relative_to(root)), "error": e.message})
        if v := active_version(tool_dir):
            active[tool_dir.name] = v
    return specs, active, problems


def _mcp_specs() -> list[ToolSpec]:
    out = []
    folder = tools_root() / "_mcp"
    if not folder.is_dir():
        return out
    for snap in sorted(folder.glob("*.json")):
        try:
            data = json.loads(snap.read_text("utf-8"))
            for t in data.get("tools", []):
                ex = {k: v for k, v in (t.get("execution") or {}).items() if k not in APP_ONLY_EXECUTION}
                if t.get("kind") == "mcp":  # snapshots may only describe remote MCP tools
                    out.append(ToolSpec.model_validate({**t, "execution": ex}))
        except (OSError, ValueError, AttributeError):
            continue
    return out


# ------------------------------------------------------------------ index
class Registry:
    """Versioned index over all sources. Rebuilt on demand (cheap) so newly added/promoted tools appear without a
    restart: an agent can discover a tool that did not exist when its task started."""

    def __init__(self, extra_sources: list | None = None):
        self.extra_sources = list(extra_sources or [])

    def _all(self) -> tuple[dict, dict, list]:
        specs, active, problems = _manifest_specs()
        builtin = builtin_specs()
        reserved = {s.id for s in builtin}
        by_id: dict[str, dict[str, ToolSpec]] = {}
        for s in builtin:
            by_id.setdefault(s.id, {})[s.version] = s
        others = specs + _mcp_specs()
        try:  # optional isolated Google Colab / Drive MCP tools (application-defined execution, off by default)
            from backend.tools import google_mcp
            others += google_mcp.specs()
        except Exception as e:  # a broken optional integration never breaks discovery
            problems.append({"path": "google_mcp", "error": f"unavailable: {type(e).__name__}"})
        for source in self.extra_sources:
            others += source()
        for s in others:
            if s.id in reserved or s.version in by_id.get(s.id, {}):
                problems.append({"path": s.ref, "error": "duplicate or reserved tool id/version ignored"})
                continue
            by_id.setdefault(s.id, {})[s.version] = s
        return by_id, active, problems

    def versions(self, tool_id: str) -> list[str]:
        by_id, _, _ = self._all()
        return sorted(by_id.get(tool_id, {}), key=parse_version)

    def resolve(self, tool_id: str, constraint: str = "") -> ToolSpec:
        from backend.core.config import APP_VERSION
        by_id, active, _ = self._all()
        versions = by_id.get(tool_id)
        if not versions:
            near = [s["id"] for s in self.search(tool_id.replace(".", " ").replace("_", " "), limit=3)]
            raise ToolError("not_found", f"Unknown tool {tool_id!r}", hint=f"Search the registry; similar: {near}")
        if constraint:
            ok = [v for v in versions if satisfies(v, constraint)]
            if not ok:
                raise ToolError("incompatible_version", f"No {tool_id} version satisfies {constraint!r}",
                                hint=f"Available versions: {sorted(versions, key=parse_version)}")
            spec = versions[max(ok, key=parse_version)]
        else:
            pinned = active.get(tool_id)
            spec = versions[pinned] if pinned in versions else versions[max(versions, key=parse_version)]
        if spec.requires_app and not satisfies(APP_VERSION, spec.requires_app):
            raise ToolError("incompatible_version", f"{spec.ref} requires application {spec.requires_app}, running {APP_VERSION}")
        return spec

    def probe(self, spec: ToolSpec) -> dict:
        from backend.tools.adapters import ADAPTERS
        key = (spec.ref, spec.digest())
        with _lock:
            hit = _probe_cache.get(key)
            if hit and time.monotonic() - hit[0] < PROBE_TTL:
                return hit[1]
        try:
            state = ADAPTERS[spec.kind].probe(spec)
        except Exception as e:  # a broken probe reports unavailability, never breaks discovery
            state = {"available": False, "reason": f"probe failed: {type(e).__name__}"}
        with _lock:
            _probe_cache[key] = (time.monotonic(), state)
        return state

    def listing(self, *, kind: str = "", capability: str = "", include_unavailable: bool = True) -> dict:
        by_id, active, problems = self._all()
        tools = []
        for tool_id in sorted(by_id):
            try:
                spec = self.resolve(tool_id)
            except ToolError:
                continue
            if (kind and spec.kind != kind) or (capability and capability.lower() not in spec.capabilities):
                continue
            state = self.probe(spec)
            if not include_unavailable and not state["available"]:
                continue
            entry = spec.summary(state["available"])
            entry["versions"] = sorted(by_id[tool_id], key=parse_version)
            if not state["available"]:
                entry["unavailable_reason"] = state["reason"]
            tools.append(entry)
        return {"tools": tools, "count": len(tools), "invalid_manifests": problems}

    def describe(self, tool_id: str, constraint: str = "") -> dict:
        spec = self.resolve(tool_id, constraint)
        state = self.probe(spec)
        out = spec.model_dump(exclude={"execution"})
        out.update(available=state["available"], unavailable_reason=state["reason"], digest=spec.digest(),
                   versions=self.versions(tool_id),
                   execution={k: v for k, v in spec.execution.items() if k not in ("home", "python")})
        return out

    def search(self, query: str, *, capability: str = "", kind: str = "", permissions: list | None = None,
               available_only: bool = False, limit: int = 10) -> list:
        """Rank tools by lexical relevance (BM25-style over id/title/description/capabilities)."""
        by_id, _, _ = self._all()
        docs = []
        for tool_id in by_id:
            try:
                spec = self.resolve(tool_id)
            except ToolError:
                continue
            if (capability and capability.lower() not in spec.capabilities) or (kind and spec.kind != kind):
                continue
            if permissions is not None and not set(spec.permissions) <= set(permissions):
                continue
            text = " ".join([spec.id.replace("_", " ").replace(".", " "), spec.title, spec.description,
                             " ".join(spec.capabilities) * 2]).lower()
            docs.append((spec, WORD.findall(text)))
        terms = set(WORD.findall((query or "").lower()))
        n = len(docs) or 1
        avg = sum(len(d) for _, d in docs) / n if docs else 1
        df = {t: sum(1 for _, d in docs if t in d) for t in terms}
        ranked = []
        for spec, words in docs:
            score = 0.0
            for t in terms:
                tf = words.count(t)
                if tf:
                    idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(words) / avg))
            if score > 0 or not terms:
                ranked.append((score, spec))
        ranked.sort(key=lambda x: (-x[0], x[1].id))
        out = []
        for score, spec in ranked:
            state = self.probe(spec)
            if available_only and not state["available"]:
                continue
            out.append({**spec.summary(state["available"]), "score": round(score, 4)})
            if len(out) >= limit:
                break
        return out


REGISTRY = Registry()


# ------------------------------------------------------------------ external MCP discovery
def _servers_file() -> Path:
    return tools_root() / "mcp_servers.json"


def mcp_servers() -> list:
    try:
        data = json.loads(_servers_file().read_text("utf-8"))
        return [s for s in data.get("servers", []) if isinstance(s, dict)]
    except (OSError, ValueError, AttributeError):
        return []


def add_mcp_server(name: str, url: str) -> dict:
    from backend.providers.mcp_agent import endpoint
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", name or ""):
        raise ToolError("invalid_input", "Server name must be lowercase letters, digits or underscore")
    try:
        endpoint(url)
    except ValueError as e:
        raise ToolError("invalid_input", str(e)) from e
    servers = [s for s in mcp_servers() if s.get("name") != name] + [{"name": name, "url": url}]
    _servers_file().parent.mkdir(parents=True, exist_ok=True)
    _servers_file().write_text(json.dumps({"servers": servers}, indent=1), "utf-8")
    return {"name": name, "url": url}


def discover_mcp(name: str, timeout: float = 20) -> dict:
    """Explicitly list an external MCP server's tools and snapshot them as registry entries (mcp.<server>.<tool>)."""
    from backend.tools.adapters import McpSession
    server = next((s for s in mcp_servers() if s.get("name") == name), None)
    if not server:
        raise ToolError("not_found", f"No MCP server named {name!r} is configured")
    with McpSession(server["url"], timeout) as session:
        remote = session.list_tools()
    specs, skipped = [], []
    for t in remote:
        tool = re.sub(r"[^a-z0-9_]", "_", str(t.get("name", "")).lower())[:60]
        try:
            specs.append(ToolSpec(id=f"mcp.{name}.{tool}", version="1.0.0", kind="mcp", source=f"mcp:{name}",
                                  description=str(t.get("description") or t.get("name"))[:4000],
                                  title=str(t.get("title") or t.get("name"))[:200], capabilities=["mcp", name],
                                  input_schema=t.get("inputSchema") or {"type": "object"},
                                  output_schema=t.get("outputSchema") or {}, permissions=["network"],
                                  mutates=not ((t.get("annotations") or {}).get("readOnlyHint", False)),
                                  idempotent=bool((t.get("annotations") or {}).get("idempotentHint", False)),
                                  execution={"url": server["url"], "tool": t.get("name")}).model_dump())
        except ValueError as e:
            skipped.append({"tool": t.get("name"), "error": str(e)[:300]})
    folder = tools_root() / "_mcp"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps({"server": name, "discovered_at": time.time(), "tools": specs},
                                                    indent=1), "utf-8")
    return {"server": name, "imported": [s["id"] for s in specs], "skipped": skipped}
