"""Breakdowns service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.breakdowns import (
    ACTION_BREAKDOWN_VALUES,
    ATTRIBUTION_WINDOWS,
    BREAKDOWN_VALUES,
    DATE_PRESETS,
    DEFAULT_METRICS,
)
from src.core.services import Services
from src.utils import to_dict


class BreakdownsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _acct(self, ad_account_id: str = "") -> str:
        return self.config.resolve_ad_account_id(ad_account_id)

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
                    raise ValueError(
                        f"action_attribution_windows غير صالح: {w}. الاختيارات: {', '.join(ATTRIBUTION_WINDOWS)}"
                    )
            params["action_attribution_windows"] = windows
        if action_breakdowns:
            items = [a.strip() for a in action_breakdowns.split(",") if a.strip()]
            for a in items:
                if a not in ACTION_BREAKDOWN_VALUES:
                    raise ValueError(
                        f"action_breakdowns غير صالح: {a}. الاختيارات: {', '.join(ACTION_BREAKDOWN_VALUES)}"
                    )
            params["action_breakdowns"] = items
        return params

    def get_account_breakdown(
        self,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
        ad_account_id: str = "",
    ) -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(
            date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns
        )
        acct = self._acct(ad_account_id)
        data = self.services.api.get(f"{acct}/insights", params)
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(i) for i in rows]

    def get_campaign_breakdown(
        self,
        campaign_id: str,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(
            date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns
        )
        data = self.services.api.get(f"{campaign_id}/insights", params)
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(i) for i in rows]

    def get_adset_breakdown(
        self,
        adset_id: str,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(
            date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns
        )
        data = self.services.api.get(f"{adset_id}/insights", params)
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(i) for i in rows]

    def get_ad_breakdown(
        self,
        ad_id: str,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> Any:
        fields, bl = self._validate(date_preset, metrics, breakdown)
        params = self._build_params(
            date_preset, fields, bl, time_increment, action_attribution_windows, action_breakdowns
        )
        data = self.services.api.get(f"{ad_id}/insights", params)
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(i) for i in rows]
