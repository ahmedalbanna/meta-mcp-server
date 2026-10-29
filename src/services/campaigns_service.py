"""Campaigns service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign

from src.config import resolve_ad_account_id
from src.core.services import Services
from src.helpers import json_dumps, to_dict
from src.utils import paginate

_DEPRECATED_OBJECTIVES = {
    "LINK_CLICKS": "OUTCOME_TRAFFIC",
    "CONVERSIONS": "OUTCOME_SALES",
    "LEAD_GENERATION": "OUTCOME_LEADS",
    "REACH": "OUTCOME_AWARENESS",
    "BRAND_AWARENESS": "OUTCOME_AWARENESS",
    "APP_INSTALLS": "OUTCOME_APP_PROMOTION",
    "VIDEO_VIEWS": "OUTCOME_ENGAGEMENT",
    "MESSAGES": "OUTCOME_ENGAGEMENT",
    "ENGAGEMENT": "OUTCOME_ENGAGEMENT",
}


class CampaignsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list_campaigns(self, status: str = "", limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [
            Campaign.Field.name, Campaign.Field.status, Campaign.Field.objective,
            Campaign.Field.daily_budget, Campaign.Field.lifetime_budget,
            Campaign.Field.created_time, Campaign.Field.id,
        ]
        extra = {}
        if status:
            extra["filtering"] = json_dumps([{"field": "status", "operator": "EQUAL", "value": status}])
        acct = resolve_ad_account_id(ad_account_id)
        rows = paginate(
            lambda params: AdAccount(acct).get_campaigns(params=params),
            fields=fields, params=extra or None, limit=limit,
        )
        return rows

    def get_campaign(self, campaign_id: str) -> Any:
        campaign = Campaign(campaign_id)
        info = campaign.api_get(fields=[
            Campaign.Field.name, Campaign.Field.status, Campaign.Field.objective,
            Campaign.Field.daily_budget, Campaign.Field.lifetime_budget,
            Campaign.Field.buying_type, Campaign.Field.created_time, Campaign.Field.updated_time,
        ])
        return to_dict(info)

    def create_campaign(self, name: str, objective: str = "OUTCOME_TRAFFIC",
                        daily_budget: int = 0, lifetime_budget: int = 0,
                        status: str = "PAUSED", ad_account_id: str = "") -> Any:
        objective = _DEPRECATED_OBJECTIVES.get(objective.strip().upper(), objective.strip().upper())
        if not (daily_budget or lifetime_budget):
            raise ValueError("يجب تحديد ميزانية يومية أو إجمالية")
        acct = resolve_ad_account_id(ad_account_id)
        account = AdAccount(acct)
        params = {
            Campaign.Field.name: name,
            Campaign.Field.objective: objective,
            Campaign.Field.status: status,
            Campaign.Field.special_ad_categories: [],
            "is_adset_budget_sharing_enabled": False,
        }
        if daily_budget and daily_budget > 0:
            params[Campaign.Field.daily_budget] = daily_budget
        if lifetime_budget and lifetime_budget > 0:
            params[Campaign.Field.lifetime_budget] = lifetime_budget
        campaign = account.create_campaign(params=params)
        return to_dict(campaign)

    def update_status(self, campaign_id: str, status: str) -> dict[str, Any]:
        valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
        status = status.upper()
        if status not in valid:
            raise ValueError(f"status غير صالح. القيم: {', '.join(sorted(valid))}")
        campaign = Campaign(campaign_id)
        result = campaign.api_update(params={Campaign.Field.status: status})
        return {"success": True, "campaign_id": campaign_id, "new_status": status, "result": to_dict(result)}

    def update_budget(self, campaign_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> dict[str, Any]:
        campaign = Campaign(campaign_id)
        params = {}
        if daily_budget and daily_budget > 0:
            params[Campaign.Field.daily_budget] = daily_budget
        if lifetime_budget and lifetime_budget > 0:
            params[Campaign.Field.lifetime_budget] = lifetime_budget
        if not params:
            raise ValueError("حدد ميزانية يومية أو إجمالية")
        result = campaign.api_update(params=params)
        return {"success": True, "campaign_id": campaign_id, "result": to_dict(result)}

    def delete(self, campaign_id: str) -> dict[str, Any]:
        campaign = Campaign(campaign_id)
        result = campaign.api_delete()
        return {"success": True, "campaign_id": campaign_id, "result": to_dict(result)}
