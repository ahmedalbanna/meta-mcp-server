"""Analytics service — business logic extracted from tools (Phase B)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from src.analytics import ADDITIVE_METRICS
from src.core.services import Services


class AnalyticsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api
        self.storage = services.storage

    def ingest_daily(self, account_id: str, level: str, entity_id: str, metric_date: str,
                     metrics: str) -> dict[str, Any]:
        acct = self.config.resolve_ad_account_id(account_id) if account_id else self.config.fb_ad_account_id
        if not acct:
            raise ValueError("no ad account id")
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        if not metric_date:
            tz = self.config.tz
            metric_date = (datetime.now(tz).date() - timedelta(days=1)).isoformat()

        params = {
            "time_range": {"since": metric_date, "until": metric_date},
            "fields": ",".join(metric_list),
            "level": level if level != "account" else "account",
        }
        data = self.api.get(f"{acct}/insights", params)
        rows = data.get("data") or [] if isinstance(data, dict) else []
        if not rows:
            for m in metric_list:
                if m in ADDITIVE_METRICS:
                    self.storage.upsert_daily_fact(acct, level, entity_id or acct, metric_date, m, 0.0,
                                                   currency=self.config.currency_default, tz=self.config.tz_name)
            return {"ingested": 0, "date": metric_date, "note": "no insights returned; zero-filled additive metrics"}

        row = rows[0]
        ent = entity_id or row.get("account_id") or acct
        for m in metric_list:
            if m in row and row.get(m) is not None:
                try:
                    val = float(row[m])
                except (TypeError, ValueError):
                    continue
                self.storage.upsert_daily_fact(acct, level, ent, metric_date, m, val,
                                               currency=row.get("account_currency") or self.config.currency_default,
                                               tz=self.config.tz_name)
        return {"ingested": len(metric_list), "date": metric_date, "entity": ent, "level": level}

    def build_monthly(self, year: int, month: int, account_id: str, level: str, entity_id: str,
                      metrics: str) -> dict[str, Any]:
        acct = self.config.resolve_ad_account_id(account_id) if account_id else self.config.fb_ad_account_id
        if not acct:
            raise ValueError("no ad account id")
        if month < 1 or month > 12:
            raise ValueError("month must be 1-12")
        first = date(year, month, 1)
        last = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        start = first.isoformat()
        end = last.isoformat()

        if entity_id:
            facts = self.storage.query_daily_facts(acct, level, entity_id, start, end)
        else:
            facts = self.storage.query_daily_facts_all_entities(acct, level, start, end) if hasattr(self.storage, "query_daily_facts_all_entities") else self.storage.query_daily_facts(acct, level, entity_id or acct, start, end)

        from collections import defaultdict
        by_entity: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        currencies: set[str] = set()
        for f in facts:
            by_entity[f["entity_id"]][f["metric"]] += float(f["value"])
            if f.get("currency"):
                currencies.add(f["currency"])

        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        results = []
        for ent, mvals in by_entity.items():
            row: dict[str, Any] = {"entity_id": ent}
            for m in metric_list:
                row[m] = round(mvals.get(m, 0.0), 4)
            if "ctr" in metric_list and mvals.get("impressions"):
                row["ctr"] = round(mvals.get("clicks", 0.0) / mvals["impressions"] * 100, 4)
            if "cpc" in metric_list and mvals.get("clicks"):
                row["cpc"] = round(mvals.get("spend", 0.0) / mvals["clicks"], 4)
            if "cpm" in metric_list and mvals.get("impressions"):
                row["cpm"] = round(mvals.get("spend", 0.0) / mvals["impressions"] * 1000, 4)
            results.append(row)
            for m in metric_list:
                self.storage.upsert_monthly_snapshot(acct, level, ent, year, month, m,
                                                     float(row.get(m, 0.0)),
                                                     currency=next(iter(currencies)) if len(currencies) == 1 else None)

        out: dict[str, Any] = {
            "year": year, "month": month, "account_id": acct, "level": level,
            "entities": results, "count": len(results),
        }
        if len(currencies) > 1:
            out["warning"] = "mixed_currency"
            out["currencies"] = sorted(currencies)
        if not facts:
            out["note"] = "no daily_facts for this month; run ingest first"
        return out
