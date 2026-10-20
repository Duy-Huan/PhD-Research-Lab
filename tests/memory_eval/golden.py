"""Golden research project (hyperspectral image denoising) + golden tasks with the records an agent MUST get back.

seed()       builds the project through the public memory APIs only, so the same corpus runs on v3.2 (baseline) and v3.3.
scale(n)     adds n deterministic distractor records of every kind (latency benchmark at realistic sizes).
TASKS        the golden tasks of the v3.3 spec §20 (+ the SwinIR acceptance question): query, research role and the ids
             that must be retrieved / the facts that must survive into the compiled context.
evaluate()   recall@k, precision@k, MRR, evidence fidelity and context efficiency for one retrieval + compile function.
"""
from __future__ import annotations

import json
import time

from backend import memory as M
from backend.memory import knowledge, research

OBJECTIVE = "Hyperspectral image denoising on the CAVE dataset with lightweight transformers that fit a 12 GB GPU"
CONSTRAINT = "Hardware: single NVIDIA RTX 3060 with 12 GB VRAM — batch size and attention window must fit 12 GB"
GIT_BEST = "9f8e7d6c5b4a3921"
TASK_BEST = "c" * 32

PAPERS = [
    ("liang2021swinir", "SwinIR: Image Restoration Using Swin Transformer", 2021,
     "Swin Transformer blocks with shifted windows give strong image restoration results (denoising, super-resolution); "
     "large attention windows increase memory use quadratically."),
    ("wei2020qrnn3d", "3D Quasi-Recurrent Neural Network for Hyperspectral Image Denoising", 2020,
     "QRNN3D exploits spatial-spectral correlation with 3D convolutions and quasi-recurrent pooling; baseline for HSI denoising."),
    ("li2023sst", "Spatial-Spectral Transformer for Hyperspectral Image Denoising", 2023,
     "Spectral self-attention combined with window spatial attention improves PSNR on CAVE and ICVL."),
    ("devlin2019bert", "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding", 2019,
     "Masked language model pre-training for natural language understanding tasks."),
    ("he2016resnet", "Deep Residual Learning for Image Recognition", 2016,
     "Residual connections make very deep convolutional networks trainable for ImageNet classification."),
    ("rudin1992tv", "Nonlinear total variation based noise removal algorithms", 1992,
     "Total variation regularisation removes noise while preserving edges."),
]


def _papers(extra: int = 0) -> None:
    from backend.library import load_library, save_library
    lib = load_library()
    for key, title, year, abstract in PAPERS:
        lib[f"{key}.pdf"] = {"key": key, "title": title, "year": str(year), "abstract": abstract, "authors": [], "venue": "",
                             "include": True, "key_locked": True}
    for i in range(extra):
        lib[f"filler{i:04d}.pdf"] = {"key": f"filler{i:04d}", "title": f"Unrelated study {i} on graph neural networks for molecules",
                                     "year": "2022", "abstract": f"Message passing networks predict molecular property {i} on QM9.",
                                     "authors": [], "venue": "", "include": True, "key_locked": True}
    save_library(lib)


