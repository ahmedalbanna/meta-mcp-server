"""Webhook automation rules: local event-driven actions.

Persisted in REPORT_DIR/automations.json, gated by FB_ENABLE_WRITES.
Triggers: comment_keyword | lead_created | message_received
Actions: reply_comment | hide_comment | send_message | add_to_audience

This is Phase 3.1 of ROADMAP — bridges webhook_server events to auto-actions
without requiring Meta's Automated Rules API.
"""

import json
import logging

logger = logging.getLogger(__name__)
from typing import Any

from src.config import REPORT_DIR, ensure_report_dir

AUTOMATIONS_FILE = REPORT_DIR / "automations.json"
TRIGGER_TYPES = ["comment_keyword", "lead_created", "message_received", "webhook_event"]
ACTION_TYPES = ["reply_comment", "hide_comment", "send_message", "add_to_audience", "send_template"]


def _load_rules() -> list[dict[str, Any]]:
    ensure_report_dir()
    if not AUTOMATIONS_FILE.exists():
        return []
    try:
        data = json.loads(AUTOMATIONS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_rules(rules: list[dict[str, Any]]) -> None:
    ensure_report_dir()
    AUTOMATIONS_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def register(mcp, services=None):
    """Register webhook automation tools."""

    from src.helpers import handle_error, json_dumps, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_webhook_automations() -> str:
        """قائمة قواعد الأتمتة المحلية (webhook automations) المخزنة في reports/automations.json."""
        try:
            from src.core.services import Services
            from src.services.webhook_automations_service import WebhookAutomationsService

            svc = (
                WebhookAutomationsService(services)
                if services is not None
                else WebhookAutomationsService(Services.default())
            )
            return json_dumps(svc.list())
        except Exception as e:
            return json_dumps(handle_error(e, "list_webhook_automations"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_webhook_automation(
        name: str,
        trigger: str = "comment_keyword",
        keyword: str = "",
        action_type: str = "reply_comment",
        action_params_json: str = "",
        enabled: bool = True,
    ) -> str:
        """
        إنشاء قاعدة أتمتة محلية.
        trigger: comment_keyword | lead_created | message_received | webhook_event
        keyword: كلمة مفتاحية للtrigger comment_keyword (اختياري)
        action_type: reply_comment | hide_comment | send_message | add_to_audience | send_template
        action_params_json: JSON للبراميترات، مثال {"message":"أهلاً"} أو {"audience_id":"123"}
        """
        try:
            from src.core.services import Services
            from src.services.webhook_automations_service import WebhookAutomationsService

            svc = (
                WebhookAutomationsService(services)
                if services is not None
                else WebhookAutomationsService(Services.default())
            )
            return json_dumps(svc.create(name, trigger, keyword, action_type, action_params_json, enabled))
        except Exception as e:
            return json_dumps(handle_error(e, "create_webhook_automation"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_webhook_automation(rule_id: str) -> str:
        """حذف قاعدة أتمتة محلية حسب المعرف."""
        try:
            from src.core.services import Services
            from src.services.webhook_automations_service import WebhookAutomationsService

            svc = (
                WebhookAutomationsService(services)
                if services is not None
                else WebhookAutomationsService(Services.default())
            )
            return json_dumps(svc.delete(rule_id))
        except Exception as e:
            return json_dumps(handle_error(e, "delete_webhook_automation"))

    @mcp.tool()
    @concurrency_limit()
    def evaluate_webhook_automations(event_json: str) -> str:
        """
        محاكاة مطابقة حدث Webhook ضد القواعد المخزنة (dry-run).
        event_json: حمولة الحدث كـ JSON نصي.
        يُرجع القواعد التي كانت ستُطبّق بدون تنفيذ فعلي.
        """
        try:
            from src.core.services import Services
            from src.services.webhook_automations_service import WebhookAutomationsService

            svc = (
                WebhookAutomationsService(services)
                if services is not None
                else WebhookAutomationsService(Services.default())
            )
            return json_dumps(svc.evaluate(event_json))
        except Exception as e:
            return json_dumps(handle_error(e, "evaluate_webhook_automations"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def run_webhook_automations(event_json: str, dry_run: bool = True) -> str:
        """
        تنفيذ القواعد المطابقة لحدث Webhook فعليًا (أو محاكاة إذا dry_run=true).
        event_json: حمولة الحدث كـ JSON نصي.
        dry_run: true=محاكاة فقط، false=تنفيذ فعلي (يتطلب FB_ENABLE_WRITES)
        """
        try:
            from src.core.services import Services
            from src.services.webhook_automations_service import WebhookAutomationsService

            svc = (
                WebhookAutomationsService(services)
                if services is not None
                else WebhookAutomationsService(Services.default())
            )
            out = svc.run(event_json, dry_run)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "run_webhook_automations"))

    @mcp.resource("webhooks://overview")
    async def webhook_automations_resource() -> str:
        """نظرة عامة الأتمتة."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "webhook_automations", "resource": "webhooks://overview", "hint": "نظرة عامة الأتمتة"}
            )
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "webhooks://overview"))

    @mcp.prompt()
    def webhook_automation_prompt(topic: str = "webhook_automations") -> str:
        """أتمتة webhook."""
        return "ساعد في أتمتة webhook لـ " + topic + " — صمم أتمتة لحدث {event} (وحدة webhook_automations)"

    @mcp.resource("webhook-automations://templates")
    async def webhook_automations_extra_resource() -> str:
        """قوالب الأتمتة."""
        try:
            return json_dumps(
                {
                    "module": "webhook_automations",
                    "resource": "webhook-automations://templates",
                    "hint": "قوالب الأتمتة",
                }
            )
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "webhook-automations://templates"))

    @mcp.prompt()
    def webhook_test_prompt(topic: str = "webhook_automations") -> str:
        """اختبار webhook."""
        return "ساعد في اختبار webhook لـ " + topic + " — اختبر webhook {event} (وحدة webhook_automations)"
