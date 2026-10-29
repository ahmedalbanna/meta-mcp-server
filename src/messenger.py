"""Messenger page inbox: conversations, messages and replies (Messenger Platform API).

All calls use the page-scoped access token (page_api_call).
"""

import logging

from src.config import PAGE_ID

logger = logging.getLogger(__name__)
from src.helpers import handle_error, json_dumps, write_guard
from src.throttle import concurrency_limit

MESSENGER_MAX_TEXT_LENGTH = 2000

CONVERSATION_FIELDS = "id,updated_time,message_count,unread_count,participants,can_reply,last_used_tag"
MESSAGE_FIELDS = "id,message,created_time,from,to,sticker,attachments"


def register(mcp, services=None):
    """Register Messenger inbox tools (raw Graph API, page token)."""

    def _pid(page_id: str) -> str:
        return page_id or PAGE_ID

    @mcp.tool()
    @concurrency_limit()
    def list_conversations(page_id: str = "", limit: int = 25) -> str:
        """محادثات الصفحة على Messenger (الوارد)."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            data = svc.list_conversations(page_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_conversations"))

    @mcp.tool()
    @concurrency_limit()
    def get_conversation(conversation_id: str) -> str:
        """تفاصيل محادثة Messenger واحدة."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            data = svc.get_conversation(conversation_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_conversation"))

    @mcp.tool()
    @concurrency_limit()
    def list_conversation_messages(conversation_id: str, limit: int = 25) -> str:
        """رسائل محادثة Messenger محددة."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            data = svc.list_conversation_messages(conversation_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_conversation_messages"))

    @mcp.tool()
    @concurrency_limit()
    def get_messenger_message(message_id: str) -> str:
        """رسالة Messenger واحدة (نص، مرفقات، أطراف)."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            data = svc.get_message(message_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_messenger_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_messenger_message(recipient_id: str, text: str, page_id: str = "") -> str:
        """إرسال رد عبر Messenger إلى المستخدم الذي بدأ المحادثة."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            return json_dumps(svc.send_message(recipient_id, text, page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "send_messenger_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def mark_messenger_seen(recipient_id: str, page_id: str = "") -> str:
        """وضع علامة "تمت القراءة" على رسائل المستخدم (mark_seen)."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            return json_dumps(svc.mark_seen(recipient_id, page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "mark_messenger_seen"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def set_messenger_typing(recipient_id: str, typing: bool = True, page_id: str = "") -> str:
        """إرسال مؤشر الكتابة (typing_on/typing_off) داخل محادثة Messenger."""
        try:
            from src.core.services import Services
            from src.services.messenger_service import MessengerService
            svc = MessengerService(services) if services is not None else MessengerService(Services.default())
            return json_dumps(svc.set_typing(recipient_id, typing, page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "set_messenger_typing"))

    @mcp.resource("messenger://overview")
    async def messenger_resource() -> str:
        """نظرة عامة ماسنجر."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "messenger", "resource": "messenger://overview", "hint": "نظرة عامة ماسنجر"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "messenger://overview"))

    @mcp.prompt()
    def messenger_reply_prompt(topic: str = "messenger") -> str:
        """رد ماسنجر."""
        return "ساعد في رد ماسنجر لـ " + topic + " — اكتب رد ماسنجر لـ {message} (وحدة messenger)"

    @mcp.resource("messenger://templates")
    async def messenger_extra_resource() -> str:
        """قوالب ماسنجر."""
        try:
            return json_dumps({"module": "messenger", "resource": "messenger://templates", "hint": "قوالب ماسنجر"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "messenger://templates"))

    @mcp.prompt()
    def messenger_template_prompt(topic: str = "messenger") -> str:
        """قالب ماسنجر."""
        return "ساعد في قالب ماسنجر لـ " + topic + " — أنشئ قالب ماسنجر لـ {topic} (وحدة messenger)"
