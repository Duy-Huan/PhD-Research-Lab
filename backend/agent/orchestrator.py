"""The Primary Research Orchestrator: one turn of the research chat (UI and CLI).

    start ─▶ skill: "/command args" → that skill; plain text → intent router (launch.route)
               · run skills become background research runs (agent/runs.py) — risky ones wait for "Chấp nhận"
               · chat skills add their instructions to the agent (research or reviewer) for this turn
               · /help and /status are answered by the app itself (no model call)
          ─▶ policy (effective settings + provider capability check + security profile, fail closed)
          ─▶ tools: auto-selected / requested research tools ∩ allowlist → run (tier 0, automation) or WAIT for approval
          ─▶ context: compile manifest + bundle (tool results enter as untrusted sources)
          ─▶ manual mode: stop at awaiting_launch with the launch plan until the researcher launches
          ─▶ provider: in-app engine stream (llm.py) or CLI connector through the Context Gateway (session workspace,
             env allowlist, read-only context, lifecycle lease, process-tree kill) — events normalised
          ─▶ completion: message + structured action proposals (approval required) + artifacts + memory per mode +
             rolling summary
Turns run in a worker thread (bound to the research project they started in) so the UI and the CLI can follow the
same turn through GET …/events (or SSE …/stream) and cancel it from either side.
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time

from backend.agent import AIWSError, project_context as adapters, artifacts, context, mcp_policy, memory_modes, new_id, now, sessions as store
from backend.providers import registry as providers
from backend.agent.policy import check_provider, clean_overrides, effective, needs_approval, values

_running: dict = {}  # turn id → {"cancel": Event, "rid": gateway request id}
_lock = threading.Lock()
ACTION = re.compile(r"```phdlab-action\s*\n(.*?)```", re.S)
ENGINE = {"app:local": "local", "app:ollama": "ollama"}


def _turn(s: dict, tid: str) -> dict:
    t = next((x for x in s["turns"] if x["id"] == tid), None)
    if not t:
        raise AIWSError("Turn not found")
    return t


def _set(sid: str, tid: str, **fields) -> dict:
    def fn(s):
        t = _turn(s, tid)
        t.update(fields)
        if "status" in fields:
            s["status"] = {"running": "running", "waiting_approval": "waiting", "awaiting_launch": "waiting"}.get(fields["status"], "idle")
        return dict(t)
    return store.update(sid, fn)


def instructions(module: str, skill: str = "") -> str:
    acts = adapters.get(module).actions()
    lines = [f"- {a['name']}: {a['description']} · args schema {json.dumps(a['schema']['properties'])}" for a in acts]
    return ("You are the research assistant inside the researcher's PhD Research Lab. Answer from the compiled context, "
            "cite source ids, and say clearly when something is a hypothesis or not supported by the sources.\n"
            "To PROPOSE a change of research state, add a fenced block\n```phdlab-action\n{\"action\": \"<name>\", "
            "\"args\": {…}}\n```\nwith one of these actions (they run only after the researcher approves them):\n"
            + "\n".join(lines) + "\nTo propose a file, use a fenced block with its path, e.g. ```python path=src/train.py. "
            "To propose memory, write lines such as 'Decision: …', 'Finding: …', 'Open question: …'.\n"
            "Background work (literature runs, experiments, code, review, LaTeX) is started with the start_run action; "
            "the researcher can also type /help to see every skill.\n" + RICH_OUTPUT + _language() + _skill_block(skill))


# What the chat renders beyond Markdown + KaTeX (frontend/assets/tools.js). Data must come from the context or the
# researcher — never invented numbers presented as results.
RICH_OUTPUT = (
    "The chat renders these fenced blocks, use them when a picture says more than text:\n"
    "- ```chart with JSON {\"type\": \"line|bar|scatter|area\", \"title\": \"…\", \"x\": [labels or numbers], "
    "\"series\": [{\"name\": \"…\", \"data\": [numbers], \"error\": [optional ± values]}], \"xlabel\": \"…\", \"ylabel\": \"…\", "
    "\"ylog\": false} — interactive plot; the researcher can click any point to annotate it.\n"
    "- ```svg with one <svg> element — diagrams and schematic figures (no scripts).\n"
    "- ```mermaid — flowcharts / sequence diagrams of pipelines and architectures.\n"
    "- Markdown images ![caption](project/file.png) for figures that exist in the project.\n"
    "Plot only values from the context (MEASURED results, tables, papers) or values the researcher gave; label "
    "illustrative curves as such. The researcher can export any answer to PDF, Word, LaTeX or Markdown.\n")


def _language() -> str:
    from backend.core.config import load_config
    cfg = load_config()
    ui_cfg = cfg.get("ui") or {}
    ai_lang = ui_cfg.get("ai_language") or "auto"
    if ai_lang == "vi":
        return "Always answer in Vietnamese; keep international technical terms and standard citations in English.\n"
    elif ai_lang == "en":
        return "Always answer in English (Academic and Scientific Standard).\n"
    else:  # auto
        ui_lang = ui_cfg.get("language", "vi")
        return ("Answer in Vietnamese unless the researcher writes in another language; keep technical terms in English.\n"
                if ui_lang == "vi" else "Answer in English unless the researcher writes in another language.\n")


def _skill_block(name: str) -> str:
    if not name:
        return ""
    from backend.agent import skills
    try:
        s = skills.get(name)
    except AIWSError:
        return ""
    return f"\n# Skill /{s['name']} — {s['title']}\n{s['instructions']}\n"


def _agent(t: dict) -> str:
    """assistant | research | reviewer — the agent the turn's skill asks for."""
    if not t.get("skill"):
        return "assistant"
    from backend.agent import skills
    try:
        return skills.get(t["skill"])["agent"]
    except AIWSError:
        return "research"


