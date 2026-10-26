"""Versioned storage, regeneration, and paper attachment for v6.4.0 Figure Studio."""
from __future__ import annotations

import json
from pathlib import Path

from backend.agent import decision_ledger as L
from backend.figures import renderers, verifier
from backend.figures.contracts import FigureProvenance, FigureSpec, FigureStyle
from backend.knowledge import research_store as S

LEGACY_RASTER_WARNING = 'Legacy PNG/PDF exports used placeholder graphics. Regenerate this figure before validation, approval, paper use or raster/PDF export.'


def _legacy_raster(provenance: dict) -> bool:
    return provenance.get('renderer_used') != 'builtin-svg' and bool({'png', 'pdf'} & set(provenance.get('exports') or {}))


def _require_real_raster(provenance: dict) -> None:
    if _legacy_raster(provenance):
        raise ValueError(LEGACY_RASTER_WARNING)


def _figure_dir(tid: str, fid: str, version: int) -> Path:
    return S.safe_child(S.store_dir(), "topics", tid, "artifacts", "figures", fid, "versions", f"v{version:04d}")


def _hydrate_experiment_source(tid: str, spec: FigureSpec) -> FigureSpec:
    if spec.source.kind == "experiment_artifact" and spec.source.experiment_id and not spec.source.series:
        series, x_labels, digest = verifier.extract_experiment_metrics(tid, spec.source.experiment_id)
        spec = spec.model_copy(deep=True)
        spec.source.series = {'mean_psnr_db': series['mean_psnr_db']}
        spec.source.x_values = x_labels
        if not spec.source.expected_sha256:
            spec.source.expected_sha256 = digest
        if spec.y_label == "y":
            spec.y_label = "PSNR"
        if not spec.y_unit:
            spec.y_unit = "dB"
        if spec.x_label == "x":
            spec.x_label = "Filter Alpha"
    return spec


