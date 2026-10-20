"""Live critic (v3.2) — CLAUDE_DEVELOPMENT_PROMPT Task 4 / CUSTOMER_REQUIREMENT scenario 4.

While a cloud model streams a paper section, the critic checks the text that has already arrived:
  rules (instant, deterministic, no model):  unbalanced inline $…$, \\begin/\\end mismatches, unbalanced braces,
        \\cite keys that are not in the project's bibliography, [TBD]/[CITATION NEEDED] placeholders
  llm   (optional, background asyncio task):  a local/cheap model (agent "critic", engine "auto" → Groq/Ollama/…) looks
        for LaTeX-math and logic problems in the latest complete paragraphs; every call has a timeout and at most one
        call runs per stream, so it never slows the stream or competes for VRAM with a training run.
Only COMPLETE paragraphs are checked during streaming (a half-written formula is not an error); the final pass checks all.
Issues: {id, source, severity: error|warning|info, kind, line, message, excerpt}.
"""
from __future__ import annotations

import asyncio
import hashlib
import re

CITE_RE = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
ENV_RE = re.compile(r"\\(begin|end)\{([^}]+)\}")
PLACEHOLDER_RE = re.compile(r"\[(TBD[^\]]*|CITATION NEEDED)\]")
MATH_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "eqnarray", "displaymath", "math"}


def _strip_comments(line: str) -> str:
    return re.sub(r"(?<!\\)%.*$", "", line)


def _issue(source: str, severity: str, kind: str, line: int, message: str, excerpt: str = "") -> dict:
    key = f"{source}|{kind}|{line}|{message}"
    return {"id": hashlib.sha1(key.encode()).hexdigest()[:10], "source": source, "severity": severity, "kind": kind,
            "line": line, "message": message, "excerpt": excerpt.strip()[:120]}


def complete_part(text: str, final: bool) -> str:
    """Text up to the last paragraph break (all of it when the stream is finished)."""
    if final:
        return text
    k = text.rfind("\n\n")
    return text[:k] if k > 0 else ""


def check_rules(text: str, valid_keys: set | None = None) -> list:
    issues = []
    lines = text.split("\n")
    stack = []  # (env, line)
    in_math_env = 0
    para_start, dollars, brace = 1, 0, 0
    for i, raw in enumerate(lines, 1):
        line = _strip_comments(raw)
        for m in ENV_RE.finditer(line):
            kind, env = m.group(1), m.group(2).strip()
            if kind == "begin":
                stack.append((env, i))
                in_math_env += env in MATH_ENVS
            elif not stack:
                issues.append(_issue("rules", "error", "latex", i, f"\\end{{{env}}} without a matching \\begin", raw))
            elif stack[-1][0] != env:
                issues.append(_issue("rules", "error", "latex", i, f"\\end{{{env}}} closes \\begin{{{stack[-1][0]}}} (line {stack[-1][1]})", raw))
                stack.pop()
                in_math_env = sum(e in MATH_ENVS for e, _ in stack)
            else:
                stack.pop()
                in_math_env -= env in MATH_ENVS
        body = re.sub(r"\\\$", "", line)
        if not in_math_env:
            body2 = re.sub(r"\$\$.*?\$\$", "", body)
            dollars += body2.count("$") - 2 * body2.count("$$")
        brace += len(re.findall(r"(?<!\\)\{", line)) - len(re.findall(r"(?<!\\)\}", line))
        if not raw.strip() or i == len(lines):  # paragraph boundary
            if dollars % 2:
                issues.append(_issue("rules", "error", "math", para_start, "Unbalanced inline math: odd number of $ in this paragraph",
                                     lines[para_start - 1]))
            if brace and not stack:
                issues.append(_issue("rules", "warning", "latex", para_start,
                                     f"Unbalanced braces in this paragraph ({'+' if brace > 0 else ''}{brace})", lines[para_start - 1]))
            para_start, dollars, brace = i + 1, 0, 0
    for env, ln in stack:
        issues.append(_issue("rules", "error", "latex", ln, f"\\begin{{{env}}} is never closed", lines[ln - 1]))
    if valid_keys is not None:
        for i, raw in enumerate(lines, 1):
            for m in CITE_RE.finditer(_strip_comments(raw)):
                bad = [k.strip() for k in m.group(1).split(",") if k.strip() and k.strip() not in valid_keys]
                if bad:
                    issues.append(_issue("rules", "error", "citation", i, "Not in references.bib: " + ", ".join(bad), raw))
    for i, raw in enumerate(lines, 1):
        for m in PLACEHOLDER_RE.finditer(raw):
            issues.append(_issue("rules", "info", "placeholder", i, f"Placeholder [{m.group(1)[:60]}] needs real evidence", raw))
    return issues


