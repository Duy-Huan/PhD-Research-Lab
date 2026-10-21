"""Bounded, persisted deterministic jobs. The existing FastAPI lifespan owns one I/O worker."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.core.config import data_dir, list_projects, project_scope
from backend.knowledge import corpus, research_store as S, sources


def list_jobs(tid: str = "") -> list:
    with S.db() as c:
        if tid:
            S.topic(c, tid)
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in c.execute(
            "SELECT * FROM jobs WHERE (?='' OR topic_id=?) ORDER BY created DESC LIMIT 100", (tid, tid))]


def schedule_status(profile: dict) -> dict:
    with S.db() as c:
        previous = c.execute("SELECT created,status FROM jobs WHERE topic_id=? AND kind='discover' ORDER BY created DESC LIMIT 1", (profile["id"],)).fetchone()
    enabled = profile["enabled"] and not profile["archived"] and profile["cadence"] in ("daily", "weekly")
    next_run = None
    if enabled:
        next_run = ((datetime.fromisoformat(previous["created"]) + timedelta(days=1 if profile["cadence"] == "daily" else 7)).isoformat()
                    if previous else S.now())
    return {"enabled": enabled, "timezone": "UTC", "last_run": previous["created"] if previous else None,
            "last_status": previous["status"] if previous else None, "next_run": next_run}


def enqueue(tid: str, kind: str, payload: dict | None = None) -> dict:
    payload = dict(payload or {})
    if kind not in ("discover", "download", "sync", "index"):
        raise ValueError("Unsupported deterministic job")
    profile = S.get_topic(tid)
    if profile["archived"]:
        raise ValueError("Topic is archived")
    ids = payload.get("paper_ids") or []
    if not isinstance(ids, list) or len(ids) > 100:
        raise ValueError("Select at most 100 paper IDs")
    if kind in ("download", "index"):
        if not ids:
            raise ValueError("Select papers first")
        for pid in ids:
            corpus.paper(tid, pid)
    if kind == "sync":
        from backend.research_engines.workspaces import get
        w = get(str(payload.get("workspace_id") or ""))
        if w["topic_id"] != tid:
            raise ValueError("Workspace is outside this topic")
    with S.db() as c:
        existing = c.execute("SELECT id FROM jobs WHERE topic_id=? AND kind=? AND status IN ('queued','running','cancelling')", (tid, kind)).fetchone()
        if existing:
            raise ValueError("A job of this kind is already active for this topic")
        jid = S.uid()
        at = S.now()
        c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)", (jid, tid, kind, "queued", at, at, S.dumps(payload)))
        S.event(c, tid, "job.queued", {"job_id": jid, "kind": kind})
    return next(j for j in list_jobs(tid) if j["id"] == jid)


def _update(jid: str, status: str, payload: dict):
    with S.db() as c:
        c.execute("UPDATE jobs SET status=?,updated=?,payload=? WHERE id=?", (status, S.now(), S.dumps(payload), jid))
    from backend.core.bus import publish
    publish("research.job", job_id=jid, status=status, project_dir=str(data_dir()))


def cancel(jid: str) -> dict:
    with S.db() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            raise ValueError("Job not found in this project")
        status = "cancelled" if r["status"] == "queued" else "cancelling" if r["status"] == "running" else r["status"]
        c.execute("UPDATE jobs SET status=?,updated=? WHERE id=?", (status, S.now(), jid))
    return {"id": jid, "status": status}


def retry(jid: str) -> dict:
    old = next((j for j in list_jobs() if j["id"] == jid), None)
    if not old or old["status"] not in ("failed", "interrupted", "partial", "cancelled"):
        raise ValueError("Only failed, interrupted, partial or cancelled jobs can be retried")
    return enqueue(old["topic_id"], old["kind"], {**old["payload"], "retry_of": jid})


def cancelled(jid: str) -> bool:
    with S.db() as c:
        r = c.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
        return not r or r[0] in ("cancelling", "cancelled", "interrupted")


def _storage(tid: str) -> int:
    with S.db() as c:
        return c.execute("SELECT coalesce(sum(bytes),0) FROM documents WHERE sha256 IN (SELECT vd.sha256 FROM version_documents vd "
                         "JOIN versions v ON vd.version_id=v.id JOIN paper_topics pt ON pt.paper_id=v.paper_id WHERE pt.topic_id=?)", (tid,)).fetchone()[0]


async def download_papers(jid: str, tid: str, ids: list[str]) -> dict:
    from backend.knowledge.download import pdf_bytes_limited
    profile = S.get_topic(tid)
    errors, downloaded, indexed = [], 0, 0
    for pid in list(dict.fromkeys(ids))[:profile["pdf_limit"]]:
        if cancelled(jid):
            break
        p = corpus.paper(tid, pid)
        # Keep a source version tied to the downloaded OA location; don't attach preprint bytes to publisher metadata.
        try:
            locations = await sources.resolve_oa(p)
            if not locations:
                raise ValueError("No verified legal OA PDF found; metadata retained")
            last_error = "No PDF available"
            for location in locations[:4]:
                if cancelled(jid) or downloaded >= profile["pdf_limit"]:
                    break
                matching = next((v for v in p["versions"] if any(x.get("url") == location["url"] for x in v["oa_locations"])), None)
                if not matching:
                    vid = corpus.add_oa_version(tid, pid, location)
                    p = corpus.paper(tid, pid)
                    matching = next(v for v in p["versions"] if v["id"] == vid)
                if matching["document"]:
                    if matching["document"]["status"] != "indexed":
                        await asyncio.to_thread(corpus.index_document, tid, pid, matching["id"])
                        indexed += 1
                    last_error = ""
                    break
                available = profile["storage_mb"] * 1024 * 1024 - _storage(tid)
                cap = min(profile["max_pdf_mb"] * 1024 * 1024, available)
                if cap <= 0:
                    raise ValueError("Topic storage quota reached")
                try:
                    raw = await pdf_bytes_limited(location["url"], cap)
                    if cancelled(jid):
                        break
                    await asyncio.to_thread(corpus.store_document, tid, pid, matching["id"], raw,
                                            {"url": location["url"], "license": location.get("license", "unknown"),
                                             "version": location.get("version", "unknown"), "downloaded_at": S.now()})
                    downloaded += 1
                    # Parsing can fail independently; the verified file/metadata remains retryable.
                    try:
                        await asyncio.to_thread(corpus.index_document, tid, pid, matching["id"])
                        indexed += 1
                        last_error = ""
                    except Exception as exc:
                        last_error = "PDF preserved; parse failed: " + str(exc)[:400]
                    break
                except Exception as exc:
                    last_error = str(exc)[:500]
                await asyncio.sleep(1)  # sequential low-volume fetch; no hammering a blocked publisher
            if last_error:
                errors.append({"paper_id": pid, "error": last_error})
        except Exception as exc:
            errors.append({"paper_id": pid, "error": str(exc)[:500]})
    return {"downloaded": downloaded, "indexed": indexed, "errors": errors,
            "deferred_by_quota": max(0, len(ids) - profile["pdf_limit"])}


async def execute(job: dict):
    jid, tid = job["id"], job["topic_id"]
    payload = dict(job["payload"])
    with S.db() as c:
        claim = c.execute("UPDATE jobs SET status='running',updated=? WHERE id=? AND status='queued'", (S.now(), jid))
        if claim.rowcount != 1:
            return
    try:
        profile = S.get_topic(tid)
        if payload.get("metadata_limit"):
            profile["metadata_limit"] = min(profile["metadata_limit"],max(1,int(payload["metadata_limit"])))
        if profile["archived"] or (payload.get("scheduled") and job["kind"] == "discover" and not profile["enabled"]):
            _update(jid, "cancelled", {**payload, "reason": "Topic archived or scheduled discovery disabled"})
            return
        if payload.get("dry_run"):
            result = {"dry_run": True, "sources": profile["sources"], "metadata_limit": profile["metadata_limit"],
                      "pdf_limit": profile["pdf_limit"], "network_calls": 0}
        elif job["kind"] == "discover":
            found = await sources.discover(profile)
            if cancelled(jid):
                _update(jid, "cancelled", payload)
                return
            # Enforce the per-run unique metadata quota across all providers.
            unique, seen = [], set()
            for r in found["records"]:
                identity = corpus._aliases(corpus.normalize(r))[0]
                if identity not in seen:
                    seen.add(identity)
                    unique.append(r)
                if len(unique) >= profile["metadata_limit"]:
                    break
            result = corpus.ingest(tid, unique)
            result.update(errors=found["errors"], query=found["query"], discovered=len(unique))
            if profile["auto_download"] and result["added"]:
                result["downloads"] = await download_papers(jid, tid, result["added"])
        elif job["kind"] == "download":
            result = await download_papers(jid, tid, payload["paper_ids"])
        elif job["kind"] == "index":
            result = {"indexed": 0, "errors": []}
            for pid in payload["paper_ids"]:
                if cancelled(jid):
                    break
                for v in corpus.paper(tid, pid)["versions"]:
                    if v["document"]:
                        try:
                            await asyncio.to_thread(corpus.index_document, tid, pid, v["id"])
                            result["indexed"] += 1
                        except Exception as exc:
                            result["errors"].append({"paper_id": pid, "error": str(exc)[:500]})
        else:
            from backend.research_engines.workspaces import sync
            result = await asyncio.to_thread(sync, payload["workspace_id"], lambda: cancelled(jid))
        status = "cancelled" if cancelled(jid) else "partial" if result.get("errors") or result.get("conflicts") or result.get("status") == "partial" else "completed"
        _update(jid, status, {**payload, "result": result})
    except asyncio.CancelledError:
        _update(jid, "interrupted", {**payload, "error": "Application stopped; explicit retry is available"})
        raise
    except Exception as exc:
        _update(jid, "cancelled" if cancelled(jid) else "failed", {**payload, "error": str(exc)[:700]})


def schedule_due():
    now = datetime.now(timezone.utc)
    jobs = list_jobs()
    for t in S.topics():
        if not t["enabled"] or t["archived"] or t["cadence"] not in ("daily", "weekly"):
            continue
        previous = next((j for j in jobs if j["topic_id"] == t["id"] and j["kind"] == "discover"), None)
        days = 1 if t["cadence"] == "daily" else 7
        if not previous or now - datetime.fromisoformat(previous["created"]) >= timedelta(days=days):
            try:
                enqueue(t["id"], "discover", {"scheduled": True})
            except ValueError:
                pass
    from backend.research_engines.workspaces import list_workspaces
    for t in S.topics():
        if t["archived"]:
            continue
        for w in list_workspaces(t["id"]):
            interval = w.get("sync_interval_minutes", 0)
            previous = next((j for j in jobs if j["kind"] == "sync" and j["payload"].get("workspace_id") == w["id"]), None)
            if interval and (not previous or now - datetime.fromisoformat(previous["created"]) >= timedelta(minutes=interval)):
                try:
                    enqueue(t["id"], "sync", {"workspace_id": w["id"], "scheduled": True})
                except ValueError:  # topic already has a pending sync
                    pass


async def worker(stop: asyncio.Event):
    recovered = set()
    while not stop.is_set():
        for project in list_projects():
            path = Path(project["data_dir"])
            if not (path / "workspace/research/research.sqlite3").is_file():
                continue
            with project_scope(path):
                try:
                    if str(path) not in recovered:
                        with S.db() as c:
                            c.execute("UPDATE jobs SET status='interrupted',updated=? WHERE status IN ('running','cancelling')", (S.now(),))
                        recovered.add(str(path))
                        from backend.agent import missions
                        await asyncio.to_thread(missions.recover)
                        from backend.execution import protocols
                        await asyncio.to_thread(protocols.recover)
                    await asyncio.to_thread(schedule_due)
                    with S.db() as c:
                        row = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
                        queued = {**dict(row), "payload": json.loads(row["payload"])} if row else None
                    if queued:
                        await execute(queued)
                    from backend.agent import missions
                    await missions.tick()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Deterministic research worker failed for project")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
