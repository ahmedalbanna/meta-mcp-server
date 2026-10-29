"""Insights service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services


class InsightsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def get_account_insights(self, account_id: str = "", date_preset: str = "last_7d",
                             metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,actions,reach",
                             level: str = "account") -> Any:
        from src.config import resolve_ad_account_id
        acct = resolve_ad_account_id(account_id) if account_id else self.config.fb_ad_account_id
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        data = self.api.get(f"{acct}/insights", {
            "date_preset": date_preset,
            "fields": ",".join(metric_list),
            "level": level if level != "account" else "account",
        })
        return data.get("data", []) if isinstance(data, dict) else data

    def get_campaign_insights(self, campaign_id: str, date_preset: str = "last_7d",
                              metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,actions,reach") -> Any:
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        data = self.api.get(f"{campaign_id}/insights", {
            "date_preset": date_preset,
            "fields": ",".join(metric_list),
        })
        return data.get("data", []) if isinstance(data, dict) else data

    def get_adset_insights(self, adset_id: str, date_preset: str = "last_30d",
                           metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,actions,reach") -> Any:
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        data = self.api.get(f"{adset_id}/insights", {
            "date_preset": date_preset,
            "fields": ",".join(metric_list),
        })
        return data.get("data", []) if isinstance(data, dict) else data

    def get_ad_insights(self, ad_id: str, date_preset: str = "last_30d",
                        metrics: str = "spend,impressions,clicks,ctr,cpc,cpm,actions,reach") -> Any:
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        data = self.api.get(f"{ad_id}/insights", {
            "date_preset": date_preset,
            "fields": ",".join(metric_list),
        })
        return data.get("data", []) if isinstance(data, dict) else data
