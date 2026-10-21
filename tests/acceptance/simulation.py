"""TEST FIXTURE (not shipped as a skill): the 90-day AI Research OS experience simulation (docs: "90-Day AI Research OS Experience Simulation") as a DRY RUN.

It runs on the REAL research-run engine (state machine, events, resource guard, budget, idempotency keys, OOM recovery);
only the step executor is synthetic: no GPU / cloud job is started, no API credit is spent, no project data is
modified (everything is written under the run's own folder), and every number and artifact is labelled SYNTHETIC.

    week 1  day 1   Feynman literature → research map, paper matrix, evidence ledger           (checkpoint)
    week 2          hypothesis v1, novelty / evidence analysis
    week 3  day 21  coding provider: baseline + smoke tests, Docker/venv setup                 (checkpoint)
    week 4          ClearML baseline benchmark
    week 5          candidate v1 + unit tests (commit)
    week 6          bounded HPO
    week 7  day 48  failure analysis (no repeated failed experiment)                           (checkpoint)
    week 8  day 53  candidate v2 training — CUDA OOM injected → analysed → recovered (batch ½, grad-accum ×2)
    week 9          multi-seed validation
    week 10 day 70  ablation + claim/evidence audit                                            (checkpoint)
    week 11         IEEE LaTeX draft
    week 12 day 88  reviewer pass + consistency audit                                          (checkpoint)
    final           acceptance evaluation (PASS only with executable evidence) + gap report
"""
from __future__ import annotations

import json
import re

from backend.agent import runs

TITLE = "Design and Evaluation of a Lightweight Vision Transformer for Resource-Constrained Image Classification"
LABEL = "SYNTHETIC — mô phỏng, không phải kết quả thực nghiệm"
METRICS = {"baseline": {"accuracy": 85.2, "params_m": 5.4, "gflops": 1.20},
           "candidate_v1": {"accuracy": 86.1, "params_m": 5.1, "gflops": 1.12},
           "candidate_v2": {"accuracy": 87.4, "params_m": 4.8, "gflops": 1.05},
           "final": {"accuracy": 88.0, "params_m": 4.6, "gflops": 0.98}}
