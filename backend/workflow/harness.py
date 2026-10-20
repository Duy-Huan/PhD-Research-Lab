"""Agent harness adapter (v4.1 M3): planning, search-space proposals, interpretation and failure diagnosis.

The audit found no Pydantic AI harness in this repository (it was planned, never implemented), so the orchestrator
talks to a small `Harness` contract. `LLMHarness` implements it with the app's existing agent router (llm.call_agent:
cloud, LM Studio, Ollama or auto routing, per Settings → Agent engines). A Pydantic AI harness can replace it later by
implementing the same four methods — the orchestrator never depends on a framework class.

Rules: the harness only PROPOSES. Its output is labelled AI_SUGGESTION / AI_INTERPRETATION, search spaces go through the
deterministic validator, and nothing it says becomes research state without the researcher's approval.
"""
from __future__ import annotations

import json

AI_SUGGESTION, AI_INTERPRETATION = "AI_SUGGESTION", "AI_INTERPRETATION"
SYSTEM = ("You are part of PhD Research Lab's workflow orchestrator. You propose; the researcher decides. Never invent "
          "metrics, citations or measurements: use only the numbers given to you and say when something is unknown. "
          "Answer with ONE JSON object and nothing else.")


class Harness:
    name = "contract"

    async def plan(self, objective: str, context: str, constraints: dict) -> dict:
        raise NotImplementedError

    async def propose_search_space(self, model_report: dict, baseline: dict, hint: str, failures: list) -> dict:
        raise NotImplementedError

    async def interpret(self, results: dict, hypothesis: str) -> dict:
        raise NotImplementedError

    async def diagnose(self, failure: dict, similar: list) -> dict:
        raise NotImplementedError


class LLMHarness(Harness):
    name = "llm-router"

    async def _ask(self, agent: str, task: str, payload: dict, max_tokens: int = 2500) -> dict:
        from ..llm import call_agent, extract_json
        from ..model_lifecycle import background
        user = task + "\n\nINPUT (JSON):\n" + json.dumps(payload, ensure_ascii=False, default=str)[:24000]
        with background():  # workflow agents are background tasks for the model lifecycle
            r = await call_agent(agent, SYSTEM, user, max_tokens=max_tokens, temperature=0.2)
        try:
            data = extract_json(r["text"])
        except ValueError:
            data = {"text": r["text"].strip()[:6000], "parse_error": "the model did not return JSON"}
        data["_engine"] = {"engine": r.get("engine"), "model": r.get("model"), "note": r.get("note", "")}
        return data

    async def plan(self, objective: str, context: str, constraints: dict) -> dict:
        d = await self._ask("workflow_planner", "Write a research plan for the objective. JSON keys: objective, hypothesis, "
                            "missing_information (list), steps (list of {title, kind: tool|model_analysis|experiment|"
                            "human_decision, why, risk}), resources (text), risks (list).",
                            {"objective": objective, "research_context": context[:12000], "constraints": constraints})
        d["label"] = AI_SUGGESTION
        return d

    async def propose_search_space(self, model_report: dict, baseline: dict, hint: str, failures: list) -> dict:
        d = await self._ask("hpo_strategist", "Propose a bounded hyperparameter search space. JSON: {search_space: {name: "
                            "{type: float|int|categorical|bool, low, high, log, step, choices, condition: {param, equals}, "
                            "why}}, rationale}. Keep it small (≤ 8 parameters), avoid ranges that failed before.",
                            {"model_report": model_report, "baseline": baseline, "hint": hint, "known_failures": failures[:8]})
        d["label"] = AI_SUGGESTION
        return d

    async def interpret(self, results: dict, hypothesis: str) -> dict:
        d = await self._ask("workflow_planner", "Interpret the VALIDATED results against the hypothesis. JSON: {summary, "
                            "supports_hypothesis: supports|refutes|inconclusive, claims (list of {text, evidence: trial or "
                            "metric references}), caveats (list), next_steps (list)}. Do not add numbers that are not in "
                            "the input.", {"hypothesis": hypothesis, "validated_results": results})
        d["label"] = AI_INTERPRETATION
        return d

    async def diagnose(self, failure: dict, similar: list) -> dict:
        d = await self._ask("workflow_planner", "Diagnose the failed experiment. JSON: {diagnosis, confidence: low|medium|"
                            "high, evidence (list), safe_adjustments (list of {param, from, to, why}), needs_approval "
                            "(list of changes that touch dataset semantics, evaluation protocol or the hypothesis)}.",
                            {"failure": failure, "similar_failures": similar[:6]})
        d["label"] = AI_SUGGESTION
        return d


_current: dict = {"h": None}


def get() -> Harness:
    if _current["h"] is None:
        _current["h"] = LLMHarness()
    return _current["h"]


def use(h: Harness | None) -> None:
    """Swap the harness (tests, or a future Pydantic AI implementation)."""
    _current["h"] = h
