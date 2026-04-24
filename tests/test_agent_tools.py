"""Tests for agent-facing data lookup and daily run functions."""

from __future__ import annotations

from server.agent_tools import get_loan_details, run_daily_generation
from server.database import ReportTrackingDB


def test_get_loan_details_found_and_not_found(tmp_path):
    db = ReportTrackingDB(str(tmp_path / "tracking.db"))
    db.seed_static_data()

    found = get_loan_details(db, "LAN-001")
    missing = get_loan_details(db, "LAN-999")

    assert found["found"] is True
    assert found["loan_number"] == "LAN-001"
    assert found["customer_code"] == "CUST-001"

    assert missing["found"] is False
    assert missing["loan_number"] == "LAN-999"
    assert missing["reason"] == "loan_not_found_in_database"


def test_run_daily_generation_summary(tmp_path):
    db = ReportTrackingDB(str(tmp_path / "tracking.db"))
    db.seed_static_data()

    out = run_daily_generation(db)

    assert out["mode"] == "daily_autonomous"
    assert out["total_processed"] == 10
    assert len(out["runs"]) == 2
    assert out["overall_status_summary"]["total"] == 10
