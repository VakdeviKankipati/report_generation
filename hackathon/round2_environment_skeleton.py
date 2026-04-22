"""Round 2 extension skeleton for daily_report_env.

This file is intentionally lightweight and can be integrated into your
existing `server/daily_report_environment.py` flow incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional


class ReportStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"
    EMAIL_SENT = "email_sent"


ReportFormat = Literal["pdf", "excel", "both"]


@dataclass
class ReportJob:
    job_id: str
    customer_id: str
    customer_email: str
    report_type: str
    report_format: ReportFormat
    timezone_name: str
    window_start_utc: str
    window_end_utc: str
    should_permanently_fail: bool = False
    should_transiently_fail_n: int = 0


@dataclass
class AttemptRecord:
    attempt: int
    timestamp_utc: str
    status: ReportStatus
    note: str


@dataclass
class ReportRuntimeState:
    status: ReportStatus = ReportStatus.STARTED
    attempts: int = 0
    last_error: Optional[str] = None
    email_sent: bool = False
    delivered_customer_id: Optional[str] = None
    trace: List[AttemptRecord] = field(default_factory=list)


class MockReportDB:
    """Simple in-memory DB adapter.

    Replace with your real DB adapter (Postgres/MySQL/etc.) for production demo.
    """

    def __init__(self) -> None:
        self._rows: Dict[str, Dict[str, object]] = {}

    def upsert_status(
        self,
        job_id: str,
        status: ReportStatus,
        attempts: int,
        last_error: Optional[str],
        email_sent: bool,
    ) -> None:
        self._rows[job_id] = {
            "job_id": job_id,
            "status": status.value,
            "attempts": attempts,
            "last_error": last_error,
            "email_sent": email_sent,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def get(self, job_id: str) -> Dict[str, object]:
        return self._rows.get(job_id, {})


class Round2WorkflowSimulator:
    """Enterprise report workflow simulator with retries and escalation."""

    def __init__(self, max_retries: int = 5) -> None:
        self.max_retries = max_retries
        self.db = MockReportDB()

    def _within_window(self, job: ReportJob, now_utc: datetime) -> bool:
        start = datetime.fromisoformat(job.window_start_utc)
        end = datetime.fromisoformat(job.window_end_utc)
        return start <= now_utc <= end

    def _generate_report(self, job: ReportJob, attempt: int) -> tuple[bool, Optional[str]]:
        if job.should_permanently_fail:
            return False, "lan_unreachable_permanent"
        if attempt <= job.should_transiently_fail_n:
            return False, "transient_timeout"
        return True, None

    def _send_failure_email(self, job: ReportJob, reason: str) -> bool:
        # Plug in real notifier (SMTP/provider API) for final submission.
        _ = (job.customer_email, reason)
        return True

    def run_job(self, job: ReportJob, target_customer_id: str) -> Dict[str, object]:
        state = ReportRuntimeState(status=ReportStatus.STARTED)
        self.db.upsert_status(job.job_id, state.status, state.attempts, state.last_error, state.email_sent)

        now_utc = datetime.now(timezone.utc)
        if not self._within_window(job, now_utc):
            state.status = ReportStatus.FAILED
            state.last_error = "outside_sla_window"
            self.db.upsert_status(job.job_id, state.status, state.attempts, state.last_error, state.email_sent)
            return {"ok": False, "reason": state.last_error, "db": self.db.get(job.job_id)}

        for attempt in range(1, self.max_retries + 1):
            state.attempts = attempt
            state.status = ReportStatus.IN_PROGRESS if attempt == 1 else ReportStatus.RETRYING
            self.db.upsert_status(job.job_id, state.status, state.attempts, state.last_error, state.email_sent)

            ok, err = self._generate_report(job, attempt)
            if ok:
                if target_customer_id != job.customer_id:
                    state.status = ReportStatus.FAILED
                    state.last_error = "wrong_customer_routing"
                    self.db.upsert_status(
                        job.job_id, state.status, state.attempts, state.last_error, state.email_sent
                    )
                    return {"ok": False, "reason": state.last_error, "db": self.db.get(job.job_id)}

                state.status = ReportStatus.SUCCESS
                state.last_error = None
                state.delivered_customer_id = target_customer_id
                self.db.upsert_status(job.job_id, state.status, state.attempts, state.last_error, state.email_sent)
                return {"ok": True, "reason": None, "db": self.db.get(job.job_id)}

            state.last_error = err
            state.trace.append(
                AttemptRecord(
                    attempt=attempt,
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    status=state.status,
                    note=err or "unknown_error",
                )
            )

        email_ok = self._send_failure_email(job, state.last_error or "report_generation_failed")
        if email_ok:
            state.email_sent = True
            state.status = ReportStatus.EMAIL_SENT
            self.db.upsert_status(job.job_id, state.status, state.attempts, state.last_error, state.email_sent)

        state.status = ReportStatus.FAILED
        self.db.upsert_status(job.job_id, state.status, state.attempts, state.last_error, state.email_sent)
        return {"ok": False, "reason": state.last_error, "db": self.db.get(job.job_id)}
