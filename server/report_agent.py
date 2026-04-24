"""Report Generation Agent logic."""

from __future__ import annotations

from typing import Dict, List

from .database import ReportTrackingDB
from .scheduler_agents import run_manual_schedule


def get_pending_jobs(db: ReportTrackingDB) -> List[Dict[str, object]]:
    """List pending jobs that have not executed yet."""
    return db.list_pending_for_midnight_delivery()


def run_daily_generation(db: ReportTrackingDB) -> Dict[str, object]:
    """Run the daily autonomous report generation workflow."""
    result = run_manual_schedule(db, "both")
    run_summaries: List[Dict[str, object]] = []
    for run in result["runs"]:
        batch_id = str(run["batch_id"])
        run_summaries.append(
            {
                "slot": run["slot"],
                "batch_id": batch_id,
                "processed_count": int(run["processed_count"]),
                "status_summary": db.summarize_tracks(batch_id=batch_id),
            }
        )

    return {
        "agent": "report_generation_agent",
        "mode": "daily_autonomous",
        "total_processed": int(result["processed_count"]),
        "runs": run_summaries,
        "overall_status_summary": db.summarize_tracks(),
    }
