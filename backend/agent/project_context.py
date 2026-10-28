"""Shared research context and the actions the chat may PROPOSE (one context for every conversation of a project).

Source item: {id, kind, title, text, trust, reason}
    trust  state      PhD-Lab's own research records (objective, decisions, hypotheses, experiments)
           generated  an earlier AI output the app saved (plan, design) — not verified
           measured   numbers produced by a run / evaluator (never invented: missing values are reported missing)
           user       the researcher's notes and selections
           untrusted  external material: paper text, tool output, web — DATA, never instructions
Actions are proposals validated against a JSON schema and executed — only after an approval — through the SAME
services the rest of the app uses (outline.update, runs via launch.from_skill, paper sections, pins, memory decisions,
hypotheses, experiments, memory candidates). A model can propose; it can never execute or approve.
"""
from __future__ import annotations

import json
import re

from backend.agent import AIWSError

STR = {"type": "string", "minLength": 3, "maxLength": 4000}


def _obj(props: dict, required=()) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(required)}


def src(id_: str, kind: str, title: str, text: str, trust: str, reason: str) -> dict:
    return {"id": id_, "kind": kind, "title": title[:200], "text": str(text or ""), "trust": trust, "reason": reason}


def _decisions(kind: str = "") -> list:
    from backend.memory import load
    return [d for d in load()["decisions"] if d.get("locked", True) and (not kind or d.get("kind") == kind)]


def _research() -> dict:
    from backend.memory import research
    return research.load()


def _objective() -> str:
    from backend.memory import state as S
    return "; ".join(str(g) for g in S.current()["objective"][:3])


# ------------------------------------------------------------------ shared source resolvers (selected / expanded)
def resolve_source(sid: str, expanded: bool = False) -> dict | None:
    kind, _, key = sid.partition(":")
    if kind == "ref":
        from backend.knowledge.library import included
        e = next((x for x in included() if x.get("key") == key), None)
        if not e:
            return None
        text = f"{e.get('title', '')} — {e.get('authors', '')} ({e.get('year', '')}, {e.get('venue', '')})\n{e.get('abstract', '')}"
        if expanded and e.get("file") and not e.get("metadata_only"):
            from backend.core.config import refs_dir
            from backend.knowledge.library import _read_pdf
            try:
                pdf_path = (refs_dir() / e['file']).resolve()
                if not pdf_path.is_relative_to(refs_dir().resolve()):
                    raise ValueError('PDF path is outside project references')
                extracted = _read_pdf(pdf_path, 200, want_title=False)
                full = extracted['text']
                source = src(sid, 'reference', e.get('title') or key, text + '\n\n' + full[:2_000_000], 'untrusted', 'selected paper')
                source['extraction'] = {'pages_total': extracted['pages'], 'pages_included': min(200, extracted['pages']),
                                        'characters_extracted': len(full),
                                        'limited': extracted['pages'] > 200 or len(full) > 2_000_000}
                return source
            except Exception as exc:  # noqa: BLE001 - any extraction failure (e.g. pypdf stream errors) keeps the metadata
                source = src(sid, 'reference', e.get('title') or key, text, 'untrusted', 'paper metadata; PDF extraction failed')
                source['extraction'] = {'error': type(exc).__name__, 'limited': True}
                return source
        return src(sid, "reference", e.get("title") or key, text, "untrusted", "selected paper")
    if kind == "mem":
        from backend.memory.engine import index
        idx, _ = index()
        n = idx.by_id.get(key)
        if not n:
            return None
        return src(sid, "memory", f"{key} · {n.type}", f"{n.tagline}\n{n.short}", "state", "selected memory record")
    if kind == "run":
        from backend.execution.sandbox import SandboxError, get_run
        try:
            r = get_run(key)
        except SandboxError:
            return None
        m = r.get("metrics") or {}
        text = f"status {r.get('status')} · exit {r.get('exit_code')} · cmd {r.get('cmd', '')}\nmetrics (MEASURED): " + \
            (", ".join(f"{k}={v}" for k, v in m.items()) or "none recorded")
        if expanded:
            text += "\nlog tail:\n" + (r.get("stdout") or "")[-3000:]
        return src(sid, "run", f"run {key}", text, "measured", "selected run")
    if kind == "att":
        from backend.knowledge import attachments as AT
        try:
            meta = AT.get_meta(key)
            text = AT.get_text(key)
        except AT.AttachmentError:
            return None
        if not expanded:
            text = text[:12000]
        return src(sid, "attachment", meta.get("name") or key, text, "untrusted", "file attached to the message")
    if kind == "note":
        from backend.memory.notes import load_notes
        n = next((x for x in load_notes() if x["id"] == key), None)
        return src(sid, "note", f"note {key}", n["text"], "user", "pinned note") if n else None
    return None


