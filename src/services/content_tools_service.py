"""Content tools service (Phase B)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.content_tools import _fetch_our_posts, _parse_ts, _post_engagement
from src.core.services import Services

_WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


class ContentToolsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def best_posting_time(self, days: int = 30, metric: str = "engagement") -> Any:
        if days <= 0:
            return {"error": "days يجب أن تكون > 0"}
        posts, err = _fetch_our_posts(limit=100)
        if not posts:
            return {"error": err or "لا توجد منشورات", "metric": metric}
        rows: list[dict[str, Any]] = []
        for p in posts:
            cid = str(p.get("id") or "")
            dt = _parse_ts(p.get("created_time"))
            if not dt or not cid:
                continue
            rows.append({"dt": dt, "engagement": _post_engagement(cid)})
        if not rows:
            return {"error": "لا توجد منشورات", "metric": metric}
        buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for r in rows:
            key = (r["dt"].weekday(), r["dt"].hour)
            buckets[key].append(r["engagement"])
        slots: list[dict[str, Any]] = []
        for (wd, hr), vals in buckets.items():
            slots.append({
                "weekday": _WEEKDAYS[wd],
                "weekday_num": wd,
                "hour": hr,
                "hour_label": f"{hr:02d}:00",
                "posts": len(vals),
                "avg_engagement": round(sum(vals) / len(vals), 1),
                "total_engagement": sum(vals),
            })
        slots.sort(key=lambda s: (s["avg_engagement"], s["posts"]), reverse=True)
        best = slots[:5]
        worst = sorted(slots, key=lambda s: s["avg_engagement"])[:3]
        return {
            "analyzed_posts": len(rows),
            "best_slots": best,
            "worst_slots": worst,
            "recommendation": (
                f"انشر على {best[0]['weekday']} في {best[0]['hour_label']} "
                f"(متوسط تفاعل {best[0]['avg_engagement']})" if best else "لا توجد بيانات كافية"
            ),
            "note": "يُوصى بـ 3-5 منشورات/أسبوع في أفضل Slots (لا 6 في يوم واحد)",
        }
