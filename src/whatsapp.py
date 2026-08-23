"""WhatsApp Business (Cloud API): phone numbers, message templates and sending.

Raw Graph API calls using the system/business access token.
"""

from src.config import WABA_ID, WHATSAPP_PHONE_NUMBER_ID
from src.helpers import api_call, handle_error, json_dumps, write_guard
from src.throttle import concurrency_limit

WHATSAPP_MAX_TEXT_LENGTH = 4096

PHONE_NUMBER_FIELDS = "id,display_phone_number,verified_name,quality_rating," "code_verification_status,throughput"
TEMPLATE_FIELDS = "id,name,status,language,components,category"
TEMPLATE_CATEGORIES = ["MARKETING", "UTILITY", "AUTHENTICATION"]


def register(mcp):
    """Register WhatsApp Business tools (raw Graph API)."""

    import json as _json

    def _require_waba(waba_id: str) -> str:
        return waba_id or WABA_ID

    def _require_phone(phone_number_id: str) -> str:
        return phone_number_id or WHATSAPP_PHONE_NUMBER_ID

    @mcp.tool()
    @concurrency_limit()
    def list_whatsapp_phone_numbers(waba_id: str = "", limit: int = 25) -> str:
        """أرقام الهواتف المسجّلة في حساب واتساب للأعمال (WABA)."""
        try:
            data = api_call(
                "GET",
                f"{_require_waba(waba_id)}/phone_numbers",
                {"fields": PHONE_NUMBER_FIELDS, "limit": limit},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_whatsapp_phone_numbers"))

    @mcp.tool()
    @concurrency_limit()
    def get_whatsapp_phone_number(phone_number_id: str = "") -> str:
        """تفاصيل رقم هاتف واتساب واحد."""
        try:
            data = api_call(
                "GET",
                _require_phone(phone_number_id),
                {"fields": PHONE_NUMBER_FIELDS},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_whatsapp_phone_number"))

    @mcp.tool()
    @concurrency_limit()
    def list_whatsapp_message_templates(waba_id: str = "", limit: int = 25) -> str:
        """قوالب الرسائل المعتمدة في حساب واتساب للأعمال."""
        try:
            data = api_call(
                "GET",
                f"{_require_waba(waba_id)}/message_templates",
                {"fields": TEMPLATE_FIELDS, "limit": limit},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_whatsapp_message_templates"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_whatsapp_message_template(
        name: str,
        language: str = "ar",
        category: str = "UTILITY",
        body_text: str = "",
        header_text: str = "",
        waba_id: str = "",
    ) -> str:
        """إنشاء قالب رسالة واتساب جديد (يتطلب موافقة ميتا)."""
        try:
            cat = category.upper()
            if cat not in TEMPLATE_CATEGORIES:
                return json_dumps({"error": f"الفئة غير صالحة. اختر من: {', '.join(TEMPLATE_CATEGORIES)}"})
            components = [{"type": "BODY", "text": body_text}]
            if header_text:
                components.insert(0, {"type": "HEADER", "text": header_text})
            result = api_call(
                "POST",
                f"{_require_waba(waba_id)}/message_templates",
                {
                    "name": name,
                    "language": language,
                    "category": cat,
                    "components": _json.dumps(components),
                },
            )
            return json_dumps({"template_name": name, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "create_whatsapp_message_template"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_whatsapp_text_message(to: str, text: str, phone_number_id: str = "") -> str:
        """إرسال رسالة نصية واتساب (رقم المستخدم يجب أن يكون بدأ محادثة)."""
        try:
            if len(text) > WHATSAPP_MAX_TEXT_LENGTH:
                return json_dumps(
                    {"error": f"النص طويل جدًا ({len(text)} حرف). الحد الأقصى {WHATSAPP_MAX_TEXT_LENGTH}."}
                )
            result = api_call(
                "POST",
                f"{_require_phone(phone_number_id)}/messages",
                {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text},
                },
            )
            return json_dumps({"to": to, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "send_whatsapp_text_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_whatsapp_template_message(
        to: str,
        template_name: str,
        language: str = "ar",
        phone_number_id: str = "",
        body_params_json: str = "",
    ) -> str:
        """إرسال قالب رسالة واتساب معتمد. body_params_json: مصفوفة JSON من النصوص."""
        try:
            template: dict = {"name": template_name, "language": {"code": language}}
            if body_params_json:
                params = _json.loads(body_params_json)
                if not isinstance(params, list):
                    return json_dumps({"error": "body_params_json يجب أن يكون مصفوفة JSON"})
                template["components"] = [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": str(p)} for p in params],
                    }
                ]
            result = api_call(
                "POST",
                f"{_require_phone(phone_number_id)}/messages",
                {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": template,
                },
            )
            return json_dumps({"to": to, "template_name": template_name, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "send_whatsapp_template_message"))