def _local(sid: str, tid: str, text: str, **meta) -> None:
    """Answer a turn from the app itself (help, status, a run that was started) — no model call."""
    m = store.add_message(sid, "assistant", text, tid, provider="phdlab", status="complete", **meta)
    store.emit(sid, "message.completed", tid, "phdlab", message_id=m["id"], text=text, chars=len(text))
    _set(sid, tid, status="completed", answer_id=m["id"], ended=now(), started=now())
    store.emit(sid, "turn.completed", tid, "phdlab", message_id=m["id"], seconds=0)


def _route(sid: str, tid: str, s: dict, text: str) -> bool:
    """Skills and intents. True when the turn was handled here (no model call)."""
    from backend.agent import launch, skills
    from backend.agent.ui_actions import QUICK
    command = text.split(maxsplit=1)[0].lstrip("/").lower() if text.startswith("/") else ""
    if command in QUICK:
        _local(sid, tid, "Open the research drawer: " + QUICK[command][0] + ". This is a deterministic UI action; no model was called.")
        return True
    m = skills.match(text)
    if m:
        skill, arg = m
        if skill["name"] == "help":
            _local(sid, tid, launch.help_text())
            return True
        if skill["name"] == "status":
            if s.get("topic_id"):
                from backend.knowledge import research_store as RS, corpus
                from backend.research_engines.workspaces import list_workspaces
                topic = RS.get_topic(s["topic_id"])
                _local(sid, tid, f"Topic: {topic['title']}\n\nPapers: {corpus.search(topic['id'])['total']}\nWorkspaces: {len(list_workspaces(topic['id']))}\n\nUse /jobs or /artifacts for the scoped research state.")
                return True
            from backend.agent.dashboard import status_text
            _local(sid, tid, status_text())
            return True
        if skill["mode"] == "run":
            if s.get("topic_id"):
                if skill["name"] in ("review", "compare", "lit", "gap", "deepresearch"):
                    _set(sid, tid, skill=skill["name"], question=arg or f"/{skill['name']}")
                    return False
                _local(sid, tid, "This run changes project-scoped state. Open a project conversation to run it; Topic chat supports scoped research and review.")
                return True
            try:
                r = launch.from_skill(skill["name"], arg, s, turn_id=tid)
            except AIWSError as e:
                _local(sid, tid, f"⚠ /{skill['name']}: {e}")
                return True
            _local(sid, tid, _run_started(r), kind="run", run_id=r["id"])
            return True
        _set(sid, tid, skill=skill["name"], question=arg or f"/{skill['name']}")
        return False
    if s.get("topic_id"):
        return False
    route = launch.route(text)
    if not route:
        return False
    store.emit(sid, "status.updated", tid, "phdlab", intent=route["skill"], why=route["why"])
    if route["mode"] == "chat":
        _set(sid, tid, skill=route["skill"], intent=route)
        return False
    if route["auto"]:
        r = launch.from_skill(route["skill"], text, s, turn_id=tid)
        from backend.core.i18n import L
        _local(sid, tid, L(f"Mình hiểu đây là yêu cầu **/{route['skill']}** ({route['title']}).\n\n",
                           f"This looks like a **/{route['skill']}** request ({route['title']}).\n\n") + _run_started(r),
               kind="run", run_id=r["id"])
        return True
    ap = {"id": new_id("ap", 4), "turn_id": tid, "kind": "action", "name": "start_run",
          "args": {"skill": route["skill"], "input": text[:8000]}, "risk": route["risk"], "status": "pending",
          "created": now(), "reason": route["why"]}
    store.update(sid, lambda x: x["approvals"].append(ap))
    store.emit(sid, "action.proposed", tid, "phdlab", approval=ap["id"], action="start_run")
    store.emit(sid, "action.approval_required", tid, "phdlab", approval=ap["id"], action="start_run", risk=route["risk"])
    from backend.core.i18n import L
    _local(sid, tid, L(f"Mình đề xuất chạy **/{route['skill']}** ({route['title']}) trong nền với yêu cầu của bạn. "
                       "Việc này viết code / dùng tài nguyên máy nên cần bạn **Chấp nhận** trước — hoặc bỏ qua để "
                       "mình chỉ trả lời trong chat.",
                       f"I propose running **/{route['skill']}** ({route['title']}) in the background for your request. "
                       "It writes code / uses this machine's resources, so it needs your **Accept** first — or dismiss it "
                       "and I will only answer in the chat."), kind="proposal")
    return True


