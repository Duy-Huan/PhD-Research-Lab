"""Memory pipeline of the AI workspace (Firewall spec §9): evidence-backed, selective, reversible.

    assistant message ──extract──▶ typed candidate ──validate──▶ dedup (lifecycle) ──conflict check──▶ policy
                                                                         review queue ◀──┴──▶ restricted auto-save

Modes (effective per session, see policy.py)
    off      no extraction, no writes (chat history follows its own keep_history setting)
    manual   nothing is extracted; the researcher picks a message, chooses a type, edits the draft and saves it
    suggest  candidates are extracted after every answer and wait in the review queue — nothing becomes memory
             until the researcher approves it
    auto     like suggest, but candidates whose type is in `auto_memory_types` are saved WITHOUT review only when
             they are not duplicates, not conflicting, carry no sensitive text and are not experiment results /
             decisions without evidence (high-impact types always need review)

Extraction is deterministic and inspectable: lines such as "Decision: …", "Finding: …", "Hypothesis: …",
"Open question: …", "Rejected approach: …", "Knowledge: …", "Experiment: …" (also Vietnamese: "Quyết định:",
"Phát hiện:", "Giả thuyết:", "Câu hỏi mở:", "Hướng bị loại:", "Kiến thức:", "Thí nghiệm:") or a fenced
```phdlab-memory``` JSON list. A model-generated finding is stored as an AI CLAIM, never as a verified fact.
Every candidate carries its provenance (session, provider, message ids, reference / experiment / artifact ids).
"""
from __future__ import annotations

import json
import re

from backend.agent import AIWSError
from backend.agent.policy import MEMORY_TYPES

KIND = {"decision": "decision", "rejected_approach": "decision", "finding": "claim", "experiment": "experiment_result",
        "hypothesis": "note", "knowledge": "note", "open_question": "note"}
HIGH_IMPACT = {"decision", "rejected_approach", "experiment", "finding"}
PREFIX = {"decision": ("decision", "quyết định"), "finding": ("finding", "phát hiện"), "hypothesis": ("hypothesis", "giả thuyết"),
          "open_question": ("open question", "câu hỏi mở"), "rejected_approach": ("rejected approach", "hướng bị loại"),
          "knowledge": ("knowledge", "kiến thức"), "experiment": ("experiment", "thí nghiệm")}
LINE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\*\*)?(" + "|".join(p for ps in PREFIX.values() for p in ps) + r")(?:\*\*)?\s*:\s*(.{3,})$",
                  re.I | re.M)
BLOCK = re.compile(r"```phdlab-memory\s*\n(.*?)```", re.S)
NEG = re.compile(r"(?i)\b(not|no|never|reject|rejected|avoid|without|instead)\b|không|tránh|loại")
SENSITIVE = re.compile(r"(?i)(password|passwd|api[_ -]?key|secret|token|mật khẩu)")


def _type_of(prefix: str) -> str:
    p = prefix.lower()
    return next(t for t, ps in PREFIX.items() if p in ps)


def extract(text: str) -> list:
    out = []
    for m in BLOCK.finditer(text or ""):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for x in data if isinstance(data, list) else [data]:
            if isinstance(x, dict) and x.get("type") in MEMORY_TYPES and str(x.get("content") or x.get("text") or "").strip():
                out.append({"type": x["type"], "content": str(x.get("content") or x.get("text")).strip()[:4000],
                            "title": str(x.get("title") or "")[:200]})
    for m in LINE.finditer(BLOCK.sub("", text or "")):
        out.append({"type": _type_of(m.group(1)), "content": m.group(2).strip()[:4000], "title": ""})
    seen, uniq = set(), []
    for c in out:
        k = (c["type"], c["content"].lower())
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq[:20]


def conflicts(kind: str, text: str) -> list:
    """Existing records about the same subject (token overlap) whose polarity differs → surfaced, never overwritten."""
    from backend.memory.lifecycle import _existing_texts, _jaccard, _norm_tokens
    toks = _norm_tokens(text)
    neg = bool(NEG.search(text))
    return [rid for rid, t in _existing_texts(kind) if _jaccard(toks, _norm_tokens(t)) >= 0.3 and bool(NEG.search(t)) != neg]


