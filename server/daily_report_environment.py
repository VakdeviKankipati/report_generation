"""Daily merge report (MRG) PDF assembly — real-world ops reporting simulation."""

from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

try:
    from openenv.core.env_server.interfaces import Environment
    from openenv.core.env_server.types import EnvironmentMetadata
except ImportError:
    from openenv_core.env_server.interfaces import Environment  # type: ignore
    from openenv_core.env_server.types import EnvironmentMetadata  # type: ignore

try:
    from ..models import (
        DailyReportAction,
        DailyReportObservation,
        DailyReportState,
        ReportReward,
        TaskName,
    )
except ImportError:
    from models import (  # type: ignore
        DailyReportAction,
        DailyReportObservation,
        DailyReportState,
        ReportReward,
        TaskName,
    )

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Reproducible static dataset (simulates ETL output available at 07:00 MRG)
STATIC_DATA: Dict[str, Any] = {
    "report_date": "2026-04-04",
    "merge_window": "00:00–06:00 UTC",
    "revenue_musd": "12.4",
    "incidents": "3",
    "uptime_pct": "99.97",
    "kpi_rows_expected": [
        ["Engineering", "Merged PRs", "42"],
        ["SRE", "Pages", "1"],
    ],
}

EXPECTED_HEADER = {
    "title": "Daily Post-Merge Operations Report",
    "report_date": STATIC_DATA["report_date"],
    "author": "Automated Reporting Service",
}

EXPECTED_METRICS = {
    "revenue_musd": STATIC_DATA["revenue_musd"],
    "incidents": STATIC_DATA["incidents"],
    "uptime_pct": STATIC_DATA["uptime_pct"],
}

HEADER_KEYS = set(EXPECTED_HEADER.keys())
METRIC_KEYS = set(EXPECTED_METRICS.keys())

MAX_STEPS_BY_TASK: Dict[TaskName, int] = {
    "daily_header": 18,
    "daily_summary": 28,
    "daily_full": 40,
}


def _strict_open_unit(x: float) -> float:
    """Clamp to strict open interval required by evaluator."""
    return max(0.01, min(0.99, float(x)))


def _grade_header(header: Dict[str, str]) -> float:
    if not EXPECTED_HEADER:
        return 0.99
    ok = sum(1 for k, v in EXPECTED_HEADER.items() if header.get(k) == v)
    return _strict_open_unit(ok / len(EXPECTED_HEADER))


def _grade_summary(header: Dict[str, str], metrics: Dict[str, str]) -> float:
    h = _grade_header(header)
    if not EXPECTED_METRICS:
        return h
    m_ok = sum(1 for k, v in EXPECTED_METRICS.items() if metrics.get(k) == v)
    m = _strict_open_unit(m_ok / len(EXPECTED_METRICS))
    return _strict_open_unit(0.35 * h + 0.65 * m)


def _rows_match(expected: List[List[str]], actual: List[List[str]]) -> bool:
    if len(actual) < len(expected):
        return False
    # Order-sensitive: first N rows must match expected sequence
    for i, exp in enumerate(expected):
        if i >= len(actual) or actual[i] != exp:
            return False
    return True


def _pdf_passes(pdf_bytes: bytes) -> Tuple[float, List[str]]:
    """Return (score_contribution 0-1, reasons) for hard task PDF checks."""
    reasons: List[str] = []
    if not pdf_bytes:
        return 0.01, ["empty_pdf"]

    try:
        from pypdf import PdfReader
    except ImportError:
        return 0.01, ["pypdf_missing"]

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as exc:
        return 0.01, [f"pdf_read_error:{exc}"]

    text_lower = text.lower()
    needles = [
        EXPECTED_HEADER["title"].lower(),
        STATIC_DATA["report_date"],
        STATIC_DATA["revenue_musd"],
        "engineering",
        "merged prs",
        "42",
    ]
    hits = sum(1 for n in needles if n in text_lower or n in text)
    frac = _strict_open_unit(hits / len(needles))
    if frac < 1.0:
        reasons.append(f"text_hits={hits}/{len(needles)}")
    return frac, reasons


