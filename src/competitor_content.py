"""Competitor content tools: resolve post URLs, download top posts, analyse cadence.

These three tools close the loop that `competitors.py` leaves open — once you
know *who* the competitor is, these answer *what content works* for them:

- ``resolve_instagram_post_url``  : a post link -> author, stats, caption, media id
- ``download_top_competitor_posts``: rank a competitor's recent posts by engagement
  and download the winning images for reference
- ``analyze_competitor_cadence``  : posting frequency + engagement by media type/day

Public-data notes:
- Post pages are read as anonymous public HTML (og: meta tags) with an oEmbed
  fallback; no login and no write permissions are involved.
- Account media comes from the Instagram **Business Discovery** API, which needs
  our own account to be an Instagram *business* account (FB_IG_USER_ID).
- Downloaded images are **reference material for competitive analysis only** —
  never republish another brand's creative.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import requests  # type: ignore[import-untyped]

from src.core.config import INSTAGRAM_BUSINESS_ID
from src.throttle import concurrency_limit
from src.utils import api_call, handle_error, json_dumps

logger = logging.getLogger(__name__)

MEDIA_DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "media"

# Browser-ish headers: Instagram serves the public post shell (with og: meta
# tags) to real browsers and a stripped page to bare clients.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

_REFERENCE_ONLY_NOTE = "للتحليل التنافسي فقط — لا تعِد نشر صور المنافسين (حقوق النشر)"


def parse_ts(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_business_media(handle: str, pages: int = 3, page_size: int = 50) -> list:
    """Fetch a competitor's media via Business Discovery, paginating up to `pages`.

    Returns [] (not an error) when the account is not a business account or the
    handle is wrong — callers surface that as an error envelope.
    """
    collected: list = []
    cursor = ""
    for _ in range(max(1, pages)):
        after = f".after({cursor})" if cursor else ""
        fields = (
            f"business_discovery.username({handle})"
            f"{{username,name,followers_count,media.limit({page_size}){after}"
            "{id,caption,permalink,timestamp,like_count,comments_count,media_type}}"
        )
        data = api_call("GET", INSTAGRAM_BUSINESS_ID, {"fields": fields})
        biz = data.get("business_discovery") or {}
        media = (biz.get("media") or {}).get("data", [])
        if not media:
            break
        collected.extend(media)
        cursor = ((biz.get("media") or {}).get("paging") or {}).get("cursors", {}).get("after", "")
        if not cursor:
            break
    # de-duplicate (overlapping pages are possible)
    unique = {}
    for m in collected:
        unique[m.get("id")] = m
    return list(unique.values())


def oembed_image(permalink: str) -> str:
    """Resolve a public post permalink to its CDN image URL via the oEmbed API."""
    r = requests.get(
        "https://www.instagram.com/api/v1/oembed/",
        params={"url": permalink},
        headers=_HEADERS,
        timeout=40,
    )
    r.raise_for_status()
    return r.json().get("thumbnail_url") or ""


def download_image(url: str, target: Path) -> int:
    """Download an image, trying a larger CDN rendition first. Returns bytes."""
    larger = re.sub(r"p\d+x\d+", "p1080x1080", url)
    for candidate in (larger, url):
        try:
            r = requests.get(candidate, headers=_HEADERS, timeout=90)
            if r.status_code == 200 and len(r.content) > 1000:
                target.write_bytes(r.content)
                return len(r.content)
        except Exception:
            continue
    return 0


def register(mcp, services):
    """Register competitor-content tools."""

    @mcp.tool()
    @concurrency_limit()
    def resolve_instagram_post_url(url: str) -> str:
        """تحليل رابط منشور إنستغرام عام → صاحب الحساب والإحصائيات والكابشن.

        url: رابط المنشور (مثل https://www.instagram.com/p/DZdfUbVOqha/)
        يرجّع: اسم الحساب، معرّف المنشور، الإعجابات والتعليقات، التاريخ، الكابشن،
        ورابط الصورة — ثم استخدم discover_instagram_business(username) لتحليل الحساب كاملاً.
        يعمل بدون أي صلاحيات خاصة (بيانات عامة فقط).
        """
        try:
            if not url or "instagram.com" not in url:
                return json_dumps({"error": "أدخل رابط إنستغرام صالحاً (يحتوي instagram.com)"})
            from src.services.competitor_content_service import CompetitorContentService
            svc = CompetitorContentService(services)
            data = svc.resolve_post_url(url)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "resolve_instagram_post_url"))

    @mcp.tool()
    @concurrency_limit()
    def download_top_competitor_posts(
        handle: str,
        days: int = 30,
        top_n: int = 10,
        out_dir: str = "",
    ) -> str:
        """تنزيل أفضل منشورات منافس (مرتّبة بالتفاعل) خلال فترة — للتحليل التنافسي.

        handle: اسم حساب إنستغرام بدون @ (مثل elegant.po1)
        days: نافذة الفلترة بالأيام (افتراضي 30)
        top_n: عدد المنشورات المطلوبة (1-25)
        out_dir: مجلد الوجهة (افتراضي media/competitors/<handle>)

        يجلب المنشورات عبر Business Discovery، يفلترها بالنافذة الزمنية، يرتّبها
        بـ (إعجابات + تعليقات)، ثم ينزّل صورتها الأصلية + ملف manifest.json
        يحوي الكابشن والروابط. ⚠️ مرجع للتحليل فقط — لا تُعَد نشره.
        """
        try:
            if not handle:
                return json_dumps({"error": "handle مطلوب"})
            if days <= 0 or top_n <= 0:
                return json_dumps({"error": "days و top_n يجب أن تكون أكبر من صفر"})
            if top_n > 25:
                return json_dumps({"error": "الحد الأقصى 25 منشور للتنزيل الواحد"})
            from src.services.competitor_content_service import CompetitorContentService
            svc = CompetitorContentService(services)
            data = svc.download_top_posts(handle, days, top_n, out_dir)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "download_top_competitor_posts"))

    @mcp.tool()
    @concurrency_limit()
    def analyze_competitor_cadence(handle: str, days: int = 30, pages: int = 3) -> str:
        """تحليل وتيرة نشر منافس وأداء كل نوع محتوى (فيديو/كاروسيل/صورة).

        handle: اسم حساب إنستغرام بدون @
        days: النافذة بالأيام (افتراضي 30)
        pages: عدد صفحات الجلب (50 منشور/صفحة — الحد الأقصى لـ Business Discovery)

        يرجّع: منشورات/يوم، متوسط التفاعل لكل يوم، ومتوسط + أقصى تفاعل لكل نوع
        محتوى — لكشف ما يعمل فعلاً (مثلاً: صورة مفردة vs كاروسيل vs فيديو).
        """
        try:
            from src.services.competitor_content_service import CompetitorContentService
            svc = CompetitorContentService(services)
            data = svc.analyze_cadence(handle, days, pages)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "analyze_competitor_cadence"))

    @mcp.resource("competitor-content://overview")
    async def competitor_content_resource() -> str:
        """نظرة عامة على محتوى المنافسين."""
        try:
            return json_dumps(
                {
                    "module": "competitor_content",
                    "resource": "competitor-content://overview",
                    "tools": [
                        "resolve_instagram_post_url",
                        "download_top_competitor_posts",
                        "analyze_competitor_cadence",
                    ],
                    "workflow": "رابط منشور → resolve → تحليل الحساب → cadence → تنزيل أفضل المنشورات",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "competitor-content://overview"))

    @mcp.prompt()
    def competitor_content_prompt(topic: str = "competitor_content") -> str:
        """تحليل محتوى منافس."""
        return (
            f"ساعد في تحليل محتوى منافس لـ {topic} — قارن أنواع المحتوى (فيديو/كاروسيل/صورة) "
            "والتفاعل لكل نوع، ثم اقترح 3 تحسينات لمحتوى صفحتنا"
        )

    @mcp.resource("competitor-content://templates")
    async def competitor_content_extra_resource() -> str:
        """قوالب تحليل المنافسين."""
        try:
            return json_dumps(
                {
                    "module": "competitor_content",
                    "resource": "competitor-content://templates",
                    "steps": [
                        "resolve_instagram_post_url(url) — من رابط إلى اسم حساب",
                        "discover_instagram_business(username) — تحليل الحساب",
                        "analyze_competitor_cadence(handle) — ما النوع الأفضل تفاعلاً",
                        "download_top_competitor_posts(handle) — تنزيل الأفضل كمرجع",
                    ],
                    "note": _REFERENCE_ONLY_NOTE,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "competitor-content://templates"))

    @mcp.prompt()
    def competitor_post_breakdown_prompt(url: str = "") -> str:
        """تفكيك منشور منافس."""
        return (
            f"فكّك منشور المنافس ({url or 'رابط'}) — السعر، الضمان، الندرة، نوع المحتوى، "
            "وزراعة نفس العناصر في منشورنا القادم (وحدة competitor_content)"
        )