CHECKPOINTS = {
    1: ("Tôi muốn nghiên cứu lightweight ViT cho thiết bị có tài nguyên hạn chế. Hãy phân tích literature, tìm research "
        "gap và đề xuất hướng có thể kiểm chứng.",
        "Đã tạo project, ghi nhận mục tiêu và giới hạn. Feynman tổng hợp literature, lập evidence matrix và đề xuất "
        "hypotheses. Nhận định về novelty ở trạng thái unverified cho đến khi đối chiếu nguồn."),
    21: ("Tôi chọn giả thuyết số 2. Hãy xây baseline và chạy thử với ngân sách tính toán thấp.",
         "Đã khôi phục quyết định nghiên cứu. Coding provider dựng baseline và test; ClearML ghi cấu hình, seed và "
         "metrics. Chỉ chạy trong ngân sách và quyền thực thi đã được duyệt."),
    48: ("Accuracy chưa tốt. Phân tích nguyên nhân, thử cải tiến và đừng lặp lại thí nghiệm thất bại.",
         "Đã đối chiếu các run trước và learning curves, xác định thay đổi cần thử; chạy một nhóm thí nghiệm có giới hạn, "
         "ghi cả kết quả thất bại để tránh lặp lại."),
    70: ("Kiểm chứng kết quả tốt nhất, chạy nhiều seeds và cho tôi biết đóng góp nào đủ bằng chứng.",
         "Khoá cấu hình candidate, multi-seed validation, ablation và đối chiếu từng claim với metrics hoặc nguồn. "
         "Claim chưa đủ bằng chứng không vào nhóm verified."),
    88: ("Tạo paper IEEE tối đa 6 trang từ các kết quả đã xác minh và review như một reviewer khó tính.",
         "Tổng hợp findings đã xác minh, đối chiếu bảng/biểu đồ với experiment manifests, tạo LaTeX draft và review "
         "novelty, methodology, fairness, citation consistency."),
}
WEEKS = [
    # (week, day, provider, label, outputs, extra spec)
    (1, 1, "feynman", "Feynman: tìm, lọc, phân loại literature",
     ["literature/research_map.md", "literature/paper_matrix.csv", "literature/evidence_ledger.json"], {}),
    (2, 10, "app", "Phân tích novelty, mâu thuẫn, evidence → Hypothesis v1",
     ["hypotheses/hypotheses.md", "hypotheses/decisions.jsonl"], {"decision": "chọn giả thuyết H2 (SIMULATED approval)"}),
    (3, 21, "claude_code", "Coding provider dựng baseline + smoke tests",
     ["code/baseline/README.md", "experiments/run_manifests/baseline.json"], {}),
    (4, 28, "clearml", "ClearML chạy benchmark baseline có kiểm soát",
     ["experiments/metrics/baseline_metrics.json"], {"metrics": "baseline"}),
    (5, 35, "codex", "Coding provider tạo model v1 + unit tests",
     ["code/candidate_v1/README.md", "experiments/metrics/candidate_v1.json"], {"metrics": "candidate_v1", "commit": True}),
    (6, 42, "python", "HPO giới hạn (≤ 20 trial, tuần tự trên 1 GPU)", ["experiments/hpo_summary.md"], {}),
    (7, 48, "app", "Phân tích thất bại, ablation sơ bộ", ["reports/failure_analysis.md"], {}),
    (8, 53, "python", "Huấn luyện candidate v2 (tiêm lỗi CUDA OOM)",
     ["code/candidate_v2/README.md", "experiments/metrics/candidate_v2.json", "experiments/logs/candidate_v2.log"],
     {"metrics": "candidate_v2", "command": "python train.py --model vit-tiny-v2 --batch-size 64 --grad-accum 1",
      "inject": "oom"}),
    (9, 63, "python", "Multi-seed validation (3 seeds)", ["experiments/multi_seed_results.csv"], {"metrics": "final"}),
    (10, 70, "app", "Ablation + đối chiếu claim/evidence",
     ["experiments/ablation_matrix.csv", "findings/claim_evidence_report.md", "findings/verified_findings.md"], {}),
    (11, 77, "latex", "Soạn LaTeX draft IEEE", ["paper/main.tex", "paper/references.bib"], {}),
    (12, 88, "feynman", "Feynman reviewer + consistency audit", ["reports/review_report.md"], {}),
]


def steps() -> list:
    out = []
    for week, day, prov, label, outs, extra in WEEKS:
        out.append({"kind": "synthetic", "provider": prov, "label": f"Tuần {week} · ngày {day}: {label}",
                    "spec": {"week": week, "day": day, "outputs": outs, **extra}})
    out.append({"kind": "synthetic", "provider": "phdlab", "label": "Đánh giá 8 tiêu chí nghiệm thu + gap report",
                "spec": {"final": True, "outputs": ["reports/acceptance_evaluation.md", "reports/gap_report.md",
                                                    "reports/final_research_report.md", "memory/research_state_snapshot.json",
                                                    "project_manifest.json"]}})
    return out


def create(session_id: str = "", turn_id: str = "") -> dict:
    return runs.create("simulate", "Mô phỏng 90 ngày — " + TITLE[:60] + "… (SYNTHETIC)", TITLE, {"dry_run": True},
                       session_id, turn_id, "simulate", 0, "app", steps(), synthetic=True,
                       budget={"max_retries": 3, "max_minutes": 30})


def _header(path: str) -> str:
    if path.endswith(".json") or path.endswith(".jsonl"):
        return ""
    if path.endswith(".csv"):
        return f"# {LABEL}\n"
    if path.endswith(".tex") or path.endswith(".bib"):
        return f"% {LABEL}\n"
    return f"> **{LABEL}**\n\n"