def _grade_full(
    header: Dict[str, str],
    metrics: Dict[str, str],
    rows: List[List[str]],
    pdf_bytes: Optional[bytes],
    pdf_flag: bool,
) -> float:
    base = _grade_summary(header, metrics)
    exp_rows = STATIC_DATA["kpi_rows_expected"]
    row_part = 0.99 if _rows_match(exp_rows, rows) else 0.01
    pdf_part = 0.01
    if pdf_flag and pdf_bytes:
        pdf_part, _ = _pdf_passes(pdf_bytes)
    elif pdf_flag and not pdf_bytes:
        pdf_part = 0.01
    # Weighted blend: summary 0.45, table 0.25, pdf integrity 0.30
    return _strict_open_unit(0.45 * base + 0.25 * row_part + 0.30 * pdf_part)


def _task_grade(
    task: TaskName,
    header: Dict[str, str],
    metrics: Dict[str, str],
    rows: List[List[str]],
    pdf_bytes: Optional[bytes],
    pdf_flag: bool,
) -> float:
    if task == "daily_header":
        raw = _grade_header(header)
    elif task == "daily_summary":
        raw = _grade_summary(header, metrics)
    else:
        raw = _grade_full(header, metrics, rows, pdf_bytes, pdf_flag)
    
    # Clamp score to strictly (0, 1) to pass Phase 2 fail-fast requirement
    return _strict_open_unit(raw)


def _build_pdf_bytes(
    header: Dict[str, str],
    metrics: Dict[str, str],
    rows: List[List[str]],
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    title = header.get("title", "Untitled Report")
    c.drawString(50, y, title[:120])
    y -= 24
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Date: {header.get('report_date', '')}")
    y -= 16
    c.drawString(50, y, f"Author: {header.get('author', '')}")
    y -= 28
    c.drawString(50, y, f"Revenue (MUSD): {metrics.get('revenue_musd', '')}")
    y -= 16
    c.drawString(50, y, f"Incidents: {metrics.get('incidents', '')}")
    y -= 16
    c.drawString(50, y, f"Uptime %: {metrics.get('uptime_pct', '')}")
    y -= 28
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "KPI Table")
    y -= 18
    c.setFont("Helvetica", 10)
    for row in rows:
        line = " | ".join(row)
        c.drawString(50, y, line[:100])
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
    c.save()
    return buf.getvalue()


def _action_fingerprint(action: DailyReportAction) -> str:
    payload = action.model_dump()
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]


