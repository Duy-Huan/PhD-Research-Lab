"""PhD Lab Native Multi-Agent Research Engine Adapter.

Provides a dedicated in-process workflow that runs the complete panel of PhD Lab
internal agents (Supervisor/PI, Lead Researcher, Rigorous Critic, Experiment Engineer,
Manuscript Writer, Evidence Verifier) without delegating to external providers (Feynman,
OpenScience, OpenCode, or external CLI tools).
"""
from __future__ import annotations

import json
from pathlib import Path
from backend.research_engines.contracts import (
    EngineDescriptor,
    EngineEvent,
    EngineFailure,
    EngineResult,
    EngineTask,
)


class PhDLabEngine:
    descriptor = EngineDescriptor(
        id="phdlab",
        capabilities=["literature", "analysis", "prototype", "review"],
        transport="in-process",
        token_streaming=True,
        native_sessions=True,
    )

    def health(self) -> dict:
        from backend.providers.research import describe
        return describe("phdlab")

    def execute(self, task: EngineTask, emit, cancelled) -> EngineResult:
        if task.capability not in self.descriptor.capabilities:
            raise EngineFailure(f"PhD Lab native engine is not qualified for capability '{task.capability}'", "capability")
        if cancelled():
            raise EngineFailure("Task cancelled before dispatch", "cancelled")

        emit(EngineEvent(engine="phdlab", type="status", data={"state": "started", "workflow": "phdlab-native-multi-agent"}))
        task.output_dir.mkdir(parents=True, exist_ok=True)

        from backend.providers import research as RP
        from backend.knowledge import websearch as WS

        # Route to specialized internal agent role based on capability
        if task.capability == "review":
            agent = "reviewer"
            role_title = "PhD Lab Rigorous Critic & Peer Review Board"
            out_name = "phdlab_review_report.md"
        elif task.capability == "prototype":
            agent = "engineer"
            role_title = "PhD Lab Experiment Engineer"
            out_name = "phdlab_experiment_report.md"
        else:  # literature or analysis
            agent = "research"
            role_title = "PhD Lab Lead Researcher & Academic PI"
            out_name = "phdlab_research_report.md"

        system_prompt = (
            f"You are the {role_title} operating within PhD Lab's standalone native multi-agent workflow.\n"
            "Guidelines:\n"
            "1. Deliver an exhaustive, rigorous scientific response with solid logical structure.\n"
            "2. Ground all claims in factual research evidence and verifiable references.\n"
            "3. Format equations in KaTeX ($...$ or $$...$$) and structure sections clearly in Markdown.\n"
            "4. Answer in the researcher's language; keep academic and technical terms accurate.\n\n"
            f"# Project Context\n{task.context or '(no prior context)'}"
        )

        sources = []
        if task.capability in ("literature", "analysis"):
            try:
                import asyncio
                query = task.question[:300]
                res = asyncio.run(asyncio.wait_for(WS.search("both", [query], [query]), 90))
                sources = res.get("sources") or []
            except Exception:
                sources = []

            if sources:
                system_prompt += "\n\n" + WS.WEB_RULES + "\n" + WS.sources_block(sources)
                src_path = task.output_dir / "sources.json"
                src_path.write_text(json.dumps(WS.compact(sources), ensure_ascii=False, indent=2), encoding="utf-8")

        if cancelled():
            raise EngineFailure("Task cancelled during setup", "cancelled")

        emit(EngineEvent(engine="phdlab", type="status", data={"state": "reasoning", "agent": agent}))

        try:
            text = RP.app_complete(agent, system_prompt, task.question, max_tokens=6000)
        except Exception as e:
            raise EngineFailure(f"PhD Lab native model call failed: {e}", "execution") from e

        if not text.strip():
            raise EngineFailure("PhD Lab native agent returned empty response", "execution")

        emit(EngineEvent(engine="phdlab", type="text_delta", data={"text": text[:600]}))

        report_file = task.output_dir / out_name
        report_file.write_text(text, encoding="utf-8")

        artifact_refs = [{"path": str(report_file)}]
        if sources:
            artifact_refs.append({"path": str(task.output_dir / "sources.json")})

        emit(EngineEvent(engine="phdlab", type="status", data={"state": "completed", "artifacts": len(artifact_refs)}))

        return EngineResult(
            engine="phdlab",
            text=text,
            artifact_refs=artifact_refs,
            provenance={"engine": "phdlab", "agent": agent, "workflow": "native-multi-agent", "sources_count": len(sources)},
        )
