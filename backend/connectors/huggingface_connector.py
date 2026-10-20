"""Hugging Face Hub datasets (public API, no key): https://huggingface.co/api/datasets?search=…"""
from __future__ import annotations

import httpx

from .base import BaseConnector, ConnectorError

API = "https://huggingface.co/api/datasets"


class HuggingFaceConnector(BaseConnector):
    name = "huggingface"
    label = "Hugging Face datasets"
    description = "Search public datasets on the Hugging Face Hub (metadata only; download with `datasets.load_dataset(id)`)."

    def fetch_data(self, query: str, limit: int = 10) -> dict:
        try:
            r = httpx.get(API, params={"search": query, "limit": limit, "full": "false"}, timeout=20,
                          headers={"User-Agent": "PhD-Research-Lab"})
        except httpx.HTTPError as e:
            raise ConnectorError(f"Hugging Face not reachable: {e}")
        if r.status_code != 200:
            raise ConnectorError(f"Hugging Face API error {r.status_code}")
        items = []
        for d in r.json()[:limit]:
            did = d.get("id") or ""
            tags = [t for t in d.get("tags") or [] if not t.startswith(("region:", "format:"))][:8]
            items.append({"id": did, "title": did, "url": f"https://huggingface.co/datasets/{did}", "downloads": d.get("downloads"),
                          "likes": d.get("likes"), "tags": tags, "updated": d.get("lastModified", ""),
                          "summary": f"{d.get('downloads') or 0} downloads · {', '.join(tags[:4])}",
                          "load": f'datasets.load_dataset("{did}")'})
        return {"source": self.name, "query": query, "items": items}
