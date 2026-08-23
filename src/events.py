"""Webhook event integration: bridge between webhook receiver and MCP tools.

Provides MCP tools to query received webhook events, and an in-memory event
queue that the webhook server can push to for real-time processing.
"""

import contextlib
import json
import logging
import threading
from datetime import datetime, timezone

from src.config import REPORT_DIR

logger = logging.getLogger(__name__)

# Thread-safe event queue for real-time webhook events
_event_lock = threading.Lock()
_event_queue: list[dict] = []
_MAX_QUEUE = 500


def push_webhook_event(event: dict) -> None:
    """Called by the webhook server to enqueue an event for MCP tools."""
    with _event_lock:
        event["_queued_at"] = datetime.now(timezone.utc).isoformat()
        _event_queue.append(event)
        if len(_event_queue) > _MAX_QUEUE:
            _event_queue.pop(0)


def get_queued_events(limit: int = 50) -> list[dict]:
    """Return recent queued events without consuming them."""
    with _event_lock:
        return list(_event_queue[-limit:])


def pop_queued_events(limit: int = 50) -> list[dict]:
    """Return and remove the most recent queued events (up to limit)."""
    with _event_lock:
        events = list(_event_queue[-limit:])
        for e in events:
            with contextlib.suppress(ValueError):
                _event_queue.remove(e)
        return events


def load_saved_events(limit: int = 50) -> list[dict]:
    """Load events from the reports/webhooks/ directory (most recent first)."""
    webhook_dir = REPORT_DIR / "webhooks"
    if not webhook_dir.exists():
        return []
    files = sorted(webhook_dir.glob("event_*.json"), reverse=True)[:limit]
    events = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = f.name
            events.append(data)
        except Exception as e:
            logger.warning("Failed to load webhook event %s: %s", f.name, e)
    return events


def register(mcp):
    """Register webhook integration tools."""

    from src.helpers import json_dumps
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def get_webhook_events(limit: int = 50, source: str = "both") -> str:
        """
        استقبال أحداث Webhook المخزنة (من الذاكرة أو الملفات).
        source: queue (ال-events المخزنة في الذاكرة فقط) | saved (الملفات) | both (الاثنان).
        """
        try:
            events = []
            if source in ("queue", "both"):
                events.extend(get_queued_events(limit))
            if source in ("saved", "both"):
                saved = load_saved_events(limit)
                existing_ids = {e.get("id") for e in events}
                for s in saved:
                    if s.get("id") not in existing_ids:
                        events.append(s)
            return json_dumps(
                {
                    "events": events[:limit],
                    "count": len(events[:limit]),
                }
            )
        except Exception as e:
            return json_dumps({"error": str(e)})

    @mcp.tool()
    @concurrency_limit()
    def pop_webhook_events(limit: int = 50) -> str:
        """
        استخراج أحداث Webhook من الذاكرة (تُحذف بعد الاستخراج).
        مفيد للمعالجةBitConverter.
        """
        try:
            events = pop_queued_events(limit)
            return json_dumps(
                {
                    "events": events,
                    "count": len(events),
                }
            )
        except Exception as e:
            return json_dumps({"error": str(e)})

    @mcp.tool()
    @concurrency_limit()
    def get_webhook_event_count() -> str:
        """عدد أحداث Webhook المخزنة حالياً في الذاكرة والملفات."""
        try:
            queue_count = len(_event_queue)
            webhook_dir = REPORT_DIR / "webhooks"
            file_count = len(list(webhook_dir.glob("event_*.json"))) if webhook_dir.exists() else 0
            return json_dumps(
                {
                    "queued": queue_count,
                    "saved_files": file_count,
                    "total": queue_count + file_count,
                }
            )
        except Exception as e:
            return json_dumps({"error": str(e)})
