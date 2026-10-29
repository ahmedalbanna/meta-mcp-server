"""Competitive intelligence tools (أدوات استخبارات المنافسة).

Find pages/accounts similar to ours (by keyword + city), analyse any page we
can read (Facebook), discover any public Instagram business account, then
compare several competitors side by side.

Why these exist: the working/page tools in `pages.py` are scoped to pages the
token *manages* — nothing in the server answered "who else sells jewellery in
Sana'a and how are they doing?". These tools close that gap.

Permissions:
- Facebook page search uses ``GET /search?type=page``. Meta may require the
  **Page Public Content Access** feature for pages we do not manage; failures
  come back as a clear error envelope naming the missing permission/feature.
- Instagram discovery uses the **Business Discovery** API
  (``business_discovery.username(x){...}``), which requires the connected
  account to be an Instagram *business* account (FB_IG_USER_ID).
"""

import logging
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

from src.competitor_content import fetch_business_media
from src.config import INSTAGRAM_BUSINESS_ID, PAGE_ID
from src.hashtags import marketing_hashtags
from src.helpers import api_call, handle_error, json_dumps, page_api_call
from src.throttle import concurrency_limit

SECONDS_PER_DAY = 86400

# What Meta needs before we can read a page we do NOT manage.
_PPCA_HINT = (
    "قراءة صفحة لا نديرها تحتاج ميزة Page Public Content Access على التطبيق "
    "(App Review) — راجع خطأ الصلاحيات في partial_errors"
)

# Purchase-intent / CTA markers (Arabic + English) used to judge how
# "sales-ready" a competitor's posts are.
_CTA_MARKERS = (
    # عربي
    "للطلب",
    "اطلب",
    "اطلبي",
    "اطلبوا",
    "الطلب",
    "راسلنا",
    "تواصل",
    "خاص",
    "واتساب",
    "واتس",
    "راسل",
    "طلب",
    "توصيل",
    "شحن",
    "السعر",
    "ريال",
    "ريالاً",
    "خصم",
    "عرض",
    "هدية",
    "كتالوج",
    "الكمية",
    "نفاد",
    "محفظ",
    # إنجليزي
    "buy",
    "order",
    "dm",
    "message",
    "whatsapp",
    "delivery",
    "discount",
    "price",
    "shop",
    "cash on delivery",
    "cod",
)


# Instagram handles: 1-30 chars, letters/digits/dots/underscores only.
_IG_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def _parse_iso(ts) -> float | None:
    """Parse an ISO-8601 timestamp into a UTC epoch (None if unparseable)."""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _engagement_of(post: dict) -> dict:
    """Extract reaction/comment/share counts from a Graph API post object."""
    reactions = (((post.get("reactions") or {}).get("summary") or {}).get("total_count")) or 0
    comments = (((post.get("comments") or {}).get("summary") or {}).get("total_count")) or 0
    shares = (post.get("shares") or {}).get("count") or 0
    return {"reactions": reactions, "comments": comments, "shares": shares, "total": reactions + comments + shares}


def _content_signals(posts: list) -> dict:
    """Caption-level signals: length, hashtags, CTA usage, questions."""
    captions = [p.get("message") or "" for p in posts]
    if not captions:
        return {"posts_analysed": 0}
    hashtags: list[str] = []
    for cap in captions:
        hashtags.extend(marketing_hashtags(cap))
    top = Counter(h.lower() for h in hashtags).most_common(10)
    lowered = [c.lower() for c in captions]
    cta_posts = sum(1 for c in lowered if any(m in c for m in _CTA_MARKERS))
    questions = sum(1 for c in lowered if "؟" in c or "?" in c)
    total_len = sum(len(c) for c in captions)
    return {
        "posts_analysed": len(captions),
        "avg_caption_length": round(total_len / len(captions), 1),
        "top_hashtags": [{"tag": t, "count": n} for t, n in top],
        "posts_with_cta": cta_posts,
        "cta_ratio": round(cta_posts / len(captions), 2),
        "posts_with_question": questions,
    }


