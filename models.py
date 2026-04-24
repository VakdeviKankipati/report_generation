# Copyright (c) Meta-style OSS header for OpenEnv-style environments.

"""Typed Action, Observation, Reward, and State models for the daily report environment."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

try:
    from openenv.core.env_server.types import Action, Observation, State
except ImportError:
    from openenv_core.env_server.types import Action, Observation, State  # type: ignore


TaskName = Literal["daily_header", "daily_summary", "daily_full"]


class ReportReward(BaseModel):
    """Decomposed reward for debugging and learning (all components in [0, 1] where noted)."""

    progress_score: float = Field(
        ..., ge=0.0, le=1.0, description="Task grader after this step (0–1)"
    )
    delta_progress: float = Field(
        ..., description="Change in grader since previous step (can be negative)"
    )
    step_total: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Shaped reward for this step (progress delta + bonuses − penalties, clamped)",
    )


class DailyReportAction(Action):
    """Agent command for assembling a scheduled daily merge (MRG) PDF report."""

    command: Literal[
        "set_header_field",
        "set_summary_metric",
        "add_kpi_row",
        "finalize_pdf",
        "submit_report",
        "noop",
    ]
    key: Optional[str] = Field(
        default=None,
        description="Header key (title, report_date, author) or metric key (revenue_musd, incidents, uptime_pct)",
    )
    value: Optional[str] = Field(default=None, description="Value to set for header or metric")
    row_cells: Optional[List[str]] = Field(
        default=None,
        description="One KPI table row (hard task): cells left-to-right",
    )


class DailyReportObservation(Observation):
    """What the agent sees after each step."""

    task: TaskName
    instructions: str
    static_data: Dict[str, Any] = Field(default_factory=dict)
    header_fields: Dict[str, str] = Field(default_factory=dict)
    summary_metrics: Dict[str, str] = Field(default_factory=dict)
    kpi_rows: List[List[str]] = Field(default_factory=list)
    pdf_generated: bool = False
    submitted: bool = False
    graded_score: float = Field(0.0, ge=0.0, le=1.0)
    max_steps: int = 30
    steps_remaining: int = 30
    feedback: str = ""
    last_action_error: Optional[str] = None
    reward_detail: Optional[ReportReward] = None


class DailyReportState(State):
    """Serializable server state beyond episode_id / step_count."""

    task: TaskName = "daily_header"
    header_fields: Dict[str, str] = Field(default_factory=dict)
    summary_metrics: Dict[str, str] = Field(default_factory=dict)
    kpi_rows: List[List[str]] = Field(default_factory=list)
    pdf_generated: bool = False
    submitted: bool = False
    graded_score: float = 0.0
    last_action_error: Optional[str] = None
    repeat_action_streak: int = 0
    last_action_fingerprint: Optional[str] = None
