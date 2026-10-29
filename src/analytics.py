"""Analytics pipeline: timezone normalization, daily facts ingestion, monthly rollups.

Phase 1 of the analytics roadmap. Stores facts in SQLite (src.persistence) so
daily/monthly reports become reproducible and backfillable.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.config import (
    AD_ACCOUNT_ID,
    ANALYTICS_TZ,
    FB_CURRENCY_DEFAULT,
    resolve_ad_account_id,
)
from src.helpers import handle_error, json_dumps, to_dict
from src.persistence import (
    init_db,
    query_daily_facts,
    upsert_daily_fact,
)
from src.throttle import concurrency_limit

logger = logging.getLogger(__name__)

ADDITIVE_METRICS = {"spend", "impressions", "clicks", "reach", "frequency"}
NON_ADDITIVE = {"ctr", "cpc", "cpm"}  # derived; recompute from additive


def _tz(name: str | None = None) -> ZoneInfo:
    return ZoneInfo(name or ANALYTICS_TZ)


def normalize_date_range(preset: str, tz_name: str | None = None) -> tuple[str, str]:
    """Convert a date_preset into (start_iso, end_iso) in the given tz."""
    tz = _tz(tz_name)
    now = datetime.now(tz)
    today = now.date()
    presets = {
        "today": (today, today),
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "last_3d": (today - timedelta(days=3), today - timedelta(days=1)),
        "last_7d": (today - timedelta(days=7), today - timedelta(days=1)),
        "last_14d": (today - timedelta(days=14), today - timedelta(days=1)),
        "last_28d": (today - timedelta(days=28), today - timedelta(days=1)),
        "last_30d": (today - timedelta(days=30), today - timedelta(days=1)),
        "last_90d": (today - timedelta(days=90), today - timedelta(days=1)),
        "this_month": (today.replace(day=1), today),
        "last_month": None,
        "this_quarter": None,
        "this_year": (today.replace(month=1, day=1), today),
        "lifetime": (date(2000, 1, 1), today),
    }
    if preset == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.isoformat(), last_prev.isoformat()
    if preset not in presets:
        raise ValueError(f"unknown date_preset: {preset}")
    r = presets[preset]
    if r is None:
        raise ValueError(f"preset not implemented: {preset}")
    s, e = r
    return s.isoformat(), e.isoformat()


def zero_fill_daily(series: dict[str, float], start: date, end: date) -> list[dict[str, Any]]:
    """Return one row per day in [start,end], filling missing with 0."""
    out = []
    cur = start
    while cur <= end:
        out.append({"date": cur.isoformat(), "value": float(series.get(cur.isoformat(), 0.0))})
        cur += timedelta(days=1)
    return out


def _date_range(start: str, end: str) -> list[str]:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    out = []
    cur = s
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def register(mcp, services=None):
    """Register analytics tools."""
    if services is None:
        from src.core.services import Services
        services = Services.default()
    init_db()

    from facebook_business.adobjects.adaccount import AdAccount


    @mcp.tool()
    @concurrency_limit()
    def ingest_daily_facts(
        account_id: str = "",
        level: str = "account",
        entity_id: str = "",
        metric_date: str = "",
        metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,reach",
    ) -> str:
        """Ingest one day of insights into SQLite for a given entity.

        metric_date: YYYY-MM-DD (in FB_TZ). Empty -> yesterday.
        level: account|campaign|adset|ad
        """
        try:
            from src.core.services import Services
            from src.services.analytics_service import AnalyticsService
            svc = AnalyticsService(services) if services is not None else AnalyticsService(Services.default())
            result = svc.ingest_daily(account_id, level, entity_id, metric_date, metrics)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e))

    @mcp.tool()
    @concurrency_limit()
    def ingest_daily_facts_range(
        account_id: str = "",
        level: str = "account",
        entity_id: str = "",
        start_date: str = "",
        end_date: str = "",
        metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,reach",
    ) -> str:
        """Ingest a range of days (YYYY-MM-DD) into SQLite."""
        try:
            acct = resolve_ad_account_id(account_id) if account_id else AD_ACCOUNT_ID
            if not acct:
                return json_dumps({"error": "no ad account id"})
            if not start_date or not end_date:
                return json_dumps({"error": "start_date and end_date required (YYYY-MM-DD)"})
            metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
            acc = AdAccount(acct)
            params = {
                "time_range": {"since": start_date, "until": end_date},
                "fields": metric_list,
                "level": level if level != "account" else "account",
                "time_increment": 1,
            }
            insights = acc.get_insights(params=params)
            rows = [to_dict(i) for i in insights]
            # index by date
            by_date = {r.get("date_start"): r for r in rows if r.get("date_start")}
            ingested_days = 0
            for d in _date_range(start_date, end_date):
                row = by_date.get(d)
                ent = entity_id or (row.get("account_id") if row else None) or acct
                if row:
                    for m in metric_list:
                        if m in row and row.get(m) is not None:
                            try:
                                val = float(row[m])
                            except (TypeError, ValueError):
                                continue
                            upsert_daily_fact(acct, level, ent, d, m, val,
                                              currency=row.get("account_currency") or FB_CURRENCY_DEFAULT,
                                              tz=ANALYTICS_TZ)
                    ingested_days += 1
                else:
                    for m in metric_list:
                        if m in ADDITIVE_METRICS:
                            upsert_daily_fact(acct, level, ent, d, m, 0.0,
                                              currency=FB_CURRENCY_DEFAULT, tz=ANALYTICS_TZ)
                    ingested_days += 1
            return json_dumps({"ingested_days": ingested_days, "start": start_date, "end": end_date, "level": level})
        except Exception as e:
            return json_dumps(handle_error(e))

    @mcp.tool()
    @concurrency_limit()
    def build_monthly_report(
        year: int,
        month: int,
        account_id: str = "",
        level: str = "account",
        entity_id: str = "",
        metrics: str = "spend,impressions,clicks,reach",
    ) -> str:
        """Build a monthly snapshot from daily_facts (additive sum; reach approximated)."""
        try:
            from src.core.services import Services
            from src.services.analytics_service import AnalyticsService
            svc = AnalyticsService(services) if services is not None else AnalyticsService(Services.default())
            result = svc.build_monthly(year, month, account_id, level, entity_id, metrics)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e))

    @mcp.tool()
    @concurrency_limit()
    def zero_fill_check(
        account_id: str = "",
        level: str = "account",
        entity_id: str = "",
        start_date: str = "",
        end_date: str = "",
        metric: str = "spend",
    ) -> str:
        """Return daily series with zero-fill for a metric over a date range."""
        try:
            acct = resolve_ad_account_id(account_id) if account_id else AD_ACCOUNT_ID
            if not acct:
                return json_dumps({"error": "no ad account id"})
            if not start_date or not end_date:
                return json_dumps({"error": "start_date and end_date required"})
            ent = entity_id or acct
            facts = query_daily_facts(acct, level, ent, start_date, end_date, metric=metric)
            series = {f["metric_date"]: f["value"] for f in facts}
            s = date.fromisoformat(start_date)
            e = date.fromisoformat(end_date)
            filled = zero_fill_daily(series, s, e)
            return json_dumps({"account_id": acct, "level": level, "entity_id": ent, "metric": metric,
                               "days": len(filled), "data": filled})
        except Exception as e:
            return json_dumps(handle_error(e))

    @mcp.tool()
    @concurrency_limit()
    def backfill_daily(
        account_id: str = "",
        level: str = "account",
        entity_id: str = "",
        start_date: str = "",
        end_date: str = "",
        metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,reach",
    ) -> str:
        """Backfill a date range (delegates to ingest_daily_facts_range)."""
        result = ingest_daily_facts_range(account_id, level, entity_id, start_date, end_date, metrics)
        return result  # type: ignore[no-any-return]

    @mcp.tool()
    @concurrency_limit()
    def prune_analytics(retention_days: int = 0) -> str:
        """Prune daily_facts older than retention_days (default from config)."""
        try:
            from src.persistence import prune_old_facts

            days = retention_days or 1110
            n = prune_old_facts(days)
            return json_dumps({"deleted_rows": n, "retention_days": days})
        except Exception as e:
            return json_dumps(handle_error(e))

    @mcp.tool()
    def analytics_db_status() -> str:
        """Report analytics DB path, counts, schema version."""
        try:
            from src.persistence import _db_path, get_conn

            conn = get_conn()
            counts = {}
            for t in ("daily_facts", "monthly_snapshots", "competitor_snapshots"):
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            ver = conn.execute("SELECT version FROM schema_version").fetchone()[0]
            return json_dumps({"db_path": str(_db_path()), "schema_version": ver, "counts": counts,
                               "tz": ANALYTICS_TZ})
        except Exception as e:
            return json_dumps(handle_error(e))