def _run_started(r: dict) -> str:
    from backend.core.i18n import L
    steps = " → ".join(x["label"] for x in r["steps"])
    if r["status"] == "APPROVAL_PENDING":
        return L(f"Đã lập kế hoạch run `{r['id']}`: {steps}.\n\nRun này cần bạn **Chấp nhận** trước khi chạy "
                 "(viết code / dùng GPU / thay đổi dự án).",
                 f"Planned run `{r['id']}`: {steps}.\n\nThis run needs your **Accept** before it starts "
                 "(writes code / uses the GPU / changes the project).")
    return L(f"Đã bắt đầu run `{r['id']}` trong nền: {steps}. Bạn có thể tiếp tục trò chuyện; kết quả sẽ hiện ở đây "
             "để bạn duyệt.", f"Started run `{r['id']}` in the background: {steps}. You can keep chatting; the results "
             "will appear here for your review.")


# ------------------------------------------------------------------ public API
def start(sid: str, text: str, overrides: dict | None = None, base_url: str = "", replace_from: str = "") -> dict:
    text = (text or "").strip()
    if not text:
        raise AIWSError("Write a message")
    s = store.get(sid)
    if s["archived"]:
        raise AIWSError("Session is archived — restore it first")
    if any(t["status"] in ("running", "queued") for t in s["turns"]):
        raise AIWSError("A turn is already running in this session — wait or cancel it")
    ov = clean_overrides(overrides or {})
    if s.get("topic_id"):
        from backend.knowledge.research_context import validate_sources
        validate_sources(s["topic_id"], list(s.get("selected_sources") or []) + list(ov.get("sources") or []))
        if ov.get("run_tools"):
            raise AIWSError("Project-scoped tools are unavailable in Topic chat")
    eff = effective(s, ov)
    tid = new_id("t", 4)
    if replace_from:
        def cut(x):
            i = next((k for k, m in enumerate(x["messages"]) if m["id"] == replace_from), None)
            if i is None:
                raise AIWSError("Message not found")
            del x["messages"][i:]
        store.update(sid, cut)
    msg = store.add_message(sid, "user", text, tid)
    turn = {"id": tid, "status": "queued", "created": now(), "message_id": msg["id"], "question": text, "overrides": ov,
            "effective": eff, "notes": check_provider(eff), "tools": [], "manifest": None, "plan": None,
            "answer_id": "", "error": "", "base_url": base_url, "launched": False, "started": None, "ended": None}
    store.update(sid, lambda x: (x["turns"].append(turn), x.update(status="running")))
    store.emit(sid, "turn.started", tid, values(eff)["provider"], question_chars=len(text), message_id=msg["id"],
               overrides=sorted(ov))
    try:
        handled = _route(sid, tid, s, text)
    except AIWSError as e:  # unknown /command, invalid input
        _local(sid, tid, f"⚠ {e}")
        handled = True
    if handled:
        return _turn(store.get(sid), tid)
    for n in turn["notes"]:
        store.emit(sid, "status.updated", tid, values(eff)["provider"], setting=n["setting"], note=n["note"])
    _spawn(sid, tid, "start")
    return _turn(store.get(sid), tid)