def _verdict(profile: dict) -> dict:
    """Turn a profile into a 0-100 activity score + qualitative level + notes."""
    score = 0
    notes: list[str] = []
    posts = profile.get("posts_in_window", 0)
    days_since = profile.get("days_since_last_post")
    eng_rate = profile.get("engagement_rate")

    # Cadence (30)
    if posts >= 8:
        score += 30
    elif posts >= 3:
        score += 15
    else:
        notes.append("نشاط منشورات منخفض في الفترة المحددة")
    # Recency (25)
    if days_since is None:
        notes.append("لا يوجد منشور في الفترة المحددة")
    elif days_since <= 3:
        score += 25
    elif days_since <= 10:
        score += 12
    else:
        notes.append(f"آخر منشور قبل {int(days_since)} يوم")
    # Engagement rate (35)
    if not profile.get("engagement_data_available"):
        notes.append("بيانات التفاعل غير متاحة لهذه الصفحة (تحتاج صلاحيات/ميزة إضافية)")
    elif eng_rate is None:
        notes.append("تعذّر حساب نسبة التفاعل (عدد المتابعين غير متاح)")
    elif eng_rate >= 5:
        score += 35
    elif eng_rate >= 1:
        score += 22
    elif eng_rate >= 0.2:
        score += 10
    else:
        notes.append("نسبة تفاعل ضعيفة جداً")
    # Sales readiness (10)
    if profile.get("cta_ratio", 0) >= 0.7:
        score += 10

    level = "قوي" if score >= 70 else "متوسط" if score >= 40 else "خامل/ضعيف"
    return {"score": score, "level": level, "notes": notes or ["لا ملاحظات سلبية"]}


