"""FastAPI app for the Daily Report OpenEnv server."""

import inspect
import os
import smtplib
import threading
from email.message import EmailMessage
from typing import Any, Dict, Optional

from fastapi import HTTPException, Response
from fastapi.responses import HTMLResponse
from pathlib import Path
from pydantic import BaseModel, ConfigDict

try:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.serialization import deserialize_action, serialize_observation
    from openenv.core.env_server.types import ResetResponse, StepRequest, StepResponse

    from ..models import DailyReportAction, DailyReportObservation
    from .database import ReportTrackingDB
    from .daily_report_environment import DailyReportEnvironment, run_gold_full_episode
    from .scheduler_agents import run_manual_schedule
except ImportError:
    from models import DailyReportAction, DailyReportObservation  # type: ignore

    from openenv.core.env_server.http_server import create_app  # type: ignore
    from openenv.core.env_server.serialization import deserialize_action, serialize_observation  # type: ignore
    from openenv.core.env_server.types import ResetResponse, StepRequest, StepResponse  # type: ignore

    from server.database import ReportTrackingDB  # type: ignore
    from server.daily_report_environment import DailyReportEnvironment, run_gold_full_episode  # type: ignore
    from server.scheduler_agents import run_manual_schedule  # type: ignore


def _create_app():
    try:
        first_param = next(iter(inspect.signature(create_app).parameters.values()))
        annotation_text = str(first_param.annotation)
    except (StopIteration, TypeError, ValueError):
        annotation_text = "typing.Callable"

    expects_instance = "Environment" in annotation_text and "Callable" not in annotation_text
    env_arg = DailyReportEnvironment() if expects_instance else DailyReportEnvironment
    return create_app(
        env_arg,
        DailyReportAction,
        DailyReportObservation,
        env_name="daily_report_env",
    )


app = _create_app()

# Stateful HTTP session (OpenEnv's standard POST /step creates a *new* env each call, so it cannot
# remember prior steps). Use /session/* for browser/curl demos, or WebSocket /ws for agents.
_session_lock = threading.Lock()
_session_env: Optional[DailyReportEnvironment] = None


class SessionResetBody(BaseModel):
    """Body for POST /session/reset — picks task and optional OpenEnv reset fields."""

    model_config = ConfigDict(extra="allow")

    task: str = "daily_full"
    seed: Optional[int] = None
    episode_id: Optional[str] = None


class EmailRequest(BaseModel):
    email: str


class ManualScheduleRequest(BaseModel):
    slot: str = "both"  # 10am | 11am | both


@app.get("/")
def root() -> HTMLResponse:
    """Serve the frontend HTML."""
    html_path = Path(__file__).parent / "frontend" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Frontend UI not found.</h1>", status_code=404)


@app.post("/session/reset", tags=["Session (stateful HTTP)"])
def session_reset(body: SessionResetBody = SessionResetBody()) -> ResetResponse:
    """Start a new episode that persists across POST /session/step (same server process)."""
    global _session_env
    with _session_lock:
        _session_env = DailyReportEnvironment()
        kwargs = body.model_dump(exclude_none=True)
        obs = _session_env.reset(**kwargs)
    return ResetResponse(**serialize_observation(obs))


@app.post("/session/step", tags=["Session (stateful HTTP)"])
def session_step(request: StepRequest) -> StepResponse:
    """Same as OpenEnv /step but uses the session started by POST /session/reset."""
    global _session_env
    with _session_lock:
        if _session_env is None:
            raise HTTPException(
                status_code=400,
                detail="No session. Call POST /session/reset first (or POST /session/run_static_demo).",
            )
        try:
            action = deserialize_action(request.action, DailyReportAction)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid action: {exc}. Wrap fields in an 'action' object (see /docs).",
            ) from exc
        obs = _session_env.step(action)
    return StepResponse(**serialize_observation(obs))


