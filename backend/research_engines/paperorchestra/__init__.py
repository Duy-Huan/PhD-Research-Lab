"""PaperOrchestra Research Writing Engine Plugin for PhD Research Lab."""
from backend.research_engines.paperorchestra.contracts import (
    PaperOrchestraConfig,
    PaperOutline,
    PaperWritingTaskSpec,
    SectionOutline,
    VerificationQualityReport,
    WritingArtifact,
)
from backend.research_engines.paperorchestra.engine import PaperOrchestraEngine
from backend.research_engines.paperorchestra.modes import (
    create_l2_paper_mission,
    create_l3_team_mission,
    create_l4_research_to_paper_mission,
    execute_mission_task,
)

__all__ = [
    "PaperOrchestraEngine",
    "WritingArtifact",
    "PaperWritingTaskSpec",
    "PaperOrchestraConfig",
    "PaperOutline",
    "SectionOutline",
    "VerificationQualityReport",
    "create_l2_paper_mission",
    "create_l3_team_mission",
    "create_l4_research_to_paper_mission",
    "execute_mission_task",
]