def seed() -> dict:
    """The golden project. Returns {name: id} of records whose ids are not sequential (decisions)."""
    ids: dict = {}
    M.set_tier3({"goals": [OBJECTIVE], "constraints": [CONSTRAINT]})
    h1 = research.add_hypothesis("Spectral self-attention improves PSNR over the 3D-CNN QRNN3D baseline on CAVE", status="supported")
    h2 = research.add_hypothesis("Swin Transformer shifted windows capture spatial-spectral correlation for HSI denoising",
                                 status="testing")
    h3 = research.add_hypothesis("A total variation prior helps at high noise level sigma=50", status="refuted")
    research.add_experiment({"title": "QRNN3D baseline on CAVE", "hypothesis_id": h1["id"], "dataset_version": "CAVE-v2",
                             "git_sha": "1a2b3c4d5e6f7081", "clearml_task_id": "a" * 32, "observation": "PSNR 29.10 dB, SSIM 0.912",
                             "conclusion": "Baseline PSNR 29.10 dB on CAVE", "verdict": ""})
    research.add_experiment({"title": "Spectral attention model on CAVE", "hypothesis_id": h1["id"], "dataset_version": "CAVE-v2",
                             "git_sha": "2b3c4d5e6f708192", "clearml_task_id": "b" * 32, "observation": "PSNR 30.85 dB",
                             "conclusion": "Spectral attention +1.75 dB over QRNN3D baseline", "verdict": "supports"})
    research.add_experiment({"title": "SwinIR-large window 16 on CAVE", "hypothesis_id": h2["id"], "dataset_version": "CAVE-v2",
                             "git_sha": "3c4d5e6f70819203", "environment": "RTX 3060 12GB, torch 2.4, batch 8",
                             "observation": "CUDA out of memory at the first forward pass (attention window 16, batch 8)",
                             "conclusion": "Configuration does not fit 12 GB VRAM", "verdict": "inconclusive"})
    research.add_experiment({"title": "SwinIR-small window 8 on CAVE", "hypothesis_id": h2["id"], "dataset_version": "CAVE-v2",
                             "git_sha": GIT_BEST, "clearml_task_id": TASK_BEST, "environment": "RTX 3060 12GB, torch 2.4, batch 4",
                             "observation": "PSNR 31.42 dB, SSIM 0.941 — best result so far",
                             "conclusion": "Swin windows beat spectral attention by 0.57 dB", "verdict": "supports"})
    research.add_experiment({"title": "TV prior at sigma 50 on ICVL", "hypothesis_id": h3["id"], "dataset_version": "ICVL-v1",
                             "git_sha": "5e6f708192a3b4c5", "observation": "PSNR 28.0 dB, worse than without prior",
                             "conclusion": "TV prior over-smooths spectra", "verdict": "refutes"})
    research.add_failure("CUDA OOM: SwinIR-large with attention window 16 and batch 8 on RTX 3060 12GB",
                         hypothesis_id=h2["id"],
                         reason="Attention window too large: memory grows quadratically with the window size. Lesson: keep "
                                "window <= 8 and batch <= 4 under 12 GB VRAM.")
    research.add_failure("TV prior degraded PSNR at sigma 50 (over-smoothing)", hypothesis_id=h3["id"],
                         reason="Spectral detail removed by the total variation term.")
    ids["dec_dataset"] = M.add_decision("Use CAVE-v2 as the primary benchmark dataset for every comparison", kind="direction")["id"]
    ids["dec_tv"] = M.add_decision("Do not use a total variation prior again", kind="rejected")["id"]
    knowledge.add("concept", "PSNR", "Peak signal-to-noise ratio in dB; the main denoising quality metric of this project.")
    knowledge.add("method", "Shifted window attention", "Swin-style local window self-attention with shifted windows.",
                  refs=["liang2021swinir"])

    def eps(st):
        for i, (title, summary) in enumerate([
            ("Chat about LaTeX template formatting", "Discussed IEEE template, figure placement and bibliography style."),
            ("Debugging the OOM of SwinIR-large", "SwinIR-large with window 16 crashed with CUDA OOM on the RTX 3060; "
                                                  "reducing window to 8 and batch to 4 fixed it. See EXP-003, FAIL-001."),
            ("Conference deadline planning", "CVPR deadline in November; writing schedule agreed."),
        ]):
            st["tier2"].append({"id": f"E00000{i}", "created": f"2026-0{i + 1}-01T00:00:00+00:00", "source": "chat:data:s1",
                                "title": title, "summary": summary})
    M.update(eps)
    _papers()
    for name, fn in (("claim_swin", "_seed_v33"),):  # v3.3 entities when the evidence layer exists
        f = globals().get(fn)
        if f:
            ids.update(f() or {})
    return ids


def _seed_v33() -> dict:
    try:
        from backend.memory import evidence
    except ImportError:
        return {}
    c = evidence.add_claim("Swin window attention improves HSI denoising PSNR over spectral attention on CAVE",
                           hypothesis_id="HYPE-002", source_refs=["lit:liang2021swinir"])
    ev = evidence.add_evidence({"claim_id": c["id"], "source_type": "experiment", "experiment_id": "EXP-004",
                                "stance": "supports", "metric": {"name": "PSNR", "value": 31.42}, "status": "validated"})
    return {"claim_swin": c["id"], "evid_best": ev["id"]}