def _spawn(sid: str, tid: str, stage: str) -> None:
    from backend.core.config import data_dir
    proj = str(data_dir().resolve())
    with _lock:
        _running.setdefault(tid, {"cancel": threading.Event(), "rid": ""})

    def work():
        from backend.core.config import project_scope
        with project_scope(proj):
            try:
                run(sid, tid, stage)
            except Exception as e:  # never leave a turn running
                _fail(sid, tid, f"{type(e).__name__}: {e}"[:500])
    threading.Thread(target=work, daemon=True, name=f"aiws-{tid}").start()


def _fail(sid: str, tid: str, why: str, kind: str = "error") -> None:
    _set(sid, tid, status="failed", error=why, ended=now())
    store.emit(sid, "permission.denied" if kind == "denied" else "error", tid, message=why)
    store.emit(sid, "turn.failed", tid, message=why)
    with _lock:
        _running.pop(tid, None)


def run(sid: str, tid: str, stage: str) -> None:
    s = store.get(sid)
    t = _turn(s, tid)
    v = values(t["effective"])
    pid = v["provider"]
    _set(sid, tid, status="running", started=t["started"] or now())
    if stage == "start":
        prov = providers.describe(pid)
        if not prov["available"]:
            return _fail(sid, tid, f"{prov['label']} is not available ({prov['state']}): {prov['detail']}")
        if pid.startswith("cli:"):
            from backend.providers import cli_space as W
            try:
                iso = W.check_profile(pid[4:], v["security_profile"], bool(v.get("consent_weaker")))
            except W.WorkspaceError as e:
                return _fail(sid, tid, str(e), "denied")
            _set(sid, tid, isolation=iso)
        if not _tools(sid, tid, v):
            return
        stage = "after_tools"
    if stage == "after_tools":
        s = store.get(sid)
        t = _turn(s, tid)
        extra = [adapters.src(f"tool:{x['id']}", "tool_result", f"{x['name']} result", (x.get("result") or {}).get("text", ""),
                              "untrusted", "research tool run for this turn")
                 for x in s["approvals"] if x["turn_id"] == tid and x["kind"] == "tool" and x["status"] == "executed"]
        from backend.core.telemetry import span
        clock = time.perf_counter()
        with span("chat.context", session_id=sid, provider=pid):
            ctx = context.compile(s, t["question"], t["effective"], extra)
        _set(sid, tid, manifest=ctx["manifest"], context_text=ctx["text"],
             timings_ms={"context": round((time.perf_counter() - clock) * 1000, 2)})
        store.update(sid, lambda x: x.update(last_manifest=ctx["manifest"]))
        store.emit(sid, "context.compiled", tid, pid, manifest=ctx["manifest"]["id"], sources=len(ctx["manifest"]["sources"]),
                   omitted=len(ctx["manifest"]["omitted"]), tokens=ctx["manifest"]["budget"]["used_tokens"],
                   cache=ctx["manifest"]["cache"])
        if v["operating_mode"] == "manual" and not t["launched"]:
            plan = launch_plan(sid, tid)
            _set(sid, tid, status="awaiting_launch", plan=plan)
            store.emit(sid, "turn.awaiting_launch", tid, pid, provider=pid)
            return
    _dispatch(sid, tid)


