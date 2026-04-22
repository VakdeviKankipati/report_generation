"""Tests for customer/lan mapping and live report tracking."""

from __future__ import annotations

from server.database import ReportTrackingDB


def test_seed_mapping_and_live_tracking(tmp_path):
    db_file = tmp_path / "tracking.db"
    db = ReportTrackingDB(str(db_file))
    db.seed_static_data()

    pairs = db.get_customer_lan_pairs()
    assert len(pairs) == 5
    first = pairs[0]

    report_id = "rep-10am-001"
    db.create_live_track(
        report_id=report_id,
        batch_id="20260422101010999-10am",
        customer_id=int(first["customer_id"]),
        lan_id=int(first["lan_id"]),
        report_type="daily_sales_summary",
        report_format="pdf",
        scheduler_slot="10am",
    )

    db.update_live_track_status(
        report_id,
        status="in_progress",
        retries_used=1,
        report_generated=False,
    )
    db.update_live_track_status(
        report_id,
        status="retrying",
        retries_used=2,
        error_code="lan_unreachable",
        error_message="LAN unreachable",
        report_generated=False,
    )
    db.update_live_track_status(
        report_id,
        status="failed",
        retries_used=5,
        error_code="lan_permanent_failure",
        error_message="Permanent failure after retries",
        report_generated=False,
        finished=True,
    )
    db.update_email_status(report_id, sent=True, status="failure_sent")

    track = db.get_live_track(report_id)
    all_tracks = db.list_live_tracks()

    assert track is not None
    assert track["status"] == "failed"
    assert track["retries_used"] == 5
    assert track["last_error_code"] == "lan_permanent_failure"
    assert track["email_sent"] == 1
    assert track["email_status"] == "failure_sent"
    assert track["finished_at_utc"] is not None

    assert len(all_tracks) == 1
    assert all_tracks[0]["customer_code"].startswith("CUST-")


def test_email_routing_rules(tmp_path):
    db_file = tmp_path / "tracking.db"
    db = ReportTrackingDB(str(db_file))
    db.seed_static_data()
    pairs = db.get_customer_lan_pairs()

    good = next(p for p in pairs if p["customer_code"] == "CUST-001")
    blocked = next(p for p in pairs if p["customer_code"] == "CUST-005")

    ok_report = "rep-ok-001"
    db.create_live_track(
        report_id=ok_report,
        batch_id="20260422101010999-10am",
        customer_id=int(good["customer_id"]),
        lan_id=int(good["lan_id"]),
        report_type="daily_morning_operational",
        report_format="pdf",
        scheduler_slot="10am",
    )

    blocked_report = "rep-block-001"
    db.create_live_track(
        report_id=blocked_report,
        batch_id="20260422101010999-10am",
        customer_id=int(blocked["customer_id"]),
        lan_id=int(blocked["lan_id"]),
        report_type="daily_morning_operational",
        report_format="pdf",
        scheduler_slot="10am",
    )

    # Success path -> mapped customer email.
    assert db.resolve_recipient_email(ok_report, is_failure=False) == "vakdevikankipati@gmail.com"

    # Failure path -> fixed escalation email only.
    assert db.resolve_recipient_email(ok_report, is_failure=True) == "vakdevikankipati@gmail.com"

    # Blocked customer email -> reroute to fixed email.
    assert db.resolve_recipient_email(blocked_report, is_failure=False) == "vakdevikankipati@gmail.com"
