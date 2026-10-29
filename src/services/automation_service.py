"""Automation (ad rules) service (Phase B)."""

from __future__ import annotations

import json
import time
from typing import Any

from src.core.services import Services
from src.utils import to_dict

SECONDS_PER_DAY = 86400


class AutomationService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _acct(self) -> str:
        return self.config.fb_ad_account_id

    def list_auto_rules(self, limit: int = 25) -> Any:
        data = self.services.api.get(f"{self._acct()}/ad_rules_library", {"limit": limit})
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(r) for r in rows]

    def create_auto_rule(
        self, name: str, evaluation_spec: str, execution_spec: str, schedule_spec: str = "", status: str = "ACTIVE"
    ) -> Any:
        params: dict[str, Any] = {
            "name": name,
            "evaluation_spec": evaluation_spec,
            "execution_spec": execution_spec,
            "status": status,
        }
        if schedule_spec:
            params["schedule_spec"] = schedule_spec
        data = self.services.api.post(f"{self._acct()}/ad_rules_library", params)
        return to_dict(data)

    def create_simple_auto_rule(
        self,
        name: str,
        object_type: str = "campaign",
        field: str = "spend",
        operator: str = "GREATER_THAN",
        value: float = 100.0,
        action: str = "pause",
        time_zone: str = "America/New_York",
        status: str = "ACTIVE",
    ) -> Any:
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
        data = self.services.api.post(f"{self._acct()}/ad_rules_library", params)
        return to_dict(data)

    def delete_auto_rule(self, rule_id: str) -> dict[str, Any]:
        self.services.api.delete(f"{rule_id}")
        return {"success": True, "rule_id": rule_id}

    def get_history(self, days: int = 7) -> Any:
        since = int(time.time()) - days * SECONDS_PER_DAY
        data = self.services.api.get(
            f"{self._acct()}/ad_rules_history",
            {"start_time": since, "end_time": int(time.time())},
        )
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(h) for h in rows]
