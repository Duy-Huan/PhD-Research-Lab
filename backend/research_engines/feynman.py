"""Bridge the existing Feynman implementation without duplicating its workflows."""
from backend.research_engines.contracts import EngineDescriptor, EngineEvent, EngineFailure, EngineResult


class FeynmanEngine:
    descriptor = EngineDescriptor(id="feynman", capabilities=["literature", "review"], transport="native-cli",
                                  token_streaming=False, native_sessions=False)

    def health(self) -> dict:
        from backend.providers.research import describe
        return describe("feynman")

    def execute(self, task, emit, cancelled):
        from backend.providers.research import run_feynman, ProviderUnavailable
        if task.capability not in self.descriptor.capabilities:
            raise EngineFailure("Feynman adapter is not qualified for this task capability", "capability")
        if cancelled():
            raise EngineFailure("Task cancelled before dispatch", "cancelled")
        emit(EngineEvent(engine="feynman", type="status", data={"state": "started"}))
        try:
            result = run_feynman(task.operation_id.replace(":", "-") + f"-{task.attempt}", task.native_workflow,
                                 task.question, task.context, task.output_dir, cancelled)
        except ProviderUnavailable as e:
            from backend.providers.cli import classify_error
            raise EngineFailure(str(e), {"RATE_LIMITED": "quota", "AUTH_EXPIRED": "auth"}.get(classify_error(str(e)), "execution")) from e
        return EngineResult(engine="feynman", text=result["text"],
                            artifact_refs=[{"path": str(task.output_dir / f)} for f in result["files"]])
