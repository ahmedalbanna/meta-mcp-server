import json
import time

from src.config import AD_ACCOUNT_ID
from src.helpers import handle_error, json_dumps, to_dict, write_guard
from src.throttle import concurrency_limit

SECONDS_PER_DAY = 86400


def register(mcp):
    """Register automated rules (ad rules) tools."""

    from facebook_business.adobjects.adaccount import AdAccount

    @mcp.tool()
    @concurrency_limit()
    def list_auto_rules(limit: int = 25) -> str:
        """قائمة القواعد التلقائية في الحساب الإعلاني."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            rules = account.get_ad_rules_library(params={"limit": limit})
            return json_dumps([to_dict(r) for r in rules])
        except Exception as e:
            return json_dumps(handle_error(e, "list_auto_rules"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_auto_rule(
        name: str,
        evaluation_spec: str,
        execution_spec: str,
        schedule_spec: str = "",
        status: str = "ACTIVE",
    ) -> str:
        """
        إنشاء قاعدة تلقائية من مواصفات JSON جاهزة.
        evaluation_spec: JSON يتضمن filters و trigger.
        execution_spec: JSON يحدد الإجراء (إيقاف/تفعيل/تعديل).
        مثال (إيقاف عند تجاوز الإنفاق 100):
        evaluation_spec='{"evaluation_type":"schedule","filters":[{"field":"spend","operator":"GREATER_THAN","value":100}],"trigger":{"type":"schedule","time_zone":"America/New_York","time_in_minutes":[0]}}'
        execution_spec='{"execution_type":"value","execution_options":[{"field":"STATUS","operator":"EQUAL","value":"PAUSED"}]}'
        """
        try:
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
            return json_dumps(to_dict(rule))
        except Exception as e:
            return json_dumps(handle_error(e, "create_auto_rule"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_simple_auto_rule(
        name: str,
        object_type: str = "campaign",
        field: str = "spend",
        operator: str = "GREATER_THAN",
        value: float = 100.0,
        action: str = "PAUSE",
        time_zone: str = "America/New_York",
        status: str = "ACTIVE",
    ) -> str:
        """
        إنشاء قاعدة تلقائية بسيطة: عند تجاوز مؤشر معين، نفّذ إجراءً.
        object_type: campaign | adset | ad
        field: spend, cpc, ctr, impressions, clicks...
        operator: GREATER_THAN, LESS_THAN, EQUAL...
        action: PAUSE, ACTIVATE (لتفعيل/إيقاف)
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            execution_options = [
                {"field": "STATUS", "operator": "EQUAL", "value": "PAUSED" if action == "PAUSE" else "ACTIVE"}
            ]
            execution_spec = {
                "execution_type": "value",
                "execution_options": execution_options,
            }
            evaluation_spec = {
                "evaluation_type": "schedule",
                "filters": [{"field": field, "operator": operator, "value": value}],
                "trigger": {"type": "schedule", "time_zone": time_zone, "time_in_minutes": [0]},
            }
            params = {
                "name": name,
                "evaluation_spec": json.dumps(evaluation_spec),
                "execution_spec": json.dumps(execution_spec),
                "status": status,
            }
            rule = account.create_ad_rules_library(params=params)
            return json_dumps(to_dict(rule))
        except Exception as e:
            return json_dumps(handle_error(e, "create_simple_auto_rule"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_auto_rule(rule_id: str) -> str:
        """حذف قاعدة تلقائية."""
        try:
            from facebook_business.adobjects.adrule import AdRule

            rule = AdRule(rule_id)
            rule.api_delete()
            return json_dumps({"success": True, "rule_id": rule_id})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_auto_rule"))

    @mcp.tool()
    @concurrency_limit()
    def get_auto_rules_history(days: int = 7) -> str:
        """سجل تنفيذ القواعد التلقائية خلال الأيام الأخيرة."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            since = int(time.time()) - days * SECONDS_PER_DAY
            history = account.get_ad_rules_history(
                params={"start_time": since, "end_time": int(time.time())}
            )
            return json_dumps([to_dict(h) for h in history])
        except Exception as e:
            return json_dumps(handle_error(e, "get_auto_rules_history"))
