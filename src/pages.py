import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from src.throttle import concurrency_limit
from src.utils import (
    handle_error,
    json_dumps,
    paginate,
    to_dict,
    write_guard,
)

SECONDS_PER_DAY = 86400


def register(mcp, services):
    """Register Facebook Page tools (all use the page-scoped token)."""

    @mcp.tool()
    @concurrency_limit()
    def get_page_info(page_id: str = "") -> str:
        """معلومات صفحة فيسبوك (الاسم، عدد المتابعين، التصنيف)."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            data = svc.get_page_info(page_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_info"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_posts(page_id: str = "", limit: int = 25) -> str:
        """منشورات صفحة فيسبوك."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            data = svc.list_posts(page_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_posts"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_post(message: str, page_id: str = "") -> str:
        """نشر منشور نصي على صفحة فيسبوك."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.publish_post(message, page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_post"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_photo(image_url: str, message: str = "", page_id: str = "") -> str:
        """نشر صورة على صفحة فيسبوك (مع نص اختياري)."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.publish_photo(image_url, message, page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_photo"))

    def _host_local_image_via_uguu(file_path: str) -> str:
        """رفع صورة محلية → رابط عام دائم (Cloudinary) أو مؤقت (uguu.se fallback).

        يحاول Cloudinary أولاً (سنوات) عبر src/media_hosting.py، وإن لم يكن CLOUDINARY_URL
        مضبوطاً يعود تلقائياً إلى uguu.se (72 ساعة). يصلح مشكلة انتهاء صور الكتالوج.
        """
        try:
            from src.media_hosting import host_image

            return host_image(file_path)
        except Exception:
            # Fallback direct uguu (legacy)
            from pathlib import Path

            import requests  # type: ignore[import-untyped]

            p = Path(file_path)
            if not p.exists():
                raise FileNotFoundError(f"الملف غير موجود: {file_path}") from None
            with open(p, "rb") as f:
                r = requests.post("https://uguu.se/upload.php", files={"files[]": f}, timeout=60)
                r.raise_for_status()
                data = r.json()
                if not data.get("success") or not data.get("files"):
                    raise RuntimeError(f"فشل الرفع: {data}") from None
            url = data["files"][0]["url"]
            return str(url).replace("http://", "https://")

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_album(image_urls: str, message: str = "", page_id: str = "", product_ids: str = "") -> str:
        """نشر ألبوم (2-10 صور في بوست واحد) على صفحة فيسبوك — يدعم Product Tagging (اختياري).

        image_urls: روابط الصور مفصولة بفواصل (مثال "https://a.jpg,https://b.jpg")
        message: نص المنشور (يدعم العربية + هاشتاغ)
        page_id: معرف الصفحة (افتراضي FB_PAGE_ID)
        product_ids: معرفات منتجات الكتالوج للـ Shopping Tags (اختياري) — مثال "38981123561474624"
                      إنستغرام يدعم Tagging مباشر، فيسبوك يضيف روابط المنتجات كتعليق تلقائي.
        يتطلب FB_ENABLE_WRITES=true. الحد 2-10 صور.
        """
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.publish_album(image_urls, message, page_id, product_ids))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_album"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_album_from_media(
        message: str, media_dir: str = "media", page_id: str = "", product_ids: str = ""
    ) -> str:
        """نشر ألبوم مباشرة من مجلد محلي (media/*.jpeg) بدون رابط عام — يدعم Product Tagging.

        message: نص المنشور
        media_dir: مجلد الصور المحلي (افتراضي "media" → media/image1.jpeg ...)
        page_id: معرف الصفحة
        product_ids: معرفات منتجات للـ Shopping Tags (اختياري)
        يقرأ كل الصور jpeg/png/webp في المجلد (2-10) وينشرها كألبوم فيسبوك.
        """
        try:
            from pathlib import Path

            pid = page_id or services.config.page_id
            base = Path(__file__).resolve().parent.parent / media_dir
            # sanitize
            if not base.exists():
                return json_dumps({"error": f"المجلد غير موجود: {base}"})
            exts = {".jpg", ".jpeg", ".png", ".webp"}
            files = sorted([p for p in base.iterdir() if p.suffix.lower() in exts])
            if len(files) < 2:
                return json_dumps({"error": f"وجد {len(files)} صور فقط في {base} — الألبوم يتطلب 2-10"})
            if len(files) > 10:
                files = files[:10]
            # host each via Cloudinary (permanent) then reuse publish_page_album logic
            from src.media_hosting import host_image

            urls = []
            for f in files:
                urls.append(host_image(str(f)))
            return publish_page_album(",".join(urls), message, pid, product_ids)  # type: ignore[no-any-return]
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_album_from_media"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def schedule_page_post(message: str, scheduled_time: int, page_id: str = "") -> str:
        """
        جدولة منشور على صفحة فيسبوك.
        scheduled_time: طابع زمني Unix (ثوانٍ) في المستقبل.
        """
        try:
            pid = page_id or services.config.page_id
            data = services.api.post(
                f"{pid}/feed",
                {
                    "message": message,
                    "published": False,
                    "scheduled_publish_time": scheduled_time,
                },
            )
            return json_dumps(data if isinstance(data, dict) else {})
        except Exception as e:
            return json_dumps(handle_error(e, "schedule_page_post"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_page_post_caption(post_id: str, message: str) -> str:
        """
        تعديل نص منشور صفحة فيسبوك.
        post_id: معرّف المنشور (مثال 1838820466244084_123456789).
        """
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.update_post_caption(post_id, message))
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_post_caption"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_page_post(post_id: str) -> str:
        """حذف منشور من صفحة فيسبوك."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.delete_post(post_id))
        except Exception as e:
            return json_dumps(handle_error(e, "delete_page_post"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_post_insights(
        post_id: str,
        metrics: str = "post_media_view,post_engaged_users,post_reactions_by_type_total,post_comments,post_shares,post_saves",
    ) -> str:
        """تحليلات منشور صفحة فيسبوك واحد (تفاعل، انطباعات، ردود فعل)."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.get_post_insights(post_id, metrics))
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_post_insights"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_post_comments(post_id: str, limit: int = 25) -> str:
        """التعليقات على منشور صفحة فيسبوك."""
        try:
            data = services.api.get(
                f"{post_id}/comments", {"limit": limit, "fields": "id,message,created_time,from,like_count"}
            )
            rows = data.get("data", []) if isinstance(data, dict) else []
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_post_comments"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def reply_to_page_comment(comment_id: str, message: str) -> str:
        """الرد على تعليق صفحة فيسبوك."""
        try:
            data = services.api.post(f"{comment_id}/comments", {"message": message})
            return json_dumps(data if isinstance(data, dict) else {})
        except Exception as e:
            return json_dumps(handle_error(e, "reply_to_page_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_page_comment(comment_id: str) -> str:
        """حذف تعليق من صفحة فيسبوك."""
        try:
            services.api.delete(comment_id)
            return json_dumps({"id": comment_id, "deleted": True, "result": {}})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_page_comment"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_albums(page_id: str = "", limit: int = 25) -> str:
        """ألبومات الصور على صفحة فيسبوك."""
        try:
            pid = page_id or services.config.page_id
            data = services.api.get(
                f"{pid}/albums",
                {"fields": ["id", "name", "count", "created_time"], "limit": limit},
            )
            rows = data.get("data", []) if isinstance(data, dict) else []
            return json_dumps([to_dict(a) for a in rows])
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_albums"))

    @mcp.tool()
    @concurrency_limit()
    def get_album_photos(album_id: str, limit: int = 25) -> str:
        """صور ألبوم معيّن في صفحة فيسبوك."""
        try:
            data = services.api.get(
                f"{album_id}/photos",
                {"fields": ["id", "name", "picture", "source", "created_time"], "limit": limit},
            )
            rows = data.get("data", []) if isinstance(data, dict) else []
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_album_photos"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_page_cover(photo_id: str, page_id: str = "") -> str:
        """تعيين صورة غلاف الصفحة من صورة موجودة في ألبوم."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            result = svc.update_page_cover(photo_id, page_id)
            return json_dumps(
                {
                    "page_id": page_id or services.config.page_id,
                    "cover_photo_id": photo_id,
                    "result": result,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_cover"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_insights(
        page_id: str = "",
        period: str = "day",
        days: int = 7,
        metrics: str = "page_views_total,page_post_engagements,page_actions_post_reactions_total",
    ) -> str:
        """تحليلات صفحة فيسبوك (مشاهدات، تفاعل، تفاعلات المنشورات). ملاحظة: مقاييس impressions/page_fans أُوقفت من Meta في 2025-11."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            data = svc.get_page_insights(page_id, period, days, metrics)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_insights"))

    # ------------------------------------------------------------------
    # صحة صفحتنا (تجميع كل التحليلات في تقرير واحد)
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def analyze_our_page(days: int = 30, include_instagram: bool = True) -> str:
        """تقرير صحة صفحتنا (Facebook + Instagram) في تقرير واحد.

        days: نافذة التحليل (افتراضي 30)
        include_instagram: تضمين إنستغرام (افتراضي true)

        يجمع: المتابعون، المنشورات (آخر 10)، مشاهدات/تفاعل آخر 7 أيام،
        أيام آخر منشور، إنستغرام (متابعون + تفاعل 28 يوم)، ومقياس صحة 0-100
        مع توصيات مبنية على بيانات المنافسين (وتيرة، سعر، ضمان).
        """
        try:
            import time

            # 1. Facebook page info
            try:
                pid = services.config.page_id
                fb_info = services.api.get(
                    pid,
                    {
                        "fields": "name,fan_count,link,category,phone,website",
                    },
                )
                fb_info = fb_info if isinstance(fb_info, dict) else {}
            except Exception as e:
                fb_info = {"error": str(e)[:120]}

            # 2. FB page insights (last 7 days)
            try:
                pid = services.config.page_id
                ins_data = services.api.get(
                    f"{pid}/insights",
                    {
                        "metric": "page_views_total,page_post_engagements,page_actions_post_reactions_total",
                        "period": "day",
                        "since": int(time.time()) - 7 * SECONDS_PER_DAY,
                    },
                )
                fb_insights = ins_data.get("data", []) if isinstance(ins_data, dict) else []
            except Exception as e:
                fb_insights = {"error": str(e)[:120]}

            # 3. recent posts
            try:
                pid = services.config.page_id
                posts_data = services.api.get(
                    f"{pid}/posts",
                    {"fields": "message,created_time,permalink_url,id", "limit": 10},
                )
                fb_posts = posts_data.get("data", []) if isinstance(posts_data, dict) else []
            except Exception as e:
                fb_posts = {"error": str(e)[:120]}

            fb_days_since = None
            if isinstance(fb_posts, list) and fb_posts:
                ts = None
                for p in fb_posts:
                    try:
                        dt = datetime.fromisoformat(str(p.get("created_time", "")).replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        ts = max(ts or 0, dt.timestamp())
                    except Exception:
                        pass
                if ts:
                    fb_days_since = round((time.time() - ts) / SECONDS_PER_DAY, 1)

            # 4. Instagram
            ig_info = None
            ig_insights = None
            if include_instagram and services.config.instagram_business_id:
                try:
                    ig_id = services.config.instagram_business_id
                    ig_info = services.api.get(
                        ig_id,
                        {"fields": "id,username,media_count,followers_count,biography"},
                    )
                except Exception as e:
                    ig_info = {"error": str(e)[:120]}
                try:
                    ig_insights = services.api.get(
                        ig_id,
                        {
                            "fields": "insights.metric(reach,follower_count,profile_views,accounts_engaged,total_interactions).period(days_28)"
                        },
                    )
                except Exception as e:
                    ig_insights = {"error": str(e)[:120]}

            # 5. health score + recommendations
            fan_count = fb_info.get("fan_count") if isinstance(fb_info, dict) else None
            score = 0
            notes: list[str] = []
            posts_count = len(fb_posts) if isinstance(fb_posts, list) else 0
            if posts_count >= 10:
                score += 25
            elif posts_count >= 5:
                score += 12
            else:
                notes.append("منشورات قليلة — زد وتيرة النشر (هدف: 2-3/أسبوع)")
            if fb_days_since is None:
                notes.append("لا توجد منشورات حديثة")
            elif fb_days_since <= 3:
                score += 25
            elif fb_days_since <= 10:
                score += 12
            else:
                notes.append(f"آخر منشور قبل {int(fb_days_since)} يوم — نشر قديم")
            # engagement from insights
            total_eng = 0
            if isinstance(fb_insights, list):
                for ins in fb_insights:
                    if ins.get("name") == "page_post_engagements":
                        for v in ins.get("values", []):
                            total_eng += v.get("value", 0) or 0
            if fan_count and total_eng:
                rate = (total_eng / fan_count) * 100
                if rate >= 5:
                    score += 30
                elif rate >= 1:
                    score += 18
                elif rate >= 0.2:
                    score += 8
                else:
                    notes.append("نسبة تفاعل ضعيفة (أقل من 0.2%)")
            else:
                notes.append("لا توجد بيانات تفاعل (الصفحة خاملة أو حملة موقوفة)")
            ig_followers = (ig_info or {}).get("followers_count") if isinstance(ig_info, dict) else None
            if ig_followers:
                score += 10  # bonus for having IG connected
            if (ig_followers or 0) >= 5000:
                score += 10

            level = "قوي" if score >= 70 else "متوسط" if score >= 40 else "خامل/ضعيف"
            return json_dumps(
                {
                    "facebook": {
                        "name": fb_info.get("name") if isinstance(fb_info, dict) else None,
                        "fan_count": fan_count,
                        "category": fb_info.get("category") if isinstance(fb_info, dict) else None,
                        "link": fb_info.get("link") if isinstance(fb_info, dict) else None,
                        "phone": fb_info.get("phone") if isinstance(fb_info, dict) else None,
                        "website": fb_info.get("website") if isinstance(fb_info, dict) else None,
                        "days_since_last_post": fb_days_since,
                        "recent_posts_count": posts_count,
                        "recent_posts": fb_posts if isinstance(fb_posts, list) else None,
                        "insights_last_7d": fb_insights if isinstance(fb_insights, list) else None,
                    },
                    "instagram": {
                        "account": ig_info if isinstance(ig_info, dict) else None,
                        "insights_last_28d": ig_insights,
                    }
                    if include_instagram
                    else None,
                    "health": {
                        "score": score,
                        "level": level,
                        "notes": notes or ["لا ملاحظات — أداء جيد"],
                    },
                    "recommendations": [
                        "نشر 2-3 منشورات/أسبوع (فيديو أو كاروسيل — وليس صورة مفردة)",
                        "كتابة السعر على الصورة (كل منشورات المنافسين الناجحة تحمله)",
                        "إضافة 'ضمان سنة' في كل منشور (سلاحك ضد المنافسين المطلية)",
                        "استهداف بوسوم #استيل #ستانلس_ستيل #بديل_الذهب #صنعاء",
                    ],
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "analyze_our_page"))

    # ------------------------------------------------------------------
    # الأحداث Events
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_page_events(page_id: str = "", limit: int = 25) -> str:
        """الأحداث المرتبطة بصفحة فيسبوك."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            return json_dumps(svc.list_events(page_id, limit))
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_events"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_event(event_id: str) -> str:
        """تفاصيل حدث واحد على الصفحة."""
        try:
            data = services.api.get(
                event_id,
                {
                    "fields": "id,name,description,start_time,end_time,place,ticket_uri,cover,is_canceled,guest_list_enabled",
                },
            )
            return json_dumps(data if isinstance(data, dict) else {})
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_event"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_page_event(
        name: str,
        start_time: str,
        end_time: str = "",
        description: str = "",
        ticket_uri: str = "",
        place: str = "",
        page_id: str = "",
    ) -> str:
        """
        إنشاء حدث على صفحة فيسبوك.
        start_time / end_time بصيغة ISO (مثال 2026-09-01T18:00:00+0300).
        """
        try:
            pid = page_id or services.config.page_id
            params = {"name": name, "start_time": start_time}
            if end_time:
                params["end_time"] = end_time
            if description:
                params["description"] = description
            if ticket_uri:
                params["ticket_uri"] = ticket_uri
            if place:
                params["place"] = place
            result = services.api.post(f"{pid}/events", params)
            return json_dumps(result if isinstance(result, dict) else {})
        except Exception as e:
            return json_dumps(handle_error(e, "create_page_event"))

    # ------------------------------------------------------------------
    # المراجعات والتقييمات Ratings
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_page_ratings(page_id: str = "", limit: int = 25) -> str:
        """تقييمات ومراجعات صفحة فيسبوك."""
        try:
            pid = page_id or services.config.page_id
            rows = paginate(
                lambda params: services.api.get(f"{pid}/ratings", params),
                fields=[
                    "id",
                    "rating",
                    "recommendation_type",
                    "review_text",
                    "created_time",
                    "reviewer",
                    "open_graph_story",
                ],
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_ratings"))

    # ------------------------------------------------------------------
    # أدوار الصفحة Roles
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_page_roles(page_id: str = "", limit: int = 25) -> str:
        """الأشخاص الذين يديرون الصفحة وأدوارهم ومهامهم."""
        try:
            pid = page_id or services.config.page_id
            rows = paginate(
                lambda params: services.api.get(f"{pid}/roles", params),
                fields=["id", "name", "admin_notes", "business_persona", "permitted_tasks"],
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_roles"))

    # ------------------------------------------------------------------
    # أزرار CTA
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def get_page_cta(page_id: str = "") -> str:
        """زر الدعوة لاتخاذ إجراء الحالي على الصفحة."""
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            data = svc.get_page_cta(page_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_cta"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_page_cta(cta_type: str, cta_link: str, page_id: str = "") -> str:
        """
        تعيين زر CTA على الصفحة.
        cta_type: LEARN_MORE | SHOP_NOW | SIGN_UP | CONTACT_US | MESSAGE_PAGE | BOOK_NOW ...
        cta_link: الرابط أو معرف Messenger المرتبط بالزر.
        """
        try:
            from src.services.pages_service import PagesService

            svc = PagesService(services)
            result = svc.update_page_cta(cta_type, cta_link, page_id)
            return json_dumps(
                {
                    "page_id": page_id or services.config.page_id,
                    "cta_type": cta_type,
                    "result": result,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_cta"))

    # ------------------------------------------------------------------
    # Phase 2.2 — نشر ريلز وتحليلات الفيديو
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_reel(video_url: str, description: str = "", page_id: str = "") -> str:
        """نشر ريلز على صفحة فيسبوك (Page Reel)."""
        try:
            pid = page_id or services.config.page_id
            if not video_url:
                return json_dumps({"error": "video_url مطلوب"})
            result = services.api.post(
                f"{pid}/video_reels",
                {"file_url": video_url, "description": description},
            )
            return json_dumps({"page_id": pid, "result": result if isinstance(result, dict) else {}})
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_reel"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_reel_from_media(
        description: str = "", video_path: str = "media/reel.mp4", page_id: str = ""
    ) -> str:
        """نشر ريلز فيسبوك من ملف فيديو محلي (media/*.mp4) — يرفع تلقائيا لاستضافة دائمة ثم ينشر.

        video_path: مسار ملف الفيديو المحلي (مثال "media/video.mp4") — أو مجلد "media" سيختار أول .mp4
        description: وصف الريلز
        page_id: معرف الصفحة
        يدعم Cloudinary للاستضافة الدائمة.
        """
        try:
            from pathlib import Path

            from src.media_hosting import host_video

            pid = page_id or services.config.page_id
            p = Path(video_path)
            if p.is_dir():
                vids = sorted([x for x in p.iterdir() if x.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"}])
                if not vids:
                    return json_dumps({"error": f"لا يوجد فيديو في {p}"})
                p = vids[0]
            if not p.exists():
                alt = Path(__file__).resolve().parent.parent / video_path
                if alt.exists():
                    p = alt
                else:
                    return json_dumps({"error": f"ملف الفيديو غير موجود: {video_path}"})
            video_url = host_video(str(p))
            result = services.api.post(f"{pid}/video_reels", {"file_url": video_url, "description": description})
            return json_dumps(
                {
                    "success": True,
                    "page_id": pid,
                    "video_url": video_url,
                    "result": result if isinstance(result, dict) else {},
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_reel_from_media"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_video_insights(
        video_id: str, metrics: str = "post_video_views,post_video_complete_views,post_video_avg_time_watched"
    ) -> str:
        """تحليلات فيديو صفحة فيسبوك (views, completes, avg watch)."""
        try:
            data = services.api.get(
                f"{video_id}/insights",
                {"metric": metrics},
            )
            rows = data.get("data", []) if isinstance(data, dict) else []
            return json_dumps([to_dict(i) for i in rows])
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_video_insights"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_post_reactions(post_id: str, limit: int = 25) -> str:
        """قائمة تفاعلات (Reactions) على منشور صفحة."""
        try:
            data = services.api.get(
                f"{post_id}/reactions",
                {"limit": limit, "fields": "id,name,type"},
            )
            rows = data.get("data", []) if isinstance(data, dict) else []
            return json_dumps({"post_id": post_id, "reactions": rows, "count": len(rows)})
        except Exception as e:
            # Fallback to raw api_call if SDK edge not available
            try:
                data = services.api.get(
                    f"{post_id}/reactions",
                    {"limit": limit, "fields": "id,name,type"},
                )
                return json_dumps(data)
            except Exception:
                return json_dumps(handle_error(e, "list_page_post_reactions"))

    @mcp.resource("pages://overview")
    async def pages_resource() -> str:
        """نظرة عامة الصفحات."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "pages", "resource": "pages://overview", "hint": "نظرة عامة الصفحات"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "pages://overview"))

    @mcp.prompt()
    def page_content_prompt(topic: str = "pages") -> str:
        """محتوى صفحة."""
        return f"ساعد في محتوى صفحة لـ {topic} — اقترح محتوى صفحة لـ {topic} (وحدة pages)"

    @mcp.resource("pages://templates")
    async def pages_extra_resource() -> str:
        """قوالب الصفحات."""
        try:
            return json_dumps({"module": "pages", "resource": "pages://templates", "hint": "قوالب الصفحات"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "pages://templates"))

    @mcp.prompt()
    def page_insights_prompt(topic: str = "pages") -> str:
        """رؤى صفحة."""
        return "ساعد في رؤى صفحة لـ " + topic + " — حلل صفحة {page_id} (وحدة pages)"
