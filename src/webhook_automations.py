"""Webhook automation rules: local event-driven actions.

Persisted in REPORT_DIR/automations.json, gated by FB_ENABLE_WRITES.
Triggers: comment_keyword | lead_created | message_received
Actions: reply_comment | hide_comment | send_message | add_to_audience

This is Phase 3.1 of ROADMAP — bridges webhook_server events to auto-actions
without requiring Meta's Automated Rules API.
"""

import json
import uuid
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


def register(mcp):
    """Register webhook automation tools."""

    from src.helpers import handle_error, json_dumps, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_webhook_automations() -> str:
        """قائمة قواعد الأتمتة المحلية (webhook automations) المخزنة في reports/automations.json."""
        try:
            rules = _load_rules()
            return json_dumps({"rules": rules, "count": len(rules), "file": str(AUTOMATIONS_FILE)})
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
            trig = trigger.strip().lower()
            if trig not in TRIGGER_TYPES:
                return json_dumps({"error": f"trigger غير صالح. اختر من: {', '.join(TRIGGER_TYPES)}"})
            act = action_type.strip().lower()
            if act not in ACTION_TYPES:
                return json_dumps({"error": f"action_type غير صالح. اختر من: {', '.join(ACTION_TYPES)}"})
            if trig == "comment_keyword" and not keyword:
                return json_dumps({"error": "keyword مطلوب عند trigger=comment_keyword"})
            params = {}
            if action_params_json:
                try:
                    params = json.loads(action_params_json)
                except Exception:
                    return json_dumps({"error": "action_params_json ليس JSON صالح"})
            rule_id = uuid.uuid4().hex[:12]
            rule = {
                "id": rule_id,
                "name": name,
                "trigger": trig,
                "keyword": keyword,
                "action_type": act,
                "action_params": params,
                "enabled": enabled,
            }
            rules = _load_rules()
            rules.append(rule)
            _save_rules(rules)
            return json_dumps({"success": True, "rule": rule, "total": len(rules)})
        except Exception as e:
            return json_dumps(handle_error(e, "create_webhook_automation"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_webhook_automation(rule_id: str) -> str:
        """حذف قاعدة أتمتة محلية حسب المعرف."""
        try:
            rules = _load_rules()
            orig_len = len(rules)
            rules = [r for r in rules if r.get("id") != rule_id]
            if len(rules) == orig_len:
                return json_dumps({"error": f"القاعدة {rule_id} غير موجودة"})
            _save_rules(rules)
            return json_dumps({"success": True, "deleted": rule_id, "remaining": len(rules)})
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
            try:
                event = json.loads(event_json)
            except Exception:
                return json_dumps({"error": "event_json ليس JSON صالح"})
            rules = [r for r in _load_rules() if r.get("enabled")]
            matched = []
            event_str = json.dumps(event, ensure_ascii=False).lower()
            for rule in rules:
                trig = rule.get("trigger")
                if trig == "comment_keyword":
                    kw = (rule.get("keyword") or "").lower()
                    if kw and kw in event_str:
                        matched.append(rule)
                elif trig in ("lead_created", "message_received", "webhook_event"):
                    # generic: match if trigger word appears in event type or object
                    trig_val = rule.get("trigger") or ""
                    if trig.replace("_", "") in event_str or trig_val in event_str:
                        matched.append(rule)
                    # For demo, also match all lead/message triggers regardless
                    # if event contains "leadgen" or "message"
                    if "lead" in event_str and trig == "lead_created" and rule not in matched:
                        matched.append(rule)
                    if "message" in event_str and trig == "message_received" and rule not in matched:
                        matched.append(rule)
            return json_dumps({"matched": matched, "count": len(matched), "total_rules": len(rules)})
        except Exception as e:
            return json_dumps(handle_error(e, "evaluate_webhook_automations"))