def create_or_regenerate(spec: FigureSpec, figure_id: str = "") -> dict:
    """Create a new figure (v0001) or append an immutable version (v0002+) and run QA verification."""
    S.get_topic(spec.topic_id)
    spec = _hydrate_experiment_source(spec.topic_id, spec)
    fid = figure_id or spec.figure_id or f"fig-{S.uid()[:8]}"
    spec = spec.model_copy(update={"figure_id": fid})

    with S.db() as c:
        existing = c.execute("SELECT * FROM figures WHERE id=?", (fid,)).fetchone()
        if existing and existing["topic_id"] != spec.topic_id:
            raise ValueError("Figure ID belongs to another Topic")
        version = int(existing["current_version"]) + 1 if existing else 1

    out_dir = _figure_dir(spec.topic_id, fid, version)
    data_sha = verifier.compute_source_data_sha256(spec.topic_id, spec)
    if spec.source.expected_sha256 and spec.source.expected_sha256 != data_sha:
        raise ValueError("Source data SHA-256 mismatch: refusing to export tampered or stale source data")

    rendered = renderers.render_all(spec, out_dir)
    qa = verifier.verify_figure(spec.topic_id, fid, version, spec, data_sha, rendered["exports"])
    (out_dir / "qa-report.json").write_text(json.dumps(qa.model_dump(mode="json"), indent=2, ensure_ascii=False), "utf-8")

    prov = FigureProvenance(
        project_id=S.project_id(),
        topic_id=spec.topic_id,
        mission_id=spec.mission_id,
        figure_id=fid,
        version=version,
        renderer_used=rendered["renderer_used"],
        renderer_version=rendered["renderer_version"],
        spec_sha256=rendered["spec_sha256"],
        script_sha256=rendered["script_sha256"],
        data_sha256=data_sha,
        source_kind=spec.source.kind,
        experiment_id=spec.source.experiment_id,
        artifact_id=spec.source.artifact_id,
        transformations=spec.transformations,
        camera_state=rendered["camera_state"],
        exports=rendered["exports"],
        warnings=rendered["warnings"] + qa.warnings,
        scientific_review="illustrative_only" if qa.overall_status == "illustrative_only" else "pending",
        created_at=S.now(),
    )
    (out_dir / "provenance.json").write_text(json.dumps(prov.model_dump(mode="json"), indent=2, ensure_ascii=False), "utf-8")

    version_payload = {
        "spec": spec.model_dump(mode="json"),
        "provenance": prov.model_dump(mode="json"),
        "verification": qa.model_dump(mode="json"),
        "svg_preview": rendered["svg_preview"],
        "out_dir": str(out_dir),
    }

    with S.db() as c:
        at = S.now()
        vid = S.uid()
        fig_payload = {
            "latest_spec": spec.model_dump(mode="json"),
            "latest_provenance": prov.model_dump(mode="json"),
            "latest_verification": qa.model_dump(mode="json"),
        }
        if existing:
            old_payload = json.loads(existing['payload'])
            fig_payload['approvals'] = old_payload.get('approvals') or {}
            if old_payload.get('approval'):
                fig_payload['approval'] = old_payload['approval']
            c.execute(
                "UPDATE figures SET title=?,category=?,current_version=?,status=?,payload=?,updated=? WHERE id=?",
                (spec.title, spec.category, version, qa.overall_status, S.dumps(fig_payload), at, fid),
            )
        else:
            c.execute(
                "INSERT INTO figures VALUES(?,?,?,?,?,?,?,?,?,?)",
                (fid, spec.topic_id, spec.mission_id, spec.title, spec.category, version, qa.overall_status, S.dumps(fig_payload), at, at),
            )
        c.execute(
            "INSERT INTO figure_versions VALUES(?,?,?,?,?,?,?,?,?)",
            (vid, fid, spec.topic_id, version, rendered["spec_sha256"], rendered["script_sha256"], data_sha, S.dumps(version_payload), at),
        )
        c.execute(
            "INSERT INTO figure_verifications VALUES(?,?,?,?,?,?)",
            (S.uid(), fid, version, qa.overall_status, S.dumps(qa.model_dump(mode="json")), at),
        )
        L.append(
            c,
            spec.topic_id,
            fid,
            "figure.rendered",
            {"version": version, "renderer": rendered["renderer_used"], "spec_sha256": rendered["spec_sha256"], "data_sha256": data_sha, "qa_status": qa.overall_status},
        )

    # Also register in v6.4.2 Unified Research Artifact Protocol if available
    try:
        from backend.intelligence import urap
        svg_exp = rendered["exports"].get("svg") or next(iter(rendered["exports"].values()), {})
        urap.register_artifact(
            topic_id=spec.topic_id,
            artifact_type="figure_render",
            sha256=svg_exp.get("sha256", rendered["spec_sha256"]),
            byte_size=int(svg_exp.get("bytes", 0)),
            uri=svg_exp.get("path", str(out_dir)),
            media_type=svg_exp.get("mime", "image/svg+xml"),
            mission_id=spec.mission_id,
            producer_runtime=rendered["renderer_used"],
            input_artifact_ids=[x for x in (spec.source.experiment_id, spec.source.artifact_id) if x],
            metadata={"figure_id": fid, "version": version, "title": spec.title},
        )
    except Exception:
        pass

    return get_figure(spec.topic_id, fid, version)


def list_figures(tid: str) -> list[dict]:
    S.get_topic(tid)
    with S.db() as c:
        rows = c.execute("SELECT * FROM figures WHERE topic_id=? ORDER BY updated DESC", (tid,)).fetchall()
        out = []
        for r in rows:
            p = json.loads(r["payload"])
            legacy = _legacy_raster(p.get('latest_provenance') or {})
            if legacy:
                p['latest_verification']['overall_status'] = 'needs_review'
                p['latest_verification'].setdefault('warnings', []).append(LEGACY_RASTER_WARNING)
                p['latest_provenance']['scientific_review'] = 'pending'
            out.append({**dict(r), 'status': 'needs_review' if legacy else r['status'], "payload": p})
        return out


