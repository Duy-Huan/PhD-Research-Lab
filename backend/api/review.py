"""Paper review session (its own view): upload a manuscript → reviewers R1–R3 → area chair → issue list → quick fixes the
researcher accepts or dismisses → apply to the LaTeX source → response letter. Every stage streams (SSE)."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response

from backend.api.common import call, sse_job
from backend.paper import review as RX
from backend.paper import review_prompts as RP

router = APIRouter()


@router.get("/api/review")
def review_list():
    return {"reviews": RX.list_reviews(), "active": RX.get_active()}


@router.post("/api/review/upload")
async def review_upload(file: UploadFile = File(...)):
    """A new review from a manuscript file (PDF / DOCX / TEX / MD / TXT)."""
    meta = await call(RX.create_review, file.filename or "paper.pdf", await file.read())
    return {"meta": meta, "state": RX.load_state(meta["id"])}


@router.get("/api/review/{rid}")
async def review_get(rid: str):
    return await call(RX.get_review, rid)


@router.delete("/api/review/{rid}")
async def review_delete(rid: str):
    await call(RX.delete_review, rid)
    return {"deleted": rid}


@router.put("/api/review/{rid}/settings")
async def review_settings(rid: str, body: dict = Body(...)):
    """Venue standard (conference / journal tier), number of reviewers, blind mode."""
    return {"meta": await call(RX.set_settings, rid, body)}


@router.post("/api/review/{rid}/source")
async def review_source(rid: str, file: UploadFile = File(...)):
    """Attach the LaTeX source so accepted fixes can be applied automatically."""
    return {"meta": await call(RX.add_source, rid, file.filename or "", await file.read())}


@router.get("/api/review/{rid}/text", response_class=PlainTextResponse)
async def review_text(rid: str):
    return await call(RX.paper_text, rid)


@router.get("/api/review/{rid}/original")
def review_original(rid: str):
    m = RX.load_meta(rid)
    return FileResponse(RX._dir(rid) / f"original{m.get('ext', '')}", filename=m.get("file"), content_disposition_type="inline")


def _paper(rid: str) -> str:
    t = RX.paper_text(rid)
    return t[:RX.PAPER_BUDGET] + ("\n…[manuscript truncated]" if len(t) > RX.PAPER_BUDGET else "")


@router.post("/api/review/{rid}/stage")
def review_stage(rid: str, body: dict = Body(...)):
    """Streaming stages: reviewer (idx 1–n) → meta (area chair / editor) → issues (structured list) → response letter."""
    from backend.providers.models import LLMError, extract_json
    stage = body.get("stage")
    meta = RX.load_meta(rid)
    v = meta.get("venue") or {}
    label = RP.venue_label(v)
    ps = RX.prescreen_text(meta.get("prescreen") or {}, meta.get("truncated", False))
    st = RX.load_state(rid)
    if stage == "reviewer":
        personas = RP.PERSONAS.get(meta.get("n_reviewers", 3), RP.PERSONAS[3])
        idx = int(body.get("idx", 1))
        if not 1 <= idx <= len(personas):
            raise HTTPException(400, "Reviewer index out of range")
        persona = personas[idx - 1]

        def fin(m):
            rec = {"id": persona[0], "persona": persona[1], "text": m["text"], "engine": m["engine"], "ts": RX._now(),
                   "venue": label, **RX.parse_review_header(m["text"])}

            def put(s):
                if body.get("fresh"):  # a full new round: drop the reports of the previous round
                    s["reviewers"] = {}
                for k in [k for k in s["reviewers"] if k not in {x[0] for x in personas}]:
                    s["reviewers"].pop(k)
                s["reviewers"][persona[0]] = rec
            RX.update_state(rid, put)
            return {"reviewer": rec}
        return sse_job("reviewer", RP.reviewer_system(v, persona), RP.reviewer_user(_paper(rid), ps, meta.get("title", "")),
                       fin, max_tokens=7000, temperature=0.3, start={"stage": stage, "id": persona[0], "persona": persona[1]})
    if not st["reviewers"]:
        raise HTTPException(400, "Run the reviewers first")
    if stage == "meta":
        def fin(m):
            rec = {"text": m["text"], "engine": m["engine"], "ts": RX._now(), "venue": label, **RX.parse_meta_header(m["text"])}
            RX.update_state(rid, lambda s: s.__setitem__("meta", rec))
            return {"meta": rec}
        return sse_job("reviewer", RP.meta_system(v), f"AUTOMATIC DESK CHECK:\n{ps}\n\nREVIEWER REPORTS:\n"
                       f"{RX.reviews_digest(st)}\n\nMANUSCRIPT TEXT:\n{_paper(rid)}", fin, max_tokens=7000, temperature=0.2,
                       start={"stage": stage})
    if stage == "issues":
        text = RX.paper_text(rid)

        def fin(m):
            try:
                data = extract_json(m["text"])
            except Exception as e:
                raise LLMError(f"Could not parse the issue list returned by the model ({e}). Press Retry.")
            issues = RX.normalise_issues(data.get("issues") if isinstance(data, dict) else data, text)

            def put(s):
                s["issues"] = issues
                s["fixes"] = {}
            RX.update_state(rid, put)
            return {"issues": issues}
        return sse_job("reviewer", RP.ISSUES_SYS, RP.issues_user(_paper(rid), RX.reviews_digest(st),
                                                                 (st.get("meta") or {}).get("text", "(none)"), RP.venue_brief(v)),
                       fin, max_tokens=12000, temperature=0.1, start={"stage": stage})
    if stage == "response":
        def fin(m):
            rec = {"text": m["text"], "engine": m["engine"], "ts": RX._now()}
            RX.update_state(rid, lambda s: s.__setitem__("response", rec))
            return {"response": rec}
        return sse_job("research", RP.RESPONSE_SYS, RP.response_user(RP.venue_brief(v), (st.get("meta") or {}).get("text", ""),
                                                                     RX.reviews_digest(st, 15000), RX.issues_digest(st)),
                       fin, max_tokens=8000, temperature=0.3, start={"stage": stage})
    raise HTTPException(400, f"Unknown stage {stage}")


@router.post("/api/review/{rid}/fix")
def review_fix(rid: str, body: dict = Body(...)):
    """Streaming quick fix for one issue: ORIGINAL → REVISED passage (+ note / plan)."""
    st = RX.load_state(rid)
    issue = next((i for i in st["issues"] if i["id"] == body.get("issue_id")), None)
    if not issue:
        raise HTTPException(404, "Issue not found — extract the issue list first")
    meta = RX.load_meta(rid)
    excerpt, fmt = RX.excerpt_for(rid, issue)

    def fin(m):
        fx = {**RX.parse_fix(m["text"]), "engine": m["engine"], "ts": RX._now(), "format": fmt, "status": "proposed"}
        fx["original_found"] = bool(fx["original"]) and RX.quote_found(excerpt, fx["original"])
        RX.update_state(rid, lambda s: s["fixes"].__setitem__(issue["id"], fx))
        return {"issue_id": issue["id"], "fix": fx}
    return sse_job("research", RP.FIX_SYS, RP.fix_user(RP.venue_brief(meta.get("venue") or {}), issue, excerpt, fmt,
                                                       body.get("instructions", "")),
                   fin, max_tokens=5000, temperature=0.2, start={"issue_id": issue["id"]})


@router.put("/api/review/{rid}/issue/{iid}")
async def review_issue(rid: str, iid: str, body: dict = Body(...)):
    """Issue status (open | done | wontfix) and/or fix status (proposed | accepted | dismissed) — Accept / Reject."""
    def upd(s):
        for it in s["issues"]:
            if it["id"] == iid and body.get("status") in ("open", "done", "wontfix"):
                it["status"] = body["status"]
        fx = s["fixes"].get(iid)
        if fx and body.get("fix_status") in ("proposed", "accepted", "dismissed"):
            fx["status"] = body["fix_status"]
        if fx and isinstance(body.get("revised"), str):
            fx["revised"] = body["revised"]
    st = await call(RX.update_state, rid, upd)
    return {"issue": next((i for i in st["issues"] if i["id"] == iid), None), "fix": st["fixes"].get(iid)}


@router.post("/api/review/{rid}/apply")
async def review_apply(rid: str, body: dict = Body(default={})):
    """Apply accepted fixes to the LaTeX source → source_revised.tex (the original is never modified)."""
    return await call(RX.apply_fixes, rid, body.get("ids"))


@router.get("/api/review/{rid}/download/{kind}")
def review_download(rid: str, kind: str):
    m = RX.load_meta(rid)
    stem = re.sub(r"[^\w\-]+", "_", Path(m.get("file", "paper")).stem)[:40]
    if kind in ("report", "fixes"):
        body = RX.report_md(rid) if kind == "report" else RX.fixes_md(rid)
        name = "review_report" if kind == "report" else "proposed_fixes"
        return Response(body, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{name}_{stem}.md"'})
    if kind == "response":
        st = RX.load_state(rid)
        if not st.get("response"):
            raise HTTPException(404, "Generate the response letter first")
        return Response(st["response"]["text"], media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="response_to_reviewers_{stem}.md"'})
    if kind == "source":
        f = RX._dir(rid) / "source_revised.tex"
        if not f.exists():
            raise HTTPException(404, "No revised source yet — accept fixes and press Apply")
        return FileResponse(f, filename=f"{stem}_revised.tex", media_type="application/x-tex")
    raise HTTPException(404, "Unknown download")
