"""Gateway requests: one CLI provider call with the compiled research context (agent/orchestrator.py → `cli:<name>`).

    prepare()   compile the provider context → request {status: ready}; the security profile is checked fail-closed
    send()      stream through the provider connector in a background thread; events are normalised InternalEvents;
                the final answer is stored with the request — NOT in memory
    events()    the request's events after a cursor; cancel() stops it
Never: automatic fallback to another provider or to a paid API — an unavailable provider returns its health state and
the alternatives, the researcher chooses.

Storage: <project>/gateway/requests/<id>.json (prompt + answer stay on this machine), sessions/<id>.json,
<project>/gateway/audit.jsonl (metadata only: ids, provider, token counts, blocked counts, latency — no content).
Every request runs in the provider's session workspace with a read-only context manifest (cli_space.py), holds a `cli`
lifecycle lease, and resumes the provider's native session when the cli lifecycle policy keeps sessions.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time

from backend.providers import cli as C

REQS: dict = {}
_lock = threading.RLock()
_changed = threading.Condition(_lock)
EVENT_WINDOW = 512


def _publish(r: dict, event: dict) -> dict:
    """Bounded hot window with durable replay; cursors remain absolute offsets."""
    from backend.core.telemetry import redact
    from pathlib import Path
    def clean(value):
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    event = clean(event)
    with _changed:
        path = Path(r["project_dir"]) / "gateway" / "requests" / (r["id"] + ".events.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        r["events"].append(event)
        if len(r["events"]) > EVENT_WINDOW:
            del r["events"][:-EVENT_WINDOW]
        r["event_count"] = r.get("event_count", 0) + 1
        if event.get("type") not in ("request_started", "request_completed", "request_cancelled"):
            r.setdefault("timings_ms", {}).setdefault("first_event", round((time.perf_counter() - r["_clock"]) * 1000, 2))
        _changed.notify_all()
    return event
RID_RE = re.compile(r"^gw-[0-9a-f]{10}$")
SID_RE = re.compile(r"^gs-[0-9a-f]{8}$")


class GatewayError(ValueError):
    pass


def _dir(sub: str):
    from backend.core.config import data_dir
    d = data_dir() / "gateway" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def audit(event: str, **meta) -> None:
    from backend.core.telemetry import _clean
    rec = {"ts": round(time.time(), 3), "event": event, **_clean({k: v for k, v in meta.items() if k != "extra"})}
    rec.update({k: v for k, v in (meta.get("extra") or {}).items() if isinstance(v, (int, float, bool))
                or (isinstance(v, list) and all(isinstance(x, str) and len(x) < 80 for x in v))})
    try:
        with open(_dir("") / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def _persist(r: dict) -> None:
    from pathlib import Path
    from backend.core.config import data_dir
    try:
        folder = Path(r.get("project_dir") or data_dir()) / "gateway" / "requests"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{r['id']}.json"
        tmp = target.with_name(target.name + ".tmp-" + secrets.token_hex(4))
        tmp.write_text(json.dumps({k: v for k, v in r.items() if k != "thread" and not k.startswith("_")}, indent=1,
                                  default=str), "utf-8")
        from backend.memory.store import replace_retry
        replace_retry(tmp, target)
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


def _summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("id", "provider", "status", "session_id", "context_tokens", "created", "ended", "health_state")}


def prepare(query: str, provider: str, role: str = "", session_id: str = "", profile: str = "", allow_weaker: bool = False,
            module_context: str = "", memory: bool = True) -> dict:
    clock = time.perf_counter()
    from backend.core.config import load_config, data_dir
    from backend.core.telemetry import new_request_id
    from backend.providers.context_packet import provider_context
    query = (query or "").strip()
    from backend.core.telemetry import redact
    query = redact(query)
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
    from backend.providers import cli_space as W
    from backend.providers import lifecycle as LC
    profile = profile or cfg["gateway"].get("cli_profile", "review")
    try:
        iso = W.check_profile(provider, profile, allow_weaker)
    except W.WorkspaceError as e:
        raise GatewayError(str(e))
    W.prune(cfg)
    sid = _session(session_id)
    resume_session = LC.cli_resume(sid, provider, cfg) if getattr(conn, "supports_resume", False) else ""
    rid = "gw-" + secrets.token_hex(5)
    t0 = time.perf_counter()
    pc = provider_context(query, provider, role=role, session_id=sid, cfg=cfg, request_id=new_request_id(),
                          module_context=module_context, memory=memory)
    r = {"id": rid, "provider": provider, "provider_label": conn.label, "billing": h.get("billing", ""), "session_id": sid,
         "query": query, "role": pc["role"], "prompt": pc["prompt"], "context_tokens": pc["context_tokens"],
         "context_version": pc["context_version"], "includes": pc["includes"], "included_ids": pc["included_ids"],
         "blocked": pc["blocked"], "sanitize": pc["sanitize"], "sensitivity_allowed": pc["sensitivity_allowed"],
         "status": "ready", "health_state": h["state"], "created": time.time(), "ended": None,
         "events": [], "answer": "", "errors": [], "resume_session": resume_session, "provider_session": "",
         "profile": profile, "isolation": iso, "project_dir": str(data_dir().resolve()),
         "_clock": clock, "event_count": 0,
         "timings_ms": {"context": round((time.perf_counter() - t0) * 1000, 2),
                        "prepare": round((time.perf_counter() - clock) * 1000, 2)}}
    with _lock:
        REQS[rid] = r
    _session_add(sid, rid, provider)
    _persist(r)
    audit("prepared", request_id=rid, provider=provider, session_id=sid, role=pc["role"], context_tokens=pc["context_tokens"],
          blocked_count=len(pc["blocked"]), context_version=pc["context_version"], latency_ms=round((time.perf_counter() - t0) * 1000, 1),
          extra={"included": pc["included_ids"][:60], "sanitize": pc["sanitize"]})
    return public(r)


def public(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k not in ("thread", "events") and not k.startswith("_")}
    out["event_count"] = r.get("event_count", len(r.get("events") or []))
    return out


def get(rid: str) -> dict:
    if not RID_RE.match(rid or ""):
        raise GatewayError("Invalid request id")
    if rid in REQS:
        from backend.core.config import data_dir
        cached = REQS[rid]
        if cached.get("project_dir") and cached["project_dir"] != str(data_dir().resolve()):
            raise GatewayError("Request not found")
        return cached
    f = _dir("requests") / f"{rid}.json"
    if not f.exists():
        raise GatewayError("Request not found")
    r = json.loads(f.read_text("utf-8"))
    if r.get("status") in ("starting", "running"):
        r.update(status="failed", ended=time.time())
        r.setdefault("errors", []).append("CLI process lost after restart; partial outputs retained. Resume explicitly.")
        _persist(r)
    return r


def send(rid: str, base_url: str = "", mcp: dict | None = None, model: str = "", reasoning: str = "") -> dict:
    """mcp={"token", "tools"} = an ephemeral session grant (agent/mcp_policy.py) instead of the global MCP token;
    model / reasoning are passed to connectors that support them (providers.py advertises which)."""
    r = get(rid)
    if rid not in REQS:
        raise GatewayError("Request is no longer active (app restarted) — prepare it again")
    with _changed:
        if r["status"] != "ready":
            if r["status"] in ("cancelled", "failed"):
                raise GatewayError(f"Request is {r['status']}")
            return public(r)  # same request id is an idempotency key; never launch twice
        r["status"] = "starting"
        r["_cancel"] = threading.Event()
    try:
        return _send(r, base_url, mcp, model, reasoning)
    except Exception:
        with _changed:
            r.update(status="failed", ended=time.time())
            _changed.notify_all()
        _persist(r)
        raise


def _send(r, base_url, mcp, model, reasoning):
    rid = r["id"]
    conn = C.get(r["provider"])
    h = conn.health()
    if h["state"] in ("DISCONNECTED", "UNAVAILABLE", "AUTH_EXPIRED", "RATE_LIMITED", "ERROR"):
        alt = [p for p, c in C.CONNECTORS.items() if p != r["provider"] and c.capabilities().get("send") is True
               and c.health()["state"] in ("CONNECTED", "UNKNOWN")]
        r.update(status="failed", health_state=h["state"], errors=[f"{conn.label} is {h['state']}: {h['detail']}"], alternatives=alt)
        _persist(r)
        audit("refused", request_id=rid, provider=r["provider"], status=h["state"])
        return public(r)  # never an automatic fallback — the researcher picks an alternative
    from backend.core.config import load_config
    mcfg = load_config()["mcp"]
    from backend.providers import cli_space as W
    profile = r.get("profile") or "review"
    sess = W.open_session(r["provider"], r["session_id"], profile, r.get("isolation"))
    W.stage_context(sess, rid, r["prompt"], {"provider": r["provider"], "session_id": r["session_id"],
                                             "context_version": r.get("context_version"), "role": r.get("role"),
                                             "included_ids": r.get("included_ids", []), "blocked_count": len(r.get("blocked") or []),
                                             "sensitivity_allowed": r.get("sensitivity_allowed"), "sanitize": r.get("sanitize"),
                                             "profile": profile, "isolation": r.get("isolation")})
    r["workspace"] = sess["dir"]
    ctx = {"request_id": rid, "resume_session": r.get("resume_session", ""), "cwd": sess["cwd"], "profile": profile,
           "_session": sess, "_cancel": r["_cancel"], "_timings_ms": r["timings_ms"]}
    if model:
        ctx["model"] = model
    if reasoning:
        ctx["reasoning"] = reasoning
    if base_url and mcfg.get("enabled") and mcfg.get("expose_research") and (mcp is None or mcp["tools"]):
        ctx["mcp_url"] = base_url.rstrip("/") + "/mcp"
        ctx["mcp_token"] = mcp["token"] if mcp else mcfg.get("token", "")
        if mcp:
            ctx["mcp_tools"] = list(mcp["tools"])
    r["status"] = "running"
    r["started"] = time.time()
    th = threading.Thread(target=_run, args=(r, conn, ctx), daemon=True)
    r["thread"] = th
    th.start()
    return public(r)


def _run(r: dict, conn, ctx: dict) -> None:
    from backend.core.config import project_scope, data_dir
    with project_scope(r.get("project_dir") or data_dir()):
        try:
            _run_scoped(r, conn, ctx)
        except Exception as e:
            from backend.core.telemetry import redact
            r["errors"].append(redact(f"{type(e).__name__}: {e}")[:300])
            r.update(status="failed", ended=time.time())
            _persist(r)
        finally:
            with _changed:
                _changed.notify_all()


def _run_scoped(r: dict, conn, ctx: dict) -> None:
    from backend.providers import lifecycle as LC
    with LC.lease_sync("cli", r["provider"], r["session_id"], "interactive"):
        _run_inner(r, conn, ctx)
    LC.cli_remember(r["session_id"], r["provider"], r.get("provider_session", ""))


def _run_inner(r: dict, conn, ctx: dict) -> None:
    from backend.core.telemetry import span
    from backend.core.config import data_dir
    r.setdefault("_clock", time.perf_counter())
    r.setdefault("timings_ms", {})
    r.setdefault("project_dir", str(data_dir().resolve()))
    first = None
    t0 = time.perf_counter()
    text = []
    try:
        with span("gateway.request", request_id=r["id"], provider=r["provider"], session_id=r["session_id"], streaming=True,
                  context_tokens=r["context_tokens"], context_version=r["context_version"]) as sp:
            for e in conn.stream_message(r["prompt"], ctx):
                e = _publish(r, e)
                if e["type"] == "text_delta":
                    if first is None:
                        first = time.perf_counter() - t0
                        r["timings_ms"]["first_token"] = round((time.perf_counter() - r["_clock"]) * 1000, 2)
                    text.append(e.get("text", ""))
                elif e["type"] == "status" and e.get("state") == "result" and e.get("final_text"):
                    r["answer"] = e["final_text"]
                elif e["type"] == "status" and e.get("state") == "session":
                    r["provider_session"] = e.get("session_id", "")
                elif e["type"] == "error":
                    r["errors"].append(e.get("message", ""))
                elif e["type"] == "request_cancelled":
                    r["status"] = "cancelled"
                elif e["type"] == "request_completed":
                    if not r.get("answer"):
                        r["answer"] = "".join(text)
                    r["status"] = "failed" if r["errors"] else "completed"
            if not r["answer"]:
                r["answer"] = "".join(text)
            if r["status"] == "running":
                r["status"] = "failed" if r["errors"] else "completed"
            sp.update(status=r["status"])
    except C.ProviderError as e:
        from backend.core.telemetry import redact
        r["errors"].append(redact(str(e)))
        r["status"] = "failed"
        r["health_state"] = e.state
        _publish(r, {"type": "error", "message": str(e), "ts": time.time()})
    except Exception as e:  # never leave a request "running"
        from backend.core.telemetry import redact
        r["errors"].append(redact(f"{type(e).__name__}: {e}")[:300])
        r["status"] = "failed"
    finally:
        if not r["answer"]:
            r["answer"] = "".join(text)  # a provider exception must not discard streamed findings
        r["ended"] = time.time()
        r["timings_ms"]["total"] = round((time.perf_counter() - r["_clock"]) * 1000, 2)
        r["first_token_s"] = round(first, 3) if first is not None else None
        if ctx.get("_session"):
            from backend.providers.cli_space import write_output
            write_output(ctx["_session"], r["id"], r["answer"], ctx.get("_stderr"))
        _persist(r)
        audit("completed", request_id=r["id"], provider=r["provider"], status=r["status"], session_id=r["session_id"],
              latency_ms=round((time.perf_counter() - t0) * 1000, 1), extra={"first_token_s": r["first_token_s"] or 0,
                                                                              "answer_chars": len(r["answer"])})


def cancel(rid: str) -> dict:
    r = get(rid)
    with _changed:
        if r.get("status") not in ("running", "ready", "starting"):
            raise GatewayError(f"Request is {r.get('status')}")
        if r["status"] == "ready":
            r.update(status="cancelled", ended=time.time())
            _changed.notify_all()
            _persist(r)
            return public(r)
        r["_cancel"].set()  # also covers cancellation before Popen / while waiting for a lease
    out = C.get(r["provider"]).cancel(rid)
    with _changed:
        _changed.notify_all()
    audit("cancel", request_id=rid, provider=r["provider"])
    return {**public(r), "cancel": out}


def events(rid: str, after: int = 0) -> dict:
    r = get(rid)
    from pathlib import Path
    after = max(0, after)
    with _changed:
        count = r.get("event_count", len(r.get("events") or []))
        base = count - len(r.get("events") or [])
        if after >= base:
            ev = (r.get("events") or [])[after - base:after - base + EVENT_WINDOW]
        else:
            path = Path(r["project_dir"]) / "gateway" / "requests" / (rid + ".events.jsonl")
            from itertools import islice
            with path.open(encoding="utf-8") as f:
                ev = [json.loads(line) for line in islice(f, after, after + EVENT_WINDOW)]
        return {"id": rid, "status": r.get("status"), "events": ev, "next": after + len(ev)}


def wait_events(rid: str, after: int = 0, timeout: float = 1.0) -> dict:
    end = time.monotonic() + min(15.0, max(0.0, timeout))
    with _changed:
        while True:
            batch = events(rid, after)
            if batch["events"] or batch["status"] not in ("ready", "starting", "running"):
                return batch
            left = end - time.monotonic()
            if left <= 0:
                return batch
            _changed.wait(left)
