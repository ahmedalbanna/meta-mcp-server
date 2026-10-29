"""Reports service (Phase B)."""

from __future__ import annotations

from src.core.services import Services
from src.reports import IG_MEDIA_METRICS


class ReportsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def fetch_campaign_rows(self, object_id: str, preset: str, metrics: list) -> list:
        data = self.api.get(f"{object_id}/insights",
                            {"date_preset": preset, "fields": ["campaign_name", *metrics]})
        rows = []
        for item in data.get("data", []) if isinstance(data, dict) else []:
            row = {"campaign_name": item.get("campaign_name", "N/A")}
            for m in metrics:
                row[m] = item.get(m, 0)
            rows.append(row)
        return rows

    def fetch_instagram_report_rows(self, limit: int = 25) -> list:
        from src.config import INSTAGRAM_BUSINESS_ID, REPORT_DIR  # noqa
        from pathlib import Path  # noqa
        ig = self.config.instagram_business_id
        media = self.api.get(f"{ig}/media",
                             {"fields": "id,caption,media_type,timestamp,permalink", "limit": limit})
        rows = []
        for item in media.get("data", []) if isinstance(media, dict) else []:
            mid = item.get("id")
            caption = item.get("caption", "")
            row = {"id": mid, "caption": caption, "media_type": item.get("media_type", ""),
                   "timestamp": item.get("timestamp", ""), "permalink": item.get("permalink", "")}
            try:
                insights = self.api.get(f"{mid}/insights", {"metric": ",".join(IG_MEDIA_METRICS)})
                for ins in insights.get("data", []) if isinstance(insights, dict) else []:
                    name = ins.get("name", "")
                    values = ins.get("values", [])
                    row[name] = values[-1].get("value", 0) if values else 0
            except Exception:
                pass
            rows.append(row)
        return rows