def get_figure(tid: str, fid: str, version: int = 0) -> dict:
    S.get_topic(tid)
    with S.db() as c:
        fig = c.execute("SELECT * FROM figures WHERE id=? AND topic_id=?", (fid, tid)).fetchone()
        if not fig:
            raise ValueError("Figure not found in this Topic")
        ver_num = version if version > 0 else int(fig["current_version"])
        vrow = c.execute("SELECT * FROM figure_versions WHERE figure_id=? AND version=?", (fid, ver_num)).fetchone()
        if not vrow:
            raise ValueError(f"Figure version v{ver_num:04d} not found")
        all_vers = [
            {
                "version": r["version"],
                "spec_sha256": r["spec_sha256"],
                "script_sha256": r["script_sha256"],
                "data_sha256": r["data_sha256"],
                "created": r["created"],
            }
            for r in c.execute("SELECT version,spec_sha256,script_sha256,data_sha256,created FROM figure_versions WHERE figure_id=? ORDER BY version DESC", (fid,))
        ]
        vp = json.loads(vrow["payload"])
        figure_payload = json.loads(fig['payload'])
        approval = (figure_payload.get('approvals') or {}).get(str(ver_num)) or figure_payload.get('approval') or {}
        approval_bound = (approval.get('version') == ver_num and approval.get('spec_sha256') == vrow['spec_sha256']
                          and approval.get('data_sha256') == vrow['data_sha256']
                          and approval.get('exports') == {key: value.get('sha256') for key, value in vp['provenance'].get('exports', {}).items()})
        legacy = _legacy_raster(vp['provenance'])
        if legacy:
            vp['verification']['overall_status'] = 'needs_review'
            vp['verification'].setdefault('warnings', []).append(LEGACY_RASTER_WARNING)
            vp['provenance']['scientific_review'] = 'pending'
        return {
            "id": fig["id"],
            "topic_id": fig["topic_id"],
            "mission_id": fig["mission_id"],
            "title": fig["title"],
            "category": fig["category"],
            "current_version": fig["current_version"],
            "selected_version": ver_num,
            'status': 'needs_review' if legacy else 'approved' if approval_bound and fig['status'] != 'failed' else 'needs_review' if fig['status'] == 'approved' else fig['status'],
            'approval': approval if approval_bound else None,
            "created": fig["created"],
            "updated": fig["updated"],
            "spec": vp["spec"],
            "provenance": vp["provenance"],
            "verification": vp["verification"],
            "svg_preview": vp.get("svg_preview", ""),
            "versions": all_vers,
        }


def update_style(tid: str, fid: str, style_patch: dict, title: str = "", caption: str = "") -> dict:
    """Deterministic GUI style update (no LLM invoked) -> creates a new immutable figure version."""
    current = get_figure(tid, fid)
    spec_dict = dict(current["spec"])
    style_dict = {**spec_dict.get("style", {}), **style_patch}
    spec_dict["style"] = FigureStyle.model_validate(style_dict).model_dump()
    if title.strip():
        spec_dict["title"] = title.strip()
    if caption:
        spec_dict["caption"] = caption
    spec = FigureSpec.model_validate(spec_dict)
    return create_or_regenerate(spec, figure_id=fid)


def validate_figure_version(tid: str, fid: str, version: int = 0) -> dict:
    """Re-verify figure integrity against current source data and disk files."""
    cur = get_figure(tid, fid, version)
    _require_real_raster(cur['provenance'])
    ver_num = cur["selected_version"]
    spec = FigureSpec.model_validate(cur["spec"])
    recorded_sha = cur["provenance"]["data_sha256"]
    exports = cur["provenance"].get("exports") or {}
    report = verifier.verify_figure(tid, fid, ver_num, spec, recorded_sha, exports)
    with S.db() as c:
        c.execute(
            "INSERT INTO figure_verifications VALUES(?,?,?,?,?,?)",
            (S.uid(), fid, ver_num, report.overall_status, S.dumps(report.model_dump(mode="json")), S.now()),
        )
        c.execute('UPDATE figures SET status=CASE WHEN current_version=? THEN ? ELSE status END,updated=? WHERE id=?',
                  (ver_num, report.overall_status, S.now(), fid))
        L.append(c, tid, fid, "figure.validated", {"version": ver_num, "overall_status": report.overall_status, "tests": report.tests})
    return report.model_dump(mode="json")


