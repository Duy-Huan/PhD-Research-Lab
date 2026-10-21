"""Evidence layer (v3.3 §9-10): first-class Claims and Evidence with provenance, next to Research Memory.

    Hypothesis ──tested_by──▶ Experiment ──produces──▶ Evidence ──supports/refutes──▶ Claim ──informs──▶ Decision
    Paper ──states──▶ Claim                                     (decisions carry evidence_ids, see memory.add_decision)

claims    CLM-001 …  text, hypothesis_id, source_refs (lit:<bibkey>, EXP-…), status derived from VALIDATED evidence
evidence  EVID-001 … claim_id, source_type (experiment|paper|run|observation|human), stance (supports|refutes|neutral),
                     status (candidate|validated|rejected), metric {name, value, unit}, origin (human | ai | provider:<id>)
                     + provenance copied from the experiment record at write time: run_id, git_sha, clearml_task_id,
                     dataset_version, environment — so the evidence keeps its pointers even if the experiment is edited.

Integrity rules
- Only `validated` evidence changes a claim's status; AI/provider-originated evidence is always written as `candidate`
  (it has to be validated by the researcher — lifecycle.py), whatever the caller asks for.
- Evidence is never deleted when a summary exists; `rejected` keeps the record for audit.
- Reuses the conventions of research.py: sequential ids, JsonStore (atomic write, per-file lock).
"""
from __future__ import annotations

import re

from backend.memory import mem_dir
from backend.memory.store import JsonStore, now

_store = JsonStore(lambda: mem_dir() / "evidence.json", {"seq": {}, "claims": [], "evidence": []})

SOURCE_TYPES = ("experiment", "paper", "run", "observation", "human")
STANCES = ("supports", "refutes", "neutral")
EV_STATUS = ("candidate", "validated", "rejected")
CLAIM_STATUS = ("proposed", "supported", "refuted", "contested")
ID_RE = re.compile(r"^(CLM|EVID)-\d{3,6}$")
REF_RE = re.compile(r"^(lit:[\w:.-]{1,80}|(HYPE|EXP|FAIL|CLM|EVID)-\d{3,6}|run:[\w-]{6,60}|D[0-9a-f]{6})$")
PROV_FIELDS = ("run_id", "git_sha", "clearml_task_id", "dataset_version", "environment")


class EvidenceError(ValueError):
    pass


def _next_id(st: dict, prefix: str) -> str:
    n = int(st["seq"].get(prefix, 0)) + 1
    st["seq"][prefix] = n
    return f"{prefix}-{n:03d}"


def load() -> dict:
    return _store.load()


def _derive_status(st: dict, cid: str) -> str:
    ev = [e for e in st["evidence"] if e.get("claim_id") == cid and e.get("status") == "validated"]
    sup = sum(1 for e in ev if e["stance"] == "supports")
    ref = sum(1 for e in ev if e["stance"] == "refutes")
    if sup and ref:
        return "contested"
    return "supported" if sup else ("refuted" if ref else "proposed")


def add_claim(text: str, hypothesis_id: str = "", source_refs=None, origin: str = "human") -> dict:
    text = (text or "").strip()
    if not text:
        raise EvidenceError("Empty claim")
    refs = [str(r).strip() for r in (source_refs or []) if str(r).strip()]
    bad = [r for r in refs if not REF_RE.match(r)]
    if bad:
        raise EvidenceError(f"Invalid source reference(s): {', '.join(bad[:3])}")
    if hypothesis_id:
        from backend.memory import research
        if not any(h["id"] == hypothesis_id for h in research.load()["hypotheses"]):
            raise EvidenceError(f"Hypothesis {hypothesis_id} not found")

    def put(st):
        c = {"id": _next_id(st, "CLM"), "text": text[:2000], "hypothesis_id": hypothesis_id[:20], "source_refs": refs[:20],
             "status": "proposed", "origin": origin[:60], "created": now(), "updated": now()}
        st["claims"].append(c)
        return c
    return _store.update(put)


