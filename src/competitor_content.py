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

import html as html_lib
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests  # type: ignore[import-untyped]

from src.config import INSTAGRAM_BUSINESS_ID
from src.helpers import api_call, handle_error, json_dumps, sanitize_filename, sanitize_path
from src.throttle import concurrency_limit

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


def register(mcp):
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
            out: dict = {"url": url}

            # 1) oEmbed — reliable for author/author_id/media_id/caption/thumbnail
            #    (Instagram sometimes serves a stripped HTML shell to non-browsers)
            try:
                er = requests.get(
                    "https://www.instagram.com/api/v1/oembed/",
                    params={"url": url},
                    headers=_HEADERS,
                    timeout=40,
                )
                er.raise_for_status()
                embed = er.json()
                if embed.get("author_name"):
                    out["username"] = embed["author_name"]
                    out["author_url"] = embed.get("author_url")
                    out["author_id"] = embed.get("author_id")
                    out["media_id"] = embed.get("media_id")
                    out["caption"] = (embed.get("title") or "").strip()[:500]
                    out["image_url"] = embed.get("thumbnail_url")
                    out["image_size"] = [embed.get("thumbnail_width"), embed.get("thumbnail_height")]
                    out["source"] = "oembed"
            except Exception:
                pass

            # 2) HTML page — adds likes/comments/date + shortcode when served
            try:
                r = requests.get(url, headers=_HEADERS, timeout=40)
                r.raise_for_status()
                page = r.text
                m = re.search(
                    r'<meta property="og:url" content="https://www\.instagram\.com/([^/]+)/(p|reel)/([^/]+)/', page
                )
                if m:
                    out["username"] = out.get("username") or m.group(1)
                    out["shortcode"] = m.group(3)
                m = re.search(r"instagram://media\?id=(\d+)", page)
                if m:
                    out["media_id"] = out.get("media_id") or m.group(1)
                m = re.search(r'instapp:owner_user_id" content="(\d+)"', page)
                if m:
                    out["owner_user_id"] = m.group(1)
                m = re.search(
                    r'name="description" content="(\d[\d,]*) likes?, (\d[\d,]*) comments? - ([^ ]+) on ([^:]+): &quot;(.*?)&quot;',
                    page,
                    re.S,
                )
                if m:
                    out["likes"] = int(m.group(1).replace(",", ""))
                    out["comments"] = int(m.group(2).replace(",", ""))
                    out["date"] = m.group(4).strip()
                    if "source" in out:
                        out["source"] = "html+oembed"
                    else:
                        out["source"] = "html"
                m = re.search(r'<meta property="og:image" content="([^"]+)"', page)
                if m:
                    out["image_url"] = out.get("image_url") or html_lib.unescape(m.group(1))
            except Exception:
                pass

            if not out.get("username"):
                return json_dumps(
                    {
                        "error": "تعذّر استخراج بيانات المنشور — قد يكون محذوفاً أو خاصاً",
                        "url": url,
                    }
                )
            out["next_step"] = "discover_instagram_business(username) لتحليل الحساب كاملاً"
            return json_dumps(out)
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
            if not INSTAGRAM_BUSINESS_ID:
                return json_dumps({"error": "اضبط FB_IG_USER_ID في .env (حسابنا يجب أن يكون Instagram Business)"})

            media = fetch_business_media(handle.lstrip("@"))
            if not media:
                return json_dumps(
                    {
                        "error": f"لا توجد منشورات للحساب {handle} — تأكد أنه حساب أعمال/مبدعين عام والاسم صحيح",
                        "handle": handle,
                    }
                )

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            dated = []
            for m in media:
                dt = parse_ts(m.get("timestamp"))
                if dt and dt >= cutoff:
                    dated.append((dt, m))
            if not dated:
                stamps = [t for t in (parse_ts(m.get("timestamp")) for m in media) if t]
                return json_dumps(
                    {
                        "error": f"لا منشورات ضمن آخر {days} يوم (أقدم منشور متاح: {min(stamps):%Y-%m-%d} إن وُجد)",
                        "handle": handle,
                        "fetched": len(media),
                    }
                )

            ranked = sorted(
                dated,
                key=lambda x: (x[1].get("like_count") or 0) + (x[1].get("comments_count") or 0),
                reverse=True,
            )[:top_n]

            # destination: media/competitors/<handle> (path-sanitised)
            folder = f"competitors/{sanitize_filename(handle.lstrip('@'))}"
            target = (
                sanitize_path(out_dir, MEDIA_DOWNLOAD_DIR.parent)
                if out_dir
                else sanitize_path(folder, MEDIA_DOWNLOAD_DIR.parent)
            )
            target.mkdir(parents=True, exist_ok=True)

            manifest = []
            downloaded = 0
            for i, (dt, post) in enumerate(ranked, 1):
                shortcode = post["permalink"].rstrip("/").split("/")[-1]
                likes = post.get("like_count") or 0
                comments = post.get("comments_count") or 0
                entry = {
                    "rank": i,
                    "date": dt.strftime("%Y-%m-%d"),
                    "permalink": post.get("permalink"),
                    "likes": likes,
                    "comments": comments,
                    "media_type": post.get("media_type"),
                    "caption": (post.get("caption") or "")[:300],
                    "file": None,
                }
                try:
                    img = oembed_image(post["permalink"])
                    if img:
                        local = target / f"{i:02d}_{likes}likes_{shortcode}.jpg"
                        size = download_image(img, local)
                        if size:
                            entry["file"] = local.name
                            downloaded += 1
                except Exception as e:
                    entry["error"] = str(e)[:120]
                manifest.append(entry)

            (target / "manifest.json").write_text(
                __import__("json").dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return json_dumps(
                {
                    "handle": handle,
                    "window_days": days,
                    "fetched_posts": len(media),
                    "posts_in_window": len(dated),
                    "requested": top_n,
                    "downloaded": downloaded,
                    "out_dir": str(target),
                    "manifest": str(target / "manifest.json"),
                    "note": _REFERENCE_ONLY_NOTE,
                    "top_posts": [
                        {
                            "rank": m["rank"],
                            "date": m["date"],
                            "likes": m["likes"],
                            "comments": m["comments"],
                            "file": m["file"],
                            "caption": m["caption"],
                        }
                        for m in manifest
                    ],
                }
            )
        except ValueError as e:
            return json_dumps({"error": f"مسار غير صالح: {e}"})
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
            if not handle:
                return json_dumps({"error": "handle مطلوب"})
            if not INSTAGRAM_BUSINESS_ID:
                return json_dumps({"error": "اضبط FB_IG_USER_ID في .env"})
            media = fetch_business_media(handle.lstrip("@"), pages=max(1, min(pages, 6)))
            if not media:
                return json_dumps({"error": f"لا توجد منشورات للحساب {handle}"})

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            by_day: dict = defaultdict(list)
            by_type: dict = defaultdict(list)
            in_window = 0
            for m in media:
                dt = parse_ts(m.get("timestamp"))
                if not dt or dt < cutoff:
                    continue
                in_window += 1
                eng = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
                by_day[dt.strftime("%Y-%m-%d")].append(eng)
                by_type[m.get("media_type") or "UNKNOWN"].append(eng)

            if not in_window:
                return json_dumps({"error": f"لا منشورات ضمن آخر {days} يوم", "handle": handle, "fetched": len(media)})

            day_rows = sorted(
                (
                    {
                        "date": day,
                        "posts": len(vals),
                        "avg_engagement": round(sum(vals) / len(vals), 1),
                        "max_engagement": max(vals),
                    }
                    for day, vals in by_day.items()
                ),
                key=lambda r: r["avg_engagement"],
                reverse=True,
            )
            type_rows = sorted(
                (
                    {
                        "media_type": t,
                        "posts": len(vals),
                        "avg_engagement": round(sum(vals) / len(vals), 1),
                        "max_engagement": max(vals),
                    }
                    for t, vals in by_type.items()
                ),
                key=lambda r: r["avg_engagement"],
                reverse=True,
            )
            span_days = len(by_day) or 1
            return json_dumps(
                {
                    "handle": handle,
                    "window_days": days,
                    "fetched_posts": len(media),
                    "posts_in_window": in_window,
                    "active_days": span_days,
                    "avg_posts_per_active_day": round(in_window / span_days, 1),
                    "best_days": day_rows[:5],
                    "worst_days": day_rows[-3:],
                    "by_media_type": type_rows,
                    "insight": (
                        f"أفضل نوع: {type_rows[0]['media_type']} "
                        f"(متوسط {type_rows[0]['avg_engagement']}) — "
                        f"الأضعف: {type_rows[-1]['media_type']} "
                        f"(متوسط {type_rows[-1]['avg_engagement']})"
                        if len(type_rows) > 1
                        else "نوع محتوى واحد فقط في النافذة"
                    ),
                }
            )
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
