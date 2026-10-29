import asyncio
import logging
import time

from src.config import AD_ACCOUNT_ID, resolve_ad_account_id

logger = logging.getLogger(__name__)


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
    media: dict[str, object] = {}
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

def register(mcp, services=None):
    """Register ads and creatives tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adcreative import AdCreative

    from src.helpers import handle_error, json_dumps, to_dict, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_ads(adset_id: str = "", limit: int = 25, ad_account_id: str = "") -> str:
        """قائمة الإعلانات (يمكن تحديد مجموعة إعلانية معينة)."""
        try:
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            data = svc.list_ads(adset_id, limit, ad_account_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_ads"))

    @mcp.tool()
    @concurrency_limit()
    def get_ad(ad_id: str) -> str:
        """تفاصيل إعلان واحد."""
        try:
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            data = svc.get_ad(ad_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_ad"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_ad_status(ad_id: str, status: str) -> str:
        """تغيير حالة إعلان (ACTIVE, PAUSED, DELETED, ARCHIVED)."""
        try:
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            return json_dumps(svc.update_status(ad_id, status))
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
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            return json_dumps(svc.upload_image(name, image_url, file_path))
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
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            return json_dumps(svc.upload_video(title, file_path, video_url))
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
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            return json_dumps(svc.create_ad_creative(name, page_id, message, image_hash, image_url, video_id, link, headline, call_to_action))
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
            from src.core.services import Services
            from src.services.ads_service import AdsService
            svc = AdsService(services) if services is not None else AdsService(Services.default())
            return json_dumps(svc.create_ad(adset_id, name, creative_name, page_id, message, image_hash, image_url, video_id, link, headline, call_to_action, status))
        except Exception as e:
            return json_dumps(handle_error(e, "create_ad"))

    @mcp.tool()
    @concurrency_limit()
    def list_ad_creatives(limit: int = 25, ad_account_id: str = "") -> str:
        """قائمة الإبداعات (Ad Creatives) في الحساب الإعلاني."""
        try:
            from src.utils import paginate

            rows = paginate(
                lambda params: AdAccount(resolve_ad_account_id(ad_account_id)).get_ad_creatives(params=params),
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_ad_creatives"))

    @mcp.tool()
    @concurrency_limit()
    def get_ad_creative(creative_id: str) -> str:
        """تفاصيل إبداع (Ad Creative) واحد."""
        try:
            creative = AdCreative(creative_id)
            creative.api_read()
            return json_dumps(to_dict(creative))
        except Exception as e:
            return json_dumps(handle_error(e, "get_ad_creative"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_ad_creative(creative_id: str) -> str:
        """حذف إبداع (Ad Creative) نهائيًا."""
        try:
            creative = AdCreative(creative_id)
            creative.api_delete()
            return json_dumps({"success": True, "creative_id": creative_id})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_ad_creative"))

    @mcp.resource("ads://overview")
    async def ads_resource() -> str:
        """نظرة عامة على الإعلانات."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "ads", "resource": "ads://overview", "hint": "نظرة عامة على الإعلانات"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "ads://overview"))

    @mcp.prompt()
    def ad_review_prompt(topic: str = "ads") -> str:
        """مراجعة إعلان."""
        return "ساعد في مراجعة إعلان لـ " + topic + " — راجع إعلان {ad_id} (وحدة ads)"

    @mcp.resource("ads://active")
    async def active_ads_resource() -> str:
        """قائمة الإعلانات النشطة."""
        try:

            def _fetch():
                account = AdAccount(AD_ACCOUNT_ID)
                return account.get_ads(
                    params={
                        "fields": ["name", "status", "creative", "id"],
                        "filtering": json_dumps([{"field": "status", "operator": "EQUAL", "value": "ACTIVE"}]),
                    }
                )

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("ads://active fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("ads://active failed")
            return json_dumps(handle_error(e, "ads://active"))