def scale(n: int) -> None:
    """n distractors of every kind (hypotheses n/5, experiments n, failures n/4, episodes n, papers n)."""
    hs = [research.add_hypothesis(f"Distractor hypothesis {i}: dropout rate {i % 7} changes accuracy on CIFAR-{i % 3}")
          for i in range(max(1, n // 5))]
    for i in range(n):
        research.add_experiment({"title": f"CIFAR ablation {i}", "hypothesis_id": hs[i % len(hs)]["id"],
                                 "dataset_version": f"CIFAR-{i % 3}", "git_sha": f"{i:016x}",
                                 "observation": f"accuracy {70 + i % 20}.{i % 10} percent with lr {i % 5}e-4",
                                 "conclusion": f"learning rate {i % 5}e-4 run {i}"})
    for i in range(max(1, n // 4)):
        research.add_failure(f"NaN loss in CIFAR ablation {i}", reason=f"learning rate {i % 5}e-2 too high")

    def eps(st):
        for i in range(n):
            st["tier2"].append({"id": f"EF{i:05d}", "created": "2025-06-01T00:00:00+00:00", "source": "chat:data:fill",
                                "title": f"Filler conversation {i}", "summary": f"Talked about optimizer {i % 4} and weekly meeting {i}."})
    M.update(eps)
    _papers(extra=n)


# ------------------------------------------------------------------ golden tasks
TASKS = [
    {"id": "T001", "query": "Find previous experiments using dataset CAVE", "role": "experiment_designer",
     "expected": ["EXP-001", "EXP-002", "EXP-003", "EXP-004"], "facts": ["CAVE"]},
    {"id": "T002", "query": "Why did model SwinIR-large fail?", "role": "experiment_designer",
     "expected": ["FAIL-001", "EXP-003"], "facts": ["quadratically", "window"]},
    {"id": "T003", "query": "What is the current best PSNR?", "role": "reviewer",
     "expected": ["EXP-004"], "facts": ["31.42"]},
    {"id": "T004", "query": "Which hypothesis is currently active?", "role": "director",
     "expected": ["HYPE-002"], "facts": ["Swin Transformer shifted windows"]},
    {"id": "T005", "query": "Which papers support the claim that Swin window attention improves denoising?", "role": "literature",
     "expected": ["lit:liang2021swinir"], "facts": ["SwinIR"]},
    {"id": "T006", "query": "What configuration caused the OOM?", "role": "coder",
     "expected": ["FAIL-001", "EXP-003"], "facts": ["window 16", "batch 8"]},
    {"id": "T007", "query": "What experiment should be run next?", "role": "experiment_designer",
     "expected": ["HYPE-002", "FAIL-001", "EXP-004"], "facts": ["12 GB"]},
    {"id": "T008", "query": "Which code commit produced the 31.42 PSNR result?", "role": "reviewer",
     "expected": ["EXP-004"], "facts": [GIT_BEST[:10]]},
    {"id": "T009", "query": "Should we use Swin Transformer?", "role": "experiment_designer",
     "expected": ["HYPE-002", "FAIL-001", "EXP-004", "lit:liang2021swinir"], "facts": ["31.42", "12 GB"]},
]


def _mrr(order: list, expected: set) -> float:
    for i, x in enumerate(order):
        if x in expected:
            return 1.0 / (i + 1)
    return 0.0


def evaluate(retrieve, compile_fn=None, k: int = 5, tasks: list | None = None) -> dict:
    """retrieve(task) -> ordered ids; compile_fn(task) -> context text. Returns per-task + mean metrics."""
    rows = []
    for t in tasks or TASKS:
        exp = set(t["expected"])
        t0 = time.perf_counter()
        order = list(dict.fromkeys(retrieve(t)))
        r_ms = (time.perf_counter() - t0) * 1000
        top = order[:k]
        row = {"id": t["id"], "recall@5": len(exp & set(top)) / len(exp), "recall@10": len(exp & set(order[:10])) / len(exp),
               "precision@5": len(exp & set(top)) / max(1, len(top)), "mrr": _mrr(order, exp), "retrieve_ms": round(r_ms, 1)}
        if compile_fn:
            t0 = time.perf_counter()
            text = compile_fn(t)
            row["compile_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            row["context_tokens"] = (len(text) + 3) // 4
            row["ids_in_context"] = sum(1 for e in exp if e.split(":")[-1] in text) / len(exp)
            row["fact_fidelity"] = sum(1 for f in t["facts"] if f.lower() in text.lower()) / len(t["facts"])
            useful = row["ids_in_context"] + row["fact_fidelity"]
            row["efficiency"] = round(1000 * useful / max(1, row["context_tokens"]), 3)  # useful hits per 1k tokens
        rows.append(row)
    keys = [k2 for k2 in rows[0] if k2 != "id"]
    mean = {k2: round(sum(r[k2] for r in rows) / len(rows), 3) for k2 in keys}
    return {"tasks": rows, "mean": mean}


def dump(obj) -> str:
    return json.dumps(obj, indent=1)


# Held-out tasks: written AFTER the scoring weights were tuned on TASKS and never used for tuning — the honest number.
# "$name" refers to an id returned by seed() (decision ids are random).
HELD_OUT = [
    {"id": "H001", "query": "Which experiments refuted a hypothesis?", "role": "reviewer", "expected": ["EXP-005"], "facts": ["refutes"]},
    {"id": "H002", "query": "What did we learn about total variation priors?", "role": "literature",
     "expected": ["FAIL-002", "EXP-005", "HYPE-003"], "facts": ["over-smooth"]},
    {"id": "H003", "query": "What SSIM did the SwinIR-small model reach?", "role": "reviewer", "expected": ["EXP-004"], "facts": ["0.941"]},
    {"id": "H004", "query": "Which ClearML task holds the best run?", "role": "coder", "expected": ["EXP-004"], "facts": [TASK_BEST]},
    {"id": "H005", "query": "What hardware limits do we have?", "role": "coder", "expected": ["con:0"], "facts": ["RTX 3060"]},
    {"id": "H006", "query": "Which baseline did we compare against?", "role": "writer", "expected": ["EXP-001"], "facts": ["QRNN3D"]},
    {"id": "H007", "query": "Which dataset is our primary benchmark?", "role": "director", "expected": ["$dec_dataset"], "facts": ["CAVE-v2"]},
    {"id": "H008", "query": "Is there evidence that window attention beats spectral attention?", "role": "reviewer",
     "expected": ["EVID-001", "CLM-001", "EXP-004"], "facts": ["31.42"]},
]


def resolve(tasks: list, ids: dict) -> list:
    return [{**t, "expected": [ids.get(e[1:], e) if e.startswith("$") else e for e in t["expected"]]} for t in tasks]


# Second held-out set: written BEFORE the last two generic fixes (stemming, centrality gating) and evaluated only once,
# after them — HELD_OUT was inspected for systematic errors, so it no longer counts as untouched.
HELD_OUT_2 = [
    {"id": "K001", "query": "Which runs used ICVL data?", "role": "experiment_designer", "expected": ["EXP-005"], "facts": ["ICVL"]},
    {"id": "K002", "query": "How much better is spectral attention than QRNN3D?", "role": "reviewer", "expected": ["EXP-002"],
     "facts": ["1.75"]},
    {"id": "K003", "query": "Which git commit is the QRNN3D baseline from?", "role": "coder", "expected": ["EXP-001"],
     "facts": ["1a2b3c4d5e"]},
    {"id": "K004", "query": "What batch size fits on our GPU for SwinIR?", "role": "coder", "expected": ["FAIL-001", "EXP-004"],
     "facts": ["batch 4"]},
    {"id": "K005", "query": "Which directions have we rejected?", "role": "director", "expected": ["$dec_tv"], "facts": ["total variation"]},
    {"id": "K006", "query": "Summarise the papers on transformers for hyperspectral denoising", "role": "literature",
     "expected": ["lit:li2023sst", "lit:liang2021swinir"], "facts": ["Spatial-Spectral Transformer"]},
]
