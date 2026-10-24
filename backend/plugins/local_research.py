"""Small optional adapters; dependencies are never installed by import or by a background job."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

from backend.knowledge import research_store as S


def capabilities() -> list:
    result = []
    for name, category in (("docling", "document_parser"), ("optuna", "hpo_engine"), ("pyzotero", "reference_manager")):
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = ""
        result.append({"id": name, "category": category, "version": version, "installed": bool(version),
                       "status": "installed_not_live_qualified" if version else "optional_dependency_missing",
                       "pricing": "local_free", "auto_install": False})
    result.append({"id": "zotero-json", "category": "reference_manager", "installed": True, "version": "1.0",
                   "status": "read_only_import_and_bibtex_export", "pricing": "local_free", "auto_install": False})
    return result


def import_zotero(tid: str, records: list[dict], source: str = "Zotero JSON export") -> dict:
    """Accept CSL JSON or Zotero JSON export; no credentials and no writes to Zotero."""
    from backend.knowledge.corpus import ingest
    if not isinstance(records, list) or not 1 <= len(records) <= 1000:
        raise ValueError("Import 1–1000 Zotero/CSL JSON items")
    normalized = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Zotero items must be JSON objects")
        r = record.get("data", record)
        if not isinstance(r, dict):
            raise ValueError("Zotero item data must be a JSON object")
        if r.get("itemType") in ("attachment", "note"):
            continue
        authors = r.get("author") or r.get("creators") or []
        if not isinstance(authors, list) or any(not isinstance(a, dict) for a in authors):
            raise ValueError("Zotero authors must be a list of creator objects")
        dates = (r.get("issued") or {}).get("date-parts") or [[]]
        year = dates[0][0] if dates[0] else next(iter(re.findall(r"\b(?:19|20)\d{2}\b", str(r.get("date", "")))), "")
        normalized.append({"title": r.get("title", ""), "doi": r.get("DOI", ""), "year": year,
                           "authors": [a.get("literal") or a.get("name") or " ".join(filter(None, [a.get("given", a.get("firstName")), a.get("family", a.get("lastName"))])) for a in authors],
                           "venue": r.get("container-title", r.get("publicationTitle", "")), "abstract": r.get("abstract", r.get("abstractNote", "")),
                           "url": r.get("URL", r.get("url", "")), "source": source})
    return ingest(tid, normalized)


async def sync_zotero(tid: str, *, allow_network: bool = False, start: int = 0, max_items: int = 100) -> dict:
    """Explicit bounded read from Zotero's documented local API. Never writes to Zotero.

    No arbitrary host, redirect, browser credential or Connector write API. Pagination
    continues explicitly; changes during a multi-page snapshot abort before import.
    """
    import httpx
    S.get_topic(tid)
    if not allow_network:
        raise ValueError("Authorize reading the local Zotero API explicitly")
    if not 0 <= start <= 1000000 or not 1 <= max_items <= 1000:
        raise ValueError("Use a bounded Zotero page: start 0–1000000, max_items 1–1000")
    records, version, cursor, exhausted = [], None, start, False
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
        while len(records) < max_items:
            count = min(100, max_items - len(records))
            async with client.stream("GET", "http://127.0.0.1:23119/api/users/0/items/top",
                                     params={"format": "json", "limit": count, "start": cursor, "sort": "dateAdded", "direction": "asc"},
                                     headers={"Zotero-API-Version": "3"}) as response:
                if response.status_code != 200:
                    raise ValueError(f"Local Zotero API unavailable (HTTP {response.status_code}); enable permitted local API access or import a JSON export")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 5 * 1024 * 1024:
                        raise ValueError("Zotero page exceeds 5 MB")
                current = response.headers.get("Last-Modified-Version")
            if records and (not current or current != version):
                raise ValueError("Zotero library changed during pagination; retry from the same start")
            version = current
            page = json.loads(chunks)
            if not isinstance(page, list) or any(not isinstance(r, dict) for r in page) or len(page) > count:
                raise ValueError("Unexpected Zotero item response")
            records.extend(page); cursor += len(page)
            if len(page) < count:
                exhausted = True
                break
    import asyncio
    result = await asyncio.to_thread(import_zotero, tid, records, "Zotero local API") if records else {"added": [], "duplicates": 0, "conflicts": [], "paper_ids": []}
    receipt = {"source": "Zotero local API", "read_only": True, "library_version": version,
               "start": start, "received": len(records), "next_start": None if exhausted else cursor,
               "at": S.now(), "result": result}
    with S.db() as c:
        S.event(c, tid, "zotero.synced", receipt)
    return receipt


def run_optuna(objective, *, name: str, trials: int = 10, seed: int = 42, timeout_s: int = 300,
               approved: bool = False) -> dict:
    """Call from an approved experiment in the existing executor. Never exposed as an agent write tool.

    This bounds trial admission, not arbitrary objective runtime. The existing subprocess/compute guard must
    enforce a hard time/resource limit. Resume preserves trials; sampler RNG continuity is not promised.
    """
    if not approved:
        raise ValueError("Optuna compute requires explicit experiment approval")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name) or not 1 <= trials <= 10 or not 1 <= timeout_s <= 3600:
        raise ValueError("Use a safe study name, 1–10 trials and a 1–3600s admission budget")
    try:
        import optuna
    except ImportError as exc:
        raise ValueError("Install optional optuna in the approved experiment environment") from exc
    folder = S.safe_child(S.store_dir(), "hpo")
    folder.mkdir(exist_ok=True)
    database = S.safe_child(folder, name + ".sqlite3")
    import inspect
    try:
        source = inspect.getsource(objective)
    except (OSError, TypeError):
        source = "unavailable"
    fingerprint = hashlib.sha256(source.encode()).hexdigest()
    study = optuna.create_study(study_name=name, storage="sqlite:///" + database.as_posix(), load_if_exists=True,
                                sampler=optuna.samplers.TPESampler(seed=seed))
    if study.user_attrs.get("objective_sha256", fingerprint) != fingerprint or study.user_attrs.get("seed", seed) != seed:
        raise ValueError("Resume requires the same objective fingerprint and seed")
    study.set_user_attr("objective_sha256", fingerprint)
    study.set_user_attr("seed", seed)
    before = len(study.trials)
    study.optimize(objective, n_trials=min(trials, max(0, 10-before)), timeout=timeout_s, n_jobs=1)
    complete = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    result = {"tool": "optuna", "version": optuna.__version__, "study": name, "seed": seed,
              "objective_sha256": fingerprint, "trials_before": before, "trials_total": len(study.trials),
              "best_params": study.best_params if complete else None, "best_value": study.best_value if complete else None,
              "storage": str(database), "scientific_review": "unverified", "rng_resume_continuity": False}
    from backend.agent import write_json
    write_json(S.safe_child(folder, name + ".manifest.json"), result)
    return result