class DailyReportEnvironment(Environment[DailyReportAction, DailyReportObservation, DailyReportState]):
    """Simulates compiling the 07:00 MRG PDF from static ETL extracts."""

    SUPPORTS_CONCURRENT_SESSIONS = False

    def __init__(self) -> None:
        super().__init__()
        self._task: TaskName = "daily_header"
        self._header: Dict[str, str] = {}
        self._metrics: Dict[str, str] = {}
        self._rows: List[List[str]] = []
        self._pdf_bytes: Optional[bytes] = None
        self._pdf_generated = False
        self._submitted = False
        self._state = DailyReportState(episode_id=str(uuid4()), step_count=0)
        self._prev_grade = 0.0
        self._max_steps = MAX_STEPS_BY_TASK[self._task]

    def _sync_state(self) -> None:
        score = _task_grade(
            self._task,
            self._header,
            self._metrics,
            self._rows,
            self._pdf_bytes,
            self._pdf_generated,
        )
        self._state.task = self._task
        self._state.header_fields = dict(self._header)
        self._state.summary_metrics = dict(self._metrics)
        self._state.kpi_rows = [list(r) for r in self._rows]
        self._state.pdf_generated = self._pdf_generated
        self._state.submitted = self._submitted
        self._state.graded_score = score

    def _instructions_for(self, task: TaskName) -> str:
        if task == "daily_header":
            return (
                "Easy task: Fill the report header exactly from static_data using set_header_field "
                f"for keys {sorted(HEADER_KEYS)}. Call submit_report when finished."
            )
        if task == "daily_summary":
            return (
                "Medium task: Fill all header fields, then set_summary_metric for "
                f"{sorted(METRIC_KEYS)} using values from static_data. Call submit_report when finished."
            )
        return (
            "Hard task: Complete header and summary metrics, add_kpi_row twice in order "
            f"to match static_data['kpi_rows_expected'], run finalize_pdf, then submit_report. "
            "PDF must be generated in-environment (finalize_pdf)."
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> DailyReportObservation:
        task_raw = kwargs.get("task", "daily_header")
        if task_raw not in ("daily_header", "daily_summary", "daily_full"):
            task: TaskName = "daily_header"
        else:
            task = task_raw  # type: ignore[assignment]

        self._task = task
        self._header = {}
        self._metrics = {}
        self._rows = []
        self._pdf_bytes = None
        self._pdf_generated = False
        self._submitted = False
        self._prev_grade = 0.0
        self._max_steps = MAX_STEPS_BY_TASK[task]
        self._state = DailyReportState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task=task,
            last_action_error=None,
            repeat_action_streak=0,
            last_action_fingerprint=None,
        )
        self._sync_state()
        return self._observation(
            feedback=f"New episode. {self._instructions_for(task)}",
            last_error=None,
            step_reward=0.0,
            done=False,
        )

    @property
    def state(self) -> DailyReportState:
        self._sync_state()
        return self._state

    def _observation(
        self,
        *,
        feedback: str,
        last_error: Optional[str],
        step_reward: float,
        done: bool,
    ) -> DailyReportObservation:
        self._sync_state()
        score = self._state.graded_score
        delta = score - self._prev_grade
        self._prev_grade = score
        detail = ReportReward(
            progress_score=score,
            delta_progress=delta,
            step_total=min(1.0, max(0.0, step_reward)),
        )
        obs = DailyReportObservation(
            done=done,
            reward=detail.step_total,
            metadata={},
            task=self._task,
            instructions=self._instructions_for(self._task),
            static_data=dict(STATIC_DATA),
            header_fields=dict(self._header),
            summary_metrics=dict(self._metrics),
            kpi_rows=[list(r) for r in self._rows],
            pdf_generated=self._pdf_generated,
            submitted=self._submitted,
            graded_score=score,
            max_steps=self._max_steps,
            steps_remaining=max(0, self._max_steps - self._state.step_count),
            feedback=feedback,
            last_action_error=last_error,
            reward_detail=detail,
        )
        return obs

    def _penalty_repeat(self, fp: str) -> float:
        if fp == self._state.last_action_fingerprint:
            self._state.repeat_action_streak += 1
        else:
            self._state.repeat_action_streak = 1
            self._state.last_action_fingerprint = fp
        if self._state.repeat_action_streak >= 6:
            return 0.08
        return 0.0

    def step(
        self,
        action: DailyReportAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> DailyReportObservation:
        if self._submitted:
            return self._observation(
                feedback="Episode already submitted.",
                last_error="episode_already_done",
                step_reward=0.0,
                done=True,
            )

        self._state.step_count += 1
        fp = _action_fingerprint(action)
        repeat_pen = self._penalty_repeat(fp)

        err: Optional[str] = None
        step_reward = 0.0
        feedback = ""
        done = False

        cmd = action.command
        if cmd == "noop":
            step_reward = 0.02
            feedback = "No-op recorded (small time cost)."
        elif cmd == "set_header_field":
            if not action.key or action.value is None:
                err = "set_header_field_requires_key_and_value"
                step_reward = 0.0
            elif action.key not in HEADER_KEYS:
                err = f"invalid_header_key:{action.key}"
                step_reward = 0.0
            else:
                old = self._header.get(action.key)
                self._header[action.key] = action.value.strip()
                if self._header[action.key] == EXPECTED_HEADER[action.key]:
                    step_reward = 0.25
                    feedback = f"Header field '{action.key}' matches specification."
                else:
                    step_reward = 0.08
                    feedback = f"Header field '{action.key}' stored (not yet matching gold)."
                if old == self._header[action.key]:
                    step_reward = max(0.0, step_reward - 0.06)
        elif cmd == "set_summary_metric":
            if self._task == "daily_header":
                err = "summary_metrics_not_required_for_this_task"
                step_reward = 0.03
            elif not action.key or action.value is None:
                err = "set_summary_metric_requires_key_and_value"
            elif action.key not in METRIC_KEYS:
                err = f"invalid_metric_key:{action.key}"
                step_reward = 0.0
            else:
                self._metrics[action.key] = action.value.strip()
                if self._metrics[action.key] == EXPECTED_METRICS[action.key]:
                    step_reward = 0.22
                    feedback = f"Metric '{action.key}' correct."
                else:
                    step_reward = 0.1
                    feedback = f"Metric '{action.key}' stored."
        elif cmd == "add_kpi_row":
            if self._task != "daily_full":
                err = "kpi_rows_only_for_daily_full"
                step_reward = 0.02
            elif not action.row_cells:
                err = "add_kpi_row_requires_row_cells"
            else:
                row = [c.strip() for c in action.row_cells]
                self._rows.append(row)
                exp = STATIC_DATA["kpi_rows_expected"]
                idx = len(self._rows) - 1
                if idx < len(exp) and row == exp[idx]:
                    step_reward = 0.2
                    feedback = "KPI row matches next expected row."
                else:
                    step_reward = 0.07
                    feedback = "KPI row appended (order/content may be wrong)."
        elif cmd == "finalize_pdf":
            if self._task != "daily_full":
                err = "finalize_pdf_only_for_daily_full"
                step_reward = 0.03
            else:
                self._pdf_bytes = _build_pdf_bytes(self._header, self._metrics, self._rows)
                self._pdf_generated = True
                pdf_score, reasons = _pdf_passes(self._pdf_bytes)
                step_reward = 0.15 + 0.25 * pdf_score
                feedback = "PDF generated in-memory. " + (
                    "Text checks passed." if pdf_score >= 0.99 else f"PDF checks partial: {reasons}"
                )
        elif cmd == "submit_report":
            self._submitted = True
            done = True
            final = _task_grade(
                self._task,
                self._header,
                self._metrics,
                self._rows,
                self._pdf_bytes,
                self._pdf_generated,
            )
            # Terminal reward blends final grader with last-step bonus
            step_reward = min(1.0, 0.35 + 0.65 * final)
            feedback = f"Submitted. Final grader score={final:.2f}"
        else:
            err = f"unknown_command:{cmd}"
            step_reward = 0.0

        step_reward = max(0.0, step_reward - repeat_pen)
        if self._state.step_count >= self._max_steps and not done:
            done = True
            self._submitted = True
            final = _task_grade(
                self._task,
                self._header,
                self._metrics,
                self._rows,
                self._pdf_bytes,
                self._pdf_generated,
            )
            step_reward = min(1.0, step_reward + 0.4 * final)
            feedback += f" | Max steps reached; truncated with grader={final:.2f}"

        self._state.last_action_error = err
        self._sync_state()
        return self._observation(
            feedback=feedback,
            last_error=err,
            step_reward=step_reward,
            done=done,
        )

    @property
    def pdf_bytes(self) -> Optional[bytes]:
        return self._pdf_bytes

    @property
    def has_pdf(self) -> bool:
        return bool(self._pdf_generated and self._pdf_bytes)

    def get_metadata(self) -> Any:
        return EnvironmentMetadata(
            name="daily_report_env",
            description=(
                "Simulates assembling the daily 07:00 MRG (merge) PDF report from static ETL extracts."
            ),
            version="1.0.0",
        )


def run_gold_full_episode(env: DailyReportEnvironment) -> DailyReportObservation:
    """One-shot demo: full `daily_full` report + PDF using built-in static gold values."""
    env.reset(task="daily_full")
    last: Optional[DailyReportObservation] = None
    for key, value in EXPECTED_HEADER.items():
        last = env.step(DailyReportAction(command="set_header_field", key=key, value=value))
    for key, value in EXPECTED_METRICS.items():
        last = env.step(DailyReportAction(command="set_summary_metric", key=key, value=value))
    for row in STATIC_DATA["kpi_rows_expected"]:
        last = env.step(DailyReportAction(command="add_kpi_row", row_cells=list(row)))
    last = env.step(DailyReportAction(command="finalize_pdf"))
    last = env.step(DailyReportAction(command="submit_report"))
    assert last is not None
    return last