def _content(path: str, spec: dict, rid: str) -> str:
    name = path.rsplit("/", 1)[-1]
    m = METRICS.get(spec.get("metrics", ""), {})
    if name.endswith(".json"):
        return json.dumps({"label": "SYNTHETIC", "run": rid, "week": spec.get("week"), "metrics": m or None,
                           "note": "dry-run artifact — not a measured result"}, indent=1)
    if name.endswith(".jsonl"):
        return json.dumps({"label": "SYNTHETIC", "decision": spec.get("decision", ""), "approved_by": "SIMULATED"}) + "\n"
    if name == "paper_matrix.csv":
        return _header(path) + "paper,method,dataset,metric,result,limitation\n" + "\n".join(
            f"[SYNTHETIC-{i}],efficient ViT variant {i},ImageNet-1k subset,top-1,—,not a real citation" for i in range(1, 6))
    if name == "multi_seed_results.csv":
        return _header(path) + "seed,accuracy\n" + "\n".join(f"{s},{88.0 + d}" for s, d in ((0, -0.3), (1, 0.2), (2, 0.1)))
    if name == "ablation_matrix.csv":
        return _header(path) + "variant,accuracy,params_m\nfull,88.0,4.6\n-token_pruning,87.1,4.9\n-distillation,86.4,4.6\n"
    if name.endswith(".tex"):
        rows = "\n".join(f"{k.replace('_', ' ')} & {v['accuracy']}\\% & {v['params_m']}M & {v['gflops']}G \\\\"
                         for k, v in METRICS.items())
        return (_header(path) + "\\documentclass{IEEEtran}\n\\begin{document}\n\\title{" + TITLE + " (SYNTHETIC DRAFT)}\n"
                "\\maketitle\n\\section{Results}\nAll numbers below are SYNTHETIC.\n\\begin{tabular}{lrrr}\n" + rows +
                "\n\\end{tabular}\n\\end{document}\n")
    if name.endswith(".bib"):
        return _header(path) + "% no real references are generated in a dry-run\n"
    return _header(path) + f"# {name}\n\nTuần {spec.get('week')}: nội dung minh hoạ cho bước mô phỏng. Không chứa trích dẫn, " \
                           "thí nghiệm hay số liệu thật.\n" + (f"\nMetrics (SYNTHETIC): {m}\n" if m else "")


def _execute(ctx) -> dict:
    spec, rid = ctx.step["spec"], ctx.rid
    if spec.get("final"):
        return _final(ctx)
    day = spec.get("day")
    if day in CHECKPOINTS:
        u, a = CHECKPOINTS[day]
        ctx.log(f"Ngày {day} — checkpoint hội thoại", checkpoint=day, user=u, assistant=a)
    if spec.get("inject") == "oom" and re.search(r"--batch-size 64\b", spec.get("command", "")):
        ctx.log("ClearML báo FAILED: CUDA out of memory (SYNTHETIC) — lỗi, log, resource metrics, checkpoint reference "
                "được gửi về PhD Lab", resource={"gpu_mem_gb": 11.8, "batch_size": 64, "precision": "fp32"},
                checkpoint_ref="experiments/checkpoints/candidate_v2_epoch3.pt (SYNTHETIC reference)")
        raise runs.StepFailure("RuntimeError: CUDA out of memory. Tried to allocate 1.50 GiB (SYNTHETIC injection, day 53)",
                               "gpu_oom", detail="CUDA out of memory")
    _ledger(ctx)
    outs = [ctx.write("simulation/lightweight_vit/" + p, _content(p, spec, rid)) for p in spec.get("outputs", [])]
    res = {"synthetic": True, "summary_line": f"Tuần {spec.get('week')}: {ctx.step['label'].split(': ', 1)[-1]}"}
    if spec.get("metrics"):
        res["metrics"] = METRICS[spec["metrics"]]
    if spec.get("command"):
        res["command"] = spec["command"]
        if "--batch-size 32" in spec["command"]:
            res["summary_line"] += " — phục hồi sau OOM: batch 64→32, grad-accum 1→2 (Failed → Analyzing → Recovering → Resumed)"
    if spec.get("commit"):
        res["commit"] = "SYNTH" + rid[-6:]
    return {"outputs": outs, "result": res}


