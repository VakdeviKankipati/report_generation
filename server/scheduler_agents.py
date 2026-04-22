"""Two scheduler-agent slots for report generation orchestration.

10 AM agent: report type A
11 AM agent: report type B
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from .database import ReportTrackingDB
from .execution_agent import execute_report_job


def _make_batch_id(slot: str) -> str:
    # Format: YYYYMMDDHHMMSSmmm + slot, e.g. 20260422113210987-10am
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:17]
    return f"{ts}-{slot}"


def _format_for_slot(slot: str) -> str:
    if slot == "10am":
        return "pdf"
    return "excel"


def _report_type_for_slot(slot: str) -> str:
    if slot == "10am":
        return "daily_morning_operational"
    return "daily_midday_finance"


def _create_slot_jobs(db: ReportTrackingDB, slot: str, batch_id: str) -> List[str]:
    if slot not in ("10am", "11am"):
        raise ValueError("slot must be either '10am' or '11am'")

    pairs = db.get_customer_lan_pairs()
    report_ids: List[str] = []
    for row in pairs:
        report_id = f"{batch_id}-{uuid4().hex[:8]}"
        db.create_live_track(
            report_id=report_id,
            batch_id=batch_id,
            customer_id=int(row["customer_id"]),
            lan_id=int(row["lan_id"]),
            report_type=_report_type_for_slot(slot),
            report_format=_format_for_slot(slot),
            scheduler_slot=slot,
        )
        report_ids.append(report_id)
    return report_ids


def _execute_jobs(db: ReportTrackingDB, report_ids: List[str]) -> Dict[str, object]:
    results: List[Dict[str, object]] = []
    for report_id in report_ids:
        results.append(execute_report_job(db, report_id))
    return {"processed_count": len(results), "results": results}


def run_scheduler_slot(db: ReportTrackingDB, slot: str) -> Dict[str, object]:
    """Scheduler slots:
    - 10am: generate report type A and send now
    - 11am: generate report type B and send now
    """
    if slot in ("10am", "11am"):
        batch_id = _make_batch_id(slot)
        report_ids = _create_slot_jobs(db, slot, batch_id)
        out = _execute_jobs(db, report_ids)
        out["slot"] = slot
        out["batch_id"] = batch_id
        return out
    raise ValueError("slot must be one of: 10am, 11am")


def run_manual_schedule(db: ReportTrackingDB, slot: str) -> Dict[str, object]:
    """Manual trigger:
    - slot=10am or 11am: run one scheduler now
    - slot=both: run 10am then 11am now
    """
    if slot in ("10am", "11am"):
        return run_scheduler_slot(db, slot)
    if slot == "both":
        out_10 = run_scheduler_slot(db, "10am")
        out_11 = run_scheduler_slot(db, "11am")
        return {
            "slot": "both",
            "processed_count": int(out_10["processed_count"]) + int(out_11["processed_count"]),
            "runs": [out_10, out_11],
        }
    raise ValueError("slot must be one of: 10am, 11am, both")
