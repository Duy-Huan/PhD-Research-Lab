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
