"""Webhook automations service (Phase B)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from src.core.services import Services
from src.utils import normalize_pii
from src.webhook_automations import (
    ACTION_TYPES,
    AUTOMATIONS_FILE,
    TRIGGER_TYPES,
    _load_rules,
    _save_rules,
)


class WebhookAutomationsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list(self) -> dict[str, Any]:
        rules = _load_rules()
        return {"rules": rules, "count": len(rules), "file": str(AUTOMATIONS_FILE)}

    def create(
        self,
        name: str,
        trigger: str = "comment_keyword",
        keyword: str = "",
        action_type: str = "reply_comment",
        action_params_json: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        trig = trigger.strip().lower()
        if trig not in TRIGGER_TYPES:
            raise ValueError(f"trigger غير صالح. اختر من: {', '.join(TRIGGER_TYPES)}")
        act = action_type.strip().lower()
        if act not in ACTION_TYPES:
            raise ValueError(f"action_type غير صالح. اختر من: {', '.join(ACTION_TYPES)}")
        if trig == "comment_keyword" and not keyword:
            raise ValueError("keyword مطلوب عند trigger=comment_keyword")
        params = {}
        if action_params_json:
            try:
                params = json.loads(action_params_json)
            except Exception:
                raise ValueError("action_params_json ليس JSON صالح") from None
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
        return {"success": True, "rule": rule, "total": len(rules)}

    def delete(self, rule_id: str) -> dict[str, Any]:
        rules = _load_rules()
        orig_len = len(rules)
        rules = [r for r in rules if r.get("id") != rule_id]
        if len(rules) == orig_len:
            raise ValueError(f"القاعدة {rule_id} غير موجودة")
        _save_rules(rules)
        return {"success": True, "deleted": rule_id, "remaining": len(rules)}

    def evaluate(self, event_json: str) -> dict[str, Any]:
        try:
            event = json.loads(event_json)
        except Exception:
            raise ValueError("event_json ليس JSON صالح") from None
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
                trig_val = rule.get("trigger") or ""
                if trig.replace("_", "") in event_str or trig_val in event_str:
                    matched.append(rule)
                if "lead" in event_str and trig == "lead_created" and rule not in matched:
                    matched.append(rule)
                if "message" in event_str and trig == "message_received" and rule not in matched:
                    matched.append(rule)
        return {"matched": matched, "count": len(matched), "total_rules": len(rules)}

    def run(self, event_json: str, dry_run: bool = True) -> dict[str, Any]:
        try:
            event = json.loads(event_json)
        except Exception:
            raise ValueError("event_json ليس JSON صالح") from None
        eval_result = self.evaluate(event_json)
        matched = eval_result.get("matched", [])
        if not matched:
            return {"matched": 0, "executed": 0, "message": "لا توجد قواعد مطابقة"}
        if dry_run:
            return {"matched": len(matched), "dry_run": True, "would_execute": matched}

        results = []
        for rule in matched:
            act = rule.get("action_type")
            params = rule.get("action_params", {})
            try:
                if act == "reply_comment":
                    comment_id = event.get("comment_id") or event.get("id") or params.get("comment_id") or ""
                    message = params.get("message") or "شكرًا لتعليقك!"
                    if comment_id:
                        self.services.api.post(f"{comment_id}/comments", {"message": message})
                        results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                    else:
                        results.append(
                            {"rule_id": rule["id"], "action": act, "status": "skipped", "reason": "comment_id missing"}
                        )
                elif act == "hide_comment":
                    comment_id = event.get("comment_id") or event.get("id") or params.get("comment_id") or ""
                    if comment_id:
                        self.services.api.post(f"{comment_id}", {"hide": "true"})
                        results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                    else:
                        results.append({"rule_id": rule["id"], "action": act, "status": "skipped"})
                elif act == "send_message":
                    recipient = params.get("recipient_id") or (event.get("sender") or {}).get("id") or ""
                    text = params.get("message") or "أهلاً!"
                    if recipient:
                        self.services.api.page_post(
                            f"{self.config.page_id}/messages",
                            {"recipient": {"id": recipient}, "message": {"text": text}},
                        )
                        results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                    else:
                        results.append({"rule_id": rule["id"], "action": act, "status": "skipped"})
                elif act == "add_to_audience":
                    audience_id = params.get("audience_id") or ""
                    email = event.get("email") or params.get("email") or ""
                    if audience_id and email:
                        hashed = normalize_pii([email], "email")
                        self.services.api.post(
                            f"{audience_id}/users",
                            {"schema": ["EMAIL_SHA256"], "users": hashed},
                        )
                        results.append({"rule_id": rule["id"], "action": act, "status": "executed"})
                    else:
                        results.append({"rule_id": rule["id"], "action": act, "status": "skipped"})
                else:
                    results.append({"rule_id": rule["id"], "action": act, "status": "unsupported"})
            except Exception as ex:
                results.append({"rule_id": rule["id"], "action": act, "status": "failed", "error": str(ex)})
        return {
            "matched": len(matched),
            "executed": len([r for r in results if r["status"] == "executed"]),
            "results": results,
        }