def _tools(sid: str, tid: str, v: dict) -> bool:
    """True when the turn may continue now; False when it waits for tool approvals."""
    s = store.get(sid)
    t = _turn(s, tid)
    allow = mcp_policy.allowed(v["mcp_tools"])
    wanted = mcp_policy.propose(t["question"], allow) if v["mcp_auto"] else []
    wanted += [{"tool": x["tool"], "args": x.get("args") or {}, "reason": "requested for this turn"}
               for x in (t["overrides"].get("run_tools") or [])]
    waiting = False
    for w in wanted:
        r = mcp_policy.risk(w["tool"])
        ap = {"id": new_id("ap", 4), "turn_id": tid, "kind": "tool", "name": w["tool"], "args": w["args"], "risk": r,
              "reason": w["reason"], "status": "pending", "created": now()}
        if w["tool"] not in allow:
            ap.update(status="denied", result={"text": "not in the session's MCP allowlist"})
            store.update(sid, lambda x, ap=ap: x["approvals"].append(ap))
            store.emit(sid, "permission.denied", tid, v["provider"], tool=w["tool"], reason="not in the allowlist")
            continue
        store.update(sid, lambda x, ap=ap: x["approvals"].append(ap))
        store.emit(sid, "tool.proposed", tid, v["provider"], approval=ap["id"], tool=w["tool"], risk=r, reason=w["reason"])
        if needs_approval(r, v["operating_mode"]):
            waiting = True
            store.emit(sid, "tool.approval_required", tid, v["provider"], approval=ap["id"], tool=w["tool"], risk=r)
        else:
            _exec_tool(sid, ap["id"], "auto-policy (tier 0, automation)")
    if waiting:
        _set(sid, tid, status="waiting_approval")
    return not waiting


def _exec_tool(sid: str, aid: str, by: str) -> dict:
    s = store.get(sid)
    ap = next(x for x in s["approvals"] if x["id"] == aid)
    store.emit(sid, "tool.started", ap["turn_id"], approval=aid, tool=ap["name"])
    try:
        res = mcp_policy.execute(ap["name"], ap["args"], sid)
        status, ev = "executed", "tool.completed"
    except Exception as e:
        res, status, ev = {"text": f"{type(e).__name__}: {e}"[:500]}, "failed", "tool.failed"

    def fn(x):
        a = next(y for y in x["approvals"] if y["id"] == aid)
        a.update(status=status, decided_by=by, decided_at=now(), result=res)
        return dict(a)
    out = store.update(sid, fn)
    store.emit(sid, ev, ap["turn_id"], approval=aid, tool=ap["name"], chars=len(res["text"]))
    return out


def decide(sid: str, aid: str, decision: str, edits: dict | None = None, reviewer: str = "researcher") -> dict:
    """The researcher's decision on a tool call or an action proposal (the only way anything risky runs)."""
    if decision not in ("approve", "reject"):
        raise AIWSError("decision must be approve or reject")
    s = store.get(sid)
    ap = next((x for x in s["approvals"] if x["id"] == aid), None)
    if not ap:
        raise AIWSError("Approval not found")
    if ap["status"] != "pending":
        raise AIWSError(f"Already {ap['status']}")
    if edits:
        if ap["kind"] == "action":
            adapters.validate_action(s["binding"]["module"], ap["name"], edits)
        store.update(sid, lambda x: next(y for y in x["approvals"] if y["id"] == aid).update(args=edits, edited=True))
    if decision == "reject":
        store.update(sid, lambda x: next(y for y in x["approvals"] if y["id"] == aid).update(
            status="rejected", decided_by=reviewer, decided_at=now()))
        store.emit(sid, "permission.denied", ap["turn_id"], approval=aid, name=ap["name"], by=reviewer)
    elif ap["kind"] == "tool":
        _exec_tool(sid, aid, reviewer)
    else:
        _exec_action(sid, aid, reviewer)
    s = store.get(sid)
    t = next((x for x in s["turns"] if x["id"] == ap["turn_id"]), None)
    if ap["kind"] == "tool" and t and t["status"] == "waiting_approval" and \
            not any(x["status"] == "pending" and x["kind"] == "tool" for x in s["approvals"] if x["turn_id"] == t["id"]):
        _spawn(sid, t["id"], "after_tools")
    return next(x for x in store.get(sid)["approvals"] if x["id"] == aid)


def _exec_action(sid: str, aid: str, by: str) -> None:
    s = store.get(sid)
    ap = next(x for x in s["approvals"] if x["id"] == aid)
    try:
        res, status, ev = adapters.execute(ap["name"], ap["args"], s), "executed", "action.completed"
    except Exception as e:
        res, status, ev = {"error": f"{type(e).__name__}: {e}"[:500]}, "failed", "action.failed"
    store.update(sid, lambda x: next(y for y in x["approvals"] if y["id"] == aid).update(
        status=status, decided_by=by, decided_at=now(), result=res))
    store.emit(sid, ev, ap["turn_id"], approval=aid, action=ap["name"])


