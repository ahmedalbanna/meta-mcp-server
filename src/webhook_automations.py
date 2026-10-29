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
            svc = WebhookAutomationsService(services) if services is not None else WebhookAutomationsService(Services.default())
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
            svc = WebhookAutomationsService(services) if services is not None else WebhookAutomationsService(Services.default())
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
            svc = WebhookAutomationsService(services) if services is not None else WebhookAutomationsService(Services.default())
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
            svc = WebhookAutomationsService(services) if services is not None else WebhookAutomationsService(Services.default())
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
            try:
                event = json.loads(event_json)
            except Exception:
                return json_dumps({"error": "event_json ليس JSON صالح"})
            # Reuse evaluate logic
            eval_raw = json.loads(evaluate_webhook_automations(event_json))
            matched = eval_raw.get("matched", [])
            if not matched:
                return json_dumps({"matched": 0, "executed": 0, "message": "لا توجد قواعد مطابقة"})
            if dry_run:
                return json_dumps({"matched": len(matched), "dry_run": True, "would_execute": matched})

            # Execute each matched rule
            results = []
            for rule in matched:
                act = rule.get("action_type")
                params = rule.get("action_params", {})
                try:
                    if act == "reply_comment":
                        # expects comment_id in event, message in params
                        comment_id = event.get("comment_id") or event.get("id") or params.get("comment_id") or ""
                        message = params.get("message") or "شكرًا لتعليقك!"
                        if comment_id:
                            from src.helpers import api_call

                            api_call("POST", f"{comment_id}/comments", {"message": message})
                            results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                        else:
                            results.append(
                                {
                                    "rule_id": rule["id"],
                                    "action": act,
                                    "status": "skipped",
                                    "reason": "comment_id missing",
                                }
                            )
                    elif act == "hide_comment":
                        comment_id = event.get("comment_id") or event.get("id") or params.get("comment_id") or ""
                        if comment_id:
                            from src.helpers import api_call

                            api_call("POST", f"{comment_id}", {"hide": "true"})
                            results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                        else:
                            results.append({"rule_id": rule["id"], "action": act, "status": "skipped"})
                    elif act == "send_message":
                        recipient = params.get("recipient_id") or event.get("sender", {}).get("id") or ""
                        text = params.get("message") or "أهلاً!"
                        if recipient:
                            from src.config import PAGE_ID
                            from src.helpers import page_api_call

                            page_api_call(
                                "POST",
                                f"{PAGE_ID}/messages",
                                {"recipient": {"id": recipient}, "message": {"text": text}},
                            )
                            results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                        else:
                            results.append({"rule_id": rule["id"], "action": act, "status": "skipped"})
                    elif act == "add_to_audience":
                        audience_id = params.get("audience_id") or ""
                        email = event.get("email") or params.get("email") or ""
                        if audience_id and email:
                            from facebook_business.adobjects.customaudience import CustomAudience

                            from src.utils import normalize_pii

                            hashed = normalize_pii([email], "email")
                            CustomAudience(audience_id).add_users(schema=["EMAIL_SHA256"], users=hashed)
                            results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                        else:
                            results.append({"rule_id": rule["id"], "action": act, "status": "skipped"})
                    else:
                        results.append({"rule_id": rule["id"], "action": act, "status": "unsupported"})
                except Exception as ex:
                    results.append({"rule_id": rule["id"], "action": act, "status": "failed", "error": str(ex)})
            return json_dumps(
                {
                    "matched": len(matched),
                    "executed": len([r for r in results if r["status"] == "executed"]),
                    "results": results,
                }
            )
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
