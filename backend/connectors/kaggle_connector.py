"""Kaggle datasets (official public API v1). Credentials are read from Kaggle's own standard locations —
KAGGLE_USERNAME / KAGGLE_KEY environment variables or ~/.kaggle/kaggle.json — and are never stored by this app."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from .base import BaseConnector, ConnectorError

API = "https://www.kaggle.com/api/v1/datasets/list"


def _creds() -> tuple[str, str] | None:
    u, k = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    if u and k:
        return u, k
    f = Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle") / "kaggle.json"
    try:
        d = json.loads(f.read_text("utf-8"))
        return (d["username"], d["key"]) if d.get("username") and d.get("key") else None
    except (OSError, ValueError, KeyError):
        return None


class KaggleConnector(BaseConnector):
    name = "kaggle"
    label = "Kaggle datasets"
    description = "Search Kaggle datasets (needs ~/.kaggle/kaggle.json from kaggle.com → Settings → API → Create New Token)."
    needs_credentials = True

    def status(self) -> dict:
        return {"state": "available", "detail": ""} if _creds() else \
            {"state": "unconfigured", "detail": "No Kaggle API token (~/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY)."}

    def fetch_data(self, query: str, limit: int = 10) -> dict:
        c = _creds()
        if not c:
            raise ConnectorError(self.status()["detail"])
        try:
            r = httpx.get(API, params={"search": query, "page": 1}, auth=c, timeout=20)
        except httpx.HTTPError as e:
            raise ConnectorError(f"Kaggle not reachable: {e}")
        if r.status_code == 401:
            raise ConnectorError("Kaggle rejected the API token (401)")
        if r.status_code != 200:
            raise ConnectorError(f"Kaggle API error {r.status_code}")
        items = []
        for d in (r.json() or [])[:limit]:
            ref = d.get("ref") or ""
            items.append({"id": ref, "title": d.get("title") or ref, "url": f"https://www.kaggle.com/datasets/{ref}",
                          "size": d.get("totalBytes"), "license": d.get("licenseName", ""), "updated": d.get("lastUpdated", ""),
                          "summary": (d.get("subtitle") or "")[:160], "load": f"kaggle datasets download -d {ref}"})
        return {"source": self.name, "query": query, "items": items}
