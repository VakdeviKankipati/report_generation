"""Unit tests for graders and episode flow (no network)."""

import sys
from pathlib import Path

import pytest

# Repository layout: tests live inside env package; add env root for `server` imports
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server.daily_report_environment import (  # noqa: E402
    DailyReportEnvironment,
    STATIC_DATA,
    _grade_full,
    _grade_header,
    _grade_summary,
    run_gold_full_episode,
)
from models import DailyReportAction  # noqa: E402


def test_static_data_keys():
    assert STATIC_DATA["report_date"] == "2026-04-04"
    assert len(STATIC_DATA["kpi_rows_expected"]) == 2


def test_grade_header_perfect():
    h = {
        "title": "Daily Post-Merge Operations Report",
        "report_date": "2026-04-04",
        "author": "Automated Reporting Service",
    }
    assert _grade_header(h) == pytest.approx(1.0)


def test_grade_summary_partial():
    h = dict(
        title="Daily Post-Merge Operations Report",
        report_date="2026-04-04",
        author="Automated Reporting Service",
    )
    m = {"revenue_musd": "12.4", "incidents": "0", "uptime_pct": "99.97"}
    s = _grade_summary(h, m)
    assert 0.5 < s < 1.0


def test_full_episode_easy():
    env = DailyReportEnvironment()
    obs = env.reset(task="daily_header")
    assert obs.task == "daily_header"
    assert obs.graded_score == 0.0
    obs = env.step(
        DailyReportAction(command="set_header_field", key="title", value="Daily Post-Merge Operations Report")
    )
    assert obs.header_fields["title"]
    obs = env.step(DailyReportAction(command="set_header_field", key="report_date", value="2026-04-04"))
    obs = env.step(
        DailyReportAction(command="set_header_field", key="author", value="Automated Reporting Service")
    )
    obs = env.step(DailyReportAction(command="submit_report"))
    assert obs.done
    assert obs.graded_score == pytest.approx(1.0)


def test_hard_requires_pdf():
    env = DailyReportEnvironment()
    env.reset(task="daily_full")
    # Fill everything except PDF
    for k, v in {
        "title": "Daily Post-Merge Operations Report",
        "report_date": "2026-04-04",
        "author": "Automated Reporting Service",
    }.items():
        env.step(DailyReportAction(command="set_header_field", key=k, value=v))
    for k, v in {"revenue_musd": "12.4", "incidents": "3", "uptime_pct": "99.97"}.items():
        env.step(DailyReportAction(command="set_summary_metric", key=k, value=v))
    for row in STATIC_DATA["kpi_rows_expected"]:
        env.step(DailyReportAction(command="add_kpi_row", row_cells=row))
    obs = env.step(DailyReportAction(command="submit_report"))
    assert obs.done
    assert obs.graded_score < 0.99  # PDF chunk missing


def test_run_gold_full_episode_produces_pdf():
    env = DailyReportEnvironment()
    obs = run_gold_full_episode(env)
    assert obs.done
    assert env.has_pdf
    assert env.pdf_bytes is not None
    assert len(env.pdf_bytes) > 100


def test_grade_full_integration():
    header = {
        "title": "Daily Post-Merge Operations Report",
        "report_date": "2026-04-04",
        "author": "Automated Reporting Service",
    }
    metrics = {"revenue_musd": "12.4", "incidents": "3", "uptime_pct": "99.97"}
    rows = [list(r) for r in STATIC_DATA["kpi_rows_expected"]]
    from server.daily_report_environment import _build_pdf_bytes

    pdf = _build_pdf_bytes(header, metrics, rows)
    g = _grade_full(header, metrics, rows, pdf, True)
    assert g >= 0.85
