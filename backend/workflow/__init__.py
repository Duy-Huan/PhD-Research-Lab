"""v4.1 Unified Workflow Orchestrator: schema (contracts) · steps (allowlisted step types) · templates (versioned
registry) · engine (state machine, approvals, budgets, nesting) · hpo (Optuna / local runner / Ray adapter) ·
model_intel (model adapters with MEASURED / ESTIMATED / UNAVAILABLE labels) · harness (replaceable agent planner)."""
from .engine import ORCH, OrchestratorError  # noqa: F401
