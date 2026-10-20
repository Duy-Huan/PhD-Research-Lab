"""DataConnectorRegistry: discovers every BaseConnector subclass in backend/connectors/*.py (plugins)."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from pathlib import Path

from .base import BaseConnector, ConnectorError

SKIP = {"base", "registry", "__init__"}


class DataConnectorRegistry:
    def __init__(self):
        self.connectors: dict = {}
        self.errors: dict = {}

    def scan(self) -> "DataConnectorRegistry":
        pkg_dir = Path(__file__).parent
        for mod in pkgutil.iter_modules([str(pkg_dir)]):
            if mod.name in SKIP or not re.fullmatch(r"[a-z0-9_]+", mod.name):
                continue
            try:
                m = importlib.import_module(f"{__package__}.{mod.name}")
            except Exception as e:  # a broken plugin must not break the others
                self.errors[mod.name] = f"{type(e).__name__}: {e}"
                continue
            for _, cls in inspect.getmembers(m, inspect.isclass):
                if issubclass(cls, BaseConnector) and cls is not BaseConnector and cls.__module__ == m.__name__:
                    self.connectors[cls.name] = cls()
        return self

    def list(self) -> list:
        out = []
        for name, c in sorted(self.connectors.items()):
            try:
                st = c.status()
            except Exception as e:
                st = {"state": "error", "detail": str(e)}
            out.append({"name": name, "label": c.label, "description": c.description, **st})
        return out + [{"name": n, "label": n, "state": "error", "detail": e} for n, e in self.errors.items()]

    def fetch(self, name: str, query: str, limit: int = 10) -> dict:
        c = self.connectors.get(name)
        if not c:
            raise ConnectorError(f"Unknown connector '{name}'")
        if not (query or "").strip():
            raise ConnectorError("Empty query")
        return c.fetch_data(query.strip()[:200], max(1, min(50, int(limit))))


_REG: DataConnectorRegistry | None = None


def registry() -> DataConnectorRegistry:
    global _REG
    if _REG is None:
        _REG = DataConnectorRegistry().scan()
    return _REG


CHAT_CMD = re.compile(r"^\s*/(hf|huggingface|kaggle|dataset)\s+(.+)", re.I | re.S)


def chat_block(message: str) -> str:
    """Data Chat command `/hf <query>`, `/kaggle <query>` or `/dataset <query>` → a context block with real results."""
    m = CHAT_CMD.match(message or "")
    if not m:
        return ""
    which = {"hf": ["huggingface"], "huggingface": ["huggingface"], "kaggle": ["kaggle"]}.get(m.group(1).lower(),
                                                                                             list(registry().connectors))
    q = m.group(2).strip().splitlines()[0][:200]
    parts = []
    for name in which:
        try:
            r = registry().fetch(name, q, 8)
            rows = "\n".join(f"- {it.get('title') or it['id']} — {it.get('url', '')}" + (f" · {it['summary']}" if it.get("summary") else "")
                             for it in r["items"]) or "- (no results)"
            parts.append(f"## {name} results for “{q}”\n{rows}")
        except Exception as e:
            parts.append(f"## {name}: search failed ({e})")
    return ("\n\n# DATASET SEARCH (real results from the data connectors — cite only these, do not invent datasets)\n"
            + "\n\n".join(parts))
