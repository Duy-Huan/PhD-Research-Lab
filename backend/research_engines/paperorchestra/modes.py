"""L2-L4 Execution Modes & Mission Task Dispatcher for PaperOrchestra.

Maps the three operational modes directly to PhD Lab's core contracts:
- L2: Human-controlled individual paper capabilities with step reviews.
- L3: Harness-created specialist writing team with parallel tasks & checkpoints.
- L4: Goal-driven research-to-paper workflow with independent verification & closure.
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.agent import decision_ledger as L
from backend.agent.mission_contracts import (
    AgentRole,
    ArtifactManifest,
    AutonomyPolicy,
    ExecutionResult,
    Limits,
    MissionControl,
    MissionSpec,
    Task,
    TaskAssignment,
    TeamPlan,
)
from backend.knowledge import research_store as S
from backend.research_engines.paperorchestra.artifact_store import save_artifact
from backend.research_engines.paperorchestra.backends.skill_backend import (
    generate_outline,
    refine_and_polish,
    write_section,
)
from backend.research_engines.paperorchestra.contracts import WritingArtifact
from backend.research_engines.paperorchestra.quality_gates import (
    compile_and_preview_latex,
    evaluate_quality_gates,
    run_independent_review,
    verify_citations,
    verify_experiment_provenance,
    verify_figure_sources,
)


def create_l2_paper_mission(
    topic_id: str,
    objective: str,
    capability: str,
    args: dict[str, Any],
    paper_ids: list[str] | None = None,
    time_limit_s: int = 600,
) -> MissionSpec:
    """L2 Mode: Single-step human-approved capability task."""
    p_ids = paper_ids or []
    task = Task(
        id=f"po_{capability.replace('paperorchestra.', '')}",
        capability=capability,
        args={"question": objective, "paper_ids": p_ids, **args},
        preferred_engine="paperorchestra",
    )
    return MissionSpec(
        topic_id=topic_id,
        objective=objective,
        inputs=p_ids,
        permissions=["workspace_write", "reasoning", "network"],
        limits=Limits(max_tasks=1, max_seconds=time_limit_s, max_reasoning_calls=1),
        control=MissionControl(
            success_criteria=["Human approves step writing artifact"],
            allowed_engines=["deterministic", "app"],
            end_date=S.now(),
            max_wall_seconds=time_limit_s,
        ),
        autonomy=AutonomyPolicy(level="L2", max_output_tokens=2048),
        tasks=[task],
    )


def create_l3_team_mission(
    topic_id: str,
    objective: str,
    paper_ids: list[str] | None = None,
    style: str = "IEEE",
    target_venue: str = "",
    time_limit_s: int = 1800,
) -> MissionSpec:
    """L3 Mode: Specialist writing team DAG with parallel execution and human checkpoint."""
    p_ids = paper_ids or []

    # Tasks DAG: Outline -> Lit Review & Methods -> Experiments & Discussion -> Verifier check -> Report
    t_outline = Task(
        id="draft_outline",
        capability="paperorchestra.outline",
        args={"question": objective, "paper_ids": p_ids, "style": style},
        preferred_engine="paperorchestra",
    )
    t_lit = Task(
        id="draft_lit_review",
        capability="paperorchestra.section_write",
        depends_on=["draft_outline"],
        args={"section": "related_work", "from_task": "draft_outline", "paper_ids": p_ids, "question": objective},
        preferred_engine="paperorchestra",
    )
    t_method = Task(
        id="draft_methodology",
        capability="paperorchestra.section_write",
        depends_on=["draft_outline"],
        args={"section": "methodology", "from_task": "draft_outline", "question": objective},
        preferred_engine="paperorchestra",
    )
    t_experiments = Task(
        id="draft_experiments",
        capability="paperorchestra.section_write",
        depends_on=["draft_methodology"],
        args={"section": "experiments", "from_task": "draft_methodology", "question": objective},
        preferred_engine="paperorchestra",
    )
    t_refine = Task(
        id="refine_manuscript",
        capability="paperorchestra.refine",
        depends_on=["draft_lit_review", "draft_experiments"],
        args={"from_task": "draft_experiments", "style": style, "venue": target_venue},
        preferred_engine="paperorchestra",
    )
    t_verify = Task(
        id="verify_manuscript",
        capability="paperorchestra.cite_verify",
        depends_on=["refine_manuscript"],
        args={"from_task": "refine_manuscript", "paper_ids": p_ids},
        preferred_engine="paperorchestra",
    )
    t_report = Task(
        id="final_paper_report",
        capability="mission.report",
        depends_on=["verify_manuscript"],
        args={"title": f"PaperOrchestra Manuscript Report: {objective[:60]}"},
        preferred_engine="deterministic",
    )

    tasks = [t_outline, t_lit, t_method, t_experiments, t_refine, t_verify, t_report]

    # Specialist roles
    r_lead = AgentRole(
        id="lead_author",
        purpose="Architect paper outline and synthesize sections",
        capabilities=["paperorchestra.outline", "paperorchestra.section_write", "paperorchestra.refine", "mission.report"],
        permissions=["workspace_write", "reasoning", "network"],
        engines=["app"],
        expected_value="High-coherence manuscript draft",
    )
    r_methods = AgentRole(
        id="methods_writer",
        purpose="Formalize methodology and document experimental results",
        capabilities=["paperorchestra.section_write"],
        permissions=["workspace_write", "reasoning"],
        engines=["app"],
        expected_value="Precise mathematical formulations and empirical transparency",
    )
    r_lit = AgentRole(
        id="literature_curator",
        purpose="Curate literature and integrate grounded citations",
        capabilities=["paperorchestra.section_write"],
        permissions=["workspace_write", "reasoning", "network"],
        engines=["app"],
        expected_value="Grounded citations without hallucinations",
    )
    r_verifier = AgentRole(
        id="manuscript_verifier",
        purpose="Independent verification of citations, figures, and LaTeX",
        capabilities=["paperorchestra.cite_verify", "mission.report"],
        permissions=["workspace_write"],
        engines=["app"],
        expected_value="Independent validation of all scientific claims",
    )

    assignments = [
        TaskAssignment(task_id="draft_outline", owner="lead_author", verifier="manuscript_verifier", acceptance=["Valid outline"]),
        TaskAssignment(task_id="draft_lit_review", owner="literature_curator", verifier="manuscript_verifier", acceptance=["Grounded citations"]),
        TaskAssignment(task_id="draft_methodology", owner="methods_writer", verifier="manuscript_verifier", acceptance=["Formal methods"]),
        TaskAssignment(task_id="draft_experiments", owner="methods_writer", verifier="manuscript_verifier", acceptance=["Measured results"]),
        TaskAssignment(task_id="refine_manuscript", owner="lead_author", verifier="manuscript_verifier", acceptance=["Refined LaTeX"]),
        TaskAssignment(task_id="verify_manuscript", owner="manuscript_verifier", verifier="manuscript_verifier", acceptance=["Citation check"]),
        TaskAssignment(task_id="final_paper_report", owner="lead_author", verifier="manuscript_verifier", acceptance=["Complete report"]),
    ]

    team_plan = TeamPlan(
        mode="adaptive",
        agents=[r_lead, r_methods, r_lit, r_verifier],
        assignments=assignments,
        max_agents=4,
    )

    return MissionSpec(
        topic_id=topic_id,
        objective=objective,
        inputs=p_ids,
        permissions=["workspace_write", "reasoning", "network"],
        limits=Limits(max_tasks=len(tasks), max_seconds=time_limit_s, max_reasoning_calls=3),
        control=MissionControl(
            success_criteria=["Specialist team produces verified LaTeX manuscript"],
            allowed_engines=["deterministic", "app"],
            end_date=S.now(),
            max_wall_seconds=time_limit_s,
        ),
        team=team_plan,
        autonomy=AutonomyPolicy(level="L3", max_output_tokens=2048),
        tasks=tasks,
    )


def create_l4_research_to_paper_mission(
    topic_id: str,
    objective: str,
    paper_ids: list[str],
    protocol_id: str = "",
    protocol_digest: str = "",
    approval_nonce: str = "",
    style: str = "IEEE",
    time_limit_s: int = 3600,
) -> MissionSpec:
    """L4 Mode: Goal-driven research-to-paper workflow with verified closure."""
    tasks: list[Task] = [
        Task(id="grounding", capability="paper.inspect", args={"paper_ids": paper_ids}, preferred_engine="deterministic"),
        Task(id="outline", capability="paperorchestra.outline", depends_on=["grounding"], args={"question": objective, "paper_ids": paper_ids, "style": style}, preferred_engine="paperorchestra"),
    ]

    prev_dep = "outline"
    if protocol_id and approval_nonce:
        tasks.append(Task(
            id="experiment",
            capability="experiment.run",
            depends_on=[prev_dep],
            args={"protocol_id": protocol_id, "protocol_digest": protocol_digest, "approval_nonce": approval_nonce},
            preferred_engine="deterministic",
        ))
        tasks.append(Task(
            id="verify_experiment",
            capability="experiment.verify",
            depends_on=["experiment"],
            args={"from_task": "experiment"},
            preferred_engine="deterministic",
        ))
        prev_dep = "verify_experiment"

    tasks.append(Task(
        id="section_intro",
        capability="paperorchestra.section_write",
        depends_on=[prev_dep],
        args={"section": "introduction", "from_task": prev_dep, "question": objective, "paper_ids": paper_ids},
        preferred_engine="paperorchestra",
    ))
    tasks.append(Task(
        id="section_methods",
        capability="paperorchestra.section_write",
        depends_on=["section_intro"],
        args={"section": "methodology", "from_task": "section_intro", "question": objective},
        preferred_engine="paperorchestra",
    ))
    tasks.append(Task(
        id="section_experiments",
        capability="paperorchestra.section_write",
        depends_on=["section_methods"],
        args={"section": "experiments", "from_task": "section_methods", "question": objective},
        preferred_engine="paperorchestra",
    ))
    tasks.append(Task(
        id="cite_check",
        capability="paperorchestra.cite_verify",
        depends_on=["section_experiments"],
        args={"from_task": "section_experiments", "paper_ids": paper_ids},
        preferred_engine="paperorchestra",
    ))
    tasks.append(Task(
        id="refine",
        capability="paperorchestra.refine",
        depends_on=["cite_check"],
        args={"from_task": "cite_check", "style": style},
        preferred_engine="paperorchestra",
    ))
    tasks.append(Task(
        id="report",
        capability="mission.report",
        depends_on=["refine"],
        args={"title": f"L4 Manuscript Report: {objective[:50]}"},
        preferred_engine="deterministic",
    ))
    tasks.append(Task(
        id="artifact_integrity",
        capability="artifact.verify",
        depends_on=["report"],
        args={"from_task": "report"},
        preferred_engine="deterministic",
    ))

    perms = ["workspace_write", "reasoning", "network"]
    if protocol_id:
        perms.append("compute")

    return MissionSpec(
        topic_id=topic_id,
        objective=objective,
        inputs=paper_ids,
        permissions=perms,
        limits=Limits(max_tasks=len(tasks), max_seconds=time_limit_s, max_reasoning_calls=3),
        control=MissionControl(
            success_criteria=["Generate verified manuscript artifact with technical closure"],
            allowed_engines=["deterministic", "app"],
            end_date=S.now(),
            max_wall_seconds=time_limit_s,
        ),
        autonomy=AutonomyPolicy(level="L4", max_output_tokens=2048),
        tasks=tasks,
    )


async def execute_mission_task(m: dict, task: Task, key: str) -> ExecutionResult:
    """Dispatch paperorchestra.* capabilities within PhD Lab's mission worker loop."""
    tid = m["topic_id"]
    mid = m["id"]

    if task.capability == "paperorchestra.outline":
        obj = task.args.get("question") or m["payload"]["spec"]["objective"]
        p_ids = task.args.get("paper_ids") or m["payload"]["spec"].get("inputs", [])
        style = task.args.get("style", "IEEE")

        outline = await asyncio.to_thread(generate_outline, tid, obj, p_ids, style)
        content_json = outline.model_dump_json(indent=2)
        art = WritingArtifact.create(
            task_id=task.id,
            parent_workflow_id=mid,
            topic_id=tid,
            section_id="outline",
            title=outline.paper_title,
            content=content_json,
            agent_id="outline_agent",
            provider_id="paperorchestra",
        )
        saved = await asyncio.to_thread(save_artifact, art, sync_paper_section=False)
        return ExecutionResult(
            status="completed",
            engine="paperorchestra",
            output={"outline": outline.model_dump(mode="json"), "artifact_id": saved.artifact_id},
            artifacts=[ArtifactManifest(path=saved.storage_path, sha256=saved.content_hash, bytes=len(content_json.encode()))],
        )

    if task.capability == "paperorchestra.section_write":
        sec_id = task.args.get("section", "introduction")
        obj = task.args.get("question") or m["payload"]["spec"]["objective"]
        p_ids = task.args.get("paper_ids") or m["payload"]["spec"].get("inputs", [])
        style = task.args.get("style", "IEEE")

        context = ""
        if task.args.get("from_task"):
            prev = next((t for t in m["tasks"] if t["id"] == task.args["from_task"]), None)
            if prev:
                context = str((prev.get("payload") or {}).get("result", {}).get("output", {}))

        from backend.knowledge.corpus import cite_key
        text = await asyncio.to_thread(write_section, tid, sec_id, obj, context, None, [cite_key(p) for p in p_ids], style)
        art = WritingArtifact.create(
            task_id=task.id,
            parent_workflow_id=mid,
            topic_id=tid,
            section_id=sec_id,
            title=f"Section: {sec_id}",
            content=text,
            agent_id="section_writer",
            provider_id="paperorchestra",
        )
        saved = await asyncio.to_thread(save_artifact, art, sync_paper_section=True)
        return ExecutionResult(
            status="completed",
            engine="paperorchestra",
            output={"section": sec_id, "text": text[:500], "artifact_id": saved.artifact_id},
            artifacts=[ArtifactManifest(path=saved.storage_path, sha256=saved.content_hash, bytes=len(text.encode()))],
        )

    if task.capability == "paperorchestra.cite_verify":
        p_ids = task.args.get("paper_ids") or m["payload"]["spec"].get("inputs", [])
        # Find preceding manuscript text
        text = ""
        if task.args.get("from_task"):
            prev = next((t for t in m["tasks"] if t["id"] == task.args["from_task"]), None)
            if prev:
                res_out = (prev.get("payload") or {}).get("result", {}).get("output", {})
                text = res_out.get("text") or res_out.get("manuscript", "")
        if not text:
            # Fallback to loading current sections from project.json
            from backend.paper.writer import load_project
            text = "\n\n".join(load_project().get("sections", {}).values())

        report = await asyncio.to_thread(verify_citations, tid, text)
        rep_json = report.model_dump_json(indent=2)
        art = WritingArtifact.create(
            task_id=task.id,
            parent_workflow_id=mid,
            topic_id=tid,
            section_id="citation_report",
            title="Citation Verification Report",
            content=rep_json,
            agent_id="manuscript_verifier",
            provider_id="paperorchestra",
        )
        saved = await asyncio.to_thread(save_artifact, art, sync_paper_section=False)
        return ExecutionResult(
            status="completed",
            engine="paperorchestra",
            output={"report": report.model_dump(mode="json"), "artifact_id": saved.artifact_id},
            artifacts=[ArtifactManifest(path=saved.storage_path, sha256=saved.content_hash, bytes=len(rep_json.encode()))],
        )

    if task.capability == "paperorchestra.refine":
        style = task.args.get("style", "IEEE")
        from backend.paper.writer import load_project
        sections = load_project().get("sections", {})
        refined_sections = {}
        for sid, text in sections.items():
            refined_sections[sid] = await asyncio.to_thread(refine_and_polish, sid, text, None, style)

        # Assemble full text
        full_text = "\n\n".join(refined_sections.values())
        art = WritingArtifact.create(
            task_id=task.id,
            parent_workflow_id=mid,
            topic_id=tid,
            section_id="full_manuscript",
            title="Refined Full Manuscript",
            content=full_text,
            agent_id="refinement_agent",
            provider_id="paperorchestra",
        )
        saved = await asyncio.to_thread(save_artifact, art, sync_paper_section=True)
        return ExecutionResult(
            status="completed",
            engine="paperorchestra",
            output={"refined_sections": list(refined_sections.keys()), "artifact_id": saved.artifact_id},
            artifacts=[ArtifactManifest(path=saved.storage_path, sha256=saved.content_hash, bytes=len(full_text.encode()))],
        )

    if task.capability == "paperorchestra.figure_integrate":
        fig_id = task.args.get("figure_id", "")
        from backend.paper.writer import load_project
        p = load_project()
        fig_tex = f"\n\\begin{{figure}}[htbp]\n\\centering\n\\includegraphics[width=\\columnwidth]{{figures/{fig_id}}}\n\\caption{{System evaluation and architectural overview.}}\n\\label{{fig:{fig_id}}}\n\\end{{figure}}\n"
        # Append to experiments section
        exp_text = p.get("sections", {}).get("experiments", "")
        if fig_tex not in exp_text:
            exp_text += fig_tex
            p.setdefault("sections", {})["experiments"] = exp_text
            from backend.paper.writer import save_project
            save_project(p)

        art = WritingArtifact.create(
            task_id=task.id,
            parent_workflow_id=mid,
            topic_id=tid,
            section_id="experiments_figure_integrated",
            title=f"Figure Integration: {fig_id}",
            content=exp_text,
            agent_id="visualization_agent",
            provider_id="paperorchestra",
        )
        saved = await asyncio.to_thread(save_artifact, art, sync_paper_section=True)
        return ExecutionResult(
            status="completed",
            engine="paperorchestra",
            output={"figure_id": fig_id, "status": "integrated", "artifact_id": saved.artifact_id},
            artifacts=[ArtifactManifest(path=saved.storage_path, sha256=saved.content_hash, bytes=len(exp_text.encode()))],
        )

    if task.capability == "paperorchestra.full_orchestration":
        obj = task.args.get("question") or m["payload"]["spec"]["objective"]
        p_ids = task.args.get("paper_ids") or m["payload"]["spec"].get("inputs", [])
        style = task.args.get("style", "IEEE")

        outline = await asyncio.to_thread(generate_outline, tid, obj, p_ids, style)
        from backend.knowledge.corpus import cite_key
        from backend.research_engines.paperorchestra.evidence import gather
        evidence = await asyncio.to_thread(gather, tid)  # v6.6.4: library and measured runs, once for every section
        sections = {}
        for sec in outline.sections:
            hints = [h if h in evidence.keys else cite_key(h) for h in sec.citation_hints]
            sec_text = await asyncio.to_thread(write_section, tid, sec.section_id, obj, "", sec.bullet_points,
                                               [h for h in hints if h in evidence.keys], style, evidence.text)
            sections[sec.section_id] = sec_text

        q_report = await asyncio.to_thread(evaluate_quality_gates, tid, sections, m.get("tasks", []))
        full_text = "\n\n".join(sections.values())
        art = WritingArtifact.create(
            task_id=task.id,
            parent_workflow_id=mid,
            topic_id=tid,
            section_id="complete_manuscript",
            title=f"Full Manuscript: {outline.paper_title}",
            content=full_text,
            agent_id="paperorchestra_orchestrator",
            provider_id="paperorchestra",
            execution_metrics={"sections_count": len(sections), "overall_readiness": q_report.overall_readiness},
        )
        saved = await asyncio.to_thread(save_artifact, art, sync_paper_section=True)
        return ExecutionResult(
            status="completed",
            engine="paperorchestra",
            output={"manuscript": full_text[:600], "quality_report": q_report.model_dump(mode="json"), "artifact_id": saved.artifact_id},
            artifacts=[ArtifactManifest(path=saved.storage_path, sha256=saved.content_hash, bytes=len(full_text.encode()))],
            limitations=["Scientific claims remain pending human review prior to submission"],
        )

    raise ValueError(f"Unknown PaperOrchestra capability '{task.capability}'")

