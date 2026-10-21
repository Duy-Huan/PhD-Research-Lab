"""From a prompt to work: "/" commands and plain-language requests become skills, run skills become research runs.

    /lit vision transformers        → skill lit (mode run)  → research run (Feynman or the app model)
    "chạy thử ý tưởng dùng …"       → intent idea           → proposal "start /idea" (the researcher accepts)
    "viết phần Results theo văn phong …" → intent write     → the chat answers with the write skill's instructions

The intent router is deliberately simple and transparent (keyword rules in Vietnamese and English, no model call):
it only SUGGESTS. A run that writes code or computes always waits for the researcher's acceptance; read-only research
runs start on their own when runs.auto_approve_risk allows it.
"""
from __future__ import annotations

import re

from backend.agent import AIWSError, runs, skills

INTENTS = (  # (skill, pattern) — first match wins
    ("idea", r"(chạy thử|thử ngay|test nhanh|thử nghiệm nhanh|try (this|my|an) idea|run (a )?quick experiment|"
             r"prototype).{0,60}|(ý tưởng|idea).{0,40}(chạy|thử|run|test)"),
    ("run", r"\b(chạy|run|execute|train|huấn luyện)\b.{0,30}(lệnh|command|script|thí nghiệm|experiment|training|python)"),
    ("lit", r"(tìm|tổng hợp|khảo sát|review|survey|search|find).{0,30}(tài liệu|bài báo|literature|papers?|related work)"),
    ("gap", r"(khoảng trống|research gap|\bgaps?\b|chưa ai làm|novelty)"),
    ("hypothesis", r"(giả thuyết|hypothes[ie]s)"),
    ("write", r"(viết|soạn|write|draft|rewrite|chỉnh văn)\b.{0,40}(phần|section|results?|kết quả|introduction|giới thiệu|"
              r"abstract|tóm tắt|related work|method|phương pháp|discussion|kết luận|conclusion|paper|bài báo)"),
    ("latex", r"(biên dịch|compile|xuất|export).{0,15}(latex|pdf)"),
    ("review", r"(phản biện|review|đánh giá).{0,25}(bài|paper|bản thảo|draft|manuscript)"),
    ("verify", r"(kiểm chứng|xác minh|verify|fact.?check).{0,40}(claim|kết quả|result|số liệu|bằng chứng|evidence)"),
    ("outline", r"(đề cương|outline|proposal|định hướng nghiên cứu|research direction)"),
    ("status", r"(tiến độ|đang làm gì|trạng thái|status|progress)\b"),
)
_COMPILED = [(k, re.compile(p, re.I | re.S)) for k, p in INTENTS]
PATH_RE = re.compile(r"^[\w./\\ -]+\.(md|tex|txt|pdf|docx)$", re.I)


def route(text: str) -> dict | None:
    """{skill, mode, risk, auto, why} for a plain message, or None when it is just a question."""
    t = (text or "").strip()
    if not t or t.startswith("/"):
        return None
    for name, rx in _COMPILED:
        if rx.search(t):
            try:
                s = skills.get(name)
            except AIWSError:
                continue
            risk = effective_risk(s)
            return {"skill": name, "mode": s["mode"], "risk": risk, "title": s["title"],
                    "auto": s["mode"] == "run" and not runs._needs_approval(risk),
                    "why": f"yêu cầu khớp kỹ năng /{name} ({s['title']})"}
    return None


def effective_risk(s: dict) -> int:
    from backend.core.config import load_config
    cfg = load_config()
    if s["provider"] == "openscience" or (s["pipeline"] in ("research", "review") and
            (cfg["research_providers"].get("engine_mode") in ("openscience", "collaborative") or cfg["openscience"].get("enabled"))):
        return max(2, s["risk"])
    if s["mode"] == "run" and s["pipeline"] in ("idea", "code", "experiment"):
        return max(2, s["risk"])
    return s["risk"]


