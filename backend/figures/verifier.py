"""Scientific Figure Integrity Validator (v6.4.0 Section 3 & v6.4.2 Module E)."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from backend.figures.contracts import FigureSpec, FigureVerificationReport
from backend.knowledge import research_store as S


def extract_experiment_metrics(tid: str, experiment_id: str) -> tuple[dict[str, list[float]], list[str], str]:
    """Load real experiment run metrics for a topic and return (series, x_labels, sha256)."""
    from backend.execution import protocols as P
    from backend.knowledge.verification import verify_run
    import statistics

    run = P.run(tid, experiment_id)
    checked = verify_run(tid, experiment_id, _find_reproduction=False)
    if checked['status'] != 'passed':
        raise ValueError('Independent raw experiment recomputation failed; stored summaries are not figure evidence')
    series: dict[str, list[float]] = {"mean_psnr_db": [], "mean_mse": []}
    x_labels: list[str] = []
    for trial in run.get("trials") or []:
        req = (trial.get("payload") or {}).get("request") or {}
        summary = (trial.get("payload") or {}).get("summary") or {}
        if req.get("split") == "validation":
            x_labels.append(f"alpha={req.get('alpha', 0)}")
            series['mean_psnr_db'].append(round(float(summary['mean_psnr_db']), 6))
            per_seed = summary.get('per_seed')
            if not isinstance(per_seed, dict) or not per_seed: raise ValueError('Missing measured per-seed MSE')
            series['mean_mse'].append(round(statistics.mean(float(row['mse']) for row in per_seed.values()), 8))
    if not x_labels:
        raise ValueError('No measured validation split; held-out/test data cannot silently replace it')
    canonical = S.dumps({"experiment_id": experiment_id, "x": x_labels, "series": series}).encode("utf-8")
    return series, x_labels, hashlib.sha256(canonical).hexdigest()


def compute_source_data_sha256(tid: str, spec: FigureSpec) -> str:
    """Compute canonical SHA-256 of the source data backing a FigureSpec."""
    if spec.source.kind == "experiment_artifact" and spec.source.experiment_id:
        _, _, digest = extract_experiment_metrics(tid, spec.source.experiment_id)
        return digest
    if spec.source.kind == "workspace_artifact" and spec.source.artifact_id:
        from backend.research_engines import workspaces as W

        art = W.artifact(tid, spec.source.artifact_id)
        return str(art.get("sha256") or hashlib.sha256(S.dumps(art).encode("utf-8")).hexdigest())
    payload = {
        "kind": spec.source.kind,
        "x_values": spec.source.x_values,
        "series": spec.source.series,
        "error_bars": spec.source.error_bars,
        "comparison_panels": spec.source.comparison_panels,
        "dot_source": spec.source.dot_source,
        "waveform": spec.source.waveform,
        "mesh_3d": spec.source.mesh_3d,
    }
    return hashlib.sha256(S.dumps(payload).encode("utf-8")).hexdigest()


def verify_figure(
    tid: str,
    figure_id: str,
    version: int,
    spec: FigureSpec,
    recorded_data_sha256: str,
    exports: dict[str, dict],
) -> FigureVerificationReport:
    """Run deterministic mechanical and scientific integrity checks on a figure version."""
    tests: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []
    source_ids: list[str] = []
    if spec.source.experiment_id:
        source_ids.append(f"experiment:{spec.source.experiment_id}")
    if spec.source.artifact_id:
        source_ids.append(f"artifact:{spec.source.artifact_id}")

    # 1. Data hash check
    try:
        actual_data_sha = compute_source_data_sha256(tid, spec)
        if spec.source.expected_sha256 and spec.source.expected_sha256 != actual_data_sha:
            tests["data_hash_matches"] = "fail"
            errors.append("Source data SHA-256 does not match expected_sha256 in FigureSpec.")
        elif recorded_data_sha256 and recorded_data_sha256 != actual_data_sha:
            tests["data_hash_matches"] = "fail"
            errors.append("Source data changed since figure generation (recorded data hash mismatch).")
        else:
            tests["data_hash_matches"] = "pass"
    except Exception as exc:
        tests["data_hash_matches"] = "fail"
        errors.append(f"Could not resolve source data in topic scope: {exc}")

    # 2. Numerical integrity check against experiment measurements
    if spec.source.kind == "experiment_artifact" and spec.source.experiment_id:
        try:
            exp_series, x_labels, _ = extract_experiment_metrics(tid, spec.source.experiment_id)
            mismatch = not spec.source.series or spec.source.x_values != x_labels
            if spec.source.x_values != x_labels: errors.append('Plotted X values do not match the measured validation methods/order.')
            aliases = {'Validation Mean PSNR (dB)': 'mean_psnr_db', 'Validation Mean MSE': 'mean_mse'}
            for k, vals in spec.source.series.items():
                canonical = aliases.get(k, k)  # Explicit historical display labels only.
                if canonical in exp_series:
                    ref_vals = exp_series[canonical]
                    if len(vals) != len(ref_vals) or any(
                        not math.isclose(float(a), float(b), rel_tol=1e-5, abs_tol=1e-5) for a, b in zip(vals, ref_vals)
                    ):
                        mismatch = True
                        errors.append(f"Plotted series '{k}' diverges from raw experiment measurements.")
                else:
                    mismatch = True
                    errors.append(f"Plotted series '{k}' has no independently verified experiment metric.")
            tests["numerical_values"] = "fail" if mismatch else "pass"
        except Exception as exc:
            tests["numerical_values"] = "fail"
            errors.append(f"Failed numerical check against experiment {spec.source.experiment_id}: {exc}")
    else:
        has_nonfinite = any(
            not math.isfinite(float(v)) for vals in spec.source.series.values() for v in vals
        )
        tests["numerical_values"] = "fail" if has_nonfinite else "pass"

    # 3. Labels and units check
    if spec.category == "plot_2d":
        if not spec.x_label.strip() or not spec.y_label.strip():
            tests["labels_and_units"] = "fail"
            errors.append("2D plot is missing X or Y axis labels.")
        elif not spec.x_unit.strip() or not spec.y_unit.strip():
            tests["labels_and_units"] = "needs_human_review"
            warnings.append("Axis units (x_unit or y_unit) are not explicitly declared.")
        else:
            tests["labels_and_units"] = "pass"
    else:
        tests["labels_and_units"] = "pass"

    # 4. Render bounds & exported artifact integrity
    bounds_ok = True
    if spec.style.font_size_pt < 6 or spec.style.width_in < 1.0 or spec.style.height_in < 1.0:
        bounds_ok = False
        errors.append("Figure dimensions or font size fall below minimum publication legibility bounds.")
    for fmt, meta in (exports or {}).items():
        p = Path(meta.get("path", ""))
        if not p.is_file():
            bounds_ok = False
            errors.append(f"Exported file for format '{fmt}' is missing on disk.")
        else:
            raw = p.read_bytes()
            if hashlib.sha256(raw).hexdigest() != meta.get("sha256"):
                bounds_ok = False
                errors.append(f"Exported file '{fmt}' failed SHA-256 integrity verification (tampered on disk).")
    tests["render_bounds"] = "pass" if bounds_ok else "fail"

    # 5. Waveform / diagram illustrative classification (v6.4.2 Module E.8)
    is_illustrative = spec.category in ("waveform", "diagram") or spec.source.is_illustrative_only
    if is_illustrative:
        tests["illustrative_classification"] = "illustrative_only"
        warnings.append("Schematic/waveform diagram is classified as illustrative explanation, not a measured hardware capture.")

    # 6. Caption scientific claims check (v6.4.2 Module E.9)
    claim_pattern = re.compile(r"\b(outperforms?|improves?|significant|state-of-the-art|sota|superior|gain)\b", re.IGNORECASE)
    if spec.caption and claim_pattern.search(spec.caption):
        tests["caption_scientific_claims"] = "needs_human_review"
        warnings.append("Caption contains comparative/performance claims that require human scientific sign-off.")
    else:
        tests["caption_scientific_claims"] = "pass"

    if any(v == "fail" for v in tests.values()):
        overall = "failed"
    elif is_illustrative:
        overall = "illustrative_only"
    elif any(v == "needs_human_review" for v in tests.values()):
        overall = "needs_review"
    else:
        overall = "passed"

    return FigureVerificationReport(
        figure_artifact_id=figure_id,
        version=version,
        source_data_artifact_ids=source_ids,
        tests=tests,
        warnings=warnings,
        errors=errors,
        overall_status=overall,
        checked_at=S.now(),
    )