def launch(sid: str, tid: str, edited_context: str | None = None) -> dict:
    s = store.get(sid)
    t = _turn(s, tid)
    if t["status"] != "awaiting_launch":
        raise AIWSError(f"Turn is {t['status']}")
    fields = {"launched": True, "status": "running"}
    if edited_context is not None:
        from backend.providers.privacy import sanitize
        fields.update(context_text=sanitize(edited_context[:200_000])[0], context_edited=True)
    _set(sid, tid, **fields)
    _spawn(sid, tid, "launch")
    return _turn(store.get(sid), tid)


def cancel(sid: str, tid: str) -> dict:
    s = store.get(sid)
    t = _turn(s, tid)
    if t["status"] not in ("running", "queued", "waiting_approval", "awaiting_launch"):
        raise AIWSError(f"Turn is {t['status']}")
    with _lock:
        r = _running.get(tid)
    if r:
        r["cancel"].set()
        if r["rid"]:
            from backend.providers import gateway as GS
            try:
                GS.cancel(r["rid"])
            except GS.GatewayError:
                pass
    if t["status"] in ("waiting_approval", "awaiting_launch") or not r:
        _set(sid, tid, status="cancelled", ended=now())
        store.emit(sid, "turn.cancelled", tid)

    def drop(x):  # tool calls waiting for this turn can no longer run
        for a in x["approvals"]:
            if a["turn_id"] == tid and a["kind"] == "tool" and a["status"] == "pending":
                a.update(status="cancelled", decided_at=now())
    store.update(sid, drop)
    return _turn(store.get(sid), tid)


def launch_plan(sid: str, tid: str) -> dict:
    """Everything the provider will get, shown BEFORE launch (manual mode, CLI `phdlab chat plan`)."""
    s = store.get(sid)
    t = _turn(s, tid)
    v = values(t["effective"])
    pid = v["provider"]
    plan = {"provider": pid, "model": v["model"] or "(provider default)", "reasoning": v["reasoning"],
            "context_manifest": t["manifest"], "context_chars": len(t.get("context_text") or ""),
            "mcp_tools": mcp_policy.allowed(v["mcp_tools"]), "memory_mode": v["memory_mode"], "notes": t["notes"]}
    if pid.startswith("cli:"):
        from backend.providers import cli as C
        from backend.providers import cli_space as W
        name = pid[4:]
        root = W.root()
        ws = root / name / "sessions" / (s["gateway_session"] or "<new gateway session>")
        argv = C.CONNECTORS[name].argv({"profile": v["security_profile"], "model": v["model"],
                                        "reasoning": v["reasoning"]}) if C.CONNECTORS[name].binary() else []
        plan.update(transport="cli", command=argv, cwd=str(ws / "workspace"), env_allowlist=sorted(W.ENV_ALLOW),
                    mounts=[{"path": str(ws / "context"), "access": "read-only", "what": "compiled context + manifest"},
                            {"path": str(ws / "workspace"), "access": "read-write" if v["security_profile"] == "assisted" else "read-only",
                             "what": "the only working directory"}],
                    security_profile=v["security_profile"], isolation=t.get("isolation"))
    else:
        plan.update(transport="http", command=[], cwd="", env_allowlist=[], mounts=[],
                    endpoint="local model server" if pid in ENGINE else "provider HTTPS API (key never shown)",
                    security_profile="n/a — the provider executes nothing on this computer")
    return plan


# ------------------------------------------------------------------ provider dispatch
def _history(s: dict, tid: str) -> list:
    msgs = [m for m in s["messages"] if m["role"] in ("user", "assistant") and m["turn_id"] != tid and
            not m.get("not_retained")]
    return [{"role": m["role"], "content": m["content"]} for m in msgs[-20:]]


def _dispatch(sid: str, tid: str) -> None:
    s = store.get(sid)
    t = _turn(s, tid)
    v = values(t["effective"])
    pid = v["provider"]
    t0 = time.time()
    store.emit(sid, "message.started", tid, pid)
    if pid.startswith("cli:"):
        text, ws, err, cancelled = _cli(sid, tid, s, t, v)
    else:
        text, err, cancelled = _app(sid, tid, s, t, v)
        ws = None
    if cancelled:
        if text:
            store.add_message(sid, "assistant", text, tid, provider=pid, status="cancelled")
        _set(sid, tid, status="cancelled", ended=now())
        store.emit(sid, "turn.cancelled", tid, pid)
    elif err and not text:
        _fail(sid, tid, err)
        return
    else:
        _complete(sid, tid, text, ws, t0, err)
    with _lock:
        _running.pop(tid, None)


