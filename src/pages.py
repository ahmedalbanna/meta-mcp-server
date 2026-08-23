import logging

from src.config import PAGE_ID

logger = logging.getLogger(__name__)
from src.helpers import (
    get_page_api,
    handle_error,
    json_dumps,
    page_api_call,
    to_dict,
    write_guard,
)
from src.throttle import concurrency_limit

SECONDS_PER_DAY = 86400


def register(mcp):
    """Register Facebook Page tools (all use the page-scoped token)."""

    from facebook_business.adobjects.page import Page

    def _page(node_id: str = "") -> Page:
        return Page(node_id or PAGE_ID, api=get_page_api())

    @mcp.tool()
    @concurrency_limit()
    def get_page_info(page_id: str = "") -> str:
        """معلومات صفحة فيسبوك (الاسم، عدد المتابعين، التصنيف)."""
        try:
            info = _page(page_id).api_get(
                fields=[
                    Page.Field.name,
                    Page.Field.fan_count,
                    Page.Field.link,
                    Page.Field.category,
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_info"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_posts(page_id: str = "", limit: int = 25) -> str:
        """منشورات صفحة فيسبوك."""
        try:
            posts = _page(page_id).get_posts(
                params={
                    "fields": [
                        "message",
                        "created_time",
                        "permalink_url",
                        "shares",
                        "id",
                    ],
                    "limit": limit,
                }
            )
            return json_dumps([to_dict(p) for p in posts])
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_posts"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_post(message: str, page_id: str = "") -> str:
        """نشر منشور نصي على صفحة فيسبوك."""
        try:
            post = _page(page_id).create_feed(params={"message": message})
            return json_dumps(to_dict(post))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_post"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_page_photo(image_url: str, message: str = "", page_id: str = "") -> str:
        """نشر صورة على صفحة فيسبوك (مع نص اختياري)."""
        try:
            params = {"url": image_url}
            if message:
                params["caption"] = message
            photo = _page(page_id).create_photo(params=params)
            return json_dumps(to_dict(photo))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_photo"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def schedule_page_post(message: str, scheduled_time: int, page_id: str = "") -> str:
        """
        جدولة منشور على صفحة فيسبوك.
        scheduled_time: طابع زمني Unix (ثوانٍ) في المستقبل.
        """
        try:
            post = _page(page_id).create_feed(
                params={
                    "message": message,
                    "published": False,
                    "scheduled_publish_time": scheduled_time,
                }
            )
            return json_dumps(to_dict(post))
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
            from facebook_business.adobjects.post import Post

            post = Post(post_id, api=get_page_api())
            data = post.api_update(params={"message": message})
            return json_dumps({"id": post_id, "updated": True, "result": to_dict(data)})
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_post_caption"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_page_post(post_id: str) -> str:
        """حذف منشور من صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.post import Post

            result = Post(post_id, api=get_page_api()).api_delete()
            return json_dumps({"id": post_id, "deleted": True, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_page_post"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_post_insights(
        post_id: str,
        metrics: str = "post_impressions,post_engaged_users,post_reactions_by_type_total,post_comments,post_shares,post_saves",
    ) -> str:
        """تحليلات منشور صفحة فيسبوك واحد (تفاعل، انطباعات، ردود فعل)."""
        try:
            from facebook_business.adobjects.post import Post

            insights = Post(post_id, api=get_page_api()).get_insights(params={"metric": metrics})
            return json_dumps([to_dict(i) for i in insights])
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_post_insights"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_post_comments(post_id: str, limit: int = 25) -> str:
        """التعليقات على منشور صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.post import Post

            comments = Post(post_id, api=get_page_api()).get_comments(params={"limit": limit})
            return json_dumps([to_dict(c) for c in comments])
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_post_comments"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def reply_to_page_comment(comment_id: str, message: str) -> str:
        """الرد على تعليق صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.comment import Comment

            comment = Comment(comment_id, api=get_page_api())
            reply = comment.create_comment(params={"message": message})
            return json_dumps(to_dict(reply))
        except Exception as e:
            return json_dumps(handle_error(e, "reply_to_page_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_page_comment(comment_id: str) -> str:
        """حذف تعليق من صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.comment import Comment

            result = Comment(comment_id, api=get_page_api()).api_delete()
            return json_dumps({"id": comment_id, "deleted": True, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_page_comment"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_albums(page_id: str = "", limit: int = 25) -> str:
        """ألبومات الصور على صفحة فيسبوك."""
        try:
            albums = _page(page_id).get_albums(
                params={
                    "fields": ["id", "name", "count", "created_time"],
                    "limit": limit,
                }
            )
            return json_dumps([to_dict(a) for a in albums])
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_albums"))

    @mcp.tool()
    @concurrency_limit()
    def get_album_photos(album_id: str, limit: int = 25) -> str:
        """صور ألبوم معيّن في صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.album import Album

            photos = Album(album_id, api=get_page_api()).get_photos(
                params={
                    "fields": ["id", "name", "picture", "source", "created_time"],
                    "limit": limit,
                }
            )
            return json_dumps([to_dict(p) for p in photos])
        except Exception as e:
            return json_dumps(handle_error(e, "get_album_photos"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_page_cover(photo_id: str, page_id: str = "") -> str:
        """تعيين صورة غلاف الصفحة من صورة موجودة في ألبوم."""
        try:
            result = page_api_call(
                "POST",
                page_id or PAGE_ID,
                {"cover": photo_id},
            )
            return json_dumps(
                {
                    "page_id": page_id or PAGE_ID,
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
        metrics: str = "page_impressions,page_engaged_users,page_fans",
    ) -> str:
        """تحليلات صفحة فيسبوك (انطباعات، تفاعل، متابعون)."""
        try:
            import time

            since = int(time.time()) - days * SECONDS_PER_DAY
            metric_list = [m.strip() for m in metrics.split(",") if m.strip()]

            def fetch(metric_group, period_value):
                return _page(page_id).get_insights(
                    params={
                        "metric": metric_group,
                        "period": period_value,
                        "since": since,
                    }
                )

            results = []
            page_fans = [m for m in metric_list if m == "page_fans"]
            rest = [m for m in metric_list if m != "page_fans"]
            if rest:
                for i in fetch(",".join(rest), period):
                    results.append(to_dict(i))
            if page_fans:
                for i in fetch(",".join(page_fans), "lifetime"):
                    results.append(to_dict(i))
            return json_dumps(results)
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_insights"))

    # ------------------------------------------------------------------
    # الأحداث Events
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_page_events(page_id: str = "", limit: int = 25) -> str:
        """الأحداث المرتبطة بصفحة فيسبوك."""
        try:
            from src.utils import paginate

            rows = paginate(
                lambda params: _page(page_id).get_events(params=params),
                fields=[
                    "id",
                    "name",
                    "start_time",
                    "end_time",
                    "place",
                    "ticket_uri",
                    "cover",
                    "is_canceled",
                ],
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_events"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_event(event_id: str) -> str:
        """تفاصيل حدث واحد على الصفحة."""
        try:
            from facebook_business.adobjects.event import Event

            info = Event(event_id, api=get_page_api()).api_get(
                fields=[
                    "id",
                    "name",
                    "description",
                    "start_time",
                    "end_time",
                    "place",
                    "ticket_uri",
                    "cover",
                    "is_canceled",
                    "guest_list_enabled",
                ]
            )
            return json_dumps(to_dict(info))
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
            params = {"name": name, "start_time": start_time}
            if end_time:
                params["end_time"] = end_time
            if description:
                params["description"] = description
            if ticket_uri:
                params["ticket_uri"] = ticket_uri
            if place:
                params["place"] = place
            result = page_api_call("POST", (page_id or PAGE_ID) + "/events", params)
            return json_dumps(to_dict(result))
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
            from src.utils import paginate

            rows = paginate(
                lambda params: _page(page_id).get_ratings(params=params),
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
            from src.utils import paginate

            rows = paginate(
                lambda params: _page(page_id).get_roles(params=params),
                fields=["user", "role", "tasks"],
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
            result = page_api_call("GET", (page_id or PAGE_ID) + "/call_to_actions", {})
            return json_dumps(to_dict(result))
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
            result = page_api_call(
                "POST",
                (page_id or PAGE_ID) + "/call_to_actions",
                {"type": cta_type, "link": cta_link},
            )
            return json_dumps(
                {
                    "page_id": page_id or PAGE_ID,
                    "cta_type": cta_type,
                    "result": to_dict(result),
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
            pid = page_id or PAGE_ID
            if not video_url:
                return json_dumps({"error": "video_url مطلوب"})
            result = page_api_call(
                "POST",
                f"{pid}/video_reels",
                {"file_url": video_url, "description": description},
            )
            return json_dumps({"page_id": pid, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_reel"))

    @mcp.tool()
    @concurrency_limit()
    def get_page_video_insights(
        video_id: str, metrics: str = "post_video_views,post_video_complete_views,post_video_avg_time_watched"
    ) -> str:
        """تحليلات فيديو صفحة فيسبوك (views, completes, avg watch)."""
        try:
            from facebook_business.adobjects.post import Post

            insights = Post(video_id, api=get_page_api()).get_insights(params={"metric": metrics})
            return json_dumps([to_dict(i) for i in insights])
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_video_insights"))

    @mcp.tool()
    @concurrency_limit()
    def list_page_post_reactions(post_id: str, limit: int = 25) -> str:
        """قائمة تفاعلات (Reactions) على منشور صفحة."""
        try:
            from facebook_business.adobjects.post import Post

            from src.utils import paginate

            rows = paginate(
                lambda params: Post(post_id, api=get_page_api()).get_reactions(params=params),
                fields=["id", "name", "type", "pic"],
                limit=limit,
            )
            return json_dumps({"post_id": post_id, "reactions": rows, "count": len(rows)})
        except Exception as e:
            # Fallback to raw api_call if SDK edge not available
            try:
                data = page_api_call("GET", f"{post_id}/reactions", {"limit": limit, "fields": "id,name,type"})
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
            from src.helpers import handle_error

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
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "pages://templates"))

    @mcp.prompt()
    def page_insights_prompt(topic: str = "pages") -> str:
        """رؤى صفحة."""
        return "ساعد في رؤى صفحة لـ " + topic + " — حلل صفحة {page_id} (وحدة pages)"