def propose(session: dict, mtype: str, content: str, title: str = "", created_by: str = "model", message_ids=None,
            experiment_ids=None, artifact_ids=None, provider: str = "") -> dict:
    from backend.memory import lifecycle
    if mtype not in MEMORY_TYPES:
        raise AIWSError(f"type must be one of {', '.join(MEMORY_TYPES)}")
    kind = KIND[mtype]
    exp = [x for x in (experiment_ids or []) if re.fullmatch(r"EXP-\d{3,6}", x)]
    if kind == "experiment_result" and not exp:
        kind = "claim"  # an experiment statement without an experiment record is a claim, not a result
    refs = [s["id"] for s in ((session.get("last_manifest") or {}).get("sources") or []) if s["id"].startswith("ref:")]
    text = content if kind != "note" or mtype == "knowledge" else f"{mtype.replace('_', ' ').capitalize()}: {content}"
    payload = {"text": text, "memory_type": mtype, "title": title or content[:80], "created_by": created_by,
               "source": {"session_id": session["id"], "provider_id": provider or session["settings"].get("provider", ""),
                          "message_ids": list(message_ids or []), "reference_ids": refs[:20], "experiment_ids": exp,
                          "artifact_ids": list(artifact_ids or [])},
               "confidence_note": "researcher-written" if created_by == "user" else
                                  "model statement — not verified; check the cited sources before relying on it"}
    if mtype == "rejected_approach":
        payload["decision_kind"] = "rejected"
    if kind == "experiment_result":
        payload["experiment_id"] = exp[0]
    c = lifecycle.propose(kind, payload, origin="human" if created_by == "user" else "provider",
                          provider=payload["source"]["provider_id"], session=session["id"])
    cf = conflicts(kind, text)
    if cf:
        c = lifecycle.annotate(c["id"], conflicts_with=cf)
    from backend.agent import sessions as store
    store.update(session["id"], lambda s: s["memory"].append(c["id"]))
    store.emit(session["id"], "memory.candidate", candidate=c["id"], type=mtype, status=c["status"], conflicts=len(cf))
    return c


def auto_ok(c: dict, allowed_types: list) -> str:
    """'' when restricted auto-save may commit the candidate, else why it needs review."""
    p = c["payload"]
    if p.get("memory_type") not in allowed_types:
        return "type not in the auto-save allowlist"
    if p.get("memory_type") in HIGH_IMPACT:
        return "high-impact type (decision / finding / experiment) always needs review"
    if c["status"] != "pending":
        return f"candidate is {c['status']}"
    if c.get("conflicts_with"):
        return "conflicts with existing records"
    if SENSITIVE.search(p["text"]):
        return "may contain sensitive information"
    return ""


def after_turn(session: dict, message: dict, eff_values: dict) -> list:
    """Apply the session's memory mode to one completed assistant message."""
    from backend.memory import lifecycle
    mode = eff_values["memory_mode"]
    if mode in ("off", "manual"):
        return []
    out = []
    for cand in extract(message["content"]):
        c = propose(session, cand["type"], cand["content"], cand["title"], "model", [message["id"]],
                    provider=message.get("provider", ""))
        if mode == "auto":
            why = auto_ok(c, eff_values["auto_memory_types"])
            if not why:
                c = lifecycle.approve(c["id"], reviewer="auto-policy (restricted)")
                from backend.agent import sessions as store
                store.emit(session["id"], "memory.saved", candidate=c["id"], by="auto-policy")
            else:
                c = lifecycle.annotate(c["id"], review_reason=why)
        out.append(c)
    return out


def manual(session: dict, message_id: str, mtype: str, content: str, title: str = "", save: bool = False) -> dict:
    """Manual mode: the researcher's own pick (optionally saved at once — the explicit approval)."""
    from backend.memory import lifecycle
    if not any(m["id"] == message_id for m in session["messages"]):
        raise AIWSError("Message not found in this session")
    c = propose(session, mtype, content, title, "user", [message_id])
    if save and c["status"] in ("pending", "duplicate"):
        c = lifecycle.approve(c["id"], reviewer="researcher")
        from backend.agent import sessions as store
        store.emit(session["id"], "memory.saved", candidate=c["id"], by="researcher")
    return c