def bib_keys() -> set:
    """Keys the paper may cite: included library entries + keys of the workspace references.bib."""
    keys = set()
    try:
        from .library import included
        keys |= {e["key"] for e in included() if e.get("key")}
    except Exception:
        pass
    try:
        from .config import workspace
        f = workspace() / "references.bib"
        if f.exists():
            keys |= set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", f.read_text("utf-8", errors="replace")))
    except Exception:
        pass
    return keys


LLM_SYS = """You are a meticulous LaTeX and scientific-logic checker running next to an AI author. Check ONLY the excerpt.
Report real problems: LaTeX that will not compile, malformed math, undefined notation used before definition, a claim that
contradicts an earlier sentence, a numeric claim with no source/result, a logical non-sequitur. Do not report style.
Return ONLY JSON: {"issues": [{"quote": "<= 12 words copied from the excerpt", "severity": "error|warning",
"kind": "latex|math|logic|evidence", "message": "<= 25 words"}]}  — or {"issues": []} when nothing is wrong."""


async def check_llm(text: str, offset_line: int = 0, timeout: float = 45) -> list:
    from .llm import call_agent, extract_json
    if not text.strip():
        return []
    r = await asyncio.wait_for(call_agent("critic", LLM_SYS, f"EXCERPT:\n{text[-3500:]}", max_tokens=700, temperature=0.0), timeout)
    try:
        d = extract_json(r["text"])
    except Exception:
        return []
    lines = text.split("\n")
    out = []
    for it in (d.get("issues") or [])[:8]:
        if not isinstance(it, dict) or not it.get("message"):
            continue
        q = str(it.get("quote") or "").strip()
        ln = next((i for i, l in enumerate(lines, 1) if q and q[:40] in l), 0)
        sev = it.get("severity") if it.get("severity") in ("error", "warning") else "warning"
        out.append({**_issue(f"llm:{r.get('engine', '')}", sev, str(it.get("kind") or "logic")[:12], ln + offset_line if ln else 0,
                             str(it["message"])[:200], q), "engine": r.get("engine", "")})
    return out


class StreamCritic:
    """Per-stream state: feed() after every delta, then final(); both return only NEW issues."""

    def __init__(self, cfg: dict | None = None):
        from .config import load_config
        c = (cfg or load_config())["critic"]
        self.enabled = bool(c.get("enabled", True))
        self.use_llm = self.enabled and bool(c.get("llm", True))
        self.interval = max(200, int(c.get("interval_chars", 700)))
        self.keys = bib_keys() if self.enabled else set()
        self.seen: set = set()
        self.checked = 0
        self.task: asyncio.Task | None = None
        self.llm_errors = 0

    def _new(self, issues: list) -> list:
        out = [i for i in issues if i["id"] not in self.seen]
        self.seen.update(i["id"] for i in out)
        return out

    def feed(self, text: str) -> list:
        if not self.enabled or len(text) - self.checked < self.interval:
            return []
        part = complete_part(text, False)
        if len(part) <= self.checked:
            return []
        self.checked = len(part)
        if self.use_llm and (self.task is None or self.task.done()) and self.llm_errors < 2:
            self.task = asyncio.ensure_future(check_llm(part))
        return self._new(check_rules(part, self.keys))

    def llm_ready(self) -> list:
        if not self.task or not self.task.done():
            return []
        t, self.task = self.task, None
        try:
            return self._new(t.result())
        except Exception:
            self.llm_errors += 1
            return []

    async def final(self, text: str, wait_s: float = 8) -> list:
        if not self.enabled:
            return []
        out = self._new(check_rules(text, self.keys))
        if self.task and not self.task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.task), wait_s)
            except Exception:
                pass
        out += self.llm_ready()
        self.close()
        return out

    def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None
