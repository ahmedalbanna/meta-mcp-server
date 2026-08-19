from pathlib import Path

from src.config import AD_ACCOUNT_ID


def register(mcp):
    """Register ads and creatives tools."""

    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adcreative import AdCreative
    from facebook_business.adobjects.adimage import AdImage
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.advideo import AdVideo

    from src.helpers import handle_error, json_dumps, sanitize_path, to_dict, write_guard
    from src.throttle import concurrency_limit

    def _build_object_story_spec(
        page_id: str,
        message: str,
        image_hash: str = "",
        image_url: str = "",
        video_id: str = "",
        link: str = "",
        headline: str = "",
        call_to_action: str = "",
    ) -> dict:
        """Build an object_story_spec dict for ad creative creation."""
        media = {}
        if image_hash:
            media["image_hash"] = image_hash
        elif image_url:
            media["image_url"] = image_url
        if link:
            media["link"] = link
        if headline:
            media["name"] = headline
        if call_to_action:
            media["call_to_action"] = {"type": call_to_action}
        if video_id:
            media["video_id"] = video_id
            story_key = "video_data"
        else:
            story_key = "link_data"
        return {"page_id": page_id, story_key: {**media, "message": message}}

    @mcp.tool()
    @concurrency_limit()
    def list_ads(adset_id: str = "", limit: int = 25) -> str:
        """قائمة الإعلانات (يمكن تحديد مجموعة إعلانية معينة)."""
        try:
            params = {
                "fields": [
                    Ad.Field.name,
                    Ad.Field.status,
                    Ad.Field.creative,
                    Ad.Field.adset_id,
                    Ad.Field.created_time,
                    Ad.Field.id,
                ],
                "limit": limit,
            }
            if adset_id:
                ads = AdSet(adset_id).get_ads(params=params)
            else:
                ads = AdAccount(AD_ACCOUNT_ID).get_ads(params=params)
            return json_dumps([to_dict(a) for a in ads])
        except Exception as e:
            return json_dumps(handle_error(e, "list_ads"))

    @mcp.tool()
    @concurrency_limit()
    def get_ad(ad_id: str) -> str:
        """تفاصيل إعلان واحد."""
        try:
            ad = Ad(ad_id)
            info = ad.api_get(
                fields=[
                    Ad.Field.name,
                    Ad.Field.status,
                    Ad.Field.creative,
                    Ad.Field.adset_id,
                    Ad.Field.created_time,
                    Ad.Field.updated_time,
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_ad"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_ad_status(ad_id: str, status: str) -> str:
        """تغيير حالة إعلان (ACTIVE, PAUSED, DELETED, ARCHIVED)."""
        try:
            ad = Ad(ad_id)
            ad.api_update(params={Ad.Field.status: status})
            return json_dumps({"success": True, "ad_id": ad_id, "new_status": status})
        except Exception as e:
            return json_dumps(handle_error(e, "update_ad_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def upload_image(name: str = "", image_url: str = "", file_path: str = "") -> str:
        """
        رفع صورة إلى مكتبة حساب إعلاني والعودة بمعرّف الهاش.
        قدّم image_url (رابط خارجي) أو file_path (مسار محلي).
        """
        try:
            if not image_url and not file_path:
                return json_dumps({"error": "قدّم image_url أو file_path"})
            image = AdImage(parent_id=AD_ACCOUNT_ID)
            params = {}
            if image_url:
                params[AdImage.Field.url] = image_url
            if file_path:
                try:
                    resolved = sanitize_path(file_path, Path.cwd())
                except ValueError as e:
                    return json_dumps({"error": f"مسار غير صالح: {e}"})
                if not resolved.is_file():
                    return json_dumps({"error": f"الملف غير موجود: {file_path}"})
                params[AdImage.Field.filename] = str(resolved)
            if name:
                params[AdImage.Field.name] = name
            result = image.api_create(parent_id=AD_ACCOUNT_ID, params=params)
            data = to_dict(result) if result is not None else {}
            return json_dumps(
                {
                    "hash": data.get("hash"),
                    "image_id": data.get("id"),
                    "details": data,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "upload_image"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def upload_video(title: str = "", file_path: str = "", video_url: str = "") -> str:
        """
        رفع فيديو إلى حساب إعلاني والعودة بمعرّف الفيديو.
        قدّم file_path (مسار محلي) أو video_url (رابط مباشر).
        """
        try:
            if not file_path and not video_url:
                return json_dumps({"error": "قدّم file_path أو video_url"})
            video = AdVideo(parent_id=AD_ACCOUNT_ID)
            params = {}
            if file_path:
                try:
                    resolved = sanitize_path(file_path, Path.cwd())
                except ValueError as e:
                    return json_dumps({"error": f"مسار غير صالح: {e}"})
                if not resolved.is_file():
                    return json_dumps({"error": f"الملف غير موجود: {file_path}"})
                params[AdVideo.Field.filename] = str(resolved)
            if video_url:
                params[AdVideo.Field.file_url] = video_url
            if title:
                params[AdVideo.Field.title] = title
            video.api_create(parent_id=AD_ACCOUNT_ID, params=params)
            return json_dumps({"video_id": video.get_id(), "title": title})
        except Exception as e:
            return json_dumps(handle_error(e, "upload_video"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_ad_creative(
        name: str,
        page_id: str,
        message: str,
        image_hash: str = "",
        image_url: str = "",
        video_id: str = "",
        link: str = "",
        headline: str = "",
        call_to_action: str = "",
    ) -> str:
        """
        إنشاء تصميم إعلان (Creative) فقط عبر object_story_spec.
        image_hash أو image_url للصورة، أو video_id للفيديو.
        call_to_action مثل: LEARN_MORE, SHOP_NOW, BUY_NOW, SIGN_UP
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            object_story_spec = _build_object_story_spec(
                page_id, message, image_hash, image_url, video_id, link, headline, call_to_action
            )
            params = {
                AdCreative.Field.name: name,
                AdCreative.Field.object_story_spec: json_dumps(object_story_spec),
            }
            creative = account.create_ad_creative(params=params)
            return json_dumps(to_dict(creative))
        except Exception as e:
            return json_dumps(handle_error(e, "create_ad_creative"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_ad(
        adset_id: str,
        name: str,
        creative_name: str,
        page_id: str,
        message: str,
        image_hash: str = "",
        image_url: str = "",
        video_id: str = "",
        link: str = "",
        headline: str = "",
        call_to_action: str = "",
        status: str = "PAUSED",
    ) -> str:
        """
        إنشاء إعلان: يُنشئ تصميمًا (Creative) ثم يربطه بالمجموعة الإعلانية.
        الصفحة page_id يجب أن تكون مرتبطة بالحساب الإعلاني.
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            object_story_spec = _build_object_story_spec(
                page_id, message, image_hash, image_url, video_id, link, headline, call_to_action
            )
            creative = account.create_ad_creative(
                params={
                    AdCreative.Field.name: creative_name,
                    AdCreative.Field.object_story_spec: json_dumps(object_story_spec),
                }
            )
            params = {
                Ad.Field.name: name,
                "adset_id": adset_id,
                "creative_id": creative.get_id(),
                Ad.Field.status: status,
            }
            ad = account.create_ad(params=params)
            return json_dumps(to_dict(ad))
        except Exception as e:
            return json_dumps(handle_error(e, "create_ad"))
