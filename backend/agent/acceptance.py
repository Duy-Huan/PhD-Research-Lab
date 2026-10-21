"""AI Research OS acceptance: the eight criteria of the technical acceptance plan and their evidence.

    P0  Giới hạn quyền và tài nguyên        · Theo dõi tiến trình thống nhất
        Khôi phục context qua phiên         · Khôi phục workflow sau lỗi
    P1  Prompt tự kích hoạt workflow        · Thay thế provider không mất state
        Kiểm chứng research evidence        · Research → Code → Experiment

Principle of the plan: nothing is PASS because a screen shows it or an agent says it is done. The acceptance test suite
(tests/acceptance/) runs each capability for real against the backend and writes artifacts/acceptance/report.json with
the logs, states and artifacts it observed. evaluate() reads that report:

    PASS          every test of the criterion ran and passed (evidence listed)
    FAIL          a test of the criterion failed
    SIMULATED     only the dry-run simulation shows it (no executable evidence yet)
    NOT VERIFIED  no evidence at all
"""
from __future__ import annotations

import json
import time
from pathlib import Path

CRITERIA = (
    ("P0", "permissions_resources", "Giới hạn quyền và tài nguyên"),
    ("P0", "progress_tracking", "Theo dõi tiến trình thống nhất"),
    ("P0", "context_recovery", "Khôi phục context qua phiên"),
    ("P0", "workflow_recovery", "Khôi phục workflow sau lỗi"),
    ("P1", "prompt_workflow", "Prompt tự kích hoạt workflow"),
    ("P1", "provider_swap", "Thay thế provider không mất state"),
    ("P1", "evidence", "Kiểm chứng research evidence"),
    ("P1", "research_code_experiment", "Research → Code → Experiment"),
)
# what the dry-run simulation demonstrates (shown as SIMULATED when no executable evidence exists)
SIMULATED_BY = {"progress_tracking", "workflow_recovery", "research_code_experiment", "evidence"}


def report_path() -> Path:
    from backend.core.config import ROOT
    return ROOT / "artifacts" / "acceptance" / "report.json"


def load_report() -> dict:
    try:
        return json.loads(report_path().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def evaluate(simulation: dict | None = None) -> dict:
    rep = load_report()
    crit = rep.get("criteria") or {}
    out = []
    for prio, key, title in CRITERIA:
        c = crit.get(key) or {}
        tests = c.get("tests") or []
        if tests and all(t.get("status") == "passed" for t in tests):
            verdict = "PASS"
            evidence = "; ".join(f"{t['id']}" for t in tests)[:400]
        elif tests:
            verdict = "FAIL"
            evidence = "; ".join(f"{t['id']}: {t.get('status')}" for t in tests if t.get("status") != "passed")[:400]
        elif simulation is not None and key in SIMULATED_BY:
            verdict, evidence = "SIMULATED", f"chỉ có trong dry-run {simulation.get('id', '')}"
        else:
            verdict, evidence = "NOT VERIFIED", "chưa có test nghiệm thu chạy được"
        out.append({"priority": prio, "key": key, "title": title, "verdict": verdict, "evidence": evidence or "—"})
    return {"generated": rep.get("generated"), "criteria": out, "report": str(report_path()) if rep else ""}


def gaps() -> list:
    """What the real 90-day execution still needs, from the actual state of this machine (never a fixed claim)."""
    from backend.providers.research import describe_all
    out = []
    for p in describe_all():
        if not p["ready"]:
            out.append(f"{p['label']}: {p['state']} — {p['detail']}" + (f" (cách sửa: {p['setup'][0]})" if p["setup"] else ""))
    out += [
        "Thực thi bền vững nhiều ngày: run chỉ tiến triển khi PhD Lab đang mở; sau khi khởi động lại, run được khôi phục từ "
        "bước đã commit (không có scheduler chạy khi máy tắt).",
        "Dữ liệu thật: cần dataset (đường dẫn, phiên bản, license) cho baseline và các candidate.",
        "Multi-seed / ablation thật: cần thời gian GPU thực (RTX 3060 — mỗi lần 1 job) và ngân sách được duyệt.",
        "Đánh giá novelty / chất lượng khoa học: do nhà nghiên cứu quyết định; LLM self-review không phải chứng cứ duy nhất.",
        "ClearML server (tuỳ chọn): hiện ghi offline trong từng project; cần server nếu muốn dashboard dùng chung.",
    ]
    return out


def write_report(criteria: dict, meta: dict | None = None) -> Path:
    """Called by the acceptance test suite with {key: {"tests": [{id, status, evidence}]}}."""
    p = report_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "criteria": criteria, **(meta or {})},
                            ensure_ascii=False, indent=1), "utf-8")
    return p