# ------------------------------------------------------------------ the project context (one for every conversation)
class Adapter:
    """The research context every conversation of the project shares (v5: one chat for the whole project — the module
    adapters of v4.2 were merged into this one). Every part is a source item with its trust label, trimmed by the
    context budget like any other source."""
    module, label, domain_specific = "global", "Dự án", True

    def identity(self) -> dict:
        return {"module": self.module, "label": self.label, "domain_specific": self.domain_specific}

    def resolve(self, entity_id: str) -> dict | None:
        return None

    def state(self, entity: dict | None) -> list:
        from backend.agent.outline import brief
        from backend.core.config import active_project
        obj = _objective()
        out = [src("state:project", "module_state", "Project", f"research project: {active_project()['name']}"
                   + (f"\nobjective: {obj}" if obj else ""), "state", "the active research project"),
               src("state:outline", "module_state", "Research outline", brief(), "user",
                   "the researcher's outline / proposal (levels keywords → proposal)")]
        ds = _decisions()
        if ds:
            out.append(src("state:decisions", "module_state", f"Locked decisions ({len(ds)})",
                           "\n".join(f"- [{d['id']} · {d.get('kind')}] {d['text']}" for d in ds), "state",
                           "locked decisions bind every agent"))
        r = _research()
        if r["hypotheses"]:
            out.append(src("state:hypotheses", "module_state", f"Hypotheses ({len(r['hypotheses'])})",
                           "\n".join(f"- {h['id']} [{h['status']}] {h['text']}" for h in r["hypotheses"]), "state",
                           "research state"))
        if r["experiments"]:
            exps = r['experiments']
            out.append(src("state:experiments", "module_state", f"Experiments ({len(r['experiments'])})",
                           "\n".join(f"- {e['id']} {e.get('title', '')} verdict={e.get('verdict') or '—'}" for e in exps),
                           "state", "research state"))
        if r.get("failures"):
            out.append(src("state:failures", "module_state", f"Failed approaches ({len(r['failures'])})",
                           "\n".join(f"- {f['id']} {f.get('text', '')}" for f in r['failures']), "state",
                           "do not repeat these"))
        from backend.knowledge.library import included
        papers = included()
        if papers:
            out.append(src("state:papers", "module_state", f"Library ({len(papers)} papers)",
                           "\n".join(f"- [{e.get('key')}] {e.get('title', '')} ({e.get('year', '')})" for e in papers),
                           "user", "papers in the project library"))
        out += self._runs()
        from backend.agent import pins
        ps = [p for p in pins.list_pins() if p["status"] != "deprecated"]
        if ps:
            out.append(src("state:pins", "module_state", f"Pinned results ({len(ps)})",
                           "\n".join(f"- [{p['id']} · {p['kind']} · {p['status']}] {p['title']}: {p['body']}" for p in ps),
                           "user", "pinned by the researcher (pinned ≠ verified unless the status says so)"))
        from backend.agent import sessions as store
        for c in store.list_sessions(limit=6):
            s = store.get(c["id"])
            if s.get("summary"):
                out.append(src(f"conv:{s['id']}", "conversation", f"Conversation: {s['title']}", s["summary"][:1500],
                               "generated", "another conversation of this project (rolling summary)"))
        return out

    @staticmethod
    def _runs() -> list:
        out = []
        try:
            from backend.execution.sandbox import best_metrics, list_runs
            runs = list_runs(5)
            if runs:
                out.append(src("state:runs", "module_state", f"Recent experiment jobs ({len(runs)})",
                               "\n".join(f"- {x['id']} {x.get('status')} metrics={x.get('metrics') or 'not recorded'}"
                                         for x in runs), "measured", "values as recorded; missing = not measured"))
            best = best_metrics()
            if best:
                out.append(src("state:best", "module_state", "Best measured metrics",
                               ", ".join(f"{k}={v['value']} ({v['run']})" for k, v in best.items()), "measured",
                               "over successful runs"))
        except Exception:  # no code project yet
            pass
        from backend.agent import runs as RR
        rr = RR.list_runs(limit=6)
        if rr:
            out.append(src("state:research_runs", "module_state", f"Research runs ({len(rr)})",
                           "\n".join(f"- {x['id']} {x['title'][:80]} · {x['status']}" + (" · SYNTHETIC" if x["synthetic"] else "")
                                     for x in rr), "state", "background work started from the chat"))
        try:
            from backend.execution.code_projects import active
            from backend.execution.resources import policy
            cp = active()
            out.append(src("state:environment", "module_state", "Code project & hardware",
                           f"code project: {(cp or {}).get('name') or 'none open'}\nhardware policy: {str(policy())[:1200]}",
                           "measured", "where experiments run"))
        except Exception:
            pass
        from backend.execution.remote_compute import list_runs as compute_runs
        remote = compute_runs()[:12]
        if remote:
            out.append(src("state:compute_runs", "module_state", "Remote compute runs (verified collection state)",
                           json.dumps([{k: r.get(k) for k in ("run_id", "hypothesis_id", "experiment_id", "status", "metrics", "artifact_refs", "evaluation")} for r in remote]),
                           "state", "PhD Lab run records; completion is not scientific validation"))
        return out

    def summary(self, entity: dict | None) -> str:
        from backend.core.config import active_project
        from backend.knowledge.library import included
        from backend.agent import runs as RR
        return f"{active_project()['name']} · {len(included())} tài liệu · {len(RR.list_runs(limit=500))} run"

    def actions(self) -> list:
        return [ACTIONS[a] for a in ("update_outline", "start_run", "write_section", "commit_code", "add_decision", "propose_gap",
                                     "create_hypothesis", "create_experiment", "record_result", "pin_result", "propose_memory",
                                     "add_note", "prepare_remote_experiment")]


