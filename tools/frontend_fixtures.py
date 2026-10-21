"""Record the responses the frontend tests replay: the REAL backend on a throw-away data folder, seeded like the demo
server (fake language model, no key, no GPU). Re-run after an API change:
    .venv/Scripts/python tools/frontend_fixtures.py   → tests/frontend/fixtures.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]
import demo_server  # noqa: E402  (isolated data dir + seeded project)

from fastapi.testclient import TestClient  # noqa: E402

OUT = ROOT / "tests" / "frontend" / "fixtures.json"
MANUSCRIPT = ("# Lightweight ViT on the edge\n\n## Abstract\n" + "We prune tokens adaptively and distil a small vision transformer for edge devices. " * 12
              + "\n\n## Method\nAdaptive pruning with distillation.\n").encode()


def main() -> None:
    demo_server.llm.stream_agent = demo_server.fake_stream
    demo_server.RP.app_complete = demo_server.fake_complete
    demo_server.seed()
    from backend.app import app
    out: dict = {}
    with TestClient(app) as c:
        def get(url: str, key: str | None = None) -> dict:
            r = c.get(url)
            out[key or "GET " + url] = {"status": r.status_code, "body": r.json()}
            return r.json()
        rv = c.post("/api/review/upload", files={"file": ("vit-edge.md", MANUSCRIPT, "text/markdown")}).json()
        for u in ("/api/config", "/api/projects", "/api/outline", "/api/skills", "/api/models", "/api/models/local", "/api/dashboard",
                  "/api/dashboard?advanced=1", "/api/acceptance", "/api/research", "/api/library", "/api/code", "/api/jobs",
                  "/api/memory/candidates", "/api/pins", "/api/review"):
            get(u)
        get("/api/providers")
        get(f"/api/review/{rv['meta']['id']}", "GET /api/review/:id")
        sessions = get("/api/chat/sessions")["sessions"]
        s = get(f"/api/chat/sessions/{sessions[0]['id']}", "GET /api/chat/sessions/:id")
        get(f"/api/chat/sessions/{s['id']}/effective", "GET /api/chat/sessions/:id/effective")
        rids = [m["run_id"] for m in s["messages"] if m.get("run_id")]
        rids += [a["result"]["run"] for a in s["approvals"] if (a.get("result") or {}).get("run")]
        for i, rid in enumerate(dict.fromkeys(rids)):
            get(f"/api/runs/{rid}", f"GET /api/runs/{rid}")
            get(f"/api/runs/{rid}/events", f"GET /api/runs/{rid}/events")
    out["meta"] = {"version": out["GET /api/config"]["body"]["version"], "session": s["id"], "runs": list(dict.fromkeys(rids)),
                   "review": rv["meta"]["id"]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"{len(out) - 1} responses -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
