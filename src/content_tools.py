"""Content creation & optimization tools — captions, timing, calendar, hashtags.

These close the loop between *research* (competitors) and *publishing* (posts):
generate captions, find the best posting time, plan a content calendar, and
analyze which hashtags actually perform for our own account.
"""

import logging
from datetime import datetime, timezone

from src.core.config import PAGE_ID
from src.llm import call_llm
from src.throttle import concurrency_limit
from src.utils import handle_error, json_dumps, page_api_call

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400


def _parse_ts(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _fetch_our_posts(limit: int = 100, with_message: bool = False) -> tuple[list, str | None]:
    """Recent posts of OUR page via the page-scoped token."""
    fields = "id,created_time" + (",message" if with_message else "")
    try:
        data = page_api_call("GET", f"{PAGE_ID}/published_posts", {"fields": fields, "limit": limit})
        return (data.get("data") or []), None
    except Exception as e:
        return [], str(e)[:200]


def _post_engagement(post_id: str) -> int:
    """Reactions + comments for one of our posts (0 when unavailable)."""
    try:
        data = page_api_call(
            "GET", post_id, {"fields": "reactions.limit(0).summary(true),comments.limit(0).summary(true)"}
        )
        if not isinstance(data, dict):
            return 0
        reacts = (((data.get("reactions") or {}).get("summary") or {}).get("total_count")) or 0
        comms = (((data.get("comments") or {}).get("summary") or {}).get("total_count")) or 0
        return reacts + comms
    except Exception:
        return 0


def register(mcp, services):
    """Register content-creation & optimization tools."""

    @mcp.tool()
    @concurrency_limit()
    def generate_post_caption(
        product: str,
        price: float = 0.0,
        old_price: float = 0.0,
        warranty: str = "",
        style: str = "sales",
        language: str = "ar",
        include_hashtags: bool = True,
        product_type: str = "jewelry",
    ) -> str:
        """توليد كابشن إنستغرام/فيسبوك جاهز لمنشور (عربي/إنجليزي)."""
        try:
            from src.core.services import Services
            from src.services.content_tools_service import ContentToolsService

            svc = ContentToolsService(services)
            out = svc.generate_post_caption(
                product, price, old_price, warranty, style, language, include_hashtags, product_type
            )
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "generate_post_caption"))

    @mcp.tool()
    @concurrency_limit()
    def best_posting_time(days: int = 30, metric: str = "engagement") -> str:
        """تحليل متى ننشر للحصول على أعلى تفاعل (من منشورات صفحتنا)."""
        try:
            from src.core.services import Services
            from src.services.content_tools_service import ContentToolsService

            svc = ContentToolsService(services)
            data = svc.best_posting_time(days, metric)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "best_posting_time"))

    @mcp.tool()
    @concurrency_limit()
    def hashtag_analyzer(days: int = 60) -> str:
        """تحليل أي هاشتاغات تجلب أعلى تفاعل (من منشورات صفحتنا)."""
        try:
            from src.core.services import Services
            from src.services.content_tools_service import ContentToolsService

            svc = ContentToolsService(services)
            out = svc.hashtag_analyzer(days)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "hashtag_analyzer"))

    @mcp.tool()
    @concurrency_limit()
    def content_calendar(week_start: str = "", posts_per_week: int = 5, include_stories: bool = True) -> str:
        """توليد تقويم محتوى لـ 7 أيام."""
        try:
            from src.core.services import Services
            from src.services.content_tools_service import ContentToolsService

            svc = ContentToolsService(services)
            out = svc.content_calendar(week_start, posts_per_week, include_stories)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "content_calendar"))

    @mcp.tool()
    @concurrency_limit()
    def auto_reply_comments(
        keyword: str,
        reply: str,
        page_id: str = "",
        enabled: bool = True,
    ) -> str:
        """إعداد رد تلقائي على تعليقات."""
        try:
            from src.core.services import Services
            from src.services.content_tools_service import ContentToolsService

            svc = ContentToolsService(services)
            out = svc.auto_reply_comments(keyword, reply, page_id, enabled)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "auto_reply_comments"))

    @mcp.resource("content-tools://overview")
    async def content_tools_resource() -> str:
        return json_dumps(
            {
                "module": "content_tools",
                "resource": "content-tools://overview",
                "tools": [
                    "generate_post_caption",
                    "best_posting_time",
                    "hashtag_analyzer",
                    "content_calendar",
                    "auto_reply_comments",
                ],
            }
        )

    @mcp.prompt()
    def content_tools_prompt(topic: str = "content") -> str:
        return (
            f"ساعد في إنشاء محتوى لـ {topic} — generate_post_caption(product=...) ثم "
            "best_posting_time() لاختيار الوقت، ثم content_calendar() للتخطيط (وحدة content_tools)"
        )

    @mcp.resource("content-tools://templates")
    async def content_tools_extra_resource() -> str:
        return json_dumps(
            {
                "module": "content_tools",
                "resource": "content-tools://templates",
                "weekly_plan": "5 منشورات/أسبوع (2 فيديو + 2 كاروسيل + 1 ستوري)",
                "rules": ["لا صور مفردة", "السعر على الصورة", "ضمان سنة", "3-5/أسبوع"],
            }
        )

    @mcp.prompt()
    def content_plan_prompt(product: str = "") -> str:
        return (
            f"خطط 7 أيام منشورات لـ {product or 'Butterfly'} — استخدم content_calendar() ثم "
            "generate_post_caption() لكل منشور (وحدة content_tools)"
        )


def _content_idea(i: int, post_type: str) -> str:
    ideas = {
        0: "طقم رئيسي (كارتير/ديور) — فيديو فتح + سعر + ضمان",
        1: "تفاصيل close-up — ماكرو للتشطيب + 'ضمان سنة'",
        2: " behind-the-scenes — صنع/تغليف + CTA",
        3: "عرض نهاية الأسبوع — خصم ٢٤→٧ (كمية محدودة)",
        4: "شهادة عميلة (UGC) + صورة على الموديل",
        5: "تشكيلة المحل — 3-5 أطقم على مانيكينات",
        6: "ستوري: 'آخر يوم للعرض' + شريط السعر",
    }
    return ideas.get(i, "منشور إضافي")


def _story_idea(i: int) -> str:
    ideas = {
        0: "ستوري: 'صباح الخير — ما جديد اليوم' + صورة منتج",
        1: "ستوري: استطلاع 'أي لون تفضلين؟' (ذهبي/فضي)",
        2: "ستوري: 'الكمية محدودة' (countdown)",
        3: "ستوري: 'آخر يوم للعرض' + link",
        4: "ستوري: behind-the-scenes (تغليف)",
        5: "ستوري: 'شكراً للعميلات' + repost",
        6: "ستوري: 'أسبوع جديد — ما awaiting'",
    }
    return ideas.get(i, "ستوري إضافي")
