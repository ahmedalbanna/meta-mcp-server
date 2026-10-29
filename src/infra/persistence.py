"""SQLite storage adapter implementing Storage port."""

from __future__ import annotations

from src import persistence as _p


class SqliteStorage:
    def __init__(self, db_url: str) -> None:
        self.db_url = db_url
        _p.init_db()

    def upsert_daily_fact(self, account_id, level, entity_id, metric_date, metric, value,
                          currency=None, tz="Asia/Aden"):
        _p.upsert_daily_fact(account_id, level, entity_id, metric_date, metric, value, currency, tz)

    def upsert_monthly_snapshot(self, account_id, level, entity_id, year, month, metric, value, currency=None):
        _p.upsert_monthly_snapshot(account_id, level, entity_id, year, month, metric, value, currency)

    def query_daily_facts_all_entities(self, account_id, level, start_date, end_date):
        return _p.query_daily_facts_all_entities(account_id, level, start_date, end_date)

    def query_daily_facts(self, account_id, level, entity_id, start_date, end_date, metric=None):
        return _p.query_daily_facts(account_id, level, entity_id, start_date, end_date, metric)

    def upsert_competitor_snapshot(self, platform, handle, snapshot_date, payload):
        _p.upsert_competitor_snapshot(platform, handle, snapshot_date, payload)

    def query_competitor_snapshots(self, platform, handle, limit=30):
        return _p.query_competitor_snapshots(platform, handle, limit)