def inputs_for(s: dict, text: str) -> dict:
    p = s["pipeline"]
    text = (text or "").strip()
    if p == "research":
        return {"topic": text, "workflow": s["feynman"]}
    if p == "idea":
        return {"idea": text}
    if p == "code":
        return {"task": text}
    if p == "experiment":
        m = re.search(r"--gpu\b", text)
        return {"command": re.sub(r"\s*--gpu\b", "", text).strip(), "gpu": bool(m)}
    if p in ("review", "verify"):
        if PATH_RE.match(text):
            return {"path": text.replace("\\", "/")}
        return {"text": text} if len(text) > 40 else {"path": text} if text else {}
    return {"text": text} if text else {}


def provider_for(s: dict) -> str:
    if s["provider"] == "coding":
        from backend.core.config import load_config
        return (load_config().get("research_providers") or {}).get("coding_default") or "claude_code"
    return s["provider"]


def from_skill(name: str, text: str, session: dict | None = None, approved: bool = False, turn_id: str = "", engine_mode: str = "") -> dict:
    """Create the research run of a run skill. approved=True when the researcher already accepted it (chat card)."""
    s = skills.get(name)
    if s["mode"] != "run":
        raise AIWSError(f"/{name} answers in the chat — it is not a background run")
    if s["pipeline"] == "experiment" and not inputs_for(s, text).get("command"):
        raise AIWSError("/run needs a command, e.g. /run python train.py --epochs 1")
    title = f"/{s['name']} {text}".strip()[:120]
    from backend.core.config import load_config
    cfg = load_config()
    steps, provider, risk = None, provider_for(s), effective_risk(s)
    if s["pipeline"] in ("research", "review") and (engine_mode or cfg["openscience"].get("enabled") or cfg["research_providers"].get("engine_mode", "auto") != "auto" or provider == "openscience"):
        from backend.research_engines.registry import plan
        mode = engine_mode or ("openscience" if provider == "openscience" else cfg["research_providers"].get("engine_mode", "auto"))
        capability = "analysis" if name == "science" else "review" if s["pipeline"] == "review" else "literature"
        engines = plan(mode, capability, provider)
        provider = engines[0]
        if "openscience" in engines:
            risk = max(2, risk)
        if len(engines) > 1:
            steps = [{"kind": "research", "provider": engines[0]},
                     {"kind": "review", "provider": engines[1], "spec": {"review_prior": True}},
                     {"kind": "verify_sources"}, {"kind": "report"}]
    r = runs.create(s["pipeline"], title, text, inputs_for(s, text), (session or {}).get("id", ""), turn_id, s["name"],
                    risk, provider, steps=steps)
    if approved and r["status"] == "APPROVAL_PENDING":
        r = runs.approve(r["id"], "researcher (chat)")
    return r


def help_text() -> str:
    from backend.core.i18n import L, lang
    en = lang() == "en"
    cats = ({"research": "Research", "experiment": "Experiments", "writing": "Writing", "system": "System"} if en else
            {"research": "Nghiên cứu", "experiment": "Thí nghiệm", "writing": "Viết bài", "system": "Hệ thống"})
    lines = [L("**Lệnh /** — gõ `/` trong khung chat (hoặc trong `phdlab`). Bạn cũng có thể viết bình thường; "
               "hệ thống tự chọn kỹ năng phù hợp và luôn hỏi bạn trước khi chạy code hay thí nghiệm.",
               "**/ commands** — type `/` in the chat (or in `phdlab`). You can also just write; the system picks the "
               "matching skill and always asks before it runs code or experiments."), ""]
    cur = ""
    for s in skills.catalog():
        if s["category"] != cur:
            cur = s["category"]
            lines.append(f"\n**{cats[cur]}**")
        badge = L(" · chạy nền", " · background run") if s["mode"] == "run" else ""
        desc = (s.get("description_en") or s["description"]) if en else s["description"]
        lines.append(f"- `/{s['name']}{(' ' + s['usage']) if s['usage'] else ''}` — {desc}{badge}")
    return "\n".join(lines)