def _ledger(ctx) -> None:
    """Side-effect ledger: one line per executed step with its idempotency key (duplicate detection for the evaluation)."""
    f = ctx.out / "simulation" / "executions.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"step": ctx.step["id"], "key": ctx.step["idempotency_key"], "attempt": ctx.step["attempt"]}) + "\n")


def _final(ctx) -> dict:
    from backend.agent import acceptance
    r = runs.get(ctx.rid)
    ev = acceptance.evaluate(simulation=r)
    lines = [f"# Đánh giá 8 tiêu chí nghiệm thu — {ctx.rid}", "", f"> {LABEL}. Một tiêu chí chỉ PASS khi có bằng chứng "
             "chạy được (test nghiệm thu đã chạy và đạt); phần chỉ có trong mô phỏng được ghi SIMULATED.", "",
             "| Ưu tiên | Tiêu chí | Kết luận | Bằng chứng |", "|---|---|---|---|"]
    lines += [f"| {c['priority']} | {c['title']} | **{c['verdict']}** | {c['evidence']} |" for c in ev["criteria"]]
    o1 = ctx.write("simulation/lightweight_vit/reports/acceptance_evaluation.md", "\n".join(lines) + "\n")
    gap = ["# Gap report — từ mô phỏng sang 90 ngày thực", "", f"> {LABEL}", ""] + [f"- {g}" for g in acceptance.gaps()]
    o2 = ctx.write("simulation/lightweight_vit/reports/gap_report.md", "\n".join(gap) + "\n")
    hist = [f"- {h['from'] or '∅'} → {h['to']}: {h['reason']}" for h in r["history"]]
    table = ["| Model | Accuracy | Parameters | FLOPs |", "|---|---:|---:|---:|"] + [
        f"| {k} | {v['accuracy']}% | {v['params_m']}M | {v['gflops']}G |" for k, v in METRICS.items()]
    o3 = ctx.write("simulation/lightweight_vit/reports/final_research_report.md",
                   "\n".join([f"# Final research report (DRY-RUN)", "", f"> {LABEL}", "", "## Kết quả (DỮ LIỆU GIẢ LẬP)", ""]
                             + table + ["", "## Chuyển trạng thái của run", ""] + hist) + "\n")
    o4 = ctx.write("simulation/lightweight_vit/memory/research_state_snapshot.json",
                   json.dumps({"label": "SYNTHETIC", "run": ctx.rid, "status_history": r["history"],
                               "steps": [{k: s[k] for k in ("id", "label", "provider", "status", "attempt", "idempotency_key")}
                                         for s in r["steps"]]}, ensure_ascii=False, indent=1))
    o5 = ctx.write("simulation/lightweight_vit/project_manifest.json",
                   json.dumps({"title": TITLE, "label": "SYNTHETIC", "run": ctx.rid, "weeks": 12}, indent=1))
    passed = sum(1 for c in ev["criteria"] if c["verdict"] == "PASS")
    return {"outputs": [o1, o2, o3, o4, o5],
            "result": {"synthetic": True, "acceptance": ev["criteria"], "metrics": METRICS["final"],
                       "summary": f"Mô phỏng 12 tuần xong (SYNTHETIC). Nghiệm thu: {passed}/8 PASS có bằng chứng thực thi, "
                                  "còn lại SIMULATED / NOT VERIFIED — xem acceptance_evaluation.md và gap_report.md.",
                       "summary_line": f"nghiệm thu {passed}/8 PASS (bằng chứng thực thi)"}}


runs.EXECUTORS["synthetic"] = _execute
runs.LABEL["synthetic"] = "Bước mô phỏng"
runs.PIPELINES.setdefault("simulate", ())
