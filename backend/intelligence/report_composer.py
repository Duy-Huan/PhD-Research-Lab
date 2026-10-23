"""v6.4.2 Module H — Unified Research Report Composer.

Composes traceable Markdown and LaTeX technical reports from verified URAP artifacts,
v6.4.0 figures, scientific claims, and curated papers while explicitly flagging
unverified/contested claims and non-peer-reviewed preprints.
"""
from __future__ import annotations

import json
from typing import Any

from backend.intelligence.urap import list_artifacts
from backend.knowledge import corpus as K, research_store as S


def _is_preprint(paper: dict[str, Any]) -> bool:
    venue = str(paper.get("venue") or "").strip().lower()
    source = str(paper.get("source") or "").strip().lower()
    if not venue or "arxiv" in venue or "biorxiv" in venue or "medrxiv" in venue or "preprint" in venue:
        return True
    if source == "arxiv" and not venue:
        return True
    return False


def compose_report_manifest(
    topic_id: str,
    mission_id: str = "",
    *,
    title: str = "",
    artifact_ids: list[str] | None = None,
    sections: list[dict[str, Any]] | None = None,
    export_format: str = "md",
) -> dict[str, Any]:
    """Assemble a verified research report manifest and generate Markdown/LaTeX output."""
    topic = S.get_topic(topic_id)
    report_title = (title or topic.get("title") or f"Research Report — {topic_id}").strip()
    fmt = export_format.lower().strip() if export_format else "md"
    if fmt not in ("md", "tex", "json"):
        fmt = "md"

    with S.db() as c:
        claim_rows = c.execute(
            "SELECT * FROM scientific_claims WHERE topic_id=? ORDER BY id ASC",
            (topic_id,),
        ).fetchall()
        claims = [{**dict(r), "payload": json.loads(r["payload"])} for r in claim_rows]

        fig_rows = c.execute(
            "SELECT * FROM figures WHERE topic_id=? ORDER BY created ASC",
            (topic_id,),
        ).fetchall()
        figures = [{**dict(r), "payload": json.loads(r["payload"])} for r in fig_rows]

    papers = (K.search(topic_id, q="", limit=30).get("papers") or [])
    all_artifacts = list_artifacts(topic_id=topic_id, mission_id=mission_id or "")
    if artifact_ids:
        wanted = set(artifact_ids)
        selected_artifacts = [a for a in all_artifacts if a["artifact_id"] in wanted]
    else:
        selected_artifacts = all_artifacts

    verified_claims: list[dict[str, Any]] = []
    unverified_warnings: list[dict[str, Any]] = []
    for c in claims:
        status = str(c.get("status") or "").lower()
        cpayload = c.get("payload") or {}
        entry = {
            "claim_id": c["id"],
            "claim_text": cpayload.get("text", ""),
            "kind": cpayload.get("kind", "empirical"),
            "status": status,
        }
        if status in ("supported", "verified", "accepted", "promoted"):
            verified_claims.append(entry)
        else:
            entry["warning"] = "UNVERIFIED_OR_CONTESTED_CLAIM"
            unverified_warnings.append(entry)

    for art in selected_artifacts:
        v_status = str((art.get("verification") or {}).get("status") or "unverified").lower()
        if v_status not in ("user_verified", "auto_screened", "verified", "approved"):
            unverified_warnings.append({
                "artifact_id": art["artifact_id"],
                "artifact_type": art.get("artifact_type", ""),
                "status": v_status,
                "warning": f"ARTIFACT_{v_status.upper()}",
            })

    citations: list[dict[str, Any]] = []
    for p in papers:
        preprint = _is_preprint(p)
        citations.append({
            "paper_id": p["id"],
            "title": p.get("title", ""),
            "year": p.get("year"),
            "doi": p.get("doi"),
            "venue": p.get("venue") or ("arXiv Preprint" if preprint else "Peer-Reviewed"),
            "is_preprint": preprint,
            "badge": "[PREPRINT]" if preprint else "[PEER-REVIEWED]",
        })

    figure_entries: list[dict[str, Any]] = []
    for f in figures:
        fpay = f.get("payload") or {}
        figure_entries.append({
            "figure_id": f["id"],
            "title": f.get("title", ""),
            "category": f.get("category", ""),
            "status": f.get("status", "draft"),
            "current_version": f.get("current_version", 1),
            "paper_section": fpay.get("paper_section") or "Results",
        })

    md_lines = [
        f"# {report_title}",
        "",
        f"- **Topic ID**: `{topic_id}`",
        f"- **Mission ID**: `{mission_id or 'default'}`",
        f"- **Verified Claims**: {len(verified_claims)} | **Flagged / Unverified Items**: {len(unverified_warnings)}",
        "",
        "## 1. Executive Summary & Verified Findings",
    ]
    if verified_claims:
        for vc in verified_claims:
            md_lines.append(f"- **[VERIFIED]** {vc['claim_text']} (`{vc['claim_id']}`)")
    else:
        md_lines.append("- No confirmed empirical claims promoted yet.")

    md_lines.extend(["", "## 2. Unverified Hypotheses & Contested Claims"])
    if unverified_warnings:
        for uw in unverified_warnings:
            label = uw.get("claim_text") or uw.get("artifact_id") or "Unverified item"
            md_lines.append(f"- **[UNVERIFIED / HYPOTHESIS — {uw['status']}]** {label}")
    else:
        md_lines.append("- None. All included artifacts and claims passed verification.")

    md_lines.extend(["", "## 3. Figures & Provenance"])
    if figure_entries:
        for fe in figure_entries:
            md_lines.append(
                f"- **Figure `{fe['figure_id']}` (v{fe['current_version']})**: {fe['title']} "
                f"[{fe['category']} | status: `{fe['status']}`]"
            )
    else:
        md_lines.append("- No figures attached.")

    md_lines.extend(["", "## 4. Artifact Lineage (URAP 1.0)"])
    for art in selected_artifacts:
        sha = ((art.get("content") or {}).get("sha256") or "")[:16]
        v_st = (art.get("verification") or {}).get("status", "unverified")
        md_lines.append(
            f"- `{art['artifact_id']}` ({art['artifact_type']}): "
            f"status `{v_st}`, sha256 `{sha}...`"
        )

    md_lines.extend(["", "## 5. References & Preprint Classification"])
    for cit in citations:
        md_lines.append(f"- {cit['badge']} {cit['title']} ({cit.get('year') or 'n.d.'}) — *{cit['venue']}*")

    markdown_body = "\n".join(md_lines) + "\n"

    manifest_id = f"rep-{S.uid()[:10]}"
    now = S.now()
    out_dir = S.safe_child(S.store_dir(), "topics", topic_id, "reports", manifest_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = "tex" if fmt == "tex" else "md"
    out_file = out_dir / f"report.{ext}"
    if fmt == "tex":
        tex_body = (
            "\\documentclass{article}\n\\begin{document}\n"
            f"\\title{{{report_title}}}\n\\maketitle\n"
            "\\section{Verified Findings}\n"
            + "\n".join(f"\\item {vc['claim_text']}" for vc in verified_claims)
            + "\n\\end{document}\n"
        )
        out_file.write_text(tex_body, encoding="utf-8")
    else:
        out_file.write_text(markdown_body, encoding="utf-8")

    manifest_obj = {
        "manifest_id": manifest_id,
        "topic_id": topic_id,
        "mission_id": mission_id,
        "title": report_title,
        "status": "ready_with_warnings" if unverified_warnings else "verified",
        "export_format": fmt,
        "export_path": str(out_file),
        "verified_claims": verified_claims,
        "unverified_warnings": unverified_warnings,
        "figures": figure_entries,
        "artifacts": [a["artifact_id"] for a in selected_artifacts],
        "citations": citations,
        "sections": sections or [],
        "markdown": markdown_body,
        "created_at": now,
    }

    with S.db() as c:
        c.execute(
            "INSERT INTO report_manifests VALUES(?,?,?,?,?,?,?)",
            (manifest_id, topic_id, mission_id, report_title, manifest_obj["status"], S.dumps(manifest_obj), now),
        )

    return manifest_obj
