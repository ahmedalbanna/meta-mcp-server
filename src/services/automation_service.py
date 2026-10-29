"""Automation (ad rules) service (Phase B)."""

from __future__ import annotations

import time
from typing import Any

from facebook_business.adobjects.adaccount import AdAccount

from src.config import AD_ACCOUNT_ID
from src.core.services import Services
from src.helpers import to_dict

SECONDS_PER_DAY = 86400


class AutomationService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list_auto_rules(self, limit: int = 25) -> Any:
        account = AdAccount(AD_ACCOUNT_ID)
        rules = account.get_ad_rules_library(params={"limit": limit})
        return [to_dict(r) for r in rules]

    def create_auto_rule(self, name: str, evaluation_spec: str, execution_spec: str,
                          schedule_spec: str = "", status: str = "ACTIVE") -> Any:
        account = AdAccount(AD_ACCOUNT_ID)
        params = {
            "name": name,
            "evaluation_spec": evaluation_spec,
            "execution_spec": execution_spec,
            "status": status,
        }
        if schedule_spec:
            params["schedule_spec"] = schedule_spec
        rule = account.create_ad_rules_library(params=params)
        return to_dict(rule)

    def create_simple_auto_rule(self, name: str, object_type: str = "campaign", field: str = "spend",
                                operator: str = "GREATER_THAN", value: float = 100.0,
                                action: str = "pause", time_zone: str = "America/New_York",
                                status: str = "ACTIVE") -> Any:
        import json
        account = AdAccount(AD_ACCOUNT_ID)
        execution_options = [
            {"field": "STATUS", "operator": "EQUAL", "value": "PAUSED" if action == "PAUSE" else "ACTIVE"}
        ]
        evaluation_spec = {
            "evaluation_type": "schedule",
            "filters": [{"field": field, "operator": operator, "value": value}],
            "trigger": {"type": "schedule", "time_zone": time_zone, "time_in_minutes": [0]},
        }
        params = {
            "name": name,
            "evaluation_spec": json.dumps(evaluation_spec),
            "execution_spec": json.dumps({"execution_type": "value", "execution_options": execution_options}),
            "status": status,
        }
        rule = account.create_ad_rules_library(params=params)
        return to_dict(rule)

    def delete_auto_rule(self, rule_id: str) -> dict[str, Any]:
        from facebook_business.adobjects.adrule import AdRule
        rule = AdRule(rule_id)
        rule.api_delete()
        return {"success": True, "rule_id": rule_id}

    def get_history(self, days: int = 7) -> Any:
        account = AdAccount(AD_ACCOUNT_ID)
        since = int(time.time()) - days * SECONDS_PER_DAY
        history = account.get_ad_rules_history(params={"start_time": since, "end_time": int(time.time())})
        return [to_dict(h) for h in history]
