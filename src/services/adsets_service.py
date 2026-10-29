"""Adsets service (Phase B)."""

from __future__ import annotations

import json
from typing import Any

from src.core.services import Services
from src.utils import paginate, to_dict


class AdsetsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _acct(self, ad_account_id: str = "") -> str:
        return self.config.resolve_ad_account_id(ad_account_id)

    def list_adsets(self, campaign_id: str = "", limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [
            "name",
            "status",
            "targeting",
            "daily_budget",
            "lifetime_budget",
            "optimization_goal",
            "billing_event",
            "id",
        ]

        def _getter(params):
            path = f"{campaign_id}/adsets" if campaign_id else f"{self._acct(ad_account_id)}/adsets"
            return self.services.api.get(path, params)

        return paginate(_getter, fields=fields, limit=limit)

    def get_adset(self, adset_id: str) -> Any:
        fields = [
            "name",
            "status",
            "targeting",
            "daily_budget",
            "lifetime_budget",
            "optimization_goal",
            "billing_event",
            "bid_amount",
            "pacing_type",
            "start_time",
            "end_time",
        ]
        data = self.services.api.get(f"{adset_id}", {"fields": ",".join(fields)})
        return to_dict(data)

    def create_adset(
        self,
        name: str,
        campaign_id: str,
        daily_budget: int = 0,
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        targeting: str = "",
        status: str = "PAUSED",
        bid_amount: int = 0,
        advantage_audience: bool = False,
        ad_account_id: str = "",
        lifetime_budget: int = 0,
    ) -> Any:
        from src.utils import json_dumps

        if not targeting:
            targeting = json_dumps({"geo_locations": {"countries": ["US"]}})
        target = json.loads(targeting)
        target["targeting_automation"] = {"advantage_audience": 1 if advantage_audience else 0}
        targeting = json_dumps(target)
        acct = self._acct(ad_account_id)
        params: dict[str, Any] = {
            "name": name,
            "optimization_goal": optimization_goal,
            "billing_event": billing_event,
            "targeting": targeting,
            "status": status,
            "campaign_id": campaign_id,
        }
        if daily_budget and daily_budget > 0:
            params["daily_budget"] = str(daily_budget)
        if lifetime_budget and lifetime_budget > 0:
            params["lifetime_budget"] = str(lifetime_budget)
        if bid_amount and bid_amount > 0:
            params["bid_strategy"] = "LOWEST_COST_WITH_BID_CAP"
            params["bid_amount"] = str(bid_amount)
        else:
            params["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
        data = self.services.api.post(f"{acct}/adsets", params)
        return to_dict(data)

    def update_status(self, adset_id: str, status: str) -> dict[str, Any]:
        valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
        status = status.upper()
        if status not in valid:
            raise ValueError(f"status غير صالح. القيم: {', '.join(sorted(valid))}")
        self.services.api.post(f"{adset_id}", {"status": status})
        return {"success": True, "adset_id": adset_id, "new_status": status}

    def update_budget(self, adset_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if daily_budget and daily_budget > 0:
            params["daily_budget"] = daily_budget
        if lifetime_budget and lifetime_budget > 0:
            params["lifetime_budget"] = lifetime_budget
        if not params:
            raise ValueError("حدد ميزانية يومية أو إجمالية")
        self.services.api.post(f"{adset_id}", params)
        return {"success": True, "adset_id": adset_id, "result": params}

    def update_targeting(self, adset_id: str, targeting: str, advantage_audience: bool | None = None) -> dict[str, Any]:
        from src.utils import json_dumps

        target = json.loads(targeting)
        if advantage_audience is not None:
            target["targeting_automation"] = {"advantage_audience": 1 if advantage_audience else 0}
        else:
            target.setdefault("targeting_automation", {"advantage_audience": 0})
        self.services.api.post(f"{adset_id}", {"targeting": json_dumps(target)})
        return {"success": True, "adset_id": adset_id, "targeting": target}

    def get_delivery_insights(
        self,
        adset_id: str,
        date_preset: str = "last_7d",
        metrics: str = "spend,impressions,reach,frequency,cpm,ctr,cpc",
    ) -> Any:
        fields = [m.strip() for m in metrics.split(",") if m.strip()]
        data = self.services.api.get(
            f"{adset_id}/insights",
            {"date_preset": date_preset, "fields": ",".join(fields)},
        )
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(i) for i in rows]
