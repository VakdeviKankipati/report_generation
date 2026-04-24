"""PDF builders for scheduler report emails."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _statement_transactions(seed: int) -> List[List[str]]:
    base = 5000 + (seed * 100)
    d1 = base
    d2 = d1 - 1200
    d3 = d2 - 800
    d4 = d3 + 2000
    return [
        ["2026-04-01", "CREDIT", str(base), str(d1), "SALARY", "SUCCESS"],
        ["2026-04-03", "DEBIT", "1200", str(d2), "ATM-WDL", "SUCCESS"],
        ["2026-04-05", "DEBIT", "800", str(d3), "ONLINE-PAY", "SUCCESS"],
        ["2026-04-10", "CREDIT", "2000", str(d4), "REFUND", "SUCCESS"],
    ]


def build_10am_account_statement(context: Dict[str, object]) -> bytes:
    """Build account statement style PDF (similar to provided screenshot)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("<b>Account Statement</b>", styles["Title"]))
    elems.append(Spacer(1, 12))
    elems.append(Paragraph("<b>Customer Details</b>", styles["Heading2"]))

    customer_rows = [
        ["Customer Code", str(context["customer_code"])],
        ["Account Code", str(context["lan_code"])],
        ["Account Name", str(context["account_name"])],
        ["Region", str(context["region"])],
    ]
    t1 = Table(customer_rows, colWidths=[220, 310])
    t1.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ]
        )
    )
    elems.append(t1)
    elems.append(Spacer(1, 14))

    elems.append(Paragraph("<b>Transaction Details</b>", styles["Heading2"]))
    tx_seed = int(str(context["lan_code"]).split("-")[-1])
    tx_rows = [["Date", "Type", "Amount", "Balance", "Reference", "Status"]] + _statement_transactions(
        tx_seed
    )
    t2 = Table(tx_rows, colWidths=[95, 95, 95, 95, 95, 95])
    t2.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ]
        )
    )
    elems.append(t2)
    doc.build(elems)
    return buf.getvalue()


def build_11am_finance_summary(context: Dict[str, object]) -> bytes:
    """Build second report type PDF for 11am scheduler."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("<b>Midday Finance Summary</b>", styles["Title"]))
    elems.append(Spacer(1, 10))
    elems.append(
        Paragraph(
            f"Batch generated at {datetime.now(timezone.utc).isoformat()} UTC for {context['customer_code']}",
            styles["BodyText"],
        )
    )
    elems.append(Spacer(1, 12))

    summary_rows = [
        ["Field", "Value"],
        ["Customer Code", str(context["customer_code"])],
        ["Account Code", str(context["lan_code"])],
        ["Account Name", str(context["account_name"])],
        ["Region", str(context["region"])],
        ["Revenue (MUSD)", str(context["metric_revenue_musd"])],
        ["Incident Count", str(context["metric_incidents"])],
        ["Uptime (%)", str(context["metric_uptime_pct"])],
        ["Status", "Healthy" if int(context["metric_incidents"]) <= 1 else "Watchlist"],
    ]
    t = Table(summary_rows, colWidths=[220, 310])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ]
        )
    )
    elems.append(t)
    doc.build(elems)
    return buf.getvalue()

