"""Approved native compute handoff and integrity-checked, worker-reported results."""
from fastapi import APIRouter, Body, Request, HTTPException
from fastapi.responses import FileResponse
from backend.api.common import call
from backend.execution import remote_compute as RC

router = APIRouter()


@router.get("/api/compute/runs")
async def listing():
    return {"runs": await call(RC.list_runs), "targets": list(RC.TARGETS)}


@router.post("/api/compute/runs")
async def create(body: dict = Body(...)):
    return await call(RC.create, body)


@router.get("/api/compute/runs/{rid}")
async def get(rid: str):
    return await call(RC.get, rid)


@router.post("/api/compute/runs/{rid}/approve")
async def approve(rid: str):
    return await call(RC.approve, rid)


@router.get("/api/compute/runs/{rid}/bundle")
async def bundle(rid: str):
    return FileResponse(await call(RC.bundle, rid), media_type="application/zip", filename=rid + ".zip")


@router.post("/api/compute/runs/{rid}/sync")
async def sync(rid: str, body: dict = Body(default={})):
    from backend.execution.tools import IntegrationError
    from fastapi import HTTPException
    from backend.core.telemetry import redact
    try:
        return await call(RC.sync, rid, str(body.get("task_id") or ""), bool(body.get("collect")))
    except IntegrationError as e:
        raise HTTPException(410, redact(str(e))) from e


@router.post('/api/compute/runs/{rid}/results')
async def import_results(rid: str, request: Request):
    """Raw ZIP upload; stream with a hard bound, no multipart dependency or ZIP execution."""
    import tempfile
    import zipfile
    from pathlib import Path
    await call(RC.bundle, rid)
    limit = 256*1024*1024
    if request.headers.get('content-type','').split(';')[0].strip() not in ('application/zip','application/octet-stream'):
        raise HTTPException(415, 'Upload results.zip as application/zip')
    with tempfile.NamedTemporaryFile(prefix='.results-', suffix='.zip', dir=RC.folder(rid), delete=False) as target:
        path = Path(target.name)
        try:
            total = 0
            async for chunk in request.stream():
                total += len(chunk)
                if total>limit:raise HTTPException(413, 'Results exceed 256 MiB')
                target.write(chunk)
            target.close()
            try:
                return await call(RC.import_results, rid, path)
            except (zipfile.BadZipFile, UnicodeError, KeyError, TypeError) as exc:
                raise HTTPException(422, 'Malformed native result bundle; no execution was certified') from exc
        finally:
            target.close()
            path.unlink(missing_ok=True)


@router.get('/api/compute/runs/{rid}/imports/{digest}/file')
async def imported_file(rid: str, digest: str, name: str):
    path = await call(RC.imported_file, rid, digest, name)
    return FileResponse(path, filename=path.name, media_type='application/octet-stream')
