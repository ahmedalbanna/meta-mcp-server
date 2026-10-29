"""Campaigns service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.utils import json_dumps, paginate, to_dict

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

    def _acct(self, ad_account_id: str = "") -> str:
        return self.config.resolve_ad_account_id(ad_account_id)

    def list_campaigns(self, status: str = "", limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [
            "name",
            "status",
            "objective",
            "daily_budget",
            "lifetime_budget",
            "created_time",
            "id",
        ]
        extra: dict[str, Any] = {}
        if status:
            extra["filtering"] = json_dumps([{"field": "status", "operator": "EQUAL", "value": status}])
        acct = self._acct(ad_account_id)
        rows = paginate(
            lambda params: self.services.api.get(f"{acct}/campaigns", params),
            fields=fields,
            params=extra or None,
            limit=limit,
        )
        return rows

    def get_campaign(self, campaign_id: str) -> Any:
        fields = [
            "name",
            "status",
            "objective",
            "daily_budget",
            "lifetime_budget",
            "buying_type",
            "created_time",
            "updated_time",
        ]
        data = self.services.api.get(f"{campaign_id}", {"fields": ",".join(fields)})
        return to_dict(data)

    def create_campaign(
        self,
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        daily_budget: int = 0,
        lifetime_budget: int = 0,
        status: str = "PAUSED",
        ad_account_id: str = "",
    ) -> Any:
        objective = _DEPRECATED_OBJECTIVES.get(objective.strip().upper(), objective.strip().upper())
        if not (daily_budget or lifetime_budget):
            raise ValueError("يجب تحديد ميزانية يومية أو إجمالية")
        acct = self._acct(ad_account_id)
        params: dict[str, Any] = {
            "name": name,
            "objective": objective,
            "status": status,
            "special_ad_categories": [],
            "is_adset_budget_sharing_enabled": False,
        }
        if daily_budget and daily_budget > 0:
            params["daily_budget"] = daily_budget
        if lifetime_budget and lifetime_budget > 0:
            params["lifetime_budget"] = lifetime_budget
        data = self.services.api.post(f"{acct}/campaigns", params)
        return to_dict(data)

    def update_status(self, campaign_id: str, status: str) -> dict[str, Any]:
        valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
        status = status.upper()
        if status not in valid:
            raise ValueError(f"status غير صالح. القيم: {', '.join(sorted(valid))}")
        self.services.api.post(f"{campaign_id}", {"status": status})
        return {"success": True, "campaign_id": campaign_id, "new_status": status}

    def update_budget(self, campaign_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if daily_budget and daily_budget > 0:
            params["daily_budget"] = daily_budget
        if lifetime_budget and lifetime_budget > 0:
            params["lifetime_budget"] = lifetime_budget
        if not params:
            raise ValueError("حدد ميزانية يومية أو إجمالية")
        self.services.api.post(f"{campaign_id}", params)
        return {"success": True, "campaign_id": campaign_id, "result": params}

    def delete(self, campaign_id: str) -> dict[str, Any]:
        self.services.api.delete(f"{campaign_id}")
        return {"success": True, "campaign_id": campaign_id, "result": {}}
