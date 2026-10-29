"""Messenger service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services


class MessengerService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _pid(self, page_id: str) -> str:
        return page_id or self.config.page_id

    def list_conversations(self, page_id: str = "", limit: int = 25) -> Any:
        from src.messenger import CONVERSATION_FIELDS
        return self.api.page_get(f"{self._pid(page_id)}/conversations", {"fields": CONVERSATION_FIELDS, "limit": limit})

    def get_conversation(self, conversation_id: str) -> Any:
        from src.messenger import CONVERSATION_FIELDS
        return self.api.page_get(conversation_id, {"fields": CONVERSATION_FIELDS})

    def list_conversation_messages(self, conversation_id: str, limit: int = 25) -> Any:
        from src.messenger import MESSAGE_FIELDS
        return self.api.page_get(f"{conversation_id}/messages", {"fields": MESSAGE_FIELDS, "limit": limit})

    def get_message(self, message_id: str) -> Any:
        from src.messenger import MESSAGE_FIELDS
        return self.api.page_get(message_id, {"fields": MESSAGE_FIELDS})

    def send_message(self, recipient_id: str, text: str, page_id: str = "") -> Any:
        from src.messenger import MESSENGER_MAX_TEXT_LENGTH
        if len(text) > MESSENGER_MAX_TEXT_LENGTH:
            return {"error": f"النص طويل جدًا ({len(text)} حرف). الحد الأقصى {MESSENGER_MAX_TEXT_LENGTH}."}
        result = self.api.page_post(self._pid(page_id), {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        })
        return {"recipient_id": recipient_id, "result": result}

    def mark_seen(self, recipient_id: str, page_id: str = "") -> Any:
        result = self.api.page_post(self._pid(page_id), {
            "recipient": {"id": recipient_id},
            "sender_action": "mark_seen",
        })
        return {"recipient_id": recipient_id, "result": result}

    def set_typing(self, recipient_id: str, typing: bool = True, page_id: str = "") -> Any:
        action = "typing_on" if typing else "typing_off"
        result = self.api.page_post(self._pid(page_id), {
            "recipient": {"id": recipient_id},
            "sender_action": action,
        })
        return {"recipient_id": recipient_id, "action": action, "result": result}
