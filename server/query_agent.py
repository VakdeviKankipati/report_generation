"""Query Agent logic for loan/LAN lookup and diagnostics."""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

from .database import FAILURE_NOTIFICATION_EMAIL, ReportTrackingDB


def get_loan_details(db: ReportTrackingDB, loan_number: str) -> Dict[str, object]:
    """Lookup loan/LAN details for a given loan number."""
    row = db.find_customer_lan_by_lan_code(loan_number)
    if row is None:
        return {
            "agent": "query_agent",
            "found": False,
            "loan_number": loan_number,
            "reason": "loan_not_found_in_database",
            "notify_email": FAILURE_NOTIFICATION_EMAIL,
        }

    return {
        "agent": "query_agent",
        "found": True,
        "loan_number": loan_number,
        "customer_id": row["customer_id"],
        "customer_code": row["customer_code"],
        "customer_name": row["customer_name"],
        "customer_email": row["customer_email"],
        "allow_report_delivery": int(row["allow_report_delivery"]) == 1,
        "lan_id": row["lan_id"],
        "lan_code": row["lan_code"],
        "account_name": row["account_name"],
        "region": row["region"],
        "metric_revenue_musd": row["metric_revenue_musd"],
        "metric_incidents": row["metric_incidents"],
        "metric_uptime_pct": row["metric_uptime_pct"],
        "should_fail_permanently": int(row["should_fail_permanently"]) == 1,
    }


def _tool_loan_lookup(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    lan_match = re.search(r"\bLAN-\d{3}\b", text, flags=re.IGNORECASE)
    numeric_loan_match = re.search(r"\bloan\s*(\d{1,3})\b", lowered)
    loan_number = ""
    if lan_match:
        loan_number = lan_match.group(0).upper()
    elif numeric_loan_match:
        loan_number = f"LAN-{int(numeric_loan_match.group(1)):03d}"
    details = get_loan_details(db, loan_number)
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "loan_lookup",
        "selected_tool": "get_loan_details",
        "answer": details,
    }


def _tool_loan_details_list(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    pairs = db.get_customer_lan_pairs()
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "loan_details_list",
        "selected_tool": "get_customer_lan_pairs",
        "answer": {
            "count": len(pairs),
            "loans": [
                {
                    "loan_number": p["lan_code"],
                    "account_name": p["account_name"],
                    "customer_code": p["customer_code"],
                    "customer_name": p["customer_name"],
                    "customer_email": p["customer_email"],
                    "region": p["region"],
                    "revenue_musd": p["metric_revenue_musd"],
                    "incidents": p["metric_incidents"],
                    "uptime_pct": p["metric_uptime_pct"],
                    "should_fail_permanently": int(p["should_fail_permanently"]) == 1,
                }
                for p in pairs
            ],
        },
    }


def _tool_loan_numbers_list(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    pairs = db.get_customer_lan_pairs()
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "loan_list",
        "selected_tool": "get_customer_lan_pairs",
        "answer": {
            "count": len(pairs),
            "loan_numbers": [str(p["lan_code"]) for p in pairs],
        },
    }


def _tool_customer_list(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    pairs = db.get_customer_lan_pairs()
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "customer_list",
        "selected_tool": "get_customer_lan_pairs",
        "answer": {
            "count": len(pairs),
            "customers": [
                {
                    "customer_code": p["customer_code"],
                    "customer_name": p["customer_name"],
                    "customer_email": p["customer_email"],
                    "loan_number": p["lan_code"],
                }
                for p in pairs
            ],
        },
    }


def _tool_failure_summary(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    tracks = db.list_live_tracks()
    failed = [t for t in tracks if str(t.get("status")) == "failed"]
    last_three = failed[:3]
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "failure_summary",
        "selected_tool": "list_live_tracks",
        "answer": {
            "failed_count": len(failed),
            "examples": [
                {
                    "report_id": row.get("report_id"),
                    "lan_code": row.get("lan_code"),
                    "error": row.get("last_error_code"),
                    "email_status": row.get("email_status"),
                }
                for row in last_three
            ],
        },
    }


def _tool_run_summary(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "run_summary",
        "selected_tool": "summarize_tracks",
        "answer": db.summarize_tracks(),
    }


def _tool_help(db: ReportTrackingDB, text: str, lowered: str) -> Dict[str, object]:
    return {
        "agent": "query_agent",
        "query_text": text,
        "intent": "help",
        "selected_tool": "help",
        "answer": {
            "message": (
                "I can help with loan lookup, run status, loan/customer lists, and failure diagnostics. "
                "Ask naturally and I will choose the right tool."
            ),
            "notify_email": FAILURE_NOTIFICATION_EMAIL,
        },
    }


def _score_tool(lowered: str, keywords: List[str]) -> int:
    return sum(1 for k in keywords if k in lowered)


def answer_query(db: ReportTrackingDB, query_text: str) -> Dict[str, object]:
    """Answer free-text queries using a lightweight tool router.

    The router picks the most relevant function based on extracted entities
    (LAN/loan IDs) and keyword scoring over tool descriptions.
    """
    text = query_text.strip()
    lowered = text.lower()
    if not text:
        return _tool_help(db, text, lowered)

    # Strong entity-first routing for direct ID lookups.
    if re.search(r"\bLAN-\d{3}\b", text, flags=re.IGNORECASE) or re.search(r"\bloan\s*\d{1,3}\b", lowered):
        return _tool_loan_lookup(db, text, lowered)

    ToolFn = Callable[[ReportTrackingDB, str, str], Dict[str, object]]
    tool_specs: List[Tuple[str, List[str], ToolFn]] = [
        (
            "loan_details_list",
            ["loan", "detail", "all", "every", "complete", "full"],
            _tool_loan_details_list,
        ),
        (
            "loan_list",
            ["loan", "number", "list", "all loans", "loan ids"],
            _tool_loan_numbers_list,
        ),
        (
            "customer_list",
            ["customer", "email", "list", "associate", "who"],
            _tool_customer_list,
        ),
        (
            "failure_summary",
            ["fail", "failed", "failure", "error", "issue", "problem", "why"],
            _tool_failure_summary,
        ),
        (
            "run_summary",
            ["status", "summary", "how many", "count", "success", "processed"],
            _tool_run_summary,
        ),
    ]

    best_score = 0
    best_handler: ToolFn | None = None
    for _, keywords, handler in tool_specs:
        score = _score_tool(lowered, keywords)
        if score > best_score:
            best_score = score
            best_handler = handler

    if best_handler is None or best_score == 0:
        return _tool_help(db, text, lowered)
    return best_handler(db, text, lowered)
