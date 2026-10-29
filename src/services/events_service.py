"""Events service (Phase B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.services import Services
from src.events import _event_queue, get_queued_events, load_saved_events, pop_queued_events


class EventsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def get_webhook_events(self, limit: int = 50, source: str = "both") -> dict[str, Any]:
        events = []
        if source in ("queue", "both"):
            events.extend(get_queued_events(limit))
        if source in ("saved", "both"):
            saved = load_saved_events(limit)
            existing_ids = {e.get("id") for e in events}
            for s in saved:
                if s.get("id") not in existing_ids:
                    events.append(s)
        return {"events": events[:limit], "count": len(events[:limit])}

    def pop_webhook_events(self, limit: int = 50) -> dict[str, Any]:
        events = pop_queued_events(limit)
        return {"events": events, "count": len(events)}

    def get_event_count(self) -> dict[str, Any]:
        queue_count = len(_event_queue)
        report_dir = self.config.report_dir or Path("reports")
        webhook_dir = report_dir / "webhooks"
        file_count = len(list(webhook_dir.glob("event_*.json"))) if webhook_dir.exists() else 0
        return {"queued": queue_count, "saved_files": file_count, "total": queue_count + file_count}
