"""Existing native research role adapter.

Selects one existing native role through the common model gateway. Multi-agent mission
coordination remains in the existing mission/team services; this adapter does not
pretend a single model response is a full research panel or an executed experiment.
"""
from __future__ import annotations

import json
import time
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
        token_streaming=False,
        native_sessions=True,
    )

    def health(self) -> dict:
        from backend.providers.research import describe
        return describe("phdlab")

    def execute(self, task: EngineTask, emit, cancelled) -> EngineResult:
        started=time.monotonic()
        if task.capability not in self.descriptor.capabilities:
            raise EngineFailure(f"PhD Lab native engine is not qualified for capability '{task.capability}'", "capability")
        if cancelled():
            raise EngineFailure("Task cancelled before dispatch", "cancelled")

        from backend.core.config import data_dir
        from backend.knowledge.research_store import safe_child
        try:
            relative = task.output_dir.absolute().relative_to(data_dir().resolve())
            output_dir = safe_child(data_dir(), str(relative))
        except ValueError as error:
            raise EngineFailure('Native research outputs must remain inside the active project', 'policy') from error

        emit(EngineEvent(engine="phdlab", type="status", data={"state": "started", "workflow": "native-role-response"}))
        output_dir.mkdir(parents=True, exist_ok=True)

        from backend.providers import research as RP
        from backend.knowledge import websearch as WS

        # Route to specialized internal agent role based on capability
        if task.capability == "review":
            agent = "reviewer"
            role_title = "PhD Lab Research Reviewer"
            out_name = "phdlab_review_report.md"
        elif task.capability == "prototype":
            agent = "engineer"
            role_title = "PhD Lab Experiment Engineer"
            out_name = "phdlab_experiment_report.md"
        else:  # literature or analysis
            agent = "research"
            role_title = "PhD Lab Research Assistant"
            out_name = "phdlab_research_report.md"

        system_prompt = (
            f"You are the {role_title} operating within PhD Lab's native research environment.\n"
            "Guidelines:\n"
            "1. Choose an approach and level of detail that match the researcher's question, constraints and available evidence.\n"
            "2. Ground factual claims in evidence; identify hypotheses, uncertainty and missing verification. Never invent experiments, measurements or citations.\n"
            "3. Format equations in KaTeX ($...$ or $$...$$) and structure sections clearly in Markdown.\n"
            "4. Answer in the researcher's language; keep academic and technical terms accurate.\n\n"
            f"# Project Context\n{task.context or '(no prior context)'}"
        )

        sources = []
        retrieval_status = 'NOT_REQUESTED'
        if task.capability == "literature":
            try:
                import asyncio
                query = task.question[:300]
                res = asyncio.run(asyncio.wait_for(WS.search("both", [query], [query]), min(90,task.time_limit_s)))
                sources = res.get("sources") or []
                retrieval_status = 'FOUND' if sources else 'EMPTY'
            except Exception:
                retrieval_status = 'UNAVAILABLE'
                sources = []
            emit(EngineEvent(engine="phdlab", type="status", data={"state": "retrieval", "result": retrieval_status, "sources": len(sources)}))
            if not sources:
                system_prompt += '\nExternal literature retrieval yielded no usable sources. State this limitation; do not imply that a literature search or references were verified.'

            if sources:
                system_prompt += "\n\n" + WS.WEB_RULES + "\n" + WS.sources_block(sources)
                src_path = output_dir / "sources.json"
                src_path.write_text(json.dumps(WS.compact(sources), ensure_ascii=False, indent=2), encoding="utf-8")

        if cancelled():
            raise EngineFailure("Task cancelled during setup", "cancelled")

        emit(EngineEvent(engine="phdlab", type="status", data={"state": "reasoning", "agent": agent}))

        try:
            remaining=task.time_limit_s-(time.monotonic()-started)
            if remaining<=0: raise TimeoutError('Native research setup exceeded its task deadline')
            text = RP.app_complete(agent, system_prompt, task.question, max_tokens=6000,
                                   timeout_s=remaining,cancelled=cancelled)
        except TimeoutError as e:
            raise EngineFailure('Native research task exceeded its execution deadline','timeout') from e
        except InterruptedError as e:
            raise EngineFailure('Native research task was cancelled','cancelled') from e
        except Exception as e:
            raise EngineFailure(f"PhD Lab native model call failed: {e}", "execution") from e

        if not text.strip():
            raise EngineFailure("PhD Lab native agent returned empty response", "execution")

        emit(EngineEvent(engine="phdlab", type="text_delta", data={"text": text}))

        if cancelled():
            raise EngineFailure("Task cancelled during model response; no report published", "cancelled")

        report_file = output_dir / out_name
        report_file.write_text(text, encoding="utf-8")

        artifact_refs = [{"path": str(report_file)}]
        if sources:
            artifact_refs.append({"path": str(output_dir / "sources.json")})

        emit(EngineEvent(engine="phdlab", type="status", data={"state": "completed", "artifacts": len(artifact_refs)}))

        return EngineResult(
            engine="phdlab",
            text=text,
            artifact_refs=artifact_refs,
            provenance={"engine": "phdlab", "agent": agent, "workflow": "native-role-response", "sources_count": len(sources), "retrieval": retrieval_status},
        )
