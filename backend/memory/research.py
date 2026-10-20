"""Research Memory (CONTEXT_MEMORY.md tier "Research"): the scientific meaning of experiments, with POINTERS to the
external systems that hold the raw data (Target §10/§14):

    hypotheses   HYPE-001 …  text, status (proposed/testing/supported/refuted/inconclusive/abandoned)
    experiments  EXP-001 …   hypothesis_id, run_id, clearml_task_id, git_sha, dataset_version, environment,
                             metrics summary, observation, interpretation, decision, conclusion, next_action, verdict
    failures     FAIL-001 …  validated failures / refuted hypotheses (never proposed again)

ClearML keeps the run tables, logs, checkpoints; this store keeps only IDs + research meaning. Nothing here is written
by an AI agent on its own: records are created by explicit researcher actions (or synced from the plan's hypotheses).
"""
from __future__ import annotations

import re

from . import mem_dir
from .store import JsonStore, now

_store = JsonStore(lambda: mem_dir() / "research.json", {"seq": {}, "hypotheses": [], "experiments": [], "failures": []})

H_STATUS = ("proposed", "testing", "supported", "refuted", "inconclusive", "abandoned")
VERDICTS = ("", "supports", "refutes", "inconclusive")
EXP_TEXT = ("title", "observation", "interpretation", "decision", "conclusion", "next_action", "dataset_version",
            "environment", "notes")
EXP_REFS = ("hypothesis_id", "run_id", "clearml_task_id", "clearml_url", "git_sha", "git_branch", "repository_url", "model_id")
ID_RE = re.compile(r"^(HYPE|EXP|FAIL)-\d{3,6}$")


class ResearchError(ValueError):
    pass


def _next_id(st: dict, prefix: str) -> str:
    n = int(st["seq"].get(prefix, 0)) + 1
    st["seq"][prefix] = n
    return f"{prefix}-{n:03d}"


def _norm(t: str) -> str:
    return re.sub(r"[^\w]+", " ", (t or "").lower()).strip()


def load() -> dict:
    return _store.load()


# ------------------------------------------------------------------ hypotheses
def add_hypothesis(text: str, source: str = "researcher", status: str = "proposed", plan_key: str = "") -> dict:
    text = (text or "").strip()
    if not text:
        raise ResearchError("Empty hypothesis")

    def put(st):
        h = {"id": _next_id(st, "HYPE"), "text": text[:2000], "status": status if status in H_STATUS else "proposed",
             "source": source[:120], "plan_key": plan_key[:20], "created": now(), "updated": now()}
        st["hypotheses"].append(h)
        return h
    return _store.update(put)


def update_hypothesis(hid: str, patch: dict) -> dict:
    def put(st):
        for h in st["hypotheses"]:
            if h["id"] == hid:
                if "text" in patch and str(patch["text"]).strip():
                    h["text"] = str(patch["text"]).strip()[:2000]
                if patch.get("status") in H_STATUS:
                    h["status"] = patch["status"]
                h["updated"] = now()
                return h
        raise ResearchError(f"Hypothesis {hid} not found")
    return _store.update(put)


def sync_from_plan(hypotheses: list) -> list:
    """Give every hypothesis of the research plan (Tier 3, e.g. 'H2: …') a stable HYPE id.
    Matching is by plan key first, then by normalised text, so regenerating the plan keeps the ids."""
    items = []
    for raw in hypotheses or []:
        m = re.match(r"\s*(H\d+)\s*[:.)-]\s*(.+)", str(raw), re.S)
        items.append((m.group(1), m.group(2).strip()) if m else ("", str(raw).strip()))

    def put(st):
        out = []
        for key, text in items:
            if not text:
                continue
            hit = next((h for h in st["hypotheses"] if h.get("source") == "plan" and key and h.get("plan_key") == key), None) \
                or next((h for h in st["hypotheses"] if _norm(h["text"]) == _norm(text)), None)
            if hit:
                if hit.get("source") == "plan" and _norm(hit["text"]) != _norm(text):
                    hit["text"], hit["updated"] = text[:2000], now()
                out.append(hit)
                continue
            h = {"id": _next_id(st, "HYPE"), "text": text[:2000], "status": "proposed", "source": "plan",
                 "plan_key": key, "created": now(), "updated": now()}
            st["hypotheses"].append(h)
            out.append(h)
        return out
    return _store.update(put)


