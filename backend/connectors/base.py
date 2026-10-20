"""Base class of domain data connectors (v3.2, CLAUDE_DEVELOPMENT_PROMPT Task 2).

A connector is a .py file in backend/connectors/ that defines a subclass of BaseConnector; registry.py discovers it.
fetch_data() returns METADATA about datasets (ids, links, sizes, licences) — it never downloads large data silently.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ConnectorError(Exception):
    pass


class BaseConnector(ABC):
    name = "base"
    label = "Base connector"
    description = ""
    needs_credentials = False

    def status(self) -> dict:
        """{state: available|unconfigured, detail}"""
        return {"state": "available", "detail": ""}

    @abstractmethod
    def fetch_data(self, query: str, limit: int = 10) -> dict:
        """{"source": name, "query": query, "items": [{id, title, url, ...}]}"""
