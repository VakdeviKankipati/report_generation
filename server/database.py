"""SQLite persistence for customer/lan mapping and live report tracking."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional

FAILURE_NOTIFICATION_EMAIL = "vakdevikankipati@gmail.com"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReportTrackingDB:
    """SQLite adapter for report orchestration demo/training flows."""

    def __init__(self, db_path: str = "report_tracking.db") -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    timezone_name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            customer_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(customers)").fetchall()
            }
            if "allow_report_delivery" not in customer_cols:
                conn.execute(
                    "ALTER TABLE customers ADD COLUMN allow_report_delivery INTEGER NOT NULL DEFAULT 1"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lan_code TEXT NOT NULL UNIQUE,
                    account_name TEXT NOT NULL,
                    region TEXT NOT NULL,
                    report_timezone_name TEXT NOT NULL,
                    metric_revenue_musd REAL NOT NULL,
                    metric_incidents INTEGER NOT NULL,
                    metric_uptime_pct REAL NOT NULL,
                    should_fail_permanently INTEGER NOT NULL DEFAULT 0,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_lan_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    lan_id INTEGER NOT NULL,
                    mapping_active INTEGER NOT NULL DEFAULT 1,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    UNIQUE(customer_id, lan_id),
                    FOREIGN KEY(customer_id) REFERENCES customers(id),
                    FOREIGN KEY(lan_id) REFERENCES lans(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_report_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT NOT NULL UNIQUE,
                    batch_id TEXT NOT NULL,
                    customer_id INTEGER NOT NULL,
                    lan_id INTEGER NOT NULL,
                    report_type TEXT NOT NULL,
                    report_format TEXT NOT NULL,
                    scheduler_slot TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retries_used INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 5,
                    last_error_code TEXT,
                    last_error_message TEXT,
                    report_generated INTEGER NOT NULL DEFAULT 0,
                    email_sent INTEGER NOT NULL DEFAULT 0,
                    email_status TEXT NOT NULL DEFAULT 'not_sent',
                    started_at_utc TEXT NOT NULL,
                    finished_at_utc TEXT,
                    updated_at_utc TEXT NOT NULL,
                    FOREIGN KEY(customer_id) REFERENCES customers(id),
                    FOREIGN KEY(lan_id) REFERENCES lans(id)
                )
                """
            )
            live_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(live_report_tracking)").fetchall()
            }
            if "batch_id" not in live_cols:
                conn.execute("ALTER TABLE live_report_tracking ADD COLUMN batch_id TEXT")
                conn.execute("UPDATE live_report_tracking SET batch_id = 'legacy' WHERE batch_id IS NULL")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_customer_code ON customers(customer_code)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lans_lan_code ON lans(lan_code)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_map_customer_id ON customer_lan_map(customer_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_map_lan_id ON customer_lan_map(lan_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_live_report_id ON live_report_tracking(report_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_live_batch_id ON live_report_tracking(batch_id)"
            )

    def seed_static_data(self) -> None:
        """Seed 5 customers + 5 LANs + 1:1 mapping with requested emails.

        Do not overwrite manual DB edits once records already exist.
        """
        now = utc_now_iso()
        seed_customers = [
            ("CUST-001", "Customer 1", "vakdevikankipati@gmail.com", "Asia/Kolkata", 1),
            ("CUST-002", "Customer 2", "vakya85@gmail.com", "Asia/Kolkata", 1),
            ("CUST-003", "Customer 3", "vakya2605@gmail.com", "Europe/Berlin", 1),
            ("CUST-004", "Customer 4", "jatangithanuja@gmail.com", "Europe/Berlin", 1),
            # Wrong customer email: keep mapped for test scenario, but block report delivery.
            ("CUST-005", "Customer 5", "a@x.com", "Asia/Kolkata", 0),
        ]
        seed_lans = [
            ("LAN-001", "Home Loan - Bangalore", "APAC", "Asia/Kolkata", 11.0, 1, 99.53, 0),
            ("LAN-002", "Car Loan - Hyderabad", "APAC", "Asia/Kolkata", 12.0, 0, 99.56, 0),
            ("LAN-003", "Personal Loan - Chennai", "APAC", "Europe/Berlin", 13.0, 1, 99.59, 0),
            ("LAN-004", "Gold Loan - Berlin", "EU", "Europe/Berlin", 14.0, 0, 99.62, 0),
            ("LAN-005", "Education Loan - Munich", "EU", "Asia/Kolkata", 15.0, 3, 99.65, 1),
        ]
        with self._connect() as conn:
            customer_count = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
            lan_count = conn.execute("SELECT COUNT(*) AS c FROM lans").fetchone()["c"]
            map_count = conn.execute("SELECT COUNT(*) AS c FROM customer_lan_map").fetchone()["c"]
            if customer_count >= 5 and lan_count >= 5 and map_count >= 5:
                return

            for i, row in enumerate(seed_customers, start=1):
                customer_code, name, email, tz_name, allow_delivery = row
                lan_code = f"LAN-{i:03d}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO customers
                    (customer_code, name, email, timezone_name, is_active, allow_report_delivery, created_at_utc, updated_at_utc)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (customer_code, name, email, tz_name, allow_delivery, now, now),
                )
                lan_row = seed_lans[i - 1]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO lans
                    (lan_code, account_name, region, report_timezone_name, metric_revenue_musd,
                     metric_incidents, metric_uptime_pct, should_fail_permanently, created_at_utc, updated_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*lan_row, now, now),
                )

            for i in range(1, 6):
                customer = conn.execute(
                    "SELECT id FROM customers WHERE customer_code = ?",
                    (f"CUST-{i:03d}",),
                ).fetchone()
                lan = conn.execute(
                    "SELECT id FROM lans WHERE lan_code = ?",
                    (f"LAN-{i:03d}",),
                ).fetchone()
                if customer and lan:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO customer_lan_map
                        (customer_id, lan_id, mapping_active, created_at_utc, updated_at_utc)
                        VALUES (?, ?, 1, ?, ?)
                        """,
                        (customer["id"], lan["id"], now, now),
                    )

    def get_report_context(self, report_id: str) -> Optional[Dict[str, object]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    t.report_id,
                    t.batch_id,
                    t.report_type,
                    t.report_format,
                    t.scheduler_slot,
                    c.customer_code,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    l.lan_code,
                    l.account_name,
                    l.region,
                    l.metric_revenue_musd,
                    l.metric_incidents,
                    l.metric_uptime_pct
                FROM live_report_tracking t
                JOIN customers c ON c.id = t.customer_id
                JOIN lans l ON l.id = t.lan_id
                WHERE t.report_id = ?
                """,
                (report_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_customer_lan_pairs(self) -> List[Dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id AS customer_id,
                    c.customer_code,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    c.timezone_name AS customer_timezone,
                    l.id AS lan_id,
                    l.lan_code,
                    l.account_name,
                    l.region,
                    l.report_timezone_name,
                    l.metric_revenue_musd,
                    l.metric_incidents,
                    l.metric_uptime_pct,
                    l.should_fail_permanently
                FROM customer_lan_map m
                JOIN customers c ON c.id = m.customer_id
                JOIN lans l ON l.id = m.lan_id
                WHERE m.mapping_active = 1 AND c.is_active = 1
                ORDER BY c.id
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def resolve_recipient_email(self, report_id: str, is_failure: bool) -> str:
        """Route failure emails to fixed address; otherwise route to mapped customer email.

        If customer email is blocked for delivery, route to fixed failure address.
        """
        if is_failure:
            return FAILURE_NOTIFICATION_EMAIL

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.email AS customer_email, c.allow_report_delivery
                FROM live_report_tracking t
                JOIN customers c ON c.id = t.customer_id
                WHERE t.report_id = ?
                """,
                (report_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown report_id: {report_id}")
            if int(row["allow_report_delivery"]) == 0:
                return FAILURE_NOTIFICATION_EMAIL
            return str(row["customer_email"])

    def create_live_track(
        self,
        report_id: str,
        batch_id: str,
        customer_id: int,
        lan_id: int,
        report_type: str,
        report_format: str,
        scheduler_slot: str,
        max_retries: int = 5,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO live_report_tracking (
                    report_id, batch_id, customer_id, lan_id, report_type, report_format, scheduler_slot,
                    status, retries_used, max_retries, report_generated, email_sent, email_status,
                    started_at_utc, finished_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'started', 0, ?, 0, 0, 'not_sent', ?, NULL, ?)
                """,
                (
                    report_id,
                    batch_id,
                    customer_id,
                    lan_id,
                    report_type,
                    report_format,
                    scheduler_slot,
                    max_retries,
                    now,
                    now,
                ),
            )

    def update_live_track_status(
        self,
        report_id: str,
        status: str,
        retries_used: int,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        report_generated: Optional[bool] = None,
        finished: bool = False,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            current = self.get_live_track(report_id)
            if current is None:
                raise ValueError(f"Unknown report_id: {report_id}")

            generated_flag = (
                int(report_generated)
                if report_generated is not None
                else int(current["report_generated"])
            )
            conn.execute(
                """
                UPDATE live_report_tracking
                SET status = ?,
                    retries_used = ?,
                    last_error_code = ?,
                    last_error_message = ?,
                    report_generated = ?,
                    finished_at_utc = ?,
                    updated_at_utc = ?
                WHERE report_id = ?
                """,
                (
                    status,
                    retries_used,
                    error_code,
                    error_message,
                    generated_flag,
                    now if finished else None,
                    now,
                    report_id,
                ),
            )

    def update_email_status(self, report_id: str, sent: bool, status: str) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE live_report_tracking
                SET email_sent = ?,
                    email_status = ?,
                    updated_at_utc = ?
                WHERE report_id = ?
                """,
                (1 if sent else 0, status, now, report_id),
            )

    def list_live_tracks(self) -> List[Dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    t.*,
                    c.customer_code,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    l.lan_code
                FROM live_report_tracking t
                JOIN customers c ON c.id = t.customer_id
                JOIN lans l ON l.id = t.lan_id
                ORDER BY t.id DESC
                """,
            ).fetchall()
            return [dict(r) for r in rows]

    def list_pending_for_midnight_delivery(self) -> List[Dict[str, object]]:
        """Return jobs created at 10am/11am but not executed yet."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT report_id, scheduler_slot, status
                FROM live_report_tracking
                WHERE scheduler_slot IN ('10am', '11am') AND status = 'started'
                ORDER BY id ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def find_customer_lan_by_lan_code(self, lan_code: str) -> Optional[Dict[str, object]]:
        """Find mapped customer + LAN details by LAN code."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    c.id AS customer_id,
                    c.customer_code,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    c.allow_report_delivery,
                    l.id AS lan_id,
                    l.lan_code,
                    l.account_name,
                    l.region,
                    l.metric_revenue_musd,
                    l.metric_incidents,
                    l.metric_uptime_pct,
                    l.should_fail_permanently
                FROM customer_lan_map m
                JOIN customers c ON c.id = m.customer_id
                JOIN lans l ON l.id = m.lan_id
                WHERE m.mapping_active = 1
                  AND c.is_active = 1
                  AND l.lan_code = ?
                LIMIT 1
                """,
                (lan_code,),
            ).fetchone()
            return dict(row) if row else None

    def list_tracks_for_batch(self, batch_id: str) -> List[Dict[str, object]]:
        """Return all report tracking rows for a specific batch."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    t.*,
                    c.customer_code,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    l.lan_code
                FROM live_report_tracking t
                JOIN customers c ON c.id = t.customer_id
                JOIN lans l ON l.id = t.lan_id
                WHERE t.batch_id = ?
                ORDER BY t.id ASC
                """,
                (batch_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def summarize_tracks(self, batch_id: Optional[str] = None) -> Dict[str, int]:
        """Summarize track statuses optionally scoped to one batch."""
        with self._connect() as conn:
            if batch_id is None:
                rows = conn.execute(
                    """
                    SELECT status, COUNT(*) AS c
                    FROM live_report_tracking
                    GROUP BY status
                    """
                ).fetchall()
                total_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM live_report_tracking"
                ).fetchone()
            else:
                rows = conn.execute(
                    """
                    SELECT status, COUNT(*) AS c
                    FROM live_report_tracking
                    WHERE batch_id = ?
                    GROUP BY status
                    """,
                    (batch_id,),
                ).fetchall()
                total_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM live_report_tracking WHERE batch_id = ?",
                    (batch_id,),
                ).fetchone()
            out: Dict[str, int] = {"total": int(total_row["c"])}
            for row in rows:
                out[str(row["status"])] = int(row["c"])
            return out

    def get_live_track(self, report_id: str) -> Optional[Dict[str, object]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM live_report_tracking WHERE report_id = ?",
                (report_id,),
            ).fetchone()
            return dict(row) if row else None

    def clear_live_tracks(self) -> int:
        """Delete all live tracking rows and return deleted count."""
        with self._connect() as conn:
            deleted = conn.execute("SELECT COUNT(*) AS c FROM live_report_tracking").fetchone()["c"]
            conn.execute("DELETE FROM live_report_tracking")
            return int(deleted)
