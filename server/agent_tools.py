"""Compatibility wrapper around explicit agent modules.

Prefer using:
- server.report_agent (report generation agent)
- server.query_agent (query/lookup agent)
"""

from __future__ import annotations

from typing import Dict, List

from .database import ReportTrackingDB
from .query_agent import get_loan_details
from .report_agent import get_pending_jobs, run_daily_generation


__all__ = [
    "ReportTrackingDB",
    "get_pending_jobs",
    "get_loan_details",
    "run_daily_generation",
]
