"""Execution agent loop for retries, routing, and email tracking."""

from __future__ import annotations

import base64
import os
import smtplib
from email.message import EmailMessage
from typing import Dict

import requests

from .database import ReportTrackingDB
from .report_builder import build_10am_account_statement, build_11am_finance_summary


def _send_agent_email(
    recipient_email: str,
    subject: str,
    body: str,
    attachment_name: str | None = None,
    attachment_bytes: bytes | None = None,
) -> tuple[bool, str]:
    """Send scheduler email using SMTP.

    Behavior:
    - If AGENT_EMAIL_MOCK=1, do mock send (useful for local testing).
    - Otherwise requires SMTP_EMAIL and SMTP_PASSWORD to send real emails.
    """
    if os.environ.get("AGENT_EMAIL_MOCK", "0") == "1":
        print(f"[EMAIL][MOCK] recipient={recipient_email} subject={subject}")
        return True, "mock_sent"

    sender_email = os.environ.get("SENDER_EMAIL") or os.environ.get("SMTP_EMAIL")
    api_key = os.environ.get("BREVO_API_KEY") or os.environ.get("SMTP_PASSWORD")

    if not sender_email or not api_key:
        print(f"[EMAIL][SKIP] smtp_not_configured recipient={recipient_email} (Configure SENDER_EMAIL and BREVO_API_KEY)")
        return False, "api_keys_not_configured"

    try:
        url = "https://api.brevo.com/v3/smtp/email"
        payload: Dict[str, object] = {
            "sender": {"name": "Reporting Service Agent", "email": sender_email},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "textContent": body,
        }
        
        if attachment_name and attachment_bytes:
            payload["attachments"] = [
                {
                    "name": attachment_name,
                    "content": base64.b64encode(attachment_bytes).decode("ascii")
                }
            ]

        print(f"[EMAIL][BREVO] attempting recipient={recipient_email}")
        
        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        print(f"[EMAIL][BREVO] sent recipient={recipient_email}")
        return True, "sent_via_brevo"
    except Exception as exc:
        err_msg = str(exc)
        if hasattr(exc, 'response') and exc.response is not None:
            err_msg += f" body={exc.response.text}"
        print(f"[EMAIL][BREVO][ERROR] recipient={recipient_email} err={err_msg}")
        return False, f"brevo_error:{exc}"


def execute_report_job(db: ReportTrackingDB, report_id: str) -> Dict[str, object]:
    """Run one report job with max retries and DB live updates.

    Rules:
    - Permanent LAN failure -> retry until max_retries, then fail.
    - Success -> send report to resolved customer email.
    - Failure -> send failure email only to fixed failure email.
    """
    track = db.get_live_track(report_id)
    if track is None:
        raise ValueError(f"Unknown report_id: {report_id}")

    max_retries = int(track["max_retries"])
    lan_id = int(track["lan_id"])
    lan_code = None
    should_fail_permanently = 0
    for pair in db.get_customer_lan_pairs():
        if int(pair["lan_id"]) == lan_id:
            lan_code = str(pair["lan_code"])
            should_fail_permanently = int(pair["should_fail_permanently"])
            break

    if lan_code is None:
        raise ValueError(f"LAN mapping not found for report_id: {report_id}")

    for attempt in range(1, max_retries + 1):
        db.update_live_track_status(
            report_id=report_id,
            status="in_progress" if attempt == 1 else "retrying",
            retries_used=attempt,
            error_code=None,
            error_message=None,
            report_generated=False,
            finished=False,
        )

        if should_fail_permanently == 1:
            db.update_live_track_status(
                report_id=report_id,
                status="retrying" if attempt < max_retries else "failed",
                retries_used=attempt,
                error_code="lan_permanent_failure",
                error_message=f"{lan_code} report generation failed",
                report_generated=False,
                finished=attempt == max_retries,
            )
            continue

        # Success path
        db.update_live_track_status(
            report_id=report_id,
            status="success",
            retries_used=attempt,
            error_code=None,
            error_message=None,
            report_generated=True,
            finished=True,
        )
        recipient = db.resolve_recipient_email(report_id, is_failure=False)
        context = db.get_report_context(report_id)
        if context is None:
            raise ValueError(f"Report context not found: {report_id}")
        if str(track["scheduler_slot"]) == "10am":
            pdf_bytes = build_10am_account_statement(context)
        else:
            pdf_bytes = build_11am_finance_summary(context)
        sent, reason = _send_agent_email(
            recipient_email=recipient,
            subject=f"[SUCCESS] Report generated for {lan_code}",
            body=(
                f"Hello,\n\nYour report has been generated and sent by agent.\n"
                f"Report ID: {report_id}\nLAN: {lan_code}\nType: {track['report_type']}\n"
            ),
            attachment_name=f"{report_id}.pdf",
            attachment_bytes=pdf_bytes,
        )
        # SMTP can accept mail even if remote mailbox later bounces.
        email_status = "success_accepted_by_smtp" if sent else f"success_failed:{reason}"
        db.update_email_status(report_id, sent=sent, status=email_status)
        return {
            "report_id": report_id,
            "status": "success",
            "attempts": attempt,
            "email_recipient": recipient,
            "email_sent": sent,
            "email_status": email_status,
        }

    # Final failure path: email goes only to fixed failure notification address.
    recipient = db.resolve_recipient_email(report_id, is_failure=True)
    sent, reason = _send_agent_email(
        recipient_email=recipient,
        subject=f"[FAILED] Report generation failed for {lan_code}",
        body=(
            "Report generation failed after max retries.\n"
            f"Report ID: {report_id}\n"
            f"LAN: {lan_code}\n"
            f"Retries: {max_retries}\n"
            "Please check and resolve the issue.\n"
        ),
    )
    email_status = "failure_accepted_by_smtp" if sent else f"failure_failed:{reason}"
    db.update_email_status(report_id, sent=sent, status=email_status)
    final_state = db.get_live_track(report_id)
    return {
        "report_id": report_id,
        "status": "failed",
        "attempts": max_retries,
        "email_recipient": recipient,
        "email_sent": sent,
        "email_status": email_status,
        "last_error_code": final_state["last_error_code"] if final_state else None,
    }