# ------------------------------------------------------------------ experiments
def _run_refs(run_id: str) -> dict:
    """Pointers taken from the local run record (git commit, ClearML task, environment, measured metrics)."""
    try:
        from ..sandbox import get_run
        r = get_run(run_id)
    except Exception as e:
        raise ResearchError(f"Run {run_id} not found ({e})")
    git = r.get("git") or {}
    out = {"run_id": run_id, "git_sha": git.get("sha", ""), "git_branch": git.get("branch", ""),
           "repository_url": git.get("remote", ""), "metrics": {k: v for k, v in (r.get("metrics") or {}).items()
                                                                 if isinstance(v, (int, float))},
           "environment": r.get("environment") or r.get("mode", "")}
    if isinstance(out["environment"], dict):
        out["environment"] = ", ".join(f"{k}={v}" for k, v in out["environment"].items() if v not in (None, ""))
    cm = r.get("clearml") or {}
    if cm.get("task_id"):
        out.update(clearml_task_id=cm["task_id"], clearml_url=cm.get("url", ""))
    return out


def add_experiment(data: dict) -> dict:
    data = dict(data or {})
    refs = _run_refs(data["run_id"]) if data.get("run_id") else {}
    hid = data.get("hypothesis_id") or ""
    st0 = load()
    if hid and not any(h["id"] == hid for h in st0["hypotheses"]):
        raise ResearchError(f"Hypothesis {hid} not found")

    def put(st):
        e = {"id": _next_id(st, "EXP"), "created": now(), "updated": now(), "verdict": "", "metrics": {}}
        e.update({k: str(data.get(k) or "")[:4000] for k in EXP_TEXT})
        e.update({k: str(data.get(k) or "")[:300] for k in EXP_REFS})
        for k, v in refs.items():  # measured / recorded values win over typed ones only when the typed one is empty
            if k == "metrics" or not e.get(k):
                e[k] = v
        if data.get("verdict") in VERDICTS:
            e["verdict"] = data["verdict"]
        if not e["title"]:
            e["title"] = f"Experiment {e['id']}" + (f" (run {e['run_id']})" if e.get("run_id") else "")
        st["experiments"].append(e)
        return e
    return _store.update(put)


def update_experiment(eid: str, patch: dict) -> dict:
    refs = _run_refs(patch["run_id"]) if patch.get("run_id") else None

    def put(st):
        for e in st["experiments"]:
            if e["id"] == eid:
                for k in EXP_TEXT:
                    if k in patch:
                        e[k] = str(patch[k] or "")[:4000]
                for k in EXP_REFS:
                    if k in patch:
                        e[k] = str(patch[k] or "")[:300]
                if refs:
                    e.update({k: v for k, v in refs.items() if v})
                if patch.get("verdict") in VERDICTS:
                    e["verdict"] = patch["verdict"]
                e["updated"] = now()
                return e
        raise ResearchError(f"Experiment {eid} not found")
    return _store.update(put)


FAIL_FIELDS = ("experiment_id", "model", "dataset", "environment", "configuration", "error", "cause", "observation", "lesson",
               "avoidance_rule")


