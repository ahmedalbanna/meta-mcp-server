from src.config import PAGE_ID
from src.helpers import get_page_api, handle_error, json_dumps, page_api_call, to_dict, write_guard


def register(mcp):
    """Register Facebook Page tools (all use the page-scoped token)."""

    from facebook_business.adobjects.page import Page

    def _page(node_id: str = "") -> Page:
        return Page(node_id or PAGE_ID, api=get_page_api())

    @mcp.tool()
    def get_page_info(page_id: str = "") -> str:
        """معلومات صفحة فيسبوك (الاسم، عدد المتابعين، التصنيف)."""
        try:
            info = _page(page_id).api_get(
                fields=[Page.Field.name, Page.Field.fan_count, Page.Field.link, Page.Field.category]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_info"))

    @mcp.tool()
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
    @write_guard
    def publish_page_post(message: str, page_id: str = "") -> str:
        """نشر منشور نصي على صفحة فيسبوك."""
        try:
            post = _page(page_id).create_feed(params={"message": message})
            return json_dumps(to_dict(post))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_page_post"))

    @mcp.tool()
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
                    "published": "false",
                    "scheduled_publish_time": scheduled_time,
                }
            )
            return json_dumps(to_dict(post))
        except Exception as e:
            return json_dumps(handle_error(e, "schedule_page_post"))

    @mcp.tool()
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
    def get_page_post_insights(post_id: str, metrics: str = "post_impressions,post_engaged_users,post_reactions_by_type_total,post_comments,post_shares,post_saves") -> str:
        """تحليلات منشور صفحة فيسبوك واحد (تفاعل، انطباعات، ردود فعل)."""
        try:
            from facebook_business.adobjects.post import Post

            insights = Post(post_id, api=get_page_api()).get_insights(
                params={"metric": metrics}
            )
            return json_dumps([to_dict(i) for i in insights])
        except Exception as e:
            return json_dumps(handle_error(e, "get_page_post_insights"))

    @mcp.tool()
    def list_page_post_comments(post_id: str, limit: int = 25) -> str:
        """التعليقات على منشور صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.post import Post

            comments = Post(post_id, api=get_page_api()).get_comments(params={"limit": limit})
            return json_dumps([to_dict(c) for c in comments])
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_post_comments"))

    @mcp.tool()
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
    def list_page_albums(page_id: str = "", limit: int = 25) -> str:
        """ألبومات الصور على صفحة فيسبوك."""
        try:
            albums = _page(page_id).get_albums(
                params={"fields": ["id", "name", "count", "created_time"], "limit": limit}
            )
            return json_dumps([to_dict(a) for a in albums])
        except Exception as e:
            return json_dumps(handle_error(e, "list_page_albums"))

    @mcp.tool()
    def get_album_photos(album_id: str, limit: int = 25) -> str:
        """صور ألبوم معيّن في صفحة فيسبوك."""
        try:
            from facebook_business.adobjects.album import Album

            photos = Album(album_id, api=get_page_api()).get_photos(
                params={"fields": ["id", "name", "picture", "source", "created_time"], "limit": limit}
            )
            return json_dumps([to_dict(p) for p in photos])
        except Exception as e:
            return json_dumps(handle_error(e, "get_album_photos"))

    @mcp.tool()
    @write_guard
    def update_page_cover(photo_id: str, page_id: str = "") -> str:
        """تعيين صورة غلاف الصفحة من صورة موجودة في ألبوم."""
        try:
            result = page_api_call(
                "POST",
                page_id or PAGE_ID,
                {"cover": photo_id},
            )
            return json_dumps({"page_id": page_id or PAGE_ID, "cover_photo_id": photo_id, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_cover"))

    @mcp.tool()
    def get_page_insights(page_id: str = "", period: str = "day", days: int = 7, metrics: str = "page_impressions,page_engaged_users,page_fans") -> str:
        """تحليلات صفحة فيسبوك (انطباعات، تفاعل، متابعون)."""
        try:
            import time

            since = int(time.time()) - days * 86400
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
