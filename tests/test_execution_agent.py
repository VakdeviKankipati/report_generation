"""Tests for execution agent retries and email routing."""

from __future__ import annotations

import os

from server.database import ReportTrackingDB
from server.execution_agent import execute_report_job


def test_execute_success_sends_to_customer_email(tmp_path):
    os.environ["AGENT_EMAIL_MOCK"] = "1"
    db = ReportTrackingDB(str(tmp_path / "tracking.db"))
    db.seed_static_data()
    pairs = db.get_customer_lan_pairs()
    good = next(p for p in pairs if p["customer_code"] == "CUST-001")

    report_id = "job-success-001"
    db.create_live_track(
        report_id=report_id,
        batch_id="20260422101010999-10am",
        customer_id=int(good["customer_id"]),
        lan_id=int(good["lan_id"]),
        report_type="daily_morning_operational",
        report_format="pdf",
        scheduler_slot="10am",
    )
    result = execute_report_job(db, report_id)
    state = db.get_live_track(report_id)

    assert result["status"] == "success"
    assert result["email_recipient"] == "vakdevikankipati@gmail.com"
    assert state is not None
    assert state["status"] == "success"
    assert "success" in str(state["email_status"])


def test_execute_failure_retries_and_sends_fixed_email(tmp_path):
    os.environ["AGENT_EMAIL_MOCK"] = "1"
    db = ReportTrackingDB(str(tmp_path / "tracking.db"))
    db.seed_static_data()
    pairs = db.get_customer_lan_pairs()
    failing = next(p for p in pairs if p["lan_code"] == "LAN-005")

    report_id = "job-fail-001"
    db.create_live_track(
        report_id=report_id,
        batch_id="20260422101010999-10am",
        customer_id=int(failing["customer_id"]),
        lan_id=int(failing["lan_id"]),
        report_type="daily_morning_operational",
        report_format="pdf",
        scheduler_slot="10am",
    )
    result = execute_report_job(db, report_id)
    state = db.get_live_track(report_id)

    assert result["status"] == "failed"
    assert result["attempts"] == 5
    assert result["email_recipient"] == "vakdevikankipati@gmail.com"
    assert state is not None
    assert state["status"] == "failed"
    assert state["retries_used"] == 5
    assert "failure" in str(state["email_status"])
