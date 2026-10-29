"""Per-criterion scoring of a qualification campaign (v6.6.4, agent/PLAN_6.6.4_L3.md B5).

agent/research-quality-objectives.json changes only from measured results: apply() writes criterion status and evidence
from a scored campaign record, never from role names, coverage, model self-reports or one polished paper.

Campaign record (JSON written by the campaign runner, phase C):
  {"campaign_id", "suite_digest", "planned_cases": N,
   "cases": [{"case_id", "attempts": [...], "interventions": {category: count},
              "measurements": {"RQ-04": {"passed": bool, "note": str, "evidence": [{"path", "sha256"}]}}}]}

Rules (conservative):
  QUALIFIED      every planned case measured the criterion, passed, and every evidence file resolves to its sha256
  NOT_QUALIFIED  any case measured it and failed
  INCONCLUSIVE   no failure, but a case did not measure it or its evidence does not resolve
  NOT_RUN        no case measured it
  RQ-13          also needs the suite digest and every planned case attempted (denominators reported)
  RQ-14          also needs zero scientific_rescue and zero risk_exception interventions across the cases (B2)
  L3             only when all 14 criteria are QUALIFIED
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBJECTIVES = ROOT / "agent" / "research-quality-objectives.json"
CRITERIA = [f"RQ-{i:02d}" for i in range(1, 15)]
COUNTED = ("scientific_rescue", "risk_exception")


def _resolves(evidence: list, base: Path) -> bool:
    if not evidence:
        return False
    for ref in evidence:
        path = (base / str(ref.get("path", ""))).resolve()
        if base.resolve() not in path.parents or not path.is_file():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
            return False
    return True


def score(campaign: dict, base: Path) -> dict:
    """Status and evidence of every criterion; `base` is the folder evidence paths are relative to."""
    cases = campaign.get("cases") or []
    planned = int(campaign.get("planned_cases") or 0)
    out = {}
    for cid in CRITERIA:
        measured = [(c["case_id"], c.get("measurements", {}).get(cid)) for c in cases]
        seen = [(case, m) for case, m in measured if m is not None]
        reasons, evidence = [], []
        if not seen:
            status = "NOT_RUN"
        elif any(not m.get("passed") for _, m in seen):
            status = "NOT_QUALIFIED"
            reasons += [f"{case}: {str(m.get('note') or 'failed')[:200]}" for case, m in seen if not m.get("passed")]
        elif len(seen) < max(planned, len(cases)) or any(not _resolves(m.get("evidence") or [], base) for _, m in seen):
            status = "INCONCLUSIVE"
            reasons += [f"{case}: not measured" for case, m in measured if m is None]
            reasons += [f"{case}: evidence missing or changed" for case, m in seen if not _resolves(m.get("evidence") or [], base)]
        else:
            status = "QUALIFIED"
        for _, m in seen:
            evidence += m.get("evidence") or []
        out[cid] = {"status": status, "cases_measured": len(seen), "cases_planned": planned, "reasons": reasons[:20],
                    "evidence_refs": evidence[:50]}
    attempted = sum(1 for c in cases if c.get("attempts"))
    if out["RQ-13"]["status"] == "QUALIFIED" and (not campaign.get("suite_digest") or attempted < planned):
        out["RQ-13"].update(status="NOT_QUALIFIED", reasons=[f"Suite digest {'present' if campaign.get('suite_digest') else 'missing'}; "
                                                              f"{attempted}/{planned} planned cases attempted"])
    rescues = {k: sum(int((c.get("interventions") or {}).get(k, 0)) for c in cases) for k in COUNTED}
    if out["RQ-14"]["status"] == "QUALIFIED" and any(rescues.values()):
        out["RQ-14"].update(status="NOT_QUALIFIED", reasons=[f"Human {k}: {v}" for k, v in rescues.items() if v])
    qualified = all(v["status"] == "QUALIFIED" for v in out.values())
    return {"campaign_id": campaign.get("campaign_id"), "suite_digest": campaign.get("suite_digest"), "criteria": out,
            "denominators": {"planned_cases": planned, "attempted_cases": attempted, "cases_recorded": len(cases)},
            "interventions": rescues, "achieved_level": "L3" if qualified else None,
            "qualification_status": "QUALIFIED_SCOPED_L3" if qualified else "NOT_DEMONSTRATED"}


def apply(campaign_path: Path, objectives: Path = OBJECTIVES) -> dict:
    """Write the measured scores into the objectives file (status, evidence, campaign reference). Returns the scores."""
    campaign_path = Path(campaign_path)
    raw = campaign_path.read_bytes()
    scored = score(json.loads(raw), campaign_path.parent)
    data = json.loads(objectives.read_text("utf-8"))
    for c in data["criteria"]:
        s = scored["criteria"].get(c["id"])
        if s:
            c["status"], c["evidence_refs"] = s["status"], s["evidence_refs"]
            c["measured_by"] = {"campaign_id": scored["campaign_id"], "campaign_sha256": hashlib.sha256(raw).hexdigest(),
                                "reasons": s["reasons"]}
    data["achieved_level"] = scored["achieved_level"]
    data["qualification_status"] = scored["qualification_status"]
    objectives.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return scored