def approve_figure(tid: str, fid: str, version: int, note: str) -> dict:
    if not note.strip():
        raise ValueError("Human scientific approval requires a review note")
    if len(note) > 4000: raise ValueError('Scientific approval note exceeds its explicit4000character limit')
    cur = get_figure(tid, fid, version)
    ver_num = cur["selected_version"]
    check = validate_figure_version(tid, fid, ver_num)
    if check["overall_status"] == "failed":
        raise ValueError("Cannot approve a figure that failed data/file integrity checks")
    with S.db() as c:
        fig = c.execute("SELECT payload FROM figures WHERE id=? AND topic_id=?", (fid, tid)).fetchone()
        p = json.loads(fig[0])
        if ver_num == cur['current_version']:
            p.setdefault('latest_provenance', {})['scientific_review'] = 'approved'
        p['approval'] = {'by': 'researcher', 'version': ver_num, 'note': note, 'at': S.now(),
                         'spec_sha256': cur['provenance']['spec_sha256'], 'data_sha256': cur['provenance']['data_sha256'],
                         'exports': {key: value.get('sha256') for key, value in cur['provenance'].get('exports', {}).items()}}
        p.setdefault('approvals', {})[str(ver_num)] = p['approval']
        c.execute("UPDATE figures SET status=CASE WHEN current_version=? THEN 'approved' ELSE status END,payload=?,updated=? WHERE id=?",
                  (ver_num, S.dumps(p), S.now(), fid))
        L.append(c, tid, fid, "figure.approved", p["approval"])
    return get_figure(tid, fid, ver_num)


def attach_to_paper(tid: str, fid: str, section: str = "results", version: int = 0) -> dict:
    """Insert a verified LaTeX \\includegraphics + provenance comment block into the Paper manuscript."""
    from backend.paper import writer as PW
    from backend.paper.export import tex_escape

    cur = get_figure(tid, fid, version)
    _require_real_raster(cur['provenance'])
    ver_num = cur["selected_version"]
    spec = cur["spec"]
    prov = cur["provenance"]
    check = validate_figure_version(tid, fid, ver_num)
    if check['overall_status'] == 'failed': raise ValueError('Figure data or exported files changed; manuscript use is blocked')
    if spec.get('require_approval_before_paper_use') and not cur.get('approval'):
        raise ValueError("Figure requires human scientific approval before attaching to manuscript")
    export_file_path(tid, fid, 'pdf', ver_num)  # No dangling includegraphics reference.
    snippet = (
        f"\n% PhD Lab Figure Provenance: id={fid} v{ver_num:04d} spec_sha256={prov['spec_sha256'][:16]} data_sha256={prov['data_sha256'][:16]}\n"
        "\\begin{figure}[htbp]\n"
        "  \\centering\n"
        f"  \\includegraphics[width=\\columnwidth]{{figures/{fid}_v{ver_num:04d}.pdf}}\n"
        f"  \\caption{{{tex_escape(spec.get('caption') or spec['title'])}}}\n"
        f"  \\label{{fig:{fid}}}\n"
        "\\end{figure}\n"
    )
    proj = PW.load_project()
    target_sec = section if section in PW.SECTION_TITLES else "experiments"
    proj["sections"][target_sec] = (proj["sections"].get(target_sec, "") + "\n" + snippet).strip()
    proj["section_state"][target_sec] = "edited"
    PW.save_project(proj)
    return {"attached": True, "figure_id": fid, "version": ver_num, "section": target_sec, "latex_snippet": snippet}


def export_file_path(tid: str, fid: str, fmt: str, version: int = 0) -> Path:
    cur = get_figure(tid, fid, version)
    if fmt in ('png', 'pdf'):
        _require_real_raster(cur['provenance'])
    ver_num = cur["selected_version"]
    out_dir = _figure_dir(tid, fid, ver_num)
    if fmt == "script":
        p = S.safe_child(out_dir, "source-script.py")
    elif fmt == "spec":
        p = S.safe_child(out_dir, "figure-spec.yaml")
    elif fmt == "provenance":
        p = S.safe_child(out_dir, "provenance.json")
    else:
        exports = cur["provenance"].get("exports") or {}
        if fmt not in exports:
            raise ValueError(f"Format '{fmt}' was not generated for this figure")
        p = Path(exports[fmt]["path"])
    if not p.is_file():
        raise ValueError("Requested figure file is missing on disk")
    if p.resolve() != S.safe_child(out_dir, p.name).resolve():
        raise ValueError('Figure export escaped its immutable version directory')
    # Verify integrity on export
    if fmt in (cur["provenance"].get("exports") or {}):
        expected = cur["provenance"]["exports"][fmt]["sha256"]
        import hashlib
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError("Figure file hash mismatch (tampered on disk); regeneration required")
    return p