def _cancelled(tid: str) -> bool:
    with _lock:
        r = _running.get(tid)
    return bool(r and r["cancel"].is_set())


def _app(sid, tid, s, t, v):
    from backend.providers import models as llm
    from backend.core.config import load_config
    system = instructions(s["binding"]["module"], t.get("skill", "")) + "\n" + (t.get("context_text") or "")
    if v["provider"] not in ENGINE and v["provider"] != "app:auto":
        from backend.providers.privacy import sanitize
        system = sanitize(system)[0]  # leaves the machine: credentials redacted, code under block_source_code
    msgs = _history(s, tid) + [{"role": "user", "content": t["question"]}]
    out, err = [], ""
    limit = float(load_config()["aiws"].get("max_turn_s") or 900)

    async def go():
        nonlocal err
        llm.REASONING.set(v["reasoning"])  # the chat's "cấp độ tư duy" for this answer (this task only)
        if v["provider"] == "app:auto":
            gen = llm.stream_agent(_agent(t), system, msgs, max_tokens=6000)
        else:
            eng = ENGINE.get(v["provider"]) or v["provider"][4:]
            gen = _engine_stream(llm, load_config(), eng, system, msgs, v["model"] or None)
        start = time.time()
        try:
            async for kind, val in gen:
                if _cancelled(tid) or time.time() - start > limit:
                    if not _cancelled(tid):
                        err = f"stopped after {int(limit)} s (aiws.max_turn_s)"
                    break
                if kind == "delta":
                    out.append(val)
                    store.emit(sid, "message.delta", tid, v["provider"], text=val)
        except llm.LLMError as e:
            err = str(e)
        finally:
            await gen.aclose()
    async def bounded():
        nonlocal err
        task = asyncio.create_task(go())
        started = time.monotonic()
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=0.05)
                if done:
                    break
                if _cancelled(tid) or time.monotonic() - started >= limit:
                    if not _cancelled(tid):
                        err = f"stopped after {limit:g} s (aiws.max_turn_s)"
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    return
            await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    asyncio.run(bounded())
    return "".join(out).strip(), err, _cancelled(tid)


async def _engine_stream(llm, cfg, eng, system, msgs, model):
    raw, emitted = "", 0
    async for chunk in llm._stream_engine(cfg, eng, system, msgs, 6000, 0.3, model, "interactive"):
        raw += chunk
        vis = llm.strip_think(raw)
        if len(vis) > emitted:
            yield ("delta", vis[emitted:])
            emitted = len(vis)


