"""SQLite persistence for analytics facts and competitor snapshots.

Central store for daily/monthly analytics (Phase 0) so reports are reproducible
across runs instead of being overwritten in CSV/Excel files. Uses WAL mode for
safe concurrent access from multiple MCP processes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import ANALYTICS_DB_URL, ANALYTICS_RETENTION_DAYS, ANALYTICS_TZ, ensure_report_dir

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS daily_facts (
  account_id TEXT NOT NULL,
  level TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  metric_date TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  currency TEXT,
  tz TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  PRIMARY KEY (account_id, level, entity_id, metric_date, metric)
);
CREATE INDEX IF NOT EXISTS idx_daily_facts_date ON daily_facts(metric_date);
CREATE INDEX IF NOT EXISTS idx_daily_facts_entity ON daily_facts(account_id, level, entity_id);
CREATE TABLE IF NOT EXISTS monthly_snapshots (
  account_id TEXT NOT NULL,
  level TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  currency TEXT,
  computed_at TEXT NOT NULL,
  PRIMARY KEY (account_id, level, entity_id, year, month, metric)
);
CREATE TABLE IF NOT EXISTS competitor_snapshots (
  platform TEXT NOT NULL,
  handle TEXT NOT NULL,
  snapshot_date TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  PRIMARY KEY (platform, handle, snapshot_date)
);
"""

_local = threading.local()


def _db_path() -> Path:
    # Parse sqlite:///path or sqlite:////abs/path
    url = ANALYTICS_DB_URL
    if url.startswith("sqlite:///"):
        rest = url[len("sqlite:///"):]
    elif url.startswith("sqlite://"):
        rest = url[len("sqlite://"):]
    else:
        rest = url
    # On Windows, a leading slash before drive letter (e.g. /R:/...) is invalid.
    if len(rest) >= 3 and rest[0] == "/" and rest[2] == ":":
        rest = rest[1:]
    p = Path(rest)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def init_db() -> None:
    """Create schema (idempotent). Safe to call repeatedly."""
    ensure_report_dir()
    conn = sqlite3.connect(str(_db_path()))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.executescript(_SCHEMA)
        cur = conn.execute("SELECT COUNT(*) FROM schema_version")
        if cur.fetchone()[0] == 0:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()
    finally:
        conn.close()


def get_conn() -> sqlite3.Connection:
    """Thread-local connection with WAL + busy_timeout."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(_db_path()), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        _local.conn = conn
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_daily_fact(
    account_id: str,
    level: str,
    entity_id: str,
    metric_date: str,
    metric: str,
    value: float,
    currency: str | None = None,
    tz: str = ANALYTICS_TZ,
) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO daily_facts (account_id, level, entity_id, metric_date, metric, value, currency, tz, captured_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (account_id, level, entity_id, metric_date, metric) DO UPDATE SET
             value=excluded.value, currency=excluded.currency, tz=excluded.tz, captured_at=excluded.captured_at""",
        (account_id, level, entity_id, metric_date, metric, float(value), currency, tz, _now()),
    )
    conn.commit()


def query_daily_facts(
    account_id: str,
    level: str,
    entity_id: str,
    start_date: str,
    end_date: str,
    metric: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_conn()
    sql = """SELECT * FROM daily_facts
             WHERE account_id=? AND level=? AND entity_id=? AND metric_date>=? AND metric_date<=?"""
    params: list[Any] = [account_id, level, entity_id, start_date, end_date]
    if metric:
        sql += " AND metric=?"
        params.append(metric)
    sql += " ORDER BY metric_date, metric"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_daily_facts_all_entities(
    account_id: str,
    level: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    conn = get_conn()
    sql = """SELECT * FROM daily_facts
             WHERE account_id=? AND level=? AND metric_date>=? AND metric_date<=?
             ORDER BY entity_id, metric_date, metric"""
    rows = conn.execute(sql, [account_id, level, start_date, end_date]).fetchall()
    return [dict(r) for r in rows]


def upsert_monthly_snapshot(
    account_id: str,
    level: str,
    entity_id: str,
    year: int,
    month: int,
    metric: str,
    value: float,
    currency: str | None = None,
) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO monthly_snapshots (account_id, level, entity_id, year, month, metric, value, currency, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (account_id, level, entity_id, year, month, metric) DO UPDATE SET
             value=excluded.value, currency=excluded.currency, computed_at=excluded.computed_at""",
        (account_id, level, entity_id, year, month, metric, float(value), currency, _now()),
    )
    conn.commit()


def query_monthly_snapshots(
    account_id: str,
    level: str,
    entity_id: str,
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM monthly_snapshots
           WHERE account_id=? AND level=? AND entity_id=? AND year=? AND month=?""",
        (account_id, level, entity_id, year, month),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_competitor_snapshot(platform: str, handle: str, snapshot_date: str, payload: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO competitor_snapshots (platform, handle, snapshot_date, payload_json, captured_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (platform, handle, snapshot_date) DO UPDATE SET
             payload_json=excluded.payload_json, captured_at=excluded.captured_at""",
        (platform, handle, snapshot_date, json.dumps(payload, ensure_ascii=False), _now()),
    )
    conn.commit()


def query_competitor_snapshots(platform: str, handle: str, limit: int = 30) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM competitor_snapshots WHERE platform=? AND handle=?
           ORDER BY snapshot_date DESC LIMIT ?""",
        (platform, handle, limit),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload_json"])
        except Exception:
            d["payload"] = None
        out.append(d)
    return out


def prune_old_facts(days: int = ANALYTICS_RETENTION_DAYS) -> int:
    from datetime import timedelta

    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    conn = get_conn()
    cur = conn.execute("DELETE FROM daily_facts WHERE metric_date < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


def close() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None

