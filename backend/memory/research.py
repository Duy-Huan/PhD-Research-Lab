"""Research Memory (CONTEXT_MEMORY.md tier "Research"): the scientific meaning of experiments, with POINTERS to the
external systems that hold the raw data (Target §10/§14):

    hypotheses   HYPE-001 …  text, status (proposed/testing/supported/refuted/inconclusive/abandoned)
    experiments  EXP-001 …   hypothesis_id, run_id, clearml_task_id, git_sha, dataset_version, environment,
                             metrics summary, observation, interpretation, decision, conclusion, next_action, verdict
    failures     FAIL-001 …  validated failures / refuted hypotheses (never proposed again)

Native process journals keep run logs and checkpoints; legacy tracker references remain readable; this store keeps only IDs + research meaning. Nothing here is written
by an AI agent on its own: records are created by explicit researcher actions (or synced from the plan's hypotheses).
"""
from __future__ import annotations

import re

from backend.memory import mem_dir
from backend.memory.store import JsonStore, now

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
        from backend.execution.sandbox import get_run
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
