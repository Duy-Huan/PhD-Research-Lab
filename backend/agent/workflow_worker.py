"""One process owns up to four independent Mission ticks; hardware leases remain authoritative."""
import asyncio
import logging
import time
from pathlib import Path

from backend.agent import missions
from backend.agent.autonomy import MAX_WORKFLOWS
from backend.core.config import list_projects, project_scope
from backend.knowledge import research_store as S

LOG = logging.getLogger(__name__)


async def worker(stop: asyncio.Event):
    active, recovered, served = {}, set(), {}
    try:
        while not stop.is_set():
            for key, task in list(active.items()):
                if task.done():
                    try:
                        task.result()
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        LOG.exception("Independent mission tick failed")
                    del active[key]
            candidates = []
            for project in list_projects():
                path = str(Path(project["data_dir"]).resolve())
                if not (Path(path) / "workspace/research/research.sqlite3").is_file():
                    continue
                with project_scope(path):
                    try:
                        if path not in recovered:
                            missions.recover()
                            recovered.add(path)
                        with S.db() as c:
                            for row in c.execute("SELECT id,created,coalesce(json_extract(payload,'$.spec.control.priority'),0) AS priority FROM missions WHERE status IN ('queued','running','scheduled') ORDER BY created"):
                                key = (path, row["id"])
                                if key not in active:
                                    candidates.append((-row["priority"], served.get(key, 0), row["created"], key))
                    except Exception:
                        LOG.exception("Cannot scan project for independent missions")
            # Round robin prevents waiting providers/schedules from starving later work.
            live = {item[-1] for item in candidates} | set(active)
            served = {key: value for key, value in served.items() if key in live}
            for _, _, _, key in sorted(candidates):
                if len(active) >= MAX_WORKFLOWS:
                    break
                path, mid = key
                with project_scope(path):
                    active[key] = asyncio.create_task(missions.tick(mid))
                served[key] = time.monotonic()
            waiting = asyncio.create_task(stop.wait())
            try:
                await asyncio.wait([waiting, *active.values()], timeout=.25, return_when=asyncio.FIRST_COMPLETED)
            finally:
                waiting.cancel()
                await asyncio.gather(waiting, return_exceptions=True)
    finally:
        for task in active.values():
            task.cancel()
        await asyncio.gather(*active.values(), return_exceptions=True)
