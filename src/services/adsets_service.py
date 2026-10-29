"""Adsets service (Phase B)."""

from __future__ import annotations

import json
from typing import Any

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.campaign import Campaign

from src.config import resolve_ad_account_id
from src.core.services import Services
from src.helpers import to_dict
from src.utils import paginate


class AdsetsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list_adsets(self, campaign_id: str = "", limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [
            AdSet.Field.name, AdSet.Field.status, AdSet.Field.targeting,
            AdSet.Field.daily_budget, AdSet.Field.lifetime_budget, AdSet.Field.optimization_goal,
            AdSet.Field.billing_event, AdSet.Field.id,
        ]

        def _getter(params):
            if campaign_id:
                return Campaign(campaign_id).get_ad_sets(params=params)
            return AdAccount(resolve_ad_account_id(ad_account_id)).get_ad_sets(params=params)

        return paginate(_getter, fields=fields, limit=limit)

    def get_adset(self, adset_id: str) -> Any:
        adset = AdSet(adset_id)
        info = adset.api_get(fields=[
            AdSet.Field.name, AdSet.Field.status, AdSet.Field.targeting,
            AdSet.Field.daily_budget, AdSet.Field.lifetime_budget, AdSet.Field.optimization_goal,
            AdSet.Field.billing_event, AdSet.Field.bid_amount, AdSet.Field.pacing_type,
            AdSet.Field.start_time, AdSet.Field.end_time,
        ])
        return to_dict(info)

    def create_adset(self, name: str, campaign_id: str, daily_budget: int = 0,
                     optimization_goal: str = "LINK_CLICKS", billing_event: str = "IMPRESSIONS",
                     targeting: str = "", status: str = "PAUSED", bid_amount: int = 0,
                     advantage_audience: bool = False, ad_account_id: str = "",
                     lifetime_budget: int = 0) -> Any:
        from src.helpers import json_dumps
        if not targeting:
            targeting = json_dumps({"geo_locations": {"countries": ["US"]}})
        target = json.loads(targeting)
        target["targeting_automation"] = {"advantage_audience": 1 if advantage_audience else 0}
        targeting = json_dumps(target)
        account = AdAccount(resolve_ad_account_id(ad_account_id))
        params = {
            AdSet.Field.name: name,
            AdSet.Field.optimization_goal: optimization_goal,
            AdSet.Field.billing_event: billing_event,
            AdSet.Field.targeting: targeting,
            AdSet.Field.status: status,
            "campaign_id": campaign_id,
        }
        if daily_budget and daily_budget > 0:
            params[AdSet.Field.daily_budget] = str(daily_budget)
        if lifetime_budget and lifetime_budget > 0:
            params[AdSet.Field.lifetime_budget] = str(lifetime_budget)
        if bid_amount and bid_amount > 0:
            params[AdSet.Field.bid_strategy] = "LOWEST_COST_WITH_BID_CAP"
            params[AdSet.Field.bid_amount] = str(bid_amount)
        else:
            params[AdSet.Field.bid_strategy] = "LOWEST_COST_WITHOUT_CAP"
        return to_dict(account.create_ad_set(params=params))

    def update_status(self, adset_id: str, status: str) -> dict[str, Any]:
        valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
        status = status.upper()
        if status not in valid:
            raise ValueError(f"status غير صالح. القيم: {', '.join(sorted(valid))}")
        adset = AdSet(adset_id)
        adset.api_update(params={AdSet.Field.status: status})
        return {"success": True, "adset_id": adset_id, "new_status": status}

    def update_budget(self, adset_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if daily_budget and daily_budget > 0:
            params[AdSet.Field.daily_budget] = daily_budget
        if lifetime_budget and lifetime_budget > 0:
            params[AdSet.Field.lifetime_budget] = lifetime_budget
        if not params:
            raise ValueError("حدد ميزانية يومية أو إجمالية")
        AdSet(adset_id).api_update(params=params)
        return {"success": True, "adset_id": adset_id, "result": params}

    def update_targeting(self, adset_id: str, targeting: str, advantage_audience: bool | None = None) -> dict[str, Any]:
        from src.helpers import json_dumps
        target = json.loads(targeting)
        if advantage_audience is not None:
            target["targeting_automation"] = {"advantage_audience": 1 if advantage_audience else 0}
        else:
            target.setdefault("targeting_automation", {"advantage_audience": 0})
        AdSet(adset_id).api_update(params={AdSet.Field.targeting: json_dumps(target)})
        return {"success": True, "adset_id": adset_id, "targeting": target}

    def get_delivery_insights(self, adset_id: str, date_preset: str = "last_7d",
                              metrics: str = "spend,impressions,reach,frequency,cpm,ctr,cpc") -> Any:
        fields = [m.strip() for m in metrics.split(",") if m.strip()]
        insights = AdSet(adset_id).get_insights(params={"date_preset": date_preset, "fields": fields})
        return [to_dict(i) for i in insights]
