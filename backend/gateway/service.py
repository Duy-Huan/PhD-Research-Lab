"""Gateway requests, multi-provider sessions, comparison and audit (v3.4 §12, §15-17, §21).

    prepare()   compile the provider context → request {status: review | ready}. With gateway.review_before_external
                (or review=True) nothing leaves until the researcher sends it (optionally with an edited prompt).
    send()      stream through the provider connector in a background thread; events are normalised InternalEvents
                (GET …/events, SSE); the final answer is stored with the request — NOT in memory.
    compare()   the SAME compiled context to several providers (one request each, shared compare_id). One provider's
                answer is never forwarded to another.
    propose()   researcher-selected text of an answer → lifecycle candidate (origin provider/session/request).
Never: automatic fallback to another provider or to a paid API — an unavailable provider returns its health state and
the alternatives, the researcher chooses.

Storage: <project>/gateway/requests/<id>.json (prompt + answer stay on this machine), sessions/<id>.json,
<project>/gateway/audit.jsonl (metadata only: ids, provider, token counts, blocked counts, latency — no content).
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time

from . import connectors as C

REQS: dict = {}
_lock = threading.Lock()
RID_RE = re.compile(r"^gw-[0-9a-f]{10}$")
SID_RE = re.compile(r"^gs-[0-9a-f]{8}$")


class GatewayError(ValueError):
    pass


def _dir(sub: str):
    from ..config import data_dir
    d = data_dir() / "gateway" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def audit(event: str, **meta) -> None:
    from ..telemetry import _clean
    rec = {"ts": round(time.time(), 3), "event": event, **_clean({k: v for k, v in meta.items() if k != "extra"})}
    rec.update({k: v for k, v in (meta.get("extra") or {}).items() if isinstance(v, (int, float, bool))
                or (isinstance(v, list) and all(isinstance(x, str) and len(x) < 80 for x in v))})
    try:
        with open(_dir("") / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def read_audit(limit: int = 200) -> list:
    try:
        lines = (_dir("") / "audit.jsonl").read_text("utf-8").splitlines()[-limit:]
        return [json.loads(l) for l in lines if l.strip()]
    except (OSError, ValueError):
        return []


def _persist(r: dict) -> None:
    try:
        (_dir("requests") / f"{r['id']}.json").write_text(json.dumps({k: v for k, v in r.items() if k != "thread"}, indent=1,
                                                                      default=str), "utf-8")
    except OSError:
        pass


def _session(sid: str = "") -> str:
    if sid:
        if not SID_RE.match(sid):
            raise GatewayError("Invalid session id")
        return sid
    sid = "gs-" + secrets.token_hex(4)
    (_dir("sessions") / f"{sid}.json").write_text(json.dumps({"id": sid, "created": time.time(), "requests": []}), "utf-8")
    return sid


def _session_add(sid: str, rid: str, provider: str) -> None:
    f = _dir("sessions") / f"{sid}.json"
    with _lock:
        try:
            d = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            d = {"id": sid, "created": time.time(), "requests": []}
        d["requests"].append({"id": rid, "provider": provider, "ts": time.time()})
        f.write_text(json.dumps(d, indent=1), "utf-8")


def get_session(sid: str) -> dict:
    if not SID_RE.match(sid or ""):
        raise GatewayError("Invalid session id")
    f = _dir("sessions") / f"{sid}.json"
    if not f.exists():
        raise GatewayError("Session not found")
    d = json.loads(f.read_text("utf-8"))
    d["requests"] = [{**x, **{k: v for k, v in _summary(get(x["id"])).items() if k != "id"}} for x in d["requests"] if _exists(x["id"])]
    return d


def _exists(rid: str) -> bool:
    return rid in REQS or (_dir("requests") / f"{rid}.json").exists()


def _summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("id", "provider", "status", "session_id", "compare_id", "context_tokens", "created", "ended",
                                  "health_state")}


def prepare(query: str, provider: str, role: str = "", session_id: str = "", review: bool | None = None,
            budget_tokens: int | None = None, compare_id: str = "", resume_session: str = "") -> dict:
    from ..config import load_config
    from ..telemetry import new_request_id
    from .context import provider_context
    query = (query or "").strip()
    if not query:
        raise GatewayError("Ask a question")
    cfg = load_config()
    if not cfg["gateway"].get("enabled", True):
        raise GatewayError("The Context Gateway is disabled in the configuration")
    conn = C.get(provider)
    h = conn.health()
    caps = conn.capabilities()
    if caps.get("send") == C.NOT_SUPPORTED:
        raise GatewayError(f"{conn.label} cannot be called from PhD-Lab ({h['state']}): use it as an MCP client instead")
    sid = _session(session_id)
    rid = "gw-" + secrets.token_hex(5)
    t0 = time.perf_counter()
    pc = provider_context(query, provider, role=role, session_id=sid, budget_tokens=budget_tokens, cfg=cfg,
                          request_id=new_request_id())
    review = cfg["gateway"].get("review_before_external", False) if review is None else bool(review)
    r = {"id": rid, "provider": provider, "provider_label": conn.label, "billing": h.get("billing", ""), "session_id": sid,
         "compare_id": compare_id, "query": query, "role": pc["role"], "prompt": pc["prompt"], "context_tokens": pc["context_tokens"],
         "context_version": pc["context_version"], "includes": pc["includes"], "included_ids": pc["included_ids"],
         "blocked": pc["blocked"], "sanitize": pc["sanitize"], "sensitivity_allowed": pc["sensitivity_allowed"],
         "status": "review" if review else "ready", "health_state": h["state"], "created": time.time(), "ended": None,
         "events": [], "answer": "", "errors": [], "resume_session": resume_session, "provider_session": ""}
    with _lock:
        REQS[rid] = r
    _session_add(sid, rid, provider)
    _persist(r)
    audit("prepared", request_id=rid, provider=provider, session_id=sid, role=pc["role"], context_tokens=pc["context_tokens"],
          blocked_count=len(pc["blocked"]), context_version=pc["context_version"], latency_ms=round((time.perf_counter() - t0) * 1000, 1),
          extra={"included": pc["included_ids"][:60], "sanitize": pc["sanitize"]})
    return public(r)


def public(r: dict, with_prompt: bool = True) -> dict:
    out = {k: v for k, v in r.items() if k not in ("thread", "events")}
    if not with_prompt:
        out.pop("prompt", None)
    out["event_count"] = len(r.get("events") or [])
    return out


def get(rid: str) -> dict:
    if not RID_RE.match(rid or ""):
        raise GatewayError("Invalid request id")
    if rid in REQS:
        return REQS[rid]
    f = _dir("requests") / f"{rid}.json"
    if not f.exists():
        raise GatewayError("Request not found")
    return json.loads(f.read_text("utf-8"))


def send(rid: str, edited_prompt: str | None = None, base_url: str = "", wait: bool = False) -> dict:
    r = get(rid)
    if rid not in REQS:
        raise GatewayError("Request is no longer active (app restarted) — prepare it again")
    if r["status"] not in ("review", "ready"):
        raise GatewayError(f"Request is {r['status']}")
    if edited_prompt is not None:
        from .policy import sanitize
        r["prompt"], notes = sanitize(edited_prompt[:200_000])
        r["edited"] = True
        r["sanitize"] = sorted(set(r["sanitize"] + notes))
    conn = C.get(r["provider"])
    h = conn.health()
    if h["state"] in ("DISCONNECTED", "UNAVAILABLE", "AUTH_EXPIRED", "RATE_LIMITED", "ERROR"):
        alt = [p for p, c in C.CONNECTORS.items() if p != r["provider"] and c.capabilities().get("send") is True
               and c.health()["state"] in ("CONNECTED", "UNKNOWN")]
        r.update(status="failed", health_state=h["state"], errors=[f"{conn.label} is {h['state']}: {h['detail']}"], alternatives=alt)
        _persist(r)
        audit("refused", request_id=rid, provider=r["provider"], status=h["state"])
        return public(r)  # never an automatic fallback — the researcher picks an alternative
    from ..config import load_config
    mcfg = load_config()["mcp"]
    ctx = {"request_id": rid, "resume_session": r.get("resume_session", "")}
    if base_url and mcfg.get("enabled") and mcfg.get("expose_research"):
        ctx["mcp_url"] = base_url.rstrip("/") + "/mcp"
        ctx["mcp_token"] = mcfg.get("token", "")
    r["status"] = "running"
    r["started"] = time.time()
    th = threading.Thread(target=_run, args=(r, conn, ctx), daemon=True)
    r["thread"] = th
    th.start()
    if wait:
        th.join(timeout=float(load_config()["gateway"].get("provider_timeout_s", 600)))
    return public(r)


def _run(r: dict, conn, ctx: dict) -> None:
    from ..telemetry import span
    first = None
    t0 = time.perf_counter()
    text = []
    try:
        with span("gateway.request", request_id=r["id"], provider=r["provider"], session_id=r["session_id"], streaming=True,
                  context_tokens=r["context_tokens"], context_version=r["context_version"]) as sp:
            for e in conn.stream_message(r["prompt"], ctx):
                r["events"].append(e)
                if e["type"] == "text_delta":
                    if first is None:
                        first = time.perf_counter() - t0
                    text.append(e.get("text", ""))
                elif e["type"] == "status" and e.get("state") == "result" and e.get("final_text"):
                    r["answer"] = e["final_text"]
                elif e["type"] == "status" and e.get("state") == "session":
                    r["provider_session"] = e.get("session_id", "")
                elif e["type"] == "error":
                    r["errors"].append(e.get("message", ""))
                elif e["type"] == "request_cancelled":
                    r["status"] = "cancelled"
            if not r["answer"]:
                r["answer"] = "".join(text)
            if r["status"] == "running":
                r["status"] = "failed" if r["errors"] and not r["answer"] else "completed"
            sp.update(status=r["status"])
    except C.ProviderError as e:
        r["errors"].append(str(e))
        r["status"] = "failed"
        r["health_state"] = e.state
        r["events"].append({"type": "error", "message": str(e), "ts": time.time()})
    except Exception as e:  # never leave a request "running"
        r["errors"].append(f"{type(e).__name__}: {e}"[:300])
        r["status"] = "failed"
    finally:
        r["ended"] = time.time()
        r["first_token_s"] = round(first, 3) if first is not None else None
        _persist(r)
        audit("completed", request_id=r["id"], provider=r["provider"], status=r["status"], session_id=r["session_id"],
              latency_ms=round((time.perf_counter() - t0) * 1000, 1), extra={"first_token_s": r["first_token_s"] or 0,
                                                                              "answer_chars": len(r["answer"])})


def cancel(rid: str) -> dict:
    r = get(rid)
    if r.get("status") not in ("running", "review", "ready"):
        raise GatewayError(f"Request is {r.get('status')}")
    if r["status"] in ("review", "ready"):
        r["status"] = "cancelled"
        _persist(r)
        return public(r)
    out = C.get(r["provider"]).cancel(rid)
    audit("cancel", request_id=rid, provider=r["provider"])
    return {**public(r), "cancel": out}


def events(rid: str, after: int = 0) -> dict:
    r = get(rid)
    ev = (r.get("events") or [])[after:]
    return {"id": rid, "status": r.get("status"), "events": ev, "next": after + len(ev)}


def compare(query: str, providers: list, role: str = "", session_id: str = "", review: bool | None = None,
            base_url: str = "") -> dict:
    """Same canonical context → several providers. Answers stay separate; nothing is cross-forwarded."""
    providers = list(dict.fromkeys(p for p in providers or [] if p))
    if len(providers) < 2:
        raise GatewayError("Pick at least two providers to compare")
    cid = "cmp-" + secrets.token_hex(4)
    sid = _session(session_id)
    reqs = []
    for p in providers:
        try:
            reqs.append(prepare(query, p, role=role, session_id=sid, review=review, compare_id=cid))
        except (GatewayError, C.ProviderError) as e:
            reqs.append({"provider": p, "status": "unavailable", "errors": [str(e)]})
    prompts = {x.get("prompt") for x in reqs if x.get("prompt")}
    for x in reqs:
        if x.get("status") == "ready":
            send(x["id"], base_url=base_url)
    return {"compare_id": cid, "session_id": sid, "same_context": len(prompts) <= 1,
            "requests": [_summary(get(x["id"])) if x.get("id") else x for x in reqs]}


def propose(rid: str, kind: str, text: str, **payload) -> dict:
    """Researcher picked part of a provider answer → memory CANDIDATE (classification + dedup + review)."""
    from ..memory import lifecycle
    r = get(rid)
    if r.get("status") != "completed":
        raise GatewayError("Only completed answers can be proposed to memory")
    return lifecycle.propose(kind, {"text": text, **payload}, origin="provider", provider=r["provider"],
                             session=r["session_id"], request_id=rid)


def status() -> dict:
    out = {}
    for pid, c in C.CONNECTORS.items():
        try:
            out[pid] = {**c.health(), "capabilities": c.capabilities()}
        except Exception as e:
            out[pid] = {"provider": pid, "state": "ERROR", "detail": f"{type(e).__name__}: {e}"[:200]}
    out["chatgpt_web"] = C.chatgpt_web_note()
    return out
