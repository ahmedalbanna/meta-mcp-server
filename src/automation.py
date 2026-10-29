import json
import logging

logger = logging.getLogger(__name__)
import time

from src.config import AD_ACCOUNT_ID
from src.helpers import handle_error, json_dumps, to_dict, write_guard
from src.throttle import concurrency_limit

SECONDS_PER_DAY = 86400


def register(mcp, services=None):
    """Register automated rules (ad rules) tools."""

    from facebook_business.adobjects.adaccount import AdAccount

    @mcp.tool()
    @concurrency_limit()
    def list_auto_rules(limit: int = 25) -> str:
        """قائمة القواعد التلقائية في الحساب الإعلاني."""
        try:
            from src.core.services import Services
            from src.services.automation_service import AutomationService
            svc = AutomationService(services) if services is not None else AutomationService(Services.default())
            data = svc.list_auto_rules(limit)
            return json_dumps(data)
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
            from src.core.services import Services
            from src.services.automation_service import AutomationService
            svc = AutomationService(services) if services is not None else AutomationService(Services.default())
            data = svc.create_auto_rule(name, evaluation_spec, execution_spec, schedule_spec, status)
            return json_dumps(data)
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
            from src.core.services import Services
            from src.services.automation_service import AutomationService
            svc = AutomationService(services) if services is not None else AutomationService(Services.default())
            data = svc.create_simple_auto_rule(name, object_type, field, operator, value, action, time_zone, status)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_simple_auto_rule"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_auto_rule(rule_id: str) -> str:
        """حذف قاعدة تلقائية."""
        try:
            from src.core.services import Services
            from src.services.automation_service import AutomationService
            svc = AutomationService(services) if services is not None else AutomationService(Services.default())
            data = svc.delete_auto_rule(rule_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "delete_auto_rule"))

    @mcp.tool()
    @concurrency_limit()
    def get_auto_rules_history(days: int = 7) -> str:
        """سجل تنفيذ القواعد التلقائية خلال الأيام الأخيرة."""
        try:
            from src.core.services import Services
            from src.services.automation_service import AutomationService
            svc = AutomationService(services) if services is not None else AutomationService(Services.default())
            data = svc.get_history(days)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_auto_rules_history"))

    @mcp.resource("automation://overview")
    async def automation_resource() -> str:
        """نظرة عامة على القواعد."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "automation", "resource": "automation://overview", "hint": "نظرة عامة على القواعد"}
            )
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "automation://overview"))

    @mcp.prompt()
    def automation_design_prompt(topic: str = "automation") -> str:
        """تصميم أتمتة."""
        return "ساعد في تصميم أتمتة لـ " + topic + " — صمم قاعدة أتمتة لمقياس {metric} (وحدة automation)"

    @mcp.prompt()
    def automation_rule_prompt(metric: str = "spend", threshold: str = "100") -> str:
        """شرح قاعدة أتمتة إعلانات."""
        return (
            f"اشرح قاعدة أتمتة: عند {metric} > {threshold} أوقف الحملة. "
            "اذكر: evaluation_spec و execution_spec JSON لـ create_auto_rule / create_simple_auto_rule."
        )

    @mcp.resource("automation://templates")
    async def automation_extra_resource() -> str:
        """قوالب الأتمتة."""
        try:
            return json_dumps({"module": "automation", "resource": "automation://templates", "hint": "قوالب الأتمتة"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "automation://templates"))

    @mcp.prompt()
    def automation_test_prompt(topic: str = "automation") -> str:
        """اختبار أتمتة."""
        return "ساعد في اختبار أتمتة لـ " + topic + " — اختبر قاعدة {rule_id} (وحدة automation)"