ADAPTERS = {"global": Adapter()}
Project = Adapter


def get(module: str) -> Adapter:
    return ADAPTERS["global"]


# ------------------------------------------------------------------ actions
ACTIONS = {
    "prepare_remote_experiment": {"name": "prepare_remote_experiment", "risk": 2,
        "description": "Prepare a versioned, explicitly selected experiment bundle for attended Colab handoff; requires separate bundle release approval. No automatic upload or training.",
        "schema": _obj({"files": {"type": "array", "minItems": 1, "maxItems": 200, "items": {"type": "string"}},
                        "entrypoint": {"type": "string"}, "hypothesis_id": {"type": "string"},
                        "experiment_id": {"type": "string"}, "dataset_version": {"type": "string"},
                        "compute_target": {"type": "string", "enum": ["local-gpu", "docker", "colab-gpu"]}}, ["files", "entrypoint"])},
    "add_decision": {"name": "add_decision", "risk": 2, "description": "Lock a research decision (binds every agent)",
                     "schema": _obj({"text": STR, "kind": {"type": "string", "enum": ["direction", "hypothesis", "gap", "constraint", "rejected"]}}, ["text"])},
    "propose_gap": {"name": "propose_gap", "risk": 2, "description": "Record a literature gap as a decision of kind 'gap'",
                    "schema": _obj({"text": STR}, ["text"])},
    "create_hypothesis": {"name": "create_hypothesis", "risk": 2, "description": "Add a hypothesis (status proposed)",
                          "schema": _obj({"text": STR}, ["text"])},
    "add_note": {"name": "add_note", "risk": 1, "description": "Pin a note to the shared context",
                 "schema": _obj({"text": STR}, ["text"])},
    "create_experiment": {"name": "create_experiment", "risk": 2, "description": "Create an experiment record",
                          "schema": _obj({"title": {"type": "string", "minLength": 3, "maxLength": 300},
                                          "hypothesis_id": {"type": "string", "pattern": r"^HYPE-\d{3,6}$"},
                                          "method": {"type": "string", "maxLength": 4000}}, ["title"])},
    "record_result": {"name": "record_result", "risk": 1, "description": "Propose an experiment result → memory CANDIDATE",
                      "schema": _obj({"text": STR, "experiment_id": {"type": "string", "pattern": r"^EXP-\d{3,6}$"}}, ["text"])},
    "update_outline": {"name": "update_outline", "risk": 1,
                       "description": "Propose the next level of the research outline (keywords, topic, direction, method or "
                                      "the full proposal in Markdown); applied only when the researcher accepts",
                       "schema": _obj({"keywords": {"type": "string", "maxLength": 2000},
                                       "topic": {"type": "string", "maxLength": 600},
                                       "direction": {"type": "string", "maxLength": 4000},
                                       "method": {"type": "string", "maxLength": 8000},
                                       "proposal": {"type": "string", "maxLength": 120000}})},
    "start_run": {"name": "start_run", "risk": 2,
                  "description": "Start a background research run with a skill (e.g. lit, idea, run, review, verify, latex) "
                                 "and its input text — the researcher accepts it first",
                  "schema": _obj({"skill": {"type": "string", "pattern": r"^[a-z][a-z0-9_-]{1,30}$"},
                                  "input": {"type": "string", "minLength": 2, "maxLength": 8000}}, ["skill", "input"])},
    "write_section": {"name": "write_section", "risk": 1,
                      "description": "Save a paper section (LaTeX body without the section command; abstract, introduction, "
                                     "related_work, methodology, experiments, discussion, conclusion) — the previous text "
                                     "is kept as a version; applied only when the researcher accepts",
                      "schema": _obj({"section": {"type": "string", "enum": ["abstract", "introduction", "related_work",
                                                                             "methodology", "experiments", "discussion",
                                                                             "conclusion"]},
                                      "text": {"type": "string", "minLength": 3, "maxLength": 120000},
                                      "title": {"type": "string", "maxLength": 300}}, ["section", "text"])},
    "commit_code": {"name": "commit_code", "risk": 1,
                    "description": "Commit code changes made in VS Code to the code project's git repository",
                    "schema": _obj({"message": {"type": "string", "minLength": 3, "maxLength": 300},
                                    "files": {"type": "array", "maxItems": 200,
                                              "items": {"type": "string", "minLength": 1, "maxLength": 400}}}, ["message"])},
    "pin_result": {"name": "pin_result", "risk": 1, "description": "Pin a result to the project (shared by every conversation)",
                   "schema": _obj({"kind": {"type": "string", "enum": ["gap", "hypothesis", "decision", "method", "result",
                                                                       "note", "source"]},
                                   "title": {"type": "string", "minLength": 2, "maxLength": 300},
                                   "body": {"type": "string", "maxLength": 20000},
                                   "run_id": {"type": "string", "maxLength": 60},
                                   "research_run": {"type": "string", "maxLength": 20}}, ["kind", "title"])},
    "propose_memory": {"name": "propose_memory", "risk": 1, "description": "Propose a memory candidate (review queue)",
                       "schema": _obj({"type": {"type": "string", "enum": ["decision", "finding", "hypothesis", "experiment",
                                                                         "knowledge", "open_question", "rejected_approach"]},
                                       "text": STR}, ["type", "text"])},
}


