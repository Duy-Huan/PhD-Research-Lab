"""Execution policies, not scientific autonomy certification. Reuse the Mission authority plane."""
from backend.agent import decision_ledger as L
from backend.knowledge import research_store as S

MAX_WORKFLOWS = 4
LEVELS = [
    {"level": "L1", "interaction": "Bounded assistance; accept each answer", "experimental": False},
    {"level": "L2", "interaction": "Approved tool execution; accept each result", "experimental": False},
    {"level": "L3", "interaction": "Approved DAG; final human review and exception handling", "experimental": True},
    {"level": "L4", "interaction": "Bounded technical closure; independent checks; scientific review pending", "experimental": True},
]


def level(m):
    return (m["payload"]["spec"].get("autonomy") or {}).get("level", "")


def validate(spec):
    if spec.autonomy is None:
        return
    if spec.control is None:
        raise ValueError("Autonomy workflows require explicit supervised control and budgets")
    if spec.parent_mission_id:
        raise ValueError("Independent autonomy workflows cannot be delegated child missions")
    if spec.autonomy.level == "L1" and any(t.capability not in ("paper.inspect", "paper.compare") for t in spec.tasks):
        raise ValueError("L1 only permits bounded source inspection and synthesis")
    if spec.autonomy.level == "L4":
        allowed = {
            "paper.inspect", "paper.compare", "experiment.run", "experiment.verify",
            "mission.report", "artifact.verify",
            "paperorchestra.outline", "paperorchestra.section_write", "paperorchestra.refine",
            "paperorchestra.cite_verify", "paperorchestra.figure_integrate", "paperorchestra.full_orchestration",
        }
        if any(t.capability not in allowed for t in spec.tasks):
            raise ValueError("Experimental L4 is limited to bounded evidence and approved CPU protocols")
        last = spec.tasks[-1]
        report = next((t for t in spec.tasks if t.id == last.args.get("from_task")), None)
        if last.capability != "artifact.verify" or report is None or report.capability != "mission.report" or report.id not in last.depends_on:
            raise ValueError("L4 requires a final independent artifact verification of the report")
        # Every task must precede the final verifier, so it cannot verify an incomplete branch.
        ancestors = set(last.depends_on)
        for _ in spec.tasks:
            ancestors |= {d for t in spec.tasks if t.id in ancestors for d in t.depends_on}
        if ancestors != {t.id for t in spec.tasks[:-1]}:
            raise ValueError("L4 final verifier must depend on every workflow branch")
        for task in spec.tasks:
            if task.capability == "experiment.run" and not any(
                t.capability == "experiment.verify" and t.args.get("from_task") == task.id and task.id in t.depends_on for t in spec.tasks
            ):
                raise ValueError("L4 experiments require independent numerical verification")


def pending_review(m):
    """L1/L2 review every result; at any level a completed review.checkpoint (v6.6.4) waits for the researcher."""
    every = level(m) in ("L1", "L2")
    return next((t for t in m["tasks"] if t["status"] == "completed" and not t["payload"].get("human_review")
                 and (every or t["payload"]["spec"]["capability"] == "review.checkpoint")), None)


def step_review(tid, mid, task_id, plan_digest, result_digest, accept, note):
    from backend.agent import missions as M
    if not note.strip():
        raise ValueError("A human review note is required")
    with S.db() as c:
        m = M._get(c, mid, tid)
        task = pending_review(m)
        if m["status"] != "awaiting_step_review" or task is None or task["id"] != task_id:
            raise ValueError("Workflow is not awaiting this step review")
        if plan_digest != L.digest(m["payload"]["spec"]) or plan_digest != m["payload"]["plan_digest"] or result_digest != L.digest(task["payload"]["result"]):
            raise ValueError("Stale plan or result digest")
        task["payload"]["human_review"] = {"accept": accept, "note": note, "at": S.now(), "result_digest": result_digest, "by": "researcher"}
        c.execute("UPDATE mission_tasks SET payload=? WHERE mission_id=? AND id=?", (S.dumps(task["payload"]), mid, task_id))
        state = "queued" if accept else "cancelled"
        c.execute("UPDATE missions SET status=?,updated=? WHERE id=?", (state, S.now(), mid))
        L.append(c, tid, mid, "workflow.step_reviewed", {"task_id": task_id, **task["payload"]["human_review"]})
    return M.get(mid, tid)


def completion_state(c, m):
    """Return a technical terminal/gate state; never certify model-authored conclusions."""
    mode = level(m)
    if mode in ("L1", "L2"):
        return "awaiting_step_review" if pending_review(m) else "completed"
    if mode != "L4":
        return "awaiting_review" if m["payload"]["spec"].get("control") else "completed"
    from backend.agent.research_os import checked_artifact
    try:
        checks = []
        for task in m["tasks"]:
            result = task["payload"]["result"]
            capability = task["payload"]["spec"]["capability"]
            if capability == "paper.compare":
                text = result["output"]["text"]
                if not text.strip() or "[WARNING: output truncated" in text:
                    raise ValueError("Empty or truncated reasoning output")
            if capability in ("paperorchestra.section_write", "paperorchestra.full_orchestration"):
                text = result["output"].get("text") or result["output"].get("manuscript", "")
                if not text.strip() or "[WARNING: output truncated" in text:
                    raise ValueError("Empty or truncated paper writing output")
            if capability == "experiment.verify" and result["output"].get("status") != "verified":
                raise ValueError("Numerical evidence is not independently verified")
            if capability == "artifact.verify":
                values = result["output"].get("checks", [])
                if not values or any(v["status"] != "passed" for v in values):
                    raise ValueError("Artifact verification failed or contains no checks")
            for index, ref in enumerate(result.get("artifacts", [])):
                checked_artifact(m, task["id"], index)
                checks.append(ref["sha256"])
        if not checks:
            raise ValueError("No independently checked artifact")
    except (ValueError, OSError, KeyError) as exc:
        m["payload"]["blocking_reason"] = "Technical closure refused: " + str(exc)
        state = "paused"
    else:
        m["payload"]["technical_closure"] = {"artifacts": checks, "scientific_review": "pending", "at": S.now()}
        state = "completed"
    c.execute("UPDATE missions SET payload=? WHERE id=?", (S.dumps(m["payload"]), m["id"]))
    return state
