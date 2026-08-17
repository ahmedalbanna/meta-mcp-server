from pathlib import Path

import requests

from src.config import INSTAGRAM_BUSINESS_ID
from src.helpers import api_call, handle_error, json_dumps, sanitize_path, write_guard
from src.throttle import concurrency_limit

MEDIA_DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "media"


def register(mcp):
    """Register Instagram tools (raw Graph API)."""

    from facebook_business.adobjects.igmedia import IGMedia

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_account(instagram_business_id: str = "") -> str:
        """معلومات حساب إنستغرام المرتبط بالأعمال."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                ig_id,
                {
                    "fields": "id,username,media_count,followers_count,biography,profile_picture_url"
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_account"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_media(instagram_business_id: str = "", limit: int = 25) -> str:
        """منشورات حساب إنستغرام."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                f"{ig_id}/media",
                {
                    "fields": "id,caption,media_type,media_url,permalink,timestamp",
                    "limit": limit,
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_media(media_id: str) -> str:
        """تفاصيل منشور إنستغرام واحد (كابشن، نوع، روابط، وقت النشر)."""
        try:
            data = api_call(
                "GET",
                media_id,
                {
                    "fields": "id,caption,media_type,media_url,permalink,timestamp,username"
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    def search_instagram_hashtag(hashtag: str, instagram_business_id: str = "") -> str:
        """البحث عن هاشتاغ على إنستغرام وإرجاع معرّف الهاشتاغ."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                "ig_hashtag_search",
                {"user_id": ig_id, "q": hashtag},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "search_instagram_hashtag"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_hashtag_media(
        hashtag_id: str,
        media_type: str = "recent",
        limit: int = 25,
        instagram_business_id: str = "",
    ) -> str:
        """أحدث أو الأكثر تفاعلاً من منشورات هاشتاغ معيّن. media_type: recent | top."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                f"{hashtag_id}/{media_type}_media",
                {
                    "user_id": ig_id,
                    "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                    "limit": limit,
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_hashtag_media"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_account_mentions(
        instagram_business_id: str = "", limit: int = 25
    ) -> str:
        """المنشورات التي ذُكر فيها الحساب (Mentions)."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                f"{ig_id}/mentions",
                {
                    "fields": "id,media_type,media_url,permalink,timestamp,caption,like_count,comments_count",
                    "limit": limit,
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_account_mentions"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_media_children(media_id: str) -> str:
        """جلب عناصر ألبوم كاروسيل (صور/فيديوهات) لمنشور إنستغرام معين."""
        try:
            data = api_call(
                "GET",
                f"{media_id}/children",
                {"fields": "id,media_type,media_url,permalink"},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_media_children"))

    @mcp.tool()
    @concurrency_limit()
    def download_instagram_media(media_id: str, out_dir: str = "") -> str:
        """
        تنزيل صور منشور إنستغرام إلى ملفات محلية (العملة/الصورة وكل عناصر الكاروسيل).
        out_dir: مجلد الوجهة (اختياري — الافتراضي meta-mcp-server/media).
        """
        try:
            if out_dir:
                try:
                    target = sanitize_path(out_dir, MEDIA_DOWNLOAD_DIR.parent)
                except ValueError as e:
                    return json_dumps({"error": f"مسار غير صالح: {e}"})
            else:
                target = MEDIA_DOWNLOAD_DIR
            target.mkdir(parents=True, exist_ok=True)
            meta = api_call(
                "GET", media_id, {"fields": "id,media_type,media_url,caption"}
            )
            urls = []
            if meta.get("media_type") == "CAROUSEL_ALBUM":
                children = api_call(
                    "GET", f"{media_id}/children", {"fields": "id,media_type,media_url"}
                )
                urls = [(c["id"], c.get("media_url")) for c in children.get("data", [])]
            else:
                urls = [(meta.get("id"), meta.get("media_url"))]

            saved = []
            for cid, url in urls:
                if not url:
                    continue
                ext = Path(url.split("?")[0]).suffix or ".jpg"
                local = target / f"{cid}{ext}"
                with requests.get(url, timeout=60) as r:
                    r.raise_for_status()
                    local.write_bytes(r.content)
                saved.append(str(local))
            return json_dumps({"media_id": media_id, "saved": saved})
        except Exception as e:
            return json_dumps(handle_error(e, "download_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_media_insights(
        media_id: str,
        metric: str = "reach,likes,comments,saved,total_interactions,shares",
    ) -> str:
        """تحليلات منشور إنستغرام معين."""
        try:
            insights = IGMedia(media_id).get_insights(params={"metric": metric})
            out = []
            for i in insights:
                d = i.export_all_data()
                out.append({"name": d.get("name"), "values": d.get("values")})
            return json_dumps(out or {"message": "لا توجد بيانات"})
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_media_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_account_insights(
        instagram_business_id: str = "",
        period: str = "days_28",
        metric: str = "reach,follower_count,profile_views,accounts_engaged,total_interactions",
    ) -> str:
        """تحليلات على مستوى حساب إنستغرام. period: day | week | days_28."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                f"{ig_id}/insights",
                {"metric": metric, "period": period},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_account_insights"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_photo(
        image_url: str, caption: str = "", instagram_business_id: str = ""
    ) -> str:
        """
        نشر صورة على إنستغرام.
        يتطلب صلاحية instagram_content_publish و Instagram Business Account مرتبط بصفحة.
        """
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            container = api_call(
                "POST",
                f"{ig_id}/media",
                {"image_url": image_url, "caption": caption},
            )
            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call(
                "POST", f"{ig_id}/media_publish", {"creation_id": creation_id}
            )
            return json_dumps({"container": container, "publish": result})
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_photo"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_video(
        video_url: str,
        caption: str = "",
        cover_url: str = "",
        instagram_business_id: str = "",
    ) -> str:
        """نشر فيديو على إنستغرام (صفحة/تغذية)."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            params = {"video_url": video_url, "caption": caption}
            if cover_url:
                params["cover_url"] = cover_url
            container = api_call("POST", f"{ig_id}/media", params)
            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call(
                "POST", f"{ig_id}/media_publish", {"creation_id": creation_id}
            )
            return json_dumps({"container": container, "publish": result})
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_video"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_reel(
        video_url: str,
        caption: str = "",
        thumb_offset: int = 0,
        share_to_feed: bool = True,
        instagram_business_id: str = "",
    ) -> str:
        """نشر ريلز على إنستغرام."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            params = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": str(share_to_feed).lower(),
                "thumb_offset_ms": thumb_offset,
            }
            container = api_call("POST", f"{ig_id}/media", params)
            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call(
                "POST", f"{ig_id}/media_publish", {"creation_id": creation_id}
            )
            return json_dumps({"container": container, "publish": result})
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_reel"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_carousel(
        image_urls: str, caption: str = "", instagram_business_id: str = ""
    ) -> str:
        """
        نشر ألبوم كاروسيل على إنستغرام.
        image_urls: روابط الصور مفصولة بفواصل (مثال "url1,url2,url3").
        """
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            urls = [u.strip() for u in image_urls.split(",") if u.strip()]
            if not urls:
                return json_dumps(
                    {
                        "error": "لا توجد روابط صور",
                        "context": "publish_instagram_carousel",
                    }
                )
            child_ids = []
            for url in urls:
                child = api_call(
                    "POST",
                    f"{ig_id}/media",
                    {"image_url": url, "is_carousel_item": "true"},
                )
                cid = child.get("id")
                if not cid:
                    return json_dumps(child)
                child_ids.append(cid)
            container = api_call(
                "POST",
                f"{ig_id}/media",
                {
                    "media_type": "CAROUSEL",
                    "children": ",".join(child_ids),
                    "caption": caption,
                },
            )
            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call(
                "POST", f"{ig_id}/media_publish", {"creation_id": creation_id}
            )
            return json_dumps(
                {"children": child_ids, "container": container, "publish": result}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_carousel"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def add_instagram_media_comment(media_id: str, message: str) -> str:
        """
        إضافة تعليق على منشور إنستغرام (حل بديل لإضافة نص الكابشن لمُنشور منشور مسبقًا،
        لأن Graph API لا يدعم تعديل كابشن منشور منشور).
        """
        try:
            result = api_call("POST", f"{media_id}/comments", {"message": message})
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "add_instagram_media_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_instagram_media(media_id: str) -> str:
        """
        حذف منشور إنستغرام (يُستخدم في سير عمل: حذف ثم إعادة نشر بكابشن محدّث).
        """
        try:
            result = api_call("DELETE", f"{media_id}")
            return json_dumps({"id": media_id, "deleted": True, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_instagram_media_caption(
        media_id: str, caption: str, instagram_business_id: str = ""
    ) -> str:
        """
        تحديث كابشن منشور إنستغرام (صورة أو كاروسيل) بسير عمل: إعادة نشر بكابشن جديد ثم حذف القديم.
        بما أن Graph API لا يدعم تعديل الكابشن مباشرة، يُعاد النشر بنفس الصور ثم يُحذف المنشور القديم.
        """
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            meta = api_call("GET", media_id, {"fields": "id,media_type,media_url"})
            media_type = meta.get("media_type", "")

            if media_type == "CAROUSEL_ALBUM":
                children = api_call(
                    "GET", f"{media_id}/children", {"fields": "id,media_type,media_url"}
                )
                urls = [
                    c["media_url"]
                    for c in children.get("data", [])
                    if c.get("media_url")
                ]
                if not urls:
                    return json_dumps(
                        {
                            "error": "لا توجد صور في الكاروسيل",
                            "context": "update_instagram_media_caption",
                        }
                    )
                child_ids = []
                for url in urls:
                    child = api_call(
                        "POST",
                        f"{ig_id}/media",
                        {"image_url": url, "is_carousel_item": "true"},
                    )
                    cid = child.get("id")
                    if not cid:
                        return json_dumps(child)
                    child_ids.append(cid)
                container = api_call(
                    "POST",
                    f"{ig_id}/media",
                    {
                        "media_type": "CAROUSEL",
                        "children": ",".join(child_ids),
                        "caption": caption,
                    },
                )
            else:
                url = meta.get("media_url")
                if not url:
                    return json_dumps(
                        {
                            "error": "لا يوجد رابط صورة",
                            "context": "update_instagram_media_caption",
                        }
                    )
                container = api_call(
                    "POST", f"{ig_id}/media", {"image_url": url, "caption": caption}
                )

            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call(
                "POST", f"{ig_id}/media_publish", {"creation_id": creation_id}
            )
            new_id = result.get("id")
            if new_id:
                api_call("DELETE", f"{media_id}")
            return json_dumps(
                {
                    "old_id": media_id,
                    "new_id": new_id,
                    "container": container,
                    "publish": result,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_instagram_media_caption"))

    @mcp.tool()
    @concurrency_limit()
    def get_post_insights(media_id: str) -> str:
        """
        تحليل تفاعل منشور إنستغرام مع الكابشن والوصول.
        يُرجع: الكابشن، النوع، الوصول، الإعجابات، التعليقات، الحفظ، المشاركات، الوقت.
        """
        try:
            # Get media details (caption, type, timestamp)
            media = api_call(
                "GET",
                media_id,
                {
                    "fields": "id,caption,media_type,media_product_type,permalink,timestamp,username"
                },
            )
            # Get engagement insights
            try:
                insights_raw = IGMedia(media_id).get_insights(
                    params={
                        "metric": "reach,likes,comments,saved,total_interactions,shares"
                    }
                )
                insights = {}
                for i in insights_raw:
                    d = i.export_all_data()
                    name = d.get("name", "")
                    values = d.get("values", [])
                    if values:
                        insights[name] = values[0].get("value", 0)
            except Exception:
                insights = {}

            result = {
                "id": media.get("id"),
                "caption": media.get("caption", ""),
                "media_type": media.get("media_type"),
                "permalink": media.get("permalink"),
                "timestamp": media.get("timestamp"),
                "reach": insights.get("reach", 0),
                "likes": insights.get("likes", 0),
                "comments": insights.get("comments", 0),
                "saved": insights.get("saved", 0),
                "shares": insights.get("shares", 0),
                "total_interactions": insights.get("total_interactions", 0),
            }
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "get_post_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_media_comments(media_id: str, limit: int = 25) -> str:
        """التعليقات على منشور إنستغرام."""
        try:
            media = IGMedia(media_id)
            comments = media.get_comments(params={"limit": limit})
            return json_dumps([c.export_all_data() for c in comments])
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_media_comments"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def reply_to_instagram_comment(comment_id: str, message: str) -> str:
        """الرد على تعليق إنستغرام."""
        try:
            result = api_call("POST", f"{comment_id}/replies", {"message": message})
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "reply_to_instagram_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_instagram_comment(comment_id: str) -> str:
        """حذف تعليق إنستغرام."""
        try:
            result = api_call("DELETE", f"{comment_id}")
            return json_dumps({"id": comment_id, "deleted": True, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_instagram_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def hide_instagram_comment(comment_id: str, hide: bool = True) -> str:
        """إخفاء أو إظهار تعليق على إنستغرام."""
        try:
            result = api_call(
                "POST",
                f"{comment_id}",
                {"hide": "true" if hide else "false"},
            )
            return json_dumps({"id": comment_id, "hidden": hide, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "hide_instagram_comment"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_stories(instagram_business_id: str = "", limit: int = 25) -> str:
        """قصص إنستغرام (Stories) النشطة للحساب."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                f"{ig_id}/stories",
                {
                    "fields": "id,media_type,media_url,permalink,timestamp",
                    "limit": limit,
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_stories"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def ban_instagram_commenter(instagram_business_id: str, user_id: str) -> str:
        """حظر مستخدم من التعليق على منشورات الحساب (لا يمنع المتابعة)."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            result = api_call("POST", f"{ig_id}/blocked", {"user_id": user_id})
            return json_dumps({"blocked_user_id": user_id, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "ban_instagram_commenter"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def mute_instagram_commenter(
        instagram_business_id: str, user_id: str, end_time: int
    ) -> str:
        """
        كتم مستخدم من التعليق لفترة مؤقتة.
        end_time: طابع زمني Unix (ثوانٍ) لانتهاء الكتم.
        """
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            result = api_call(
                "POST",
                f"{ig_id}/muted_commenters",
                {"user_id": user_id, "end_time": end_time},
            )
            return json_dumps(
                {"muted_user_id": user_id, "until": end_time, "result": result}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "mute_instagram_commenter"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_conversations(
        instagram_business_id: str = "", limit: int = 25
    ) -> str:
        """محادثات الرسائل المباشرة (DMs) لحساب إنستغرام."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            data = api_call(
                "GET",
                f"{ig_id}/conversations",
                {
                    "fields": "id,updated_time,unread_count,message_count,participants,pending",
                    "limit": limit,
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_conversations"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_conversation(conversation_id: str) -> str:
        """تفاصيل محادثة مباشرة واحدة على إنستغرام."""
        try:
            data = api_call(
                "GET",
                conversation_id,
                {
                    "fields": "id,updated_time,unread_count,message_count,participants,pending"
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_conversation"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_conversation_messages(
        conversation_id: str, limit: int = 25
    ) -> str:
        """رسائل محادثة مباشرة محددة على إنستغرام."""
        try:
            data = api_call(
                "GET",
                f"{conversation_id}/messages",
                {"fields": "id,text,created_time,from,to,media", "limit": limit},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_conversation_messages"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_message(message_id: str) -> str:
        """رسالة مباشرة واحدة على إنستغرام."""
        try:
            data = api_call(
                "GET",
                message_id,
                {"fields": "id,text,created_time,from,to,media"},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_instagram_dm(
        instagram_business_id: str, recipient_ig_id: str, text: str
    ) -> str:
        """إرسال رسالة مباشرة (DM) عبر إنستغرام إلى مستخدم تواصل مع الحساب."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            result = api_call(
                "POST",
                f"{ig_id}/messages",
                {
                    "recipient": {"id": recipient_ig_id},
                    "message": {"text": text},
                },
            )
            return json_dumps({"recipient_id": recipient_ig_id, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "send_instagram_dm"))
