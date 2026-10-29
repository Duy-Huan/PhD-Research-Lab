from typing import Literal
from pydantic import Field, model_validator
from backend.agent.mission_contracts import Contract


class DatasetRecipe(Contract):
    kind: Literal["generated_smooth_images_v1"] = "generated_smooth_images_v1"
    license: Literal["CC0-generated-fixture"] = "CC0-generated-fixture"
    side: int = Field(default=12,ge=8,le=32)
    noise_std: float = Field(default=0.12,gt=0,le=0.5,allow_inf_nan=False)
    train_count: int = Field(default=12,ge=1,le=64)
    validation_count: int = Field(default=8,ge=1,le=64)
    test_count: int = Field(default=8,ge=1,le=64)


class ExperimentProtocol(Contract):
    topic_id: str
    hypothesis: str = Field(min_length=1,max_length=8000)
    question: str = Field(default="Does a fixed smoothing filter reduce synthetic Gaussian noise?",max_length=4000)
    dataset: DatasetRecipe = Field(default_factory=DatasetRecipe)
    seeds: list[int] = Field(default_factory=lambda:[11,23,37],min_length=1,max_length=5)
    independent_variable: Literal["smoothing_alpha"] = "smoothing_alpha"
    dependent_variables: list[Literal["mse","psnr_db"]] = Field(default_factory=lambda:["mse","psnr_db"])
    baseline: Literal["noisy_input"] = "noisy_input"
    alphas: list[float] = Field(default_factory=lambda:[0.5,1.0],min_length=1,max_length=7)
    selection_split: Literal["validation"] = "validation"
    held_out_split: Literal["test"] = "test"
    min_psnr_gain_db: float = Field(default=0.1,ge=0,le=20,allow_inf_nan=False)
    max_trials: int = Field(default=6,ge=4,le=10)
    max_seconds: int = Field(default=120,ge=5,le=600)
    max_artifact_mb: int = Field(default=32,ge=1,le=128)
    stop_on_target: bool = False
    engine: Literal["python","docker"] = "python"
    docker_image: str = ""
    cpu_threads: Literal[1] = 1
    gpu: Literal[False] = False

    @model_validator(mode="after")
    def fixed(self):
        if len(set(self.seeds))!=len(self.seeds) or any(not 0<=s<=2**31-1 for s in self.seeds):
            raise ValueError("Seeds must be distinct nonnegative 32-bit integers")
        if len(set(self.alphas))!=len(self.alphas) or any(not 0<a<=1 for a in self.alphas):
            raise ValueError("Choose unique smoothing alphas in (0,1]")
        if self.max_trials < len(self.alphas)+3:
            raise ValueError("Budget must include baseline, variants and two held-out evaluations")
        if set(self.dependent_variables)!={"mse","psnr_db"}:
            raise ValueError("Pre-register both measured metrics")
        if self.engine=="docker" and ("@sha256:" not in self.docker_image or not __import__('re').fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}",self.docker_image)):
            raise ValueError("Docker requires an installed immutable image digest; no implicit pull")
        estimated=self.dataset.side**2*max(self.dataset.validation_count,self.dataset.test_count)*len(self.seeds)*(len(self.alphas)+3)*3*32
        if estimated > self.max_artifact_mb*1024*1024:
            raise ValueError("Conservative observation storage estimate exceeds artifact budget")
        return self


class ProtocolRef(Contract):
    protocol_id: str
    protocol_digest: str
    approval_nonce: str


NAME=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$"


class AgentCodeProtocol(Contract):
    """v6.6.4: an agent-written experiment, frozen as a code snapshot of the active code project plus a pinned
    environment. The researcher approves the exact digest; the runner never edits, installs or re-plans."""
    kind: Literal["agent_code_v1"]
    topic_id: str
    hypothesis: str = Field(min_length=1,max_length=8000)
    question: str = Field(default="",max_length=4000)
    entrypoint: str = Field(min_length=4,max_length=200)
    include: list[str] = Field(default_factory=list,max_length=50)
    conditions: list[str] = Field(min_length=2,max_length=8)
    baseline: str
    seeds: list[int] = Field(default_factory=lambda:[11,23,37],min_length=1,max_length=10)
    metrics: list[str] = Field(min_length=1,max_length=16)
    primary_metric: str
    direction: Literal["maximize","minimize"] = "maximize"
    min_effect: float = Field(default=0.0,ge=0,allow_inf_nan=False)
    reproduction_rel_tol: float = Field(default=1e-9,ge=0,le=0.5,allow_inf_nan=False)
    max_seconds: int = Field(default=600,ge=5,le=3600)
    trial_seconds: int = Field(default=120,ge=1,le=900)
    max_artifact_mb: int = Field(default=32,ge=1,le=256)
    engine: Literal["python","docker"] = "python"
    docker_image: str = ""
    cpu_threads: Literal[1] = 1
    gpu: Literal[False] = False

    @model_validator(mode="after")
    def fixed(self):
        import re
        from pathlib import PurePosixPath
        for rel in [self.entrypoint,*self.include]:
            p=PurePosixPath(rel.replace("\\","/"))
            if p.is_absolute() or ".." in p.parts or ":" in rel or not p.parts:
                raise ValueError("Code paths must be relative to the code project")
        if not self.entrypoint.endswith(".py"):raise ValueError("The entrypoint must be a .py file")
        for names,what in ((self.conditions,"conditions"),(self.metrics,"metrics")):
            if len(set(names))!=len(names) or any(not re.fullmatch(NAME,n) for n in names):
                raise ValueError(f"Choose unique simple names for {what}")
        if self.baseline not in self.conditions:raise ValueError("The baseline must be one of the conditions")
        if self.primary_metric not in self.metrics:raise ValueError("The primary metric must be one of the metrics")
        if len(set(self.seeds))!=len(self.seeds) or any(not 0<=s<=2**31-1 for s in self.seeds):
            raise ValueError("Seeds must be distinct nonnegative 32-bit integers")
        if self.engine=="docker" and not re.fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}",self.docker_image):
            raise ValueError("Docker requires an installed immutable image digest; no implicit pull")
        return self
