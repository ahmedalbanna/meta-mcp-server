"""Tests for src.persistence (SQLite analytics store)."""

import pytest

from src import persistence as p
from src.core import config as cfg


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "test.db"
    monkeypatch.setenv("FB_ANALYTICS_DB_URL", f"sqlite:///{db}")
    # reload module-level constants by re-importing persistence fresh
    import importlib

    importlib.reload(cfg)
    importlib.reload(p)
    p.init_db()
    yield db
    p.close()


def test_init_idempotent(tmp_db):
    p.init_db()
    p.init_db()
    conn = p.get_conn()
    ver = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert ver == p.SCHEMA_VERSION


def test_upsert_idempotent(tmp_db):
    p.upsert_daily_fact("act_1", "account", "act_1", "2026-10-01", "spend", 5.0, currency="YER")
    p.upsert_daily_fact("act_1", "account", "act_1", "2026-10-01", "spend", 7.0, currency="YER")
    rows = p.query_daily_facts("act_1", "account", "act_1", "2026-10-01", "2026-10-01", metric="spend")
    assert len(rows) == 1
    assert rows[0]["value"] == 7.0


def test_query_range(tmp_db):
    for d in ("2026-10-01", "2026-10-02", "2026-10-03"):
        p.upsert_daily_fact("act_1", "account", "act_1", d, "spend", 1.0)
    rows = p.query_daily_facts("act_1", "account", "act_1", "2026-10-01", "2026-10-02", metric="spend")
    assert len(rows) == 2


def test_monthly_snapshot_roundtrip(tmp_db):
    p.upsert_monthly_snapshot("act_1", "account", "act_1", 2026, 10, "spend", 100.0, currency="YER")
    rows = p.query_monthly_snapshots("act_1", "account", "act_1", 2026, 10)
    assert len(rows) == 1
    assert rows[0]["value"] == 100.0


def test_competitor_snapshot_roundtrip(tmp_db):
    p.upsert_competitor_snapshot("instagram", "handle1", "2026-10-01", {"foo": 1})
    rows = p.query_competitor_snapshots("instagram", "handle1", limit=5)
    assert len(rows) == 1
    assert rows[0]["payload"]["foo"] == 1


def test_prune(tmp_db):
    p.upsert_daily_fact("act_1", "account", "act_1", "2020-01-01", "spend", 1.0)
    p.upsert_daily_fact("act_1", "account", "act_1", "2026-10-01", "spend", 1.0)
    deleted = p.prune_old_facts(30)
    assert deleted >= 1
    rows = p.query_daily_facts("act_1", "account", "act_1", "2019-01-01", "2026-12-31", metric="spend")
    assert len(rows) == 1
    assert rows[0]["metric_date"] == "2026-10-01"


def test_wal_mode(tmp_db):
    conn = p.get_conn()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
