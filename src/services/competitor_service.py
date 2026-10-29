"""Competitor service — business logic extracted (Phase B)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.services import Services
from src.persistence import query_competitor_snapshots, upsert_competitor_snapshot


class CompetitorService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _extract_price(self, caption: str) -> float | None:
        import re

        text = (caption or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        m = re.search(r"(\d[\d.,]*)\s*(?:الف|ألف)", text)
        if m:
            try:
                return round(float(m.group(1).replace(",", "")) * 1000, 2)
            except ValueError:
                pass
        m = re.search(r"(\d[\d.,]*)\s*(?:ريال|ر\.ي|YER)", text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    def snapshot(self, handle: str, platform: str = "instagram", days: int = 30) -> dict[str, Any]:
        handle = (handle or "").strip().lstrip("@")
        if not handle:
            raise ValueError("handle مطلوب")
        platform = (platform or "instagram").strip().lower()
        snapshot_date = datetime.now(timezone.utc).date().isoformat()

        if platform == "instagram":
            if not self.config.instagram_business_id:
                raise ValueError("FB_IG_USER_ID غير مضبوط")
            import re as _re

            if not _re.match(r"^[A-Za-z0-9._]{1,30}$", handle):
                raise ValueError(f"handle غير صالح: {handle!r}")
            ig = self.api.get(
                self.config.instagram_business_id,
                {
                    "fields": (
                        f"business_discovery.username({handle})"
                        "{username,name,biography,followers_count,media_count,"
                        "media.limit(12){id,caption,permalink,timestamp,like_count,comments_count,media_type}}"
                    ),
                },
            )
            biz = ig.get("business_discovery") or {}
            media = (biz.get("media") or {}).get("data", [])
            likes = [m.get("like_count") or 0 for m in media]
            comments = [m.get("comments_count") or 0 for m in media]
            prices = [p for p in (self._extract_price(m.get("caption") or "") for m in media) if p is not None]
            payload = {
                "platform": platform,
                "handle": handle,
                "username": biz.get("username"),
                "name": biz.get("name"),
                "followers": biz.get("followers_count"),
                "media_count": biz.get("media_count"),
                "analysed_media": len(media),
                "avg_likes": round(sum(likes) / len(likes), 1) if likes else 0,
                "avg_comments": round(sum(comments) / len(comments), 1) if comments else 0,
                "engagement_total": sum(likes) + sum(comments),
                "prices_found": prices,
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
            }
        elif platform == "facebook":
            # reuse page profile via api
            data = self.api.get(handle, {"fields": "name,fan_count,category,link,about"})
            payload = {"platform": platform, "handle": handle, **(data if isinstance(data, dict) else {})}
        else:
            raise ValueError(f"platform غير مدعوم: {platform}")

        upsert_competitor_snapshot(platform, handle, snapshot_date, payload)
        return {"snapshot_date": snapshot_date, "platform": platform, "handle": handle, "payload": payload}

    def list_snapshots(self, handle: str, platform: str = "instagram", limit: int = 10) -> dict[str, Any]:
        handle = (handle or "").strip().lstrip("@")
        rows = query_competitor_snapshots(platform, handle, limit=max(1, min(limit, 50)))
        return {"platform": platform, "handle": handle, "count": len(rows), "snapshots": rows}

    def diff(self, handle: str, platform: str = "instagram") -> dict[str, Any]:
        handle = (handle or "").strip().lstrip("@")
        rows = query_competitor_snapshots(platform, handle, limit=2)
        if len(rows) < 2:
            raise ValueError("أقل من لقطتين — شغّل snapshot_competitor مرتين على الأقل")
        latest = rows[0]["payload"]
        prev = rows[1]["payload"]

        def num_diff(a, b):
            if a is None or b is None:
                return None
            try:
                return round(float(a) - float(b), 4)
            except (TypeError, ValueError):
                return None

        return {
            "handle": handle,
            "platform": platform,
            "latest_date": rows[0]["snapshot_date"],
            "previous_date": rows[1]["snapshot_date"],
            "followers_change": num_diff(latest.get("followers"), prev.get("followers")),
            "engagement_change": num_diff(latest.get("engagement_total"), prev.get("engagement_total")),
            "avg_likes_change": num_diff(latest.get("avg_likes"), prev.get("avg_likes")),
            "price_min_change": num_diff(latest.get("price_min"), prev.get("price_min")),
            "price_max_change": num_diff(latest.get("price_max"), prev.get("price_max")),
        }

    def search_business_pages(
        self, query: str, city: str = "", limit: int = 25, exclude_our_page: bool = True
    ) -> dict[str, Any]:
        parts = [p.strip() for p in (query, city) if p and p.strip()]
        q = " ".join(parts)
        if not q:
            raise ValueError("حدد كلمة مفتاحية (query) على الأقل")
        data = self.api.get(
            "search",
            {
                "q": q,
                "type": "page",
                "fields": "name,id,fan_count,category,link,verification_status",
                "limit": max(1, min(limit, 50)),
            },
        )
        rows = data.get("data", []) if isinstance(data, dict) else []
        if exclude_our_page and self.config.page_id:
            rows = [r for r in rows if str(r.get("id")) != str(self.config.page_id)]
        return {"query": q, "count": len(rows), "results": rows}