@app.get("/session/state", tags=["Session (stateful HTTP)"])
def session_state() -> Dict[str, Any]:
    """Current session state (header fields, metrics, pdf_generated, graded_score, …)."""
    global _session_env
    with _session_lock:
        if _session_env is None:
            raise HTTPException(status_code=400, detail="No session. Call POST /session/reset first.")
        st = _session_env.state
        if hasattr(st, "model_dump"):
            return st.model_dump()
        return dict(st)


@app.get("/session/report.pdf", tags=["Session (stateful HTTP)"])
def session_report_pdf() -> Response:
    """Download the PDF after `finalize_pdf` (e.g. task daily_full) or after /session/run_static_demo."""
    global _session_env
    with _session_lock:
        if _session_env is None or not _session_env.has_pdf:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No PDF in this session. For task daily_full run command finalize_pdf, or call "
                    "POST /session/run_static_demo."
                ),
            )
        pdf = _session_env.pdf_bytes
        assert pdf is not None
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="daily_mrg_report.pdf"',
            },
        )


@app.post("/session/run_static_demo", tags=["Session (stateful HTTP)"])
def session_run_static_demo() -> Dict[str, Any]:
    """Generate the full report from built-in static data + PDF in one request (manual / 7am-style trigger)."""
    global _session_env
    with _session_lock:
        _session_env = DailyReportEnvironment()
        obs = run_gold_full_episode(_session_env)
    return {
        "message": "Static gold report generated. Download: GET /session/report.pdf",
        "result": serialize_observation(obs),
    }


@app.post("/session/send_email", tags=["Session (stateful HTTP)"])
def session_send_email(body: EmailRequest) -> Dict[str, Any]:
    """Email the generated PDF report via Gmail SMTP (or mock it)."""
    global _session_env
    with _session_lock:
        if _session_env is None or not _session_env.has_pdf:
            raise HTTPException(
                status_code=400, detail="No PDF has been generated yet. Please generate the report first."
            )
        pdf_bytes = _session_env.pdf_bytes
        assert pdf_bytes is not None

    smtp_user = os.environ.get("SMTP_EMAIL")
    smtp_pass = os.environ.get("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        print(f"[MOCK EMAIL] Would send report to {body.email} (Configure SMTP_EMAIL and SMTP_PASSWORD to send real emails)")
        return {"message": f"Simulated email sent to {body.email} (Credentials missing)"}

    msg = EmailMessage()
    msg["Subject"] = "Daily Post-Merge Operations Report"
    msg["From"] = smtp_user
    msg["To"] = body.email
    msg.set_content("Hello,\\n\\nPlease find the attached Daily MRG Report generated automatically by the Reporting Service.\\n\\nThanks.")

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename="daily_mrg_report.pdf",
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")

    return {"message": f"Successfully sent email to {body.email}"}


@app.post("/session/run_manual_schedule", tags=["Scheduling"])
def session_run_manual_schedule(body: ManualScheduleRequest = ManualScheduleRequest()) -> Dict[str, Any]:
    """Manual scheduler trigger for 10am/11am report generation and sending."""
    db = ReportTrackingDB()
    db.seed_static_data()
    try:
        result = run_manual_schedule(db, body.slot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "message": "Manual schedule executed",
        "result": result,
    }


@app.get("/session/live_tracks", tags=["Scheduling"])
def session_live_tracks() -> Dict[str, Any]:
    """Return live tracking rows for UI table."""
    db = ReportTrackingDB()
    rows = db.list_live_tracks()
    return {"count": len(rows), "rows": rows}


@app.post("/session/live_tracks/reset", tags=["Scheduling"])
def session_live_tracks_reset() -> Dict[str, Any]:
    """Clear live tracking table for fresh training/evaluation episodes."""
    db = ReportTrackingDB()
    deleted = db.clear_live_tracks()
    return {"message": "Live tracking reset", "deleted_rows": deleted}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
