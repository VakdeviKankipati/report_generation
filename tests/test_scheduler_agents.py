"""Tests for 10am/11am immediate generate-and-send behavior."""

from __future__ import annotations

from server.database import ReportTrackingDB
from server.scheduler_agents import run_manual_schedule, run_scheduler_slot


def test_scheduler_two_slots_immediate_flow(tmp_path):
    db = ReportTrackingDB(str(tmp_path / "tracking.db"))
    db.seed_static_data()

    out_10 = run_scheduler_slot(db, "10am")
    out_11 = run_scheduler_slot(db, "11am")

    assert out_10["processed_count"] == 5
    assert out_11["processed_count"] == 5

    tracks = db.list_live_tracks()
    assert len(tracks) == 10

    # One LAN is permanent-fail and appears in both 10am + 11am jobs -> 2 failures.
    failed = [t for t in tracks if t["status"] == "failed"]
    success = [t for t in tracks if t["status"] == "success"]
    assert len(failed) == 2
    assert len(success) == 8


def test_manual_schedule_both_runs_two_slots(tmp_path):
    db = ReportTrackingDB(str(tmp_path / "tracking.db"))
    db.seed_static_data()
    out = run_manual_schedule(db, "both")
    assert out["slot"] == "both"
    assert out["processed_count"] == 10
    assert len(out["runs"]) == 2