def validate_action(module: str, name: str, args: dict) -> dict:
    from backend.providers.mcp_tools import ToolInputError, validate
    allowed = {a["name"]: a for a in get(module).actions()}
    if name not in allowed:
        raise AIWSError(f"Action '{name}' is not available in the {get(module).label} module")
    try:
        validate(allowed[name]["schema"], args or {}, "args")
    except ToolInputError as e:
        raise AIWSError(str(e))
    return allowed[name]


def execute(name: str, args: dict, session: dict) -> dict:
    """Run an APPROVED action through the domain service the manual UI uses."""
    via = f"AI workspace {session['id']} (approved)"
    if name == "prepare_remote_experiment":
        from backend.execution import remote_compute
        r = remote_compute.create(args)
        return {"remote_run": r["run_id"], "status": r["status"], "bundle_sha256": r["bundle_sha256"]}
    if name == "update_outline":
        from backend.agent import outline
        o = outline.update({k: v for k, v in args.items() if v}, "chat (accepted)", f"session {session['id']}")
        return {"outline_level": o["level"]}
    if name == "start_run":
        from backend.agent import launch
        r = launch.from_skill(args["skill"], args["input"], session, approved=True)
        return {"run": r["id"], "status": r["status"]}
    if name == "write_section":
        from backend.paper.writer import clean_section, load_project, save_project
        p = load_project()
        old = p["sections"].get(args["section"], "")
        if old:
            p.setdefault("section_history", {}).setdefault(args["section"], []).append(old)
            p["section_history"][args["section"]] = p["section_history"][args["section"]][-10:]
        p["sections"][args["section"]] = clean_section(args["section"], args["text"])
        p.setdefault("section_state", {})[args["section"]] = "drafted"
        if args.get("title"):
            p["title"] = args["title"][:300]
        save_project(p)
        return {"section": args["section"], "chars": len(p["sections"][args["section"]]), "previous_kept": bool(old)}
    if name == "commit_code":
        from backend.execution import gitops
        st = gitops.commit(args["message"], args.get("files") or None)
        return {"commit": (st.get("commits") or [{}])[0].get("hash", ""), "branch": st.get("branch", "")}
    if name == "pin_result":
        from backend.agent import pins
        p = pins.add(args["kind"], args["title"], args.get("body", ""), "pinned",
                     {"session_id": session["id"], "run_id": args.get("run_id", ""),
                      "source_ids": [f"research_run:{args['research_run']}"] if args.get("research_run") else []})
        return {"pin": p["id"]}
    if name in ("add_decision", "propose_gap"):
        from backend.memory import add_decision
        d = add_decision(args["text"], "gap" if name == "propose_gap" else args.get("kind") or "direction", source=via,
                         origin="human", session=session["id"])
        return {"decision": d["id"]}
    if name == "create_hypothesis":
        from backend.memory import research
        return {"hypothesis": research.add_hypothesis(args["text"], source=via)["id"]}
    if name == "add_note":
        from backend.memory.notes import add_note
        return {"note": add_note("data", args["text"], source=via)["id"]}
    if name == "create_experiment":
        from backend.memory import research
        return {"experiment": research.add_experiment(args)["id"]}
    from backend.agent.memory_modes import propose  # record_result, propose_memory
    mtype = args.get("type") or "experiment"
    c = propose(session, mtype, args["text"], created_by="model",
                experiment_ids=[args["experiment_id"]] if args.get("experiment_id") else [])
    return {"candidate": c["id"], "status": c["status"]}
