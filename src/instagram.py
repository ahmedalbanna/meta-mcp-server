import asyncio
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

import requests  # type: ignore[import-untyped]

from src.config import INSTAGRAM_BUSINESS_ID
from src.helpers import api_call, handle_error, json_dumps, sanitize_path, write_guard
from src.throttle import concurrency_limit

MEDIA_DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "media"


def register(mcp, services=None):
    """Register Instagram tools (raw Graph API)."""

    from facebook_business.adobjects.igmedia import IGMedia

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_account(instagram_business_id: str = "") -> str:
        """معلومات حساب إنستغرام المرتبط بالأعمال."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.get_account(instagram_business_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_account"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_media(instagram_business_id: str = "", limit: int = 25) -> str:
        """منشورات حساب إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.list_media(instagram_business_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_media(media_id: str) -> str:
        """تفاصيل منشور إنستغرام واحد (كابشن، نوع، روابط، وقت النشر)."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.get_media(media_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    def search_instagram_hashtag(hashtag: str, instagram_business_id: str = "") -> str:
        """البحث عن هاشتاغ على إنستغرام وإرجاع معرّف الهاشتاغ."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.search_hashtag(hashtag, instagram_business_id)
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.get_hashtag_media(hashtag_id, media_type, limit, instagram_business_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_hashtag_media"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_account_mentions(instagram_business_id: str = "", limit: int = 25) -> str:
        """المنشورات التي ذُكر فيها الحساب (Mentions)."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.get_mentions(instagram_business_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_account_mentions"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_media_children(media_id: str) -> str:
        """جلب عناصر ألبوم كاروسيل (صور/فيديوهات) لمنشور إنستغرام معين."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.get_media_children(media_id))
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
            meta = api_call("GET", media_id, {"fields": "id,media_type,media_url,caption"})
            urls = []
            if meta.get("media_type") == "CAROUSEL_ALBUM":
                children = api_call("GET", f"{media_id}/children", {"fields": "id,media_type,media_url"})
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.get_media_insights(media_id, metric))
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
            # Graph v22+: لكل مقياس قيود فترة/نوع مختلفة — نجرب الاستراتيجيتين لكل مقياس
            requested = [m.strip() for m in metric.split(",") if m.strip()]
            results = []
            unavailable = {}
            for m in requested:
                attempts = [
                    {"metric": m, "period": period},
                    {"metric": m, "period": "day", "metric_type": "total_value"},
                ]
                fetched = False
                last_err = None
                for params in attempts:
                    try:
                        data = api_call("GET", f"{ig_id}/insights", params)
                        results.extend(data.get("data", []))
                        fetched = True
                        break
                    except Exception as err:
                        last_err = err
                if not fetched and last_err is not None:
                    unavailable[m] = handle_error(last_err, f"get_instagram_account_insights:{m}")
            out = {"data": results}
            if unavailable:
                out["unavailable"] = unavailable  # type: ignore[assignment]
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_account_insights"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_photo(
        image_url: str,
        caption: str = "",
        instagram_business_id: str = "",
        product_ids: str = "",
        product_x: float = 0.5,
        product_y: float = 0.5,
    ) -> str:
        """
        نشر صورة على إنستغرام — يدعم Product Tagging.
        product_ids: معرفات منتجات الكتالوج للـ Shopping Tags (اختياري) — مثال "38981123561474624"
                     يتطلب instagram_shopping_tag_products + Shop معتمد. الحد 20 تاغ.
        """
        try:

            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.publish_photo(image_url, caption, instagram_business_id, product_ids, product_x, product_y))
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.publish_video(video_url, caption, cover_url, instagram_business_id))
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.publish_reel(video_url, caption, thumb_offset, share_to_feed, instagram_business_id))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_reel"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_story(
        image_url: str = "",
        video_url: str = "",
        link: str = "",
        instagram_business_id: str = "",
    ) -> str:
        """نشر قصة (Story) على إنستغرام. أرسل image_url أو video_url فقط."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.publish_story(image_url, video_url, link, instagram_business_id))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_story"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_carousel(
        image_urls: str,
        caption: str = "",
        instagram_business_id: str = "",
        product_ids: str = "",
        product_x: float = 0.5,
        product_y: float = 0.5,
    ) -> str:
        """
        نشر ألبوم كاروسيل على إنستغرام — يدعم Product Tagging (IG Shopping).

        image_urls: روابط الصور مفصولة بفواصل (مثال "url1,url2,url3").
        product_ids: معرفات منتجات الكتالوج مفصولة بفواصل للـ Product Tagging (اختياري) — مثال "38981123561474624,27936390912693771"
                      يتطلب instagram_shopping_tag_products + Shop معتمد. الحد 5 لكل شريحة، 20 لكل كاروسيل.
        product_x/product_y: إحداثيات التاغ (0.0-1.0) — افتراضي 0.5,0.5 (منتصف الصورة)
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
            # Parse product_ids for tagging (IG Shopping — requires catalog_management + instagram_shopping_tag_products)
            import json as _json

            pids = [p.strip() for p in (product_ids or "").split(",") if p.strip()]
            # Product Tagging: up to 5 per slide, 20 total — map products to slides round-robin
            child_ids = []
            for idx, url in enumerate(urls):
                params = {"image_url": url, "is_carousel_item": "true"}
                if pids:
                    # Assign products to this slide (max 5 per slide)
                    per_slide = 5
                    (idx * per_slide) % len(pids) if pids else 0
                    # Simple: if single product, tag same product on every slide; if multiple, distribute
                    if len(pids) == 1:
                        tags = [{"product_id": pids[0], "x": product_x, "y": product_y}]
                    else:
                        # distribute distinct products across slides
                        tags = []
                        for j in range(min(per_slide, len(pids))):
                            pid_idx = (idx * per_slide + j) % len(pids)
                            tags.append({"product_id": pids[pid_idx], "x": product_x, "y": product_y})
                        # For multi-product case, take slice
                        if len(urls) <= len(pids):
                            tags = [{"product_id": pids[idx % len(pids)], "x": product_x, "y": product_y}]
                    params["product_tags"] = _json.dumps(tags)
                child = api_call("POST", f"{ig_id}/media", params)
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
            result = api_call("POST", f"{ig_id}/media_publish", {"creation_id": creation_id})
            return json_dumps({"children": child_ids, "container": container, "publish": result})
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            result = svc.add_comment(media_id, message)
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            result = svc.delete_media(media_id)
            return json_dumps({"id": media_id, "deleted": True, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_instagram_media"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_instagram_media_caption(media_id: str, caption: str, instagram_business_id: str = "") -> str:
        """
        تحديث كابشن منشور إنستغرام (صورة أو كاروسيل) بسير عمل: إعادة نشر بكابشن جديد ثم حذف القديم.
        بما أن Graph API لا يدعم تعديل الكابشن مباشرة، يُعاد النشر بنفس الصور ثم يُحذف المنشور القديم.
        """
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            meta = api_call("GET", media_id, {"fields": "id,media_type,media_url"})
            media_type = meta.get("media_type", "")

            if media_type == "CAROUSEL_ALBUM":
                children = api_call("GET", f"{media_id}/children", {"fields": "id,media_type,media_url"})
                urls = [c["media_url"] for c in children.get("data", []) if c.get("media_url")]
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
                container = api_call("POST", f"{ig_id}/media", {"image_url": url, "caption": caption})

            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call("POST", f"{ig_id}/media_publish", {"creation_id": creation_id})
            new_id = result.get("id")
            delete_ok = True
            delete_error = ""
            if new_id:
                try:
                    api_call("DELETE", f"{media_id}")
                except Exception as del_e:
                    delete_ok = False
                    delete_error = str(del_e)
            resp = {
                "old_id": media_id,
                "new_id": new_id,
                "container": container,
                "publish": result,
            }
            if not delete_ok:
                resp["warning"] = f"تم النشر بالجديد لكن حذف المنشور القديم فشل: {delete_error}"
            return json_dumps(resp)
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
                {"fields": "id,caption,media_type,media_product_type,permalink,timestamp,username"},
            )
            # Get engagement insights
            try:
                insights_raw = IGMedia(media_id).get_insights(
                    params={"metric": "reach,likes,comments,saved,total_interactions,shares"}
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
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            return json_dumps(svc.get_media_comments(media_id, limit))
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_media_comments"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def reply_to_instagram_comment(comment_id: str, message: str) -> str:
        """الرد على تعليق إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            result = svc.reply_comment(comment_id, message)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "reply_to_instagram_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_instagram_comment(comment_id: str) -> str:
        """حذف تعليق إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            result = svc.delete_comment(comment_id)
            return json_dumps({"id": comment_id, "deleted": True, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_instagram_comment"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def hide_instagram_comment(comment_id: str, hide: bool = True) -> str:
        """إخفاء أو إظهار تعليق على إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            result = svc.hide_comment(comment_id, hide)
            return json_dumps({"id": comment_id, "hidden": hide, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "hide_instagram_comment"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_stories(instagram_business_id: str = "", limit: int = 25) -> str:
        """قصص إنستغرام (Stories) النشطة للحساب."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.list_stories(instagram_business_id, limit)
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
    def mute_instagram_commenter(instagram_business_id: str, user_id: str, end_time: int) -> str:
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
            return json_dumps({"muted_user_id": user_id, "until": end_time, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "mute_instagram_commenter"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_conversations(instagram_business_id: str = "", limit: int = 25) -> str:
        """محادثات الرسائل المباشرة (DMs) لحساب إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.list_conversations(instagram_business_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_conversations"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_conversation(conversation_id: str) -> str:
        """تفاصيل محادثة مباشرة واحدة على إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.get_conversation(conversation_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_conversation"))

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_conversation_messages(conversation_id: str, limit: int = 25) -> str:
        """رسائل محادثة مباشرة محددة على إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.list_conversation_messages(conversation_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_conversation_messages"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_message(message_id: str) -> str:
        """رسالة مباشرة واحدة على إنستغرام."""
        try:
            from src.core.services import Services
            from src.services.instagram_service import InstagramService
            svc = InstagramService(services) if services is not None else InstagramService(Services.default())
            data = svc.get_message(message_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_message"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_instagram_dm(instagram_business_id: str, recipient_ig_id: str, text: str) -> str:
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

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def send_instagram_dm_with_image(
        instagram_business_id: str,
        recipient_ig_id: str,
        image_url: str,
        text: str = "",
    ) -> str:
        """إرسال رسالة مباشرة (DM) مع صورة عبر إنستغرام."""
        try:
            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            result = api_call(
                "POST",
                f"{ig_id}/messages",
                {
                    "recipient": {"id": recipient_ig_id},
                    "message": {
                        "attachment": {
                            "type": "image",
                            "payload": {"url": image_url},
                        }
                    },
                },
            )
            if text:
                api_call(
                    "POST",
                    f"{ig_id}/messages",
                    {
                        "recipient": {"id": recipient_ig_id},
                        "message": {"text": text},
                    },
                )
            return json_dumps({"recipient_id": recipient_ig_id, "result": result})
        except Exception as e:
            return json_dumps(handle_error(e, "send_instagram_dm_with_image"))

    # ------------------------------------------------------------------
    # Phase 2.1 — Instagram completeness
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_instagram_comments(media_id: str, limit: int = 25) -> str:
        """قائمة تعليقات منشور إنستغرام مع ترقيم الصفحات (paginate)."""
        try:
            from src.utils import paginate

            rows = paginate(
                lambda params: api_call("GET", f"{media_id}/comments", params),
                fields=["id", "text", "timestamp", "username", "like_count", "replies"],
                limit=limit,
            )
            return json_dumps({"data": rows, "count": len(rows), "media_id": media_id})
        except Exception as e:
            return json_dumps(handle_error(e, "list_instagram_comments"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_reels_insights(
        media_id: str,
        metric: str = "plays,reach,likes,comments,saved,shares,total_interactions",
    ) -> str:
        """تحليلات ريلز إنستغرام (plays + reach + engagement) — مخصص لفيديوهات Reels."""
        try:
            # Reels use same IGMedia insights but metrics differ (plays, etc.)
            insights = IGMedia(media_id).get_insights(params={"metric": metric})
            out = []
            for i in insights:
                d = i.export_all_data()
                out.append({"name": d.get("name"), "values": d.get("values")})
            if not out:
                return json_dumps({"message": "لا توجد بيانات Reels", "media_id": media_id})
            return json_dumps({"media_id": media_id, "insights": out})
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_reels_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_instagram_reels_account_insights(
        instagram_business_id: str = "",
        limit: int = 10,
        days: int = 30,
    ) -> str:
        """تحليلات Reels على مستوى حساب إنستغرام (plays/reach/saved/shares) — يجمع insights
        أحدث Reels within `days` days ويرتبها حسب plays.

        instagram_business_id: حساب Instagram Business (افتراضي FB_IG_USER_ID)
        limit: عدد Reels المُحلَّلة (1-25)
        days: نافذة التحليل بالأيام (افتراضي 30)
        """
        try:
            from datetime import datetime, timedelta, timezone

            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            if not ig_id:
                return json_dumps({"error": "حدد instagram_business_id أو اضبط FB_IG_USER_ID في .env"})
            limit = max(1, min(int(limit), 25))
            days = max(1, int(days))
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # 1) recent media (fetch a bit more to filter Reels)
            media_resp = api_call(
                "GET",
                f"{ig_id}/media",
                {
                    "fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count",
                    "limit": max(limit, 25),
                },
            )
            media_list = media_resp.get("data", []) if isinstance(media_resp, dict) else []

            reels = []
            for m in media_list:
                is_reel = m.get("media_product_type") == "REELS" or (
                    m.get("media_type") == "VIDEO" and m.get("media_product_type") in (None, "REELS")
                )
                if not is_reel:
                    continue
                ts = None
                try:
                    dt = datetime.fromisoformat(str(m.get("timestamp", "")).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    ts = dt
                except Exception:
                    ts = None
                if ts is not None and ts < cutoff:
                    continue

                plays = reach = saved = shares = total_interactions = None
                try:
                    ins = api_call(
                        "GET", f"{m['id']}/insights", {"metric": "plays,reach,saved,shares,total_interactions"}
                    )
                    rows = ins.get("data", []) if isinstance(ins, dict) else []
                    for row in rows:
                        name = row.get("name")
                        vals = row.get("values") or []
                        val = vals[0].get("value") if vals and isinstance(vals[0], dict) else None
                        if name == "plays":
                            plays = val
                        elif name == "reach":
                            reach = val
                        elif name == "saved":
                            saved = val
                        elif name == "shares":
                            shares = val
                        elif name == "total_interactions":
                            total_interactions = val
                except Exception:
                    pass

                reels.append(
                    {
                        "media_id": m.get("id"),
                        "permalink": m.get("permalink"),
                        "timestamp": m.get("timestamp"),
                        "caption": (m.get("caption") or "")[:120],
                        "likes": m.get("like_count"),
                        "comments": m.get("comments_count"),
                        "plays": plays,
                        "reach": reach,
                        "saved": saved,
                        "shares": shares,
                        "total_interactions": total_interactions,
                    }
                )

            reels.sort(key=lambda r: r.get("plays") or 0, reverse=True)

            def _sum(key):
                vals = [r.get(key) for r in reels if isinstance(r.get(key), (int, float))]
                return sum(vals) if vals else None

            totals = {
                "reels_analysed": len(reels),
                "plays": _sum("plays"),
                "reach": _sum("reach"),
                "saved": _sum("saved"),
                "shares": _sum("shares"),
                "total_interactions": _sum("total_interactions"),
                "likes": _sum("likes"),
                "comments": _sum("comments"),
            }
            avg_plays = round(totals["plays"] / len(reels), 1) if totals["plays"] is not None and reels else None

            return json_dumps(
                {
                    "account": ig_id,
                    "window_days": days,
                    "totals": totals,
                    "avg_plays_per_reel": avg_plays,
                    "top_reels": reels[:limit],
                    "note": "تحليلات Reels (plays/reach) — قد تتطلب صلاحيات insights على مستوى media",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "get_instagram_reels_account_insights"))

    def _host_local_for_ig(file_path: str) -> str:
        """رفع صورة محلية لإنستغرام → رابط دائم (Cloudinary) أو مؤقت (uguu.se fallback)."""
        try:
            from src.media_hosting import host_image

            return host_image(file_path)
        except Exception:
            from pathlib import Path

            import requests

            p = Path(file_path)
            if not p.exists():
                alt = Path(__file__).resolve().parent.parent / file_path
                if alt.exists():
                    p = alt
                else:
                    raise FileNotFoundError(f"الملف غير موجود: {file_path}") from None
            with open(p, "rb") as f:
                r = requests.post("https://uguu.se/upload.php", files={"files[]": f}, timeout=60)
                r.raise_for_status()
                data = r.json()
                if not data.get("success"):
                    raise RuntimeError(f"فشل الرفع: {data}") from None
                return data["files"][0]["url"].replace("http://", "https://")  # type: ignore[no-any-return]

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_carousel_from_media(
        caption: str = "",
        media_dir: str = "media",
        instagram_business_id: str = "",
        product_ids: str = "",
        product_x: float = 0.5,
        product_y: float = 0.5,
    ) -> str:
        """نشر كاروسيل إنستغرام مباشرة من مجلد محلي (media/*.jpeg) بدون رابط عام — يدعم Product Tagging.

        caption: النص + هاشتاغ
        media_dir: مجلد الصور المحلي (افتراضي "media")
        instagram_business_id: معرف إنستغرام (افتراضي FB_IG_USER_ID)
        product_ids: معرفات منتجات للـ Shopping Tags (اختياري) — مثال "38981123561474624"
        يقرأ 2-10 صور من المجلد، يرفعها لاستضافة دائمة (Cloudinary) ثم ينشر كاروسيل مع تاغ المنتجات.
        """
        try:
            from pathlib import Path

            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            base = Path(__file__).resolve().parent.parent / media_dir
            if not base.exists():
                return json_dumps({"error": f"المجلد غير موجود: {base}"})
            exts = {".jpg", ".jpeg", ".png", ".webp"}
            files = sorted([p for p in base.iterdir() if p.suffix.lower() in exts])
            if len(files) < 2:
                return json_dumps({"error": f"وجد {len(files)} صور في {base} — الكاروسيل يتطلب 2-10"})
            if len(files) > 10:
                files = files[:10]
            urls = []
            for f in files:
                urls.append(_host_local_for_ig(str(f)))
            # reuse existing carousel logic with optional product tagging
            import json as _json

            pids = [p.strip() for p in (product_ids or "").split(",") if p.strip()]
            child_ids = []
            for idx, url in enumerate(urls):
                params = {"image_url": url, "is_carousel_item": "true"}
                if pids:
                    if len(pids) == 1:
                        tags = [{"product_id": pids[0], "x": product_x, "y": product_y}]
                    else:
                        tags = [{"product_id": pids[idx % len(pids)], "x": product_x, "y": product_y}]
                    params["product_tags"] = _json.dumps(tags)
                child = api_call("POST", f"{ig_id}/media", params)
                cid = child.get("id")
                if not cid:
                    return json_dumps(child)
                child_ids.append(cid)
            container = api_call(
                "POST",
                f"{ig_id}/media",
                {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption},
            )
            creation_id = container.get("id")
            if not creation_id:
                return json_dumps(container)
            result = api_call("POST", f"{ig_id}/media_publish", {"creation_id": creation_id})
            return json_dumps(
                {"success": True, "children": child_ids, "container": container, "publish": result, "hosted_urls": urls}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_carousel_from_media"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_instagram_reel_from_media(
        caption: str = "",
        video_path: str = "media/reel.mp4",
        thumb_offset: int = 0,
        share_to_feed: bool = True,
        instagram_business_id: str = "",
    ) -> str:
        """نشر ريلز إنستغرام من ملف فيديو محلي (media/*.mp4) — يرفع تلقائيا لاستضافة دائمة ثم ينشر.

        video_path: مسار ملف الفيديو المحلي (مثال "media/video.mp4" أو "media/reel.mp4") — أو مجلد "media" سيختار أول .mp4
        caption: النص + هاشتاغ
        thumb_offset: إزاحة صورة الغلاف بالميلي ثانية
        share_to_feed: مشاركة في الخلاصة أيضاً
        يدعم Cloudinary للاستضافة الدائمة (سنة) أو uguu fallback.
        """
        try:
            from pathlib import Path

            from src.media_hosting import host_video

            ig_id = instagram_business_id or INSTAGRAM_BUSINESS_ID
            p = Path(video_path)
            if p.is_dir():
                # pick first video in dir
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
            # Reels need processing wait
            import time

            time.sleep(5)
            result = api_call("POST", f"{ig_id}/media_publish", {"creation_id": creation_id})
            return json_dumps({"success": True, "video_url": video_url, "container": container, "publish": result})
        except Exception as e:
            return json_dumps(handle_error(e, "publish_instagram_reel_from_media"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_threads_post(text: str, media_url: str = "") -> str:
        """
        نشر منشور Threads (عبر Graph API v19+ إن كان متاحًا).
        إن لم تكن Threads API مفعّلة للحساب، تُعاد رسالة إرشادية.
        """
        try:
            # Threads is tied to Instagram Business ID; try the threads endpoint
            ig_id = INSTAGRAM_BUSINESS_ID
            if not ig_id:
                return json_dumps({"error": "FB_IG_USER_ID غير مضبوط"})
            params: dict = {"text": text}
            if media_url:
                params["media_url"] = media_url
            # Attempt threads via Instagram endpoint; if not supported, API returns error
            data = api_call("POST", f"{ig_id}/threads_profile", params)
            # Fallback try generic threads endpoint
            if not data or "error" in str(data).lower():
                return json_dumps(
                    {
                        "message": "Threads API غير متاحة لهذا الحساب/التوكن. راجع https://developers.facebook.com/docs/threads/",
                        "attempted_params": params,
                        "response": data,
                    }
                )
            return json_dumps({"success": True, "result": data})
        except Exception as e:
            # Return guidance instead of raw error for better DX
            return json_dumps(
                handle_error(
                    e,
                    "publish_threads_post: Threads API قد تتطلب صلاحيات إضافية (threads_basic, threads_content_publish)",
                )
            )

    @mcp.resource("instagram://overview")
    async def instagram_resource() -> str:
        """نظرة عامة إنستغرام."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "instagram", "resource": "instagram://overview", "hint": "نظرة عامة إنستغرام"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "instagram://overview"))

    @mcp.prompt()
    def instagram_strategy_prompt(topic: str = "instagram") -> str:
        """استراتيجية إنستغرام."""
        return "ساعد في استراتيجية إنستغرام لـ " + topic + " — خطط محتوى إنستغرام لـ {product} (وحدة instagram)"

    @mcp.resource("instagram://recent")
    async def recent_instagram_resource() -> str:
        """آخر منشورات إنستغرام."""
        try:
            from src.config import INSTAGRAM_BUSINESS_ID
            from src.helpers import api_call

            def _fetch():
                ig_id = INSTAGRAM_BUSINESS_ID
                if not ig_id:
                    return {"data": []}
                return api_call("GET", f"{ig_id}/media", {"fields": "id,caption,media_type,timestamp", "limit": 10})

            t0 = time.monotonic()
            data = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("instagram://recent fetched in %.2fs", elapsed)
            return json_dumps(data)
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("instagram://recent failed")
            return json_dumps(handle_error(e, "instagram://recent"))

    @mcp.prompt()
    def instagram_caption_prompt(image_desc: str, style: str = "engaging") -> str:
        """توليد كابشن إنستغرام من وصف الصورة."""
        return (
            f"اكتب كابشن {style} لإنستغرام لصورة وصفها: {image_desc}. "
            "أضف 3 هاشتاغات عربية/إنجليزية ودعوة للتفاعل. استخدم generate_caption_from_image إن توفر رابط الصورة."
        )
