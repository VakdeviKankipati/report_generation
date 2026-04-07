"""WebSocket client for daily_report_env."""

from typing import Any, Dict

try:
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient

    from .models import (
        DailyReportAction,
        DailyReportObservation,
        DailyReportState,
        ReportReward,
    )
except ImportError:
    from models import (  # type: ignore
        DailyReportAction,
        DailyReportObservation,
        DailyReportState,
        ReportReward,
    )

    from openenv.core.client_types import StepResult  # type: ignore
    from openenv.core.env_client import EnvClient  # type: ignore


class DailyReportEnv(EnvClient[DailyReportAction, DailyReportObservation, DailyReportState]):
    """Async client; use `.sync()` for synchronous inference scripts."""

    def _step_payload(self, action: DailyReportAction) -> Dict[str, Any]:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[DailyReportObservation]:
        obs_data = payload.get("observation", {}) or {}
        rd = obs_data.get("reward_detail")
        reward_detail = ReportReward.model_validate(rd) if isinstance(rd, dict) else None

        observation = DailyReportObservation(
            task=obs_data.get("task", "daily_header"),
            instructions=obs_data.get("instructions", ""),
            static_data=obs_data.get("static_data") or {},
            header_fields=obs_data.get("header_fields") or {},
            summary_metrics=obs_data.get("summary_metrics") or {},
            kpi_rows=obs_data.get("kpi_rows") or [],
            pdf_generated=bool(obs_data.get("pdf_generated", False)),
            submitted=bool(obs_data.get("submitted", False)),
            graded_score=float(obs_data.get("graded_score", 0.0)),
            max_steps=int(obs_data.get("max_steps", 30)),
            steps_remaining=int(obs_data.get("steps_remaining", 30)),
            feedback=obs_data.get("feedback", ""),
            last_action_error=obs_data.get("last_action_error"),
            reward_detail=reward_detail,
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=dict(obs_data.get("metadata") or {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> DailyReportState:
        return DailyReportState.model_validate(payload)
