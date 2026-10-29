"""Breakdowns service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet

from src.breakdowns import (
    ACTION_BREAKDOWN_VALUES,
    ATTRIBUTION_WINDOWS,
    BREAKDOWN_VALUES,
    DATE_PRESETS,
    DEFAULT_METRICS,
)
from src.config import resolve_ad_account_id
from src.core.services import Services
from src.helpers import to_dict


class BreakdownsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _validate(self, preset: str, metrics: str, breakdown: str) -> tuple:
        if preset not in DATE_PRESETS:
            raise ValueError(f"date_preset غير صالح. اختر من: {', '.join(DATE_PRESETS)}")
        breakdown_list = [b.strip() for b in breakdown.split(",") if b.strip()]
        for b in breakdown_list:
            if b not in BREAKDOWN_VALUES:
                raise ValueError(f"breakdown غير صالح: {b}. الاختيارات: {', '.join(BREAKDOWN_VALUES)}")
        return [m.strip() for m in metrics.split(",") if m.strip()], breakdown_list

    def _build_params(self, preset, fields, breakdown_list, time_increment, attribution, action_breakdowns):
        params = {"date_preset": preset, "fields": fields, "breakdowns": ",".join(breakdown_list)}
        if time_increment > 0:
            params["time_increment"] = time_increment
        if attribution:
            windows = [w.strip() for w in attribution.split(",") if w.strip()]
            for w in windows:
                if w not in ATTRIBUTION_WINDOWS:
                    raise ValueError(f"action_attribution_windows غير صالح: {w}. الاختيارات: {', '.join(ATTRIBUTION_WINDOWS)}")
            params["action_attribution_windows"] = windows
        if action_breakdowns:
            items = [a.strip() for a in action_breakdowns.split(",") if a.strip()]
            for a in items:
                if a not in ACTION_BREAKDOWN_VALUES:
                    raise ValueError(f"action_breakdowns غير صالح: {a}. الاختيارات: {', '.join(ACTION_BREAKDOWN_VALUES)}")
            params["action_breakdowns"] = items
        return params

    def get_account_breakdown(self, breakdown: str = "age,gender", date_preset: str = "last_30d",
                              metrics: str = ",".join(DEFAULT_METRICS), time_increment: int = 0,
                              action_attribution_windows: str = "",
                              action_breakdowns: str = "", ad_account_id: str = "") -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(date_preset, fields, bl, time_increment,
                                    action_attribution_windows, action_breakdowns)
        account = AdAccount(resolve_ad_account_id(ad_account_id))
        insights = account.get_insights(params=params)
        return [to_dict(i) for i in insights]

    def get_campaign_breakdown(self, campaign_id: str, breakdown: str = "age,gender",
                               date_preset: str = "last_30d", metrics: str = ",".join(DEFAULT_METRICS),
                               time_increment: int = 0, action_attribution_windows: str = "",
                               action_breakdowns: str = "") -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns)
        insights = AdAccount(campaign_id).get_insights(params=params)
        return [to_dict(i) for i in insights]

    def get_adset_breakdown(self, adset_id: str, breakdown: str = "age,gender",
                            date_preset: str = "last_30d", metrics: str = ",".join(DEFAULT_METRICS),
                            time_increment: int = 0, action_attribution_windows: str = "",
                            action_breakdowns: str = "") -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns)
        insights = AdSet(adset_id).get_insights(params=params)
        return [to_dict(i) for i in insights]

    def get_ad_breakdown(self, ad_id: str, breakdown: str = "age,gender",
                         date_preset: str = "last_30d", metrics: str = ",".join(DEFAULT_METRICS),
                         time_increment: int = 0, action_attribution_windows: str = "",
                         action_breakdowns: str = "") -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns)
        insights = Ad(ad_id).get_insights(params=params)
        return [to_dict(i) for i in insights]