def register(mcp, services=None):
    """Register competitive-intelligence tools."""

    def _api(method: str, path: str, params: dict, page_id: str = "") -> Any:
        """Route a Graph call through the right token.

        Pages we manage are read with the **page-scoped** token (full data:
        published posts, reactions, comments, ratings). Pages we do not manage
        fall back to the user token, which needs Page Public Content Access.
        """
        data: Any
        if page_id and PAGE_ID and str(page_id) == str(PAGE_ID):
            data = page_api_call(method, path, params)
        else:
            data = api_call(method, path, params)
        return data

    def _fetch_published_posts(page_id: str, limit: int = 50) -> tuple[list, dict | None, bool]:
        """Fetch recent published posts with engagement counters.

        Tries the rich field set first; falls back to a minimal set (then to
        none) so pages without reaction/comment edges still return something.
        Returns (posts, error_or_none, has_engagement_data).
        """
        try:
            data = _api(
                "GET",
                f"{page_id}/published_posts",
                {
                    "fields": (
                        "message,created_time,permalink_url,shares,"
                        "reactions.limit(0).summary(true),comments.limit(0).summary(true)"
                    ),
                    "limit": limit,
                },
                page_id=page_id,
            )
            if isinstance(data, dict):
                return data.get("data", []) or [], None, True
            return [], None, False
        except Exception as e:
            posts_error = handle_error(e, "analyze_competitor_page:posts")
        # Fallback 1: no engagement edges
        try:
            data = _api(
                "GET",
                f"{page_id}/published_posts",
                {"fields": "message,created_time,permalink_url", "limit": limit},
                page_id=page_id,
            )
            if isinstance(data, dict):
                return data.get("data", []) or [], posts_error, False
        except Exception:
            pass
        return [], posts_error, False

    def _fetch_page_profile(page_id: str, days: int) -> dict:
        """Collect everything we know about one Facebook page (read-only)."""
        since = time.time() - days * SECONDS_PER_DAY

        info: dict = {}
        info_error = None
        try:
            info = _api(
                "GET",
                page_id,
                {"fields": ("name,fan_count,category,link,phone,website,verification_status,about")},
                page_id=page_id,
            )
            if not isinstance(info, dict):
                info, info_error = {}, {"error": f"استجابة غير متوقعة: {type(info).__name__}"}
        except Exception as e:
            info, info_error = {}, handle_error(e, "analyze_competitor_page:info")

        posts, posts_error, has_engagement = _fetch_published_posts(page_id)
        window_posts = []
        for p in posts:
            ts = _parse_iso(p.get("created_time"))
            if ts is None or ts >= since:
                window_posts.append(p)

        if has_engagement:
            engagements = [_engagement_of(p) for p in window_posts]
            total_reactions = sum(e["reactions"] for e in engagements)
            total_comments = sum(e["comments"] for e in engagements)
            total_shares = sum(e["shares"] for e in engagements)
            total_eng = sum(e["total"] for e in engagements)
            avg_eng = round(total_eng / len(window_posts), 2) if window_posts else 0
        else:
            # Engagement edges unavailable (permission/feature) — unknown, not zero.
            engagements = []
            total_reactions = None
            total_comments = None
            total_shares = None
            avg_eng = None
            total_eng = None

        # Consistent with posts_in_window: recency is measured from posts that
        # fall inside the analysis window (not from the whole fetched set).
        last_post_days = None
        stamps = [t for t in (_parse_iso(p.get("created_time")) for p in window_posts) if t]
        if stamps:
            last_post_days = round((time.time() - max(stamps)) / SECONDS_PER_DAY, 1)

        fan_count = info.get("fan_count") if isinstance(info.get("fan_count"), (int, float)) else None
        engagement_rate = round((avg_eng / fan_count) * 100, 2) if fan_count and avg_eng is not None else None

        ratings = None
        try:
            r = _api(
                "GET",
                f"{page_id}/ratings",
                {"fields": "rating,review_text,created_time", "limit": 10},
                page_id=page_id,
            )
            if isinstance(r, dict):
                rows = r.get("data", []) or []
                vals = [float(x.get("rating")) for x in rows if str(x.get("rating", "")).replace(".", "", 1).isdigit()]
                ratings = {
                    "count": len(rows),
                    "average": round(sum(vals) / len(vals), 2) if vals else None,
                    "recent": rows[:5],
                }
        except Exception:
            ratings = None

        profile = {
            "page_id": page_id,
            "name": info.get("name"),
            "category": info.get("category"),
            "link": info.get("link"),
            "phone": info.get("phone"),
            "website": info.get("website"),
            "verified": info.get("verification_status") or "غير محدد",
            "fan_count": fan_count,
            "about": (info.get("about") or "")[:300],
            "window_days": days,
            "posts_in_window": len(window_posts),
            "avg_engagement_per_post": avg_eng,
            "total_reactions": total_reactions,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "engagement_rate": engagement_rate,
            "days_since_last_post": last_post_days,
            "ratings": ratings,
            "engagement_data_available": has_engagement,
            "content_signals": _content_signals(window_posts),
            "top_posts": (
                sorted(
                    (
                        {
                            "permalink": p.get("permalink_url"),
                            "created": p.get("created_time"),
                            "caption": (p.get("message") or "")[:120],
                            "engagement": _engagement_of(p)["total"],
                        }
                        for p in window_posts
                    ),
                    key=lambda x: x["engagement"],
                    reverse=True,
                )[:5]
                if has_engagement
                else []
            ),
        }
        profile["assessment"] = _verdict(profile)
        partial = {}
        if info_error:
            partial["info_error"] = info_error
        if posts_error:
            partial["posts_error"] = posts_error
        if partial:
            profile["partial_errors"] = partial
        return profile

    # ------------------------------------------------------------------
    # البحث والاكتشاف
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def search_business_pages(
        query: str,
        city: str = "",
        limit: int = 25,
        exclude_our_page: bool = True,
    ) -> str:
        """البحث عن صفحات تجارية على فيسبوك بكلمة مفتاحية (+ مدينة/منتج).

        query: كلمة مفتاحية مثل "مجوهرات" أو "اكسسوارات نسائية"
        city: مدينة مثل "صنعاء" — تُضاف تلقائياً للكلمة المفتاحية
        limit: عدد النتائج (1-50)
        exclude_our_page: استثناء صفحتنا (FB_PAGE_ID) من النتائج

        يرجّع لكل نتيجة: الاسم، المعرف، عدد المتابعين، الفئة، الرابط.
        ملاحظة: البحث في صفحات لا نديرها يحتاج ميزة "Page Public Content Access"
        على التطبيق؛ وعند غيابها يعود 0 نتائج (بدون خطأ). بعد الحصول على المعرفات
        استخدم analyze_competitor_page(id) لتحليل كل صفحة بعمق.
        """
        try:
            parts = [p.strip() for p in (query, city) if p and p.strip()]
            q = " ".join(parts)
            if not q:
                return json_dumps({"error": "حدد كلمة مفتاحية (query) على الأقل"})
            from src.core.services import Services
            from src.services.competitor_service import CompetitorService
            svc = CompetitorService(services) if services is not None else CompetitorService(Services.default())
            out = svc.search_business_pages(query, city, limit, exclude_our_page)
            out["next_step"] = "analyze_competitor_page(page_id) لتحليل أي صفحة، أو compare_competitors(ids) للمقارنة"
            if not out.get("results"):
                # Meta returns an empty list (not an error) when the app lacks
                # the Page Public Content Access feature — say so explicitly.
                out["empty_reason"] = _PPCA_HINT
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "search_business_pages"))

    @mcp.tool()
    @concurrency_limit()
    def check_discovery_permissions() -> str:
        """فحص أي مسارات اكتشاف المنافسين متاحة فعلياً لهذا التطبيق/التوكن.

        يجرّب المسارات الثلاثة (بحث صفحات فيسبوك، مكتبة إعلانات ميتا، هاشتاغات
        إنستغرام) ويرجع لكل واحد: متاح أم لا، كود الخطأ، والميزة المطلوبة من
        Meta لتفعيله. شغّلها أولاً إذا عاد search_business_pages بـ 0 نتائج.
        """
        probes = [
            (
                "facebook_page_search",
                "GET",
                "search",
                {"q": "test", "type": "page", "fields": "name,id", "limit": 1},
                "Page Public Content Access",
            ),
            (
                "meta_ad_library",
                "GET",
                "ads_archive",
                {"search_terms": "test", "ad_reached_countries": "['YE']", "fields": "page_name,page_id", "limit": 1},
                "Ad Library API",
            ),
        ]
        results = []
        for name, method, path, params, feature in probes:
            row = {"endpoint": name, "required_feature": feature}
            try:
                data = api_call(method, path, params)
                rows = data.get("data", []) if isinstance(data, dict) else []
                row["status"] = "available" if rows else "empty (no error — feature likely not granted)"
            except Exception as e:
                from facebook_business.exceptions import FacebookRequestError

                if isinstance(e, FacebookRequestError):
                    row["status"] = "blocked"
                    row["code"] = e.api_error_code()
                    row["message"] = e.api_error_message()
                else:
                    row["status"] = "error"
                    row["message"] = str(e)[:200]
            results.append(row)
        # Instagram hashtag search (needs our own IG business id)
        ig_row = {"endpoint": "instagram_hashtag_search", "required_feature": "Instagram Public Content Access"}
        if INSTAGRAM_BUSINESS_ID:
            try:
                api_call("GET", "ig_hashtag_search", {"user_id": INSTAGRAM_BUSINESS_ID, "q": "test"})
                ig_row["status"] = "available"
            except Exception as e:
                from facebook_business.exceptions import FacebookRequestError

                if isinstance(e, FacebookRequestError):
                    ig_row["status"] = "blocked"
                    ig_row["code"] = e.api_error_code()
                    ig_row["message"] = e.api_error_message()
                else:
                    ig_row["status"] = "error"
                    ig_row["message"] = str(e)[:200]
        else:
            ig_row["status"] = "skipped (FB_IG_USER_ID غير مضبوط)"
        results.append(ig_row)
        available = [r for r in results if r["status"] == "available"]
        return json_dumps(
            {
                "results": results,
                "available_count": len(available),
                "summary": (
                    "كل مسارات الاكتشاف محجوبة — يجب تفعيل الميزات المذكورة عبر App Review في Meta"
                    if not available
                    else f"{len(available)} من {len(results)} مسارات متاحة"
                ),
                "note": "تحليل صفحتنا وتحليل حسابات إنستغرام التجارية (باالاسم) يعملان بدون هذه الميزات",
            }
        )

    @mcp.tool()
    @concurrency_limit()
    def analyze_competitor_page(page_id: str, days: int = 30) -> str:
        """تحليل صفحة منافس بعمق: المتابعون، النمط، التفاعل، المحتوى، التقييمات.

        page_id: معرف صفحة فيسبوك (مثل 1562230989251002)
        days: نافذة التحليل بالأيام (افتراضي 30)

        يحسب: منشورات النافذة، متوسط التفاعل، نسبة التفاعل/متابع، أيام آخر منشور،
        أهم الوسوم، نسبة المنشورات الحاوية على دعوة للطلب (CTA)، ومقياس نشاط 0-100.
        ملاحظة: قراءة صفحات لا نديرها تحتاج ميزة "Page Public Content Access".
        """
        try:
            if not page_id:
                return json_dumps({"error": "page_id مطلوب"})
            if days <= 0:
                return json_dumps({"error": "days يجب أن تكون أكبر من صفر"})
            profile = _fetch_page_profile(page_id, days)
            return json_dumps(profile)
        except Exception as e:
            return json_dumps(handle_error(e, "analyze_competitor_page"))

    @mcp.tool()
    @concurrency_limit()
    def competitor_report(handle: str, page_id: str = "", days: int = 30, our_followers: int = 1457) -> str:
        """تقرير منافس شامل: صفحته + وتيرة نشره + أفضل منشوراته + توصيات.

        handle: اسم حساب إنستغرام (بدون @) — مطلوب
        page_id: معرف صفحة فيسبوك (اختياري — لتحليل صفحته também)
        days: نافذة التحليل (افتراضي 30)

        يجمع: تحليل الحساب (متابعون، تفاعل)، cadence (أفضل نوع محتوى، وتيرة),
        وأفضل 5 منشورات — مع توصيات مبنية على بياناتنا (Butterfly).
        """
        try:
            if not handle:
                return json_dumps({"error": "handle مطلوب"})
            handle = handle.lstrip("@")
            if not INSTAGRAM_BUSINESS_ID:
                return json_dumps({"error": "FB_IG_USER_ID غير مضبوط — اضبطه أو استخدم discover_ig_user", "guard": "ig_business_required"})
            if not _IG_HANDLE_RE.match(handle):
                return json_dumps({"error": f"handle غير صالح: {handle!r} (أحرف/أرقام/./_ فقط، 1-30)"})
            report = {"handle": handle, "window_days": days}

            # 1. Instagram Business Discovery
            try:
                ig = api_call(
                    "GET",
                    INSTAGRAM_BUSINESS_ID,
                    {
                        "fields": (
                            f"business_discovery.username({handle})"
                            "{username,name,biography,followers_count,follows_count,"
                            "media_count,profile_picture_url,website,media.limit(8)"
                            "{id,caption,permalink,timestamp,like_count,comments_count,media_type}}"
                        )
                    },
                )
                biz = ig.get("business_discovery") or {}
                media = (biz.get("media") or {}).get("data", [])
                likes = [m.get("like_count") or 0 for m in media]
                comments = [m.get("comments_count") or 0 for m in media]
                avg_likes = round(sum(likes) / len(likes), 1) if likes else 0
                avg_comments = round(sum(comments) / len(comments), 1) if comments else 0
                followers = biz.get("followers_count") or 0
                eng_rate = round(((avg_likes + avg_comments) / followers) * 100, 3) if followers else None
                report["instagram"] = {
                    "username": biz.get("username"),
                    "name": biz.get("name"),
                    "followers": followers,
                    "media_count": biz.get("media_count"),
                    "biography": (biz.get("biography") or "")[:200],
                    "website": biz.get("website"),
                    "avg_likes": avg_likes,
                    "avg_comments": avg_comments,
                    "engagement_rate": eng_rate,
                    "top_hashtags": [
                        {"tag": t, "count": n}
                        for t, n in Counter(
                            t for m in media for t in marketing_hashtags(m.get("caption") or "")
                        ).most_common(8)
                    ],
                    "latest_posts": [
                        {
                            "permalink": m.get("permalink"),
                            "timestamp": m.get("timestamp"),
                            "likes": m.get("like_count"),
                            "comments": m.get("comments_count"),
                            "type": m.get("media_type"),
                            "caption": (m.get("caption") or "")[:100],
                        }
                        for m in sorted(
                            media,
                            key=lambda x: (x.get("like_count") or 0) + (x.get("comments_count") or 0),
                            reverse=True,
                        )[:5]
                    ],
                }
            except Exception as e:
                report["instagram"] = {"error": str(e)[:200]}

            # 2. Facebook page (optional)
            if page_id:
                try:
                    report["facebook"] = _fetch_page_profile(page_id, days)
                except Exception as e:
                    report["facebook"] = {"error": str(e)[:200]}

            # 3. cadence (best media type, posting frequency)
            try:
                media_all = fetch_business_media(handle)
                cutoff = time.time() - days * SECONDS_PER_DAY
                by_day: dict = {}
                by_type: dict = {}
                in_window = 0
                for m in media_all:
                    ts = _parse_iso(m.get("timestamp"))  # epoch seconds (float)
                    if not ts or ts < cutoff:
                        continue
                    in_window += 1
                    eng = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
                    day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    by_day.setdefault(day, []).append(eng)
                    by_type.setdefault(m.get("media_type") or "UNKNOWN", []).append(eng)
                type_summary = sorted(
                    (
                        {"media_type": t, "posts": len(v), "avg_engagement": round(sum(v) / len(v), 1), "max": max(v)}
                        for t, v in by_type.items()
                    ),
                    key=lambda r: r["avg_engagement"],
                    reverse=True,
                )
                report["cadence"] = {
                    "fetched": len(media_all),
                    "in_window": in_window,
                    "active_days": len(by_day),
                    "avg_posts_per_day": round(in_window / max(len(by_day), 1), 1),
                    "by_media_type": type_summary,
                    "best_days": sorted(
                        ({"date": d, "avg": round(sum(v) / len(v), 1), "posts": len(v)} for d, v in by_day.items()),
                        key=lambda r: r["avg"],
                        reverse=True,
                    )[:5],
                }
            except Exception as e:
                report["cadence"] = {"error": str(e)[:200]}

            # 4. recommendations vs Butterfly (our data: 1457 followers, eng 0.213%, 154 posts)
            recs = []
            ig = report.get("instagram", {})
            if isinstance(ig, dict) and "error" not in ig:
                if (ig.get("followers") or 0) > 10000:
                    recs.append(
                        f"المنافس {handle} يملك {ig['followers']} متابع — جمهور أوسع منكِ ({our_followers:,}). ركّزي على نمو المتابعين."
                    )
                if (ig.get("engagement_rate") or 0) < 0.2:
                    recs.append(
                        f"نسبة تفاعل منخفضة ({ig.get('engagement_rate')}%) — جمهور 'مشاهد' لا 'مشتري'. فرصة لكِ."
                    )
                if ig.get("top_hashtags"):
                    recs.append(f"استخدمي وسومهم: {', '.join(h['tag'] for h in ig['top_hashtags'][:5])}")
            report["recommendations"] = recs or ["لا توصيات محددة — راجع التفاصيل"]

            return json_dumps(report)
        except Exception as e:
            return json_dumps(handle_error(e, "competitor_report"))

    # ------------------------------------------------------------------
    # مقارنة عدة منافسين
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def compare_competitors(page_ids: str, days: int = 30, include_ours: bool = True) -> str:
        """مقارنة عدة صفحات منافسة في جدول واحد (مرتّب بنسبة التفاعل).

        page_ids: معرّفات صفحات مفصولة بفواصل (مثل "111,222,333")
        days: نافذة التحليل بالأيام (افتراضي 30)
        include_ours: إضافة صفحتنا (FB_PAGE_ID) كنقطة مقارنة أساسية

        لكل منافس: المتابعون، عدد المنشورات، متوسط التفاعل، نسبة التفاعل،
        أيام آخر منشور، والحكم (قوي/متوسط/خامل) — مع توصيات موجزة.
        """
        try:
            ids = [p.strip() for p in (page_ids or "").split(",") if p.strip()]
            if include_ours and PAGE_ID and str(PAGE_ID) not in ids:
                ids.append(str(PAGE_ID))
            if not ids:
                return json_dumps({"error": "حدد معرّف صفحة واحدة على الأقل (page_ids)"})
            if len(ids) > 15:
                return json_dumps({"error": "الحد الأقصى 15 صفحة للمقارنة الواحدة"})

            rows = []
            errors = []
            for pid in ids[:15]:
                try:
                    rows.append(_fetch_page_profile(pid, days))
                except Exception as e:
                    errors.append({"page_id": pid, "error": handle_error(e, "compare_competitors")})
            ours = str(PAGE_ID)
            rows.sort(
                key=lambda r: (
                    r.get("engagement_rate") is not None,
                    r.get("engagement_rate") or 0,
                    r.get("fan_count") or 0,
                ),
                reverse=True,
            )
            table = [
                {
                    "page_id": r.get("page_id"),
                    "name": r.get("name"),
                    "ours": r.get("page_id") == ours,
                    "fan_count": r.get("fan_count"),
                    "posts_in_window": r.get("posts_in_window"),
                    "avg_engagement_per_post": r.get("avg_engagement_per_post"),
                    "engagement_rate": r.get("engagement_rate"),
                    "days_since_last_post": r.get("days_since_last_post"),
                    "level": (r.get("assessment") or {}).get("level"),
                    "score": (r.get("assessment") or {}).get("score"),
                    "partial": "partial_errors" in r,
                }
                for r in rows
            ]
            our_row = next((t for t in table if t["ours"]), None)
            recommendations = []
            if our_row:
                for t in table:
                    if t["ours"]:
                        continue
                    if (t.get("engagement_rate") or 0) > (our_row.get("engagement_rate") or 0):
                        recommendations.append(
                            f"المنافس {t['name']} ({t['page_id']}) يتفوق علينا في نسبة التفاعل "
                            f"({t['engagement_rate']}% مقابل {our_row['engagement_rate']}%) — راجع وتيرة منشوراته وأسلوب CTA"
                        )
                    if (t.get("posts_in_window") or 0) > (our_row.get("posts_in_window") or 0):
                        recommendations.append(
                            f"المنافس {t['name']} نشر {t['posts_in_window']} منشور مقابل {our_row['posts_in_window']} لنا — وتيرته أعلى"
                        )
            return json_dumps(
                {
                    "window_days": days,
                    "compared": len(table),
                    "table": table,
                    "recommendations": recommendations,
                    "errors": errors or None,
                    "hint": "استخدم analyze_competitor_page(page_id) لتفاصيل كل منافس",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "compare_competitors"))

    # ------------------------------------------------------------------
    # إنستغرام — Business Discovery
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def discover_instagram_business(
        username: str,
        instagram_business_id: str = "",
        media_limit: int = 12,
    ) -> str:
        """اكتشاف حساب إنستغرام تجاري عام وتحليل أداء منشوراته.

        username: اسم حساب إنستغرام المستهدف بدون @ (مثل "butterfly.ye")
        instagram_business_id: حسابنا (افتراضي FB_IG_USER_ID من .env)
        media_limit: عدد أحدث المنشورات للتحليل (0-25)

        يرجّع: المتابعون، عدد المنشورات، متوسط الإعجابات/التعليقات لأحدث
        المنشورات، أهم الوسوم، وتوصية موجّهة.
        ملاحظة: يحتاج أن يكون حسابنا حساب Instagram Business، وأن الحساب
        المستهدف حساب أعمال/مبدعين عام.
        """
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            if not ig_id:
                return json_dumps({"error": "حدد instagram_business_id أو اضبط FB_IG_USER_ID في .env"})
            handle = username.strip().lstrip("@")
            if not handle:
                return json_dumps({"error": "username مطلوب"})
            if not _IG_HANDLE_RE.match(handle):
                return json_dumps({"error": f"username غير صالح: {handle!r} (أحرف/أرقام/./_ فقط، 1-30)"})
            ml = max(0, min(int(media_limit), 25))
            fields = (
                f"business_discovery.username({handle})"
                "{username,name,biography,followers_count,follows_count,"
                f"media_count,profile_picture_url,website,media.limit({ml})"
                "{id,caption,permalink,timestamp,like_count,comments_count,media_type}}"
            )
            data = api_call("GET", ig_id, {"fields": fields})
            biz = (data.get("business_discovery") or {}) if isinstance(data, dict) else {}
            if not biz:
                return json_dumps(
                    {
                        "error": f"لم يُعثر على حساب إنستغرام تجاري بـ username={handle}",
                        "hint": "تأكد أن الحساب حساب أعمال/مبدعين عام وليس خاصاً",
                    }
                )
            media = biz.get("media", {}).get("data", []) if isinstance(biz.get("media"), dict) else []
            likes = [int(m.get("like_count") or 0) for m in media]
            comments = [int(m.get("comments_count") or 0) for m in media]
            hashtags: list[str] = []
            for m in media:
                hashtags.extend(marketing_hashtags(m.get("caption") or ""))
            followers = biz.get("followers_count") or 0
            avg_likes = round(sum(likes) / len(likes), 1) if likes else 0
            avg_comments = round(sum(comments) / len(comments), 1) if comments else 0
            eng_rate = round(((avg_likes + avg_comments) / followers) * 100, 3) if followers else None
            return json_dumps(
                {
                    "username": biz.get("username") or handle,
                    "name": biz.get("name"),
                    "followers_count": followers,
                    "media_count": biz.get("media_count"),
                    "biography": (biz.get("biography") or "")[:300],
                    "website": biz.get("website"),
                    "analysed_media": len(media),
                    "avg_likes": avg_likes,
                    "avg_comments": avg_comments,
                    "engagement_rate": eng_rate,
                    "top_hashtags": [
                        {"tag": t, "count": n} for t, n in Counter(h.lower() for h in hashtags).most_common(10)
                    ],
                    "latest_media": [
                        {
                            "permalink": m.get("permalink"),
                            "timestamp": m.get("timestamp"),
                            "likes": m.get("like_count"),
                            "comments": m.get("comments_count"),
                            "type": m.get("media_type"),
                            "caption": (m.get("caption") or "")[:100],
                        }
                        for m in media[:10]
                    ],
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "discover_instagram_business"))

    # ------------------------------------------------------------------
    # Helpers (monitoring)
    # ------------------------------------------------------------------
    def _extract_price_safe(caption: str):
        import re as _re
        text = (caption or "")
        # Arabic digits
        text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        m = _re.search(r"(\d[\d.,]*)\s*(?:الف|ألف)", text)
        if m:
            try:
                return round(float(m.group(1).replace(",", "")) * 1000, 2)
            except ValueError:
                pass
        m = _re.search(r"(\d[\d.,]*)\s*(?:ريال|ر\.ي|YER)", text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    def _num_diff(a, b):
        if a is None or b is None:
            return None
        try:
            return round(float(a) - float(b), 4)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Competitor monitoring over time (Phase 2.2 / 2.3)
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def snapshot_competitor(handle: str, platform: str = "instagram", days: int = 30) -> str:
        """حفظ لقطة (snapshot) لمنافس في SQLite لمراقبة التغييرات au fil du temps.

        handle: اسم حساب IG (بدون @) — أو page_id لفيسبوك
        platform: instagram (افتراضي) | facebook
        days: نافذة التحليل (افتراضي 30)

        شغّلها دورياً (scheduler) لبناء سجل تاريخي. استخدم diff_competitor_snapshots
        لمقارنة آخر لقطتين.
        """
        try:
            from src.core.services import Services
            from src.services.competitor_service import CompetitorService
            svc = CompetitorService(services) if services is not None else CompetitorService(Services.default())
            result = svc.snapshot(handle, platform, days)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "snapshot_competitor"))

    @mcp.tool()
    @concurrency_limit()
    def list_competitor_snapshots(handle: str, platform: str = "instagram", limit: int = 10) -> str:
        """سرد لقطات منافس المحفوظة (الأحدث أولاً)."""
        try:
            from src.core.services import Services
            from src.services.competitor_service import CompetitorService
            svc = CompetitorService(services) if services is not None else CompetitorService(Services.default())
            result = svc.list_snapshots(handle, platform, limit)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "list_competitor_snapshots"))

    @mcp.tool()
    @concurrency_limit()
    def diff_competitor_snapshots(handle: str, platform: str = "instagram") -> str:
        """مقارنة آخر لقطتين لمنافس: تغيّر المتابعين، التفاعل، الأسعار."""
        try:
            from src.core.services import Services
            from src.services.competitor_service import CompetitorService
            svc = CompetitorService(services) if services is not None else CompetitorService(Services.default())
            result = svc.diff(handle, platform)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "diff_competitor_snapshots"))

    @mcp.resource("competitors://overview")
    async def competitors_resource() -> str:
        """نظرة عامة على المنافسة."""
        try:
            return json_dumps(
                {
                    "module": "competitors",
                    "resource": "competitors://overview",
                    "tools": [
                        "search_business_pages",
                        "analyze_competitor_page",
                        "compare_competitors",
                        "discover_instagram_business",
                    ],
                    "hint": "ابحث عن منافس → حلّله → قارنه بصفحتك",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "competitors://overview"))

    @mcp.prompt()
    def competitor_strategy_prompt(topic: str = "competitors") -> str:
        """استراتيجية المنافسة."""
        return (
            f"ساعد في استراتيجية تنافسية لـ {topic} — قارن أدائنا بالمنافسين "
            "(متابعون، وتيرة نشر، نسبة تفاعل) واقترح 3 خطوات تحسين قابلة للتنفيذ"
        )

    @mcp.resource("competitors://templates")
    async def competitors_extra_resource() -> str:
        """قوالب تحليل المنافسين."""
        try:
            return json_dumps(
                {
                    "module": "competitors",
                    "resource": "competitors://templates",
                    "sanaa_queries": ["مجوهرات صنعاء", "اكسسوارات نسائية صنعاء", "عطور نسائية صنعاء"],
                    "hint": "استخدم هذه الاستعلامات مع search_business_pages",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "competitors://templates"))

    @mcp.prompt()
    def competitor_report_prompt(page_id: str = "") -> str:
        """تقرير منافس."""
        return (
            f"اكتب تقريراً عن المنافس {{page_id}} (المعرف: {page_id or 'غير محدد'}) — "
            "نقاط القوة، الضعف، المحتوى الأفضل أداءً، والتوصيات (وحدة competitors)"
        )