def _cli(sid, tid, s, t, v):
    from backend.providers import gateway as GS
    name = v["provider"][4:]
    ctx_text = instructions(s["binding"]["module"], t.get("skill", "")) + "\n" + (t.get("context_text") or "")
    try:
        r = GS.prepare(t["question"], name, session_id=s["gateway_session"], profile=v["security_profile"],
                       allow_weaker=bool(v.get("consent_weaker")), module_context=ctx_text,
                       memory=False)  # upstream context.compile already selected/versioned the memory for this turn
    except GS.GatewayError as e:
        return "", None, str(e), False
    store.update(sid, lambda x: x.update(gateway_session=r["session_id"]))
    allow = mcp_policy.allowed(v["mcp_tools"])
    mcp = {"token": mcp_policy.issue(sid, allow), "tools": allow}  # every CLI: scoped grant (providers/firewall.py)
    with _lock:
        _running.setdefault(tid, {"cancel": threading.Event(), "rid": ""})["rid"] = r["id"]
    _set(sid, tid, gateway_request=r["id"])
    try:
        GS.send(r["id"], base_url=t["base_url"], mcp=mcp, model=v["model"],
                reasoning=v["reasoning"] if v["reasoning"] in providers.REASONING.get(name, ()) else "")
        after, text, err = 0, [], ""
        while True:
            e = GS.wait_events(r["id"], after, 0.5)
            after = e["next"]
            for ev in e["events"]:
                ty = ev["type"]
                if ty == "text_delta":
                    text.append(ev.get("text", ""))
                    store.emit(sid, "message.delta", tid, v["provider"], text=ev.get("text", ""))
                elif ty == "tool_call":
                    store.emit(sid, "tool.started", tid, v["provider"], tool=ev.get("name", ""), detail=ev.get("detail", ""),
                               by="provider")
                elif ty == "tool_result":
                    store.emit(sid, "tool.failed" if ev.get("is_error") else "tool.completed", tid, v["provider"],
                               tool=ev.get("name", ""), by="provider")
                elif ty == "status" and ev.get("state") == "usage":
                    store.emit(sid, "usage.updated", tid, v["provider"], usage=ev.get("usage") or {})
                elif ty == "error":
                    err = ev.get("message", "")
                    store.emit(sid, "error", tid, v["provider"], message=err)
            if not e["events"] and e["status"] not in ("running", "ready", "starting"):
                break
            if _cancelled(tid):  # cancelled before the CLI process existed: keep asking until it is stopped
                try:
                    GS.cancel(r["id"])
                except GS.GatewayError:  # it finished in the meantime
                    pass
    finally:
        mcp_policy.revoke(mcp["token"])
    final = GS.get(r["id"])
    answer = final.get("answer") or "".join(text)
    from backend.providers import cli_space as W
    ws = W.root() / name / "sessions" / r["session_id"] / "workspace"
    return answer.strip(), ws, err or "; ".join(final.get("errors") or []), final.get("status") == "cancelled"


def _complete(sid: str, tid: str, text: str, ws, t0: float, err: str) -> None:
    s = store.get(sid)
    t = _turn(s, tid)
    v = values(t["effective"])
    pid = v["provider"]
    m = store.add_message(sid, "assistant", text, tid, provider=pid, model=v["model"], manifest_id=(t["manifest"] or {}).get("id"),
                          status="partial" if err else "complete")
    store.emit(sid, "message.completed", tid, pid, message_id=m["id"], text=text, chars=len(text), warning=err)
    s = store.get(sid)
    for blk in ACTION.findall(text):
        try:
            data = json.loads(blk)
            spec = adapters.validate_action(s["binding"]["module"], str(data.get("action")), data.get("args") or {})
        except (ValueError, AttributeError) as e:
            store.emit(sid, "action.failed", tid, pid, reason=f"invalid proposal: {e}"[:300])
            continue
        ap = {"id": new_id("ap", 4), "turn_id": tid, "kind": "action", "name": spec["name"], "args": data.get("args") or {},
              "risk": spec["risk"], "status": "pending", "created": now(), "reason": "đề xuất của mô hình"}
        store.update(sid, lambda x, ap=ap: x["approvals"].append(ap))
        store.emit(sid, "action.proposed", tid, pid, approval=ap["id"], action=spec["name"])
        store.emit(sid, "action.approval_required", tid, pid, approval=ap["id"], action=spec["name"], risk=spec["risk"])
    if v["collect_artifacts"]:
        artifacts.from_text(sid, tid, text, pid)
        if ws is not None:
            artifacts.from_workspace(sid, tid, ws, t0, pid)
    memory_modes.after_turn(store.get(sid), m, v)
    if v["summaries"]:
        def summ(x):
            qa = [f"Q: {y['content'].splitlines()[0][:140]}" if y["role"] == "user" else f"A: {y['content'][:160]}"
                  for y in x["messages"][-12:] if y["role"] in ("user", "assistant") and y["content"]]
            x["summary"] = "\n".join(qa)
        store.update(sid, summ)
    if not v["keep_history"]:
        def drop(x):
            for y in x["messages"]:
                if y["turn_id"] == tid:
                    y.update(content="[not retained — keep_history is off]", not_retained=True)
        store.update(sid, drop)
    _set(sid, tid, status="completed", answer_id=m["id"], ended=now(), error=err)
    store.emit(sid, "turn.completed", tid, pid, message_id=m["id"], seconds=round(time.time() - t0, 2))


def retry(sid: str, base_url: str = "", overrides: dict | None = None) -> dict:
    s = store.get(sid)
    last = next((m for m in reversed(s["messages"]) if m["role"] == "user"), None)
    if not last:
        raise AIWSError("Nothing to retry")
    return start(sid, last["content"], overrides, base_url, replace_from=last["id"])
