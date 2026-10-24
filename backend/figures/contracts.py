"""Validated contracts for v6.4.0 Figure Studio & v6.4.2 Scientific Figure Integrity."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FigurePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    width_in: float = Field(gt=0.5, le=24.0)
    height_in: float = Field(gt=0.5, le=24.0)
    font_size_pt: int = Field(ge=6, le=24)
    dpi: int = Field(ge=72, le=1200)
    palette: str = "colorblind-safe"
    venue_note: str = "Template guidance only; verify against the specific venue's current author instructions."


PRESETS: dict[str, FigurePreset] = {
    "ieee-single-column": FigurePreset(
        id="ieee-single-column",
        label="IEEE Single Column (3.5 in)",
        width_in=3.5,
        height_in=2.5,
        font_size_pt=8,
        dpi=300,
        palette="colorblind-safe",
        venue_note="Standard 3.5-inch single-column template; verify exact IEEE society formatting.",
    ),
    "ieee-double-column": FigurePreset(
        id="ieee-double-column",
        label="IEEE Double Column (7.16 in)",
        width_in=7.16,
        height_in=3.6,
        font_size_pt=9,
        dpi=300,
        palette="colorblind-safe",
        venue_note="Standard 7.16-inch double-column template; verify exact IEEE society formatting.",
    ),
    "acm": FigurePreset(
        id="acm",
        label="ACM / NeurIPS / ICML Column (5.5 in)",
        width_in=5.5,
        height_in=3.2,
        font_size_pt=9,
        dpi=300,
        palette="colorblind-safe",
    ),
    "thesis": FigurePreset(
        id="thesis",
        label="Dissertation / Thesis (6.0 in)",
        width_in=6.0,
        height_in=4.0,
        font_size_pt=10,
        dpi=300,
        palette="publication-classic",
    ),
    "presentation": FigurePreset(
        id="presentation",
        label="Slide / Presentation 16:9 (8.0 in)",
        width_in=8.0,
        height_in=4.5,
        font_size_pt=12,
        dpi=150,
        palette="viridis",
    ),
    "interactive-html": FigurePreset(
        id="interactive-html",
        label="Interactive Web / Report (7.5 in)",
        width_in=7.5,
        height_in=4.2,
        font_size_pt=10,
        dpi=150,
        palette="colorblind-safe",
    ),
}


class FigureStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str = Field(default="ieee-single-column", max_length=80)
    font_size_pt: int = Field(default=8, ge=6, le=28)
    line_width: float = Field(default=1.6, ge=0.4, le=8.0)
    marker_size: float = Field(default=4.5, ge=0.0, le=18.0)
    grid: bool = True
    legend: bool = True
    palette: Literal["colorblind-safe", "grayscale", "viridis", "publication-classic"] = "colorblind-safe"
    width_in: float = Field(default=3.5, gt=0.5, le=24.0)
    height_in: float = Field(default=2.5, gt=0.5, le=24.0)
    dpi: int = Field(default=300, ge=72, le=1200)
    truncate_y_axis: bool = False
    y_break_indicator: bool = False


class FigureDataSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "experiment_artifact",
        "workspace_artifact",
        "inline_series",
        "comparison_plate",
        "diagram_dot",
        "waveform_json",
        "surface_3d",
    ] = "inline_series"
    experiment_id: str = Field(default="", max_length=120)
    artifact_id: str = Field(default="", max_length=120)
    expected_sha256: str = Field(default="", max_length=128)
    x_values: list[float | int | str] = Field(default_factory=list, max_length=5000)
    series: dict[str, list[float]] = Field(default_factory=dict)
    error_bars: dict[str, list[float]] = Field(default_factory=dict)
    error_bar_type: Literal["none", "sd", "sem", "ci95"] = "none"
    comparison_panels: list[dict] = Field(default_factory=list, max_length=16)
    dot_source: str = Field(default="", max_length=50000)
    waveform: dict = Field(default_factory=dict)
    mesh_3d: dict = Field(default_factory=dict)
    is_synthetic_fixture: bool = False
    is_illustrative_only: bool = False


class FigureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    figure_id: str = Field(default="", max_length=120)
    topic_id: str = Field(min_length=1, max_length=120)
    mission_id: str = Field(default="", max_length=120)
    title: str = Field(min_length=1, max_length=400)
    caption: str = Field(default="", max_length=4000)
    alt_text: str = Field(default="", max_length=2000)
    category: Literal["plot_2d", "comparison_plate", "diagram", "waveform", "surface_3d"] = "plot_2d"
    plot_kind: Literal["line", "bar", "scatter", "area", "ablation"] = "line"
    x_label: str = Field(default="x", max_length=200)
    y_label: str = Field(default="y", max_length=200)
    x_unit: str = Field(default="", max_length=80)
    y_unit: str = Field(default="", max_length=80)
    transformations: list[str] = Field(default_factory=list, max_length=20)
    renderer: Literal["auto", "matplotlib", "plotly", "graphviz", "wavedrom", "comparison", "pyvista_3d"] = "auto"
    source: FigureDataSource = Field(default_factory=FigureDataSource)
    style: FigureStyle = Field(default_factory=FigureStyle)
    outputs: list[Literal["svg", "png", "pdf", "html", "dot"]] = Field(default_factory=lambda: ["svg", "png", "pdf"])
    require_data_provenance: bool = True
    require_approval_before_paper_use: bool = True

    @model_validator(mode="after")
    def _validate_figure(self):
        if not self.outputs:
            raise ValueError("At least one output format is required")
        if self.style.preset in PRESETS and self.style.width_in == 3.5 and self.style.preset != "ieee-single-column":
            p = PRESETS[self.style.preset]
            self.style.width_in = p.width_in
            self.style.height_in = p.height_in
            self.style.font_size_pt = p.font_size_pt
            self.style.dpi = p.dpi
        for name, values in self.source.series.items():
            if not name.strip():
                raise ValueError("Series name cannot be empty")
            for v in values:
                import math
                if not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                    raise ValueError(f"Non-finite value in series '{name}'")
        return self


class FigureProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    topic_id: str
    mission_id: str = ""
    figure_id: str
    version: int
    renderer_used: str
    renderer_version: str
    spec_sha256: str
    script_sha256: str
    data_sha256: str
    source_kind: str
    experiment_id: str = ""
    artifact_id: str = ""
    transformations: list[str] = Field(default_factory=list)
    camera_state: dict = Field(default_factory=dict)
    exports: dict[str, dict] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    scientific_review: Literal["pending", "approved", "rejected", "illustrative_only"] = "pending"
    created_at: str


class FigureVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    figure_artifact_id: str
    version: int
    source_data_artifact_ids: list[str]
    tests: dict[str, str]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    overall_status: Literal["passed", "needs_review", "failed", "illustrative_only"]
    validator_version: str = "6.4.2"
    checked_at: str