def _experiment(eid: str) -> dict:
    from backend.memory import research
    e = next((x for x in research.load()["experiments"] if x["id"] == eid), None)
    if not e:
        raise EvidenceError(f"Experiment {eid} not found")
    return e


def add_evidence(data: dict, origin: str = "human") -> dict:
    d = dict(data or {})
    st0 = load()
    cid = d.get("claim_id") or ""
    if cid and not any(c["id"] == cid for c in st0["claims"]):
        raise EvidenceError(f"Claim {cid} not found")
    stype = d.get("source_type") or ("experiment" if d.get("experiment_id") else "observation")
    if stype not in SOURCE_TYPES:
        raise EvidenceError(f"source_type must be one of {', '.join(SOURCE_TYPES)}")
    stance = d.get("stance") or "supports"
    if stance not in STANCES:
        raise EvidenceError(f"stance must be one of {', '.join(STANCES)}")
    prov = {}
    if d.get("experiment_id"):
        e = _experiment(d["experiment_id"])
        prov = {k: e.get(k, "") for k in PROV_FIELDS}
    elif stype == "experiment":
        raise EvidenceError("experiment evidence needs experiment_id")
    if stype == "paper" and not d.get("paper_key"):
        raise EvidenceError("paper evidence needs paper_key")
    metric = d.get("metric") or {}
    if metric:
        if not isinstance(metric, dict) or not str(metric.get("name") or "").strip():
            raise EvidenceError("metric needs a name")
        try:
            metric = {"name": str(metric["name"])[:60], "value": float(metric.get("value")), "unit": str(metric.get("unit") or "")[:20]}
        except (TypeError, ValueError):
            raise EvidenceError("metric value must be a number")
    status = d.get("status") if d.get("status") in EV_STATUS else "candidate"
    if origin != "human" and status == "validated":
        status = "candidate"  # integrity: AI / provider evidence is never self-validated

    def put(st):
        ev = {"id": _next_id(st, "EVID"), "claim_id": cid, "source_type": stype, "stance": stance, "status": status,
              "experiment_id": str(d.get("experiment_id") or "")[:20], "paper_key": str(d.get("paper_key") or "")[:80],
              "text": str(d.get("text") or "")[:2000], "metric": metric, "origin": origin[:60], "created": now(), "updated": now()}
        for k in PROV_FIELDS:
            ev[k] = str(d.get(k) or prov.get(k) or "")[:300]
        st["evidence"].append(ev)
        if cid:
            for c in st["claims"]:
                if c["id"] == cid:
                    c["status"], c["updated"] = _derive_status(st, cid), now()
        return ev
    return _store.update(put)


def get(item_id: str) -> dict:
    if not ID_RE.match(item_id or ""):
        raise EvidenceError("Invalid id")
    st = load()
    key = "claims" if item_id.startswith("CLM") else "evidence"
    hit = next((x for x in st[key] if x["id"] == item_id), None)
    if not hit:
        raise EvidenceError(f"{item_id} not found")
    if key == "claims":
        return {**hit, "evidence": [e for e in st["evidence"] if e.get("claim_id") == item_id]}
    return hit


def for_experiment(eid: str) -> list:
    return [e for e in load()["evidence"] if e.get("experiment_id") == eid]


def delete(item_id: str) -> None:
    """Only claims without evidence and CANDIDATE evidence can be deleted; validated evidence can only be rejected."""
    if not ID_RE.match(item_id or ""):
        raise EvidenceError("Invalid id")

    def put(st):
        if item_id.startswith("CLM"):
            if any(e.get("claim_id") == item_id for e in st["evidence"]):
                raise EvidenceError("Claim has evidence — reject the evidence instead of deleting the claim")
            st["claims"] = [c for c in st["claims"] if c["id"] != item_id]
            return
        ev = next((e for e in st["evidence"] if e["id"] == item_id), None)
        if not ev:
            raise EvidenceError(f"{item_id} not found")
        if ev["status"] != "candidate":
            raise EvidenceError("Validated/rejected evidence is kept for provenance — set status 'rejected' instead")
        st["evidence"] = [e for e in st["evidence"] if e["id"] != item_id]
    _store.update(put)
