"""WhatsApp service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services


class WhatsAppService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _require_waba(self, waba_id: str) -> str:
        return waba_id or self.config.fb_waba_id

    def _require_phone(self, phone_number_id: str) -> str:
        return phone_number_id or self.config.fb_whatsapp_phone_number_id

    def list_phone_numbers(self, waba_id: str = "", limit: int = 25) -> Any:
        from src.whatsapp import PHONE_NUMBER_FIELDS
        return self.api.get(f"{self._require_waba(waba_id)}/phone_numbers", {"fields": PHONE_NUMBER_FIELDS, "limit": limit})

    def get_phone_number(self, phone_number_id: str = "") -> Any:
        from src.whatsapp import PHONE_NUMBER_FIELDS
        return self.api.get(self._require_phone(phone_number_id), {"fields": PHONE_NUMBER_FIELDS})

    def list_templates(self, waba_id: str = "", limit: int = 25) -> Any:
        from src.whatsapp import TEMPLATE_FIELDS
        return self.api.get(f"{self._require_waba(waba_id)}/message_templates", {"fields": TEMPLATE_FIELDS, "limit": limit})

    def get_template(self, template_id: str) -> Any:
        from src.whatsapp import TEMPLATE_FIELDS
        return self.api.get(template_id, {"fields": TEMPLATE_FIELDS})

    def create_template(self, name: str, language: str = "ar", category: str = "UTILITY",
                        body_text: str = "", header_text: str = "", waba_id: str = "") -> dict:
        import json as _json

        from src.whatsapp import TEMPLATE_CATEGORIES
        cat = category.upper()
        if cat not in TEMPLATE_CATEGORIES:
            raise ValueError(f"الفئة غير صالحة. اختر من: {', '.join(TEMPLATE_CATEGORIES)}")
        components = [{"type": "BODY", "text": body_text}]
        if header_text:
            components.insert(0, {"type": "HEADER", "text": header_text})
        result = self.api.post(f"{self._require_waba(waba_id)}/message_templates", {
            "name": name, "language": language, "category": cat,
            "components": _json.dumps(components),
        })
        return {"template_name": name, "result": result}

    def send_text(self, to: str, text: str, phone_number_id: str = "") -> dict:
        from src.whatsapp import WHATSAPP_MAX_TEXT_LENGTH
        if len(text) > WHATSAPP_MAX_TEXT_LENGTH:
            raise ValueError(f"النص طويل جدًا ({len(text)} حرف). الحد الأقصى {WHATSAPP_MAX_TEXT_LENGTH}.")
        result = self.api.post(f"{self._require_phone(phone_number_id)}/messages", {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        })
        return {"to": to, "result": result}

    def send_template(self, to: str, template_name: str, language: str = "ar",
                      phone_number_id: str = "", body_params_json: str = "") -> dict:
        import json as _json
        template = {"name": template_name, "language": {"code": language}}
        if body_params_json:
            params = _json.loads(body_params_json)
            if not isinstance(params, list):
                raise ValueError("body_params_json يجب أن يكون مصفوفة JSON")
            template["components"] = [  # type: ignore[list-item]
                {"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]}  # type: ignore[list-item]
            ]
        result = self.api.post(f"{self._require_phone(phone_number_id)}/messages", {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template,
        })
        return {"to": to, "template_name": template_name, "result": result}