def add_failure(text: str, hypothesis_id: str = "", run_id: str = "", reason: str = "", **structured) -> dict:
    """A validated failure (v3.3 failure memory): what failed + structured fields (model, dataset, environment,
    configuration, error, cause, observation, lesson, avoidance_rule) so it is found again when a similar experiment is
    planned. `reason` stays the free-text cause of v3.2 records."""
    if not (text or "").strip():
        raise ResearchError("Describe the failure")
    unknown = set(structured) - set(FAIL_FIELDS) - {"origin"}
    if unknown:
        raise ResearchError(f"Unknown failure field(s): {', '.join(sorted(unknown))}")
    eid = structured.get("experiment_id") or ""
    if eid and not any(e["id"] == eid for e in load()["experiments"]):
        raise ResearchError(f"Experiment {eid} not found")

    def put(st):
        f = {"id": _next_id(st, "FAIL"), "text": text.strip()[:2000], "hypothesis_id": hypothesis_id[:20],
             "run_id": run_id[:80], "reason": reason[:1000], "validated": True, "created": now(),
             "origin": str(structured.get("origin") or "human")[:60]}
        for k in FAIL_FIELDS:
            f[k] = str(structured.get(k) or "")[:1000]
        if not f["cause"] and reason:
            f["cause"] = reason[:1000]
        st["failures"].append(f)
        return f
    return _store.update(put)


def update_failure(fid: str, patch: dict) -> dict:
    def put(st):
        for f in st["failures"]:
            if f["id"] == fid:
                for k in FAIL_FIELDS + ("text", "reason"):
                    if k in patch:
                        f[k] = str(patch[k] or "")[:2000]
                f["updated"] = now()
                return f
        raise ResearchError(f"Failure {fid} not found")
    return _store.update(put)


def delete(item_id: str) -> None:
    if not ID_RE.match(item_id or ""):
        raise ResearchError("Invalid id")
    key = {"HYPE": "hypotheses", "EXP": "experiments", "FAIL": "failures"}[item_id.split("-")[0]]

    def put(st):
        before = len(st[key])
        st[key] = [x for x in st[key] if x["id"] != item_id]
        if len(st[key]) == before:
            raise ResearchError(f"{item_id} not found")
    _store.update(put)


def record_clearml(run_id: str, task_id: str, url: str = "") -> int:
    """Attach a ClearML task to every experiment record of this run (after a successful sync)."""
    def put(st):
        n = 0
        for e in st["experiments"]:
            if e.get("run_id") == run_id:
                e["clearml_task_id"], e["clearml_url"], e["updated"] = task_id, url, now()
                n += 1
        return n
    return _store.update(put)


# ------------------------------------------------------------------ timeline (signature view of the Control Center)
def timeline(limit: int = 200) -> list:
    """Chronological research events: hypothesis → experiment → result/failure → interpretation → decision → next step."""
    st = load()
    ev = []
    for h in st["hypotheses"]:
        ev.append({"ts": h["created"], "kind": "hypothesis", "id": h["id"], "title": h["text"][:160], "status": h["status"], "links": []})
    for e in st["experiments"]:
        links = [x for x in (e.get("hypothesis_id"), e.get("run_id") and f"run:{e['run_id']}",
                             e.get("clearml_task_id") and f"clearml:{e['clearml_task_id']}", e.get("git_sha") and f"git:{e['git_sha'][:10]}") if x]
        ev.append({"ts": e["created"], "kind": "experiment", "id": e["id"], "title": e["title"][:160], "status": e.get("verdict") or "open",
                   "links": links, "detail": {k: e.get(k) for k in ("observation", "interpretation", "decision", "conclusion", "next_action")
                                              if e.get(k)}, "metrics": e.get("metrics") or {}, "clearml_url": e.get("clearml_url", "")})
    for f in st["failures"]:
        ev.append({"ts": f["created"], "kind": "failure", "id": f["id"], "title": f["text"][:160], "status": "validated",
                   "links": [x for x in (f.get("hypothesis_id"), f.get("run_id") and f"run:{f['run_id']}") if x]})
    try:
        from . import load as load_legacy
        for d in load_legacy()["decisions"]:
            ev.append({"ts": d.get("created", ""), "kind": "decision", "id": d["id"], "title": d["text"][:160],
                       "status": "locked" if d.get("locked") else d.get("kind", ""), "links": []})
    except Exception:
        pass
    causal = {"hypothesis": 0, "decision": 1, "experiment": 2, "failure": 3}  # same second → research order
    ev.sort(key=lambda x: (x["ts"] or "", causal.get(x["kind"], 9), x["id"]))
    return ev[-limit:]
