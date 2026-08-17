"""Messenger page inbox: conversations, messages and replies (Messenger Platform API).

All calls use the page-scoped access token (page_api_call).
"""

from src.config import PAGE_ID
from src.helpers import handle_error, json_dumps, page_api_call, write_guard
from src.throttle import concurrency_limit

CONVERSATION_FIELDS = (
    "id,updated_time,message_count,unread_count,participants,can_reply,last_used_tag"
)
MESSAGE_FIELDS = "id,message,created_time,from,to,sticker,attachments"


def register(mcp):
    """Register Messenger inbox tools (raw Graph API, page token)."""

    def _pid(page_id: str) -> str:
        return page_id or PAGE_ID

    @mcp.tool()
    @concurrency_limit()
    def list_conversations(page_id: str = "", limit: int = 25) -> str:
        """محادثات الصفحة على Messenger (الوارد)."""
        try:
            data = page_api_call(
                "GET",
                f"{_pid(page_id)}/conversations",
                {"fields": CONVERSATION_FIELDS, "limit": limit},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_conversations"))

    @mcp.tool()
    @concurrency_limit()
    def get_conversation(conversation_id: str) -> str:
        """تفاصيل محادثة Messenger واحدة."""
        try:
            data = page_api_call(
                "GET",
                conversation_id,
                {"fields": CONVERSATION_FIELDS},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_conversation"))

    @mcp.tool()
    @concurrency_limit()
    def list_conversation_messages(conversation_id: str, limit: int = 25) -> str:
        """رسائل محادثة Messenger محددة."""
        try:
            data = page_api_call(
                "GET",
                f"{conversation_id}/messages",
                {"fields": MESSAGE_FIELDS, "limit": limit},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_conversation_messages"))

    @mcp.tool()
    @concurrency_limit()
    def get_messenger_message(message_id: str) -> str:
        """رسالة Messenger واحدة (نص، مرفقات، أطراف)."""
        try:
            data = page_api_call(
                "GET",
                message_id,
                {"fields": MESSAGE_FIELDS},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_messenger_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_messenger_message(recipient_id: str, text: str, page_id: str = "") -> str:
        """إرسال رد عبر Messenger إلى المستخدم الذي بدأ المحادثة."""
        try:
            if len(text) > 2000:
                return json_dumps({"error": f"النص طويل جدًا ({len(text)} حرف). الحد الأقصى 2000."})
            result = page_api_call(
                "POST",
                f"{_pid(page_id)}/messages",
                {
                    "recipient": {"id": recipient_id},
                    "messaging_type": "RESPONSE",
                    "message": {"text": text},
                },
            )
            return json_dumps({"recipient_id": recipient_id, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "send_messenger_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def mark_messenger_seen(recipient_id: str, page_id: str = "") -> str:
        """وضع علامة "تمت القراءة" على رسائل المستخدم (mark_seen)."""
        try:
            result = page_api_call(
                "POST",
                f"{_pid(page_id)}/messages",
                {
                    "recipient": {"id": recipient_id},
                    "sender_action": "mark_seen",
                },
            )
            return json_dumps({"recipient_id": recipient_id, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "mark_messenger_seen"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def set_messenger_typing(
        recipient_id: str, typing: bool = True, page_id: str = ""
    ) -> str:
        """إرسال مؤشر الكتابة (typing_on/typing_off) داخل محادثة Messenger."""
        try:
            action = "typing_on" if typing else "typing_off"
            result = page_api_call(
                "POST",
                f"{_pid(page_id)}/messages",
                {
                    "recipient": {"id": recipient_id},
                    "sender_action": action,
                },
            )
            return json_dumps(
                {"recipient_id": recipient_id, "action": action, "result": result}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "set_messenger_typing"))
