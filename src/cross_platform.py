"""Cross-platform competitor intelligence (Phase 4).

Best-effort, feature-gated scrapers for platforms Meta does not cover (TikTok)
plus unified 360° views. TikTok scraping is fragile and gated behind
FB_CROSS_PLATFORM_TIKTOK; treat results as indicative only.
"""

import logging
import re

from src.helpers import handle_error, json_dumps
from src.throttle import concurrency_limit

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}


def _og(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
    if m:
        return m.group(1)
    m = re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:{prop}["\']', html, re.I)
    return m.group(1) if m else None


def register(mcp, services=None):
    """Register cross-platform tools."""

    @mcp.tool()
    @concurrency_limit()
    def tiktok_profile(handle: str) -> str:
        """(Experimental) جلب ملف TikTok عام (اسم، bio، متابعون) via scraping.

        handle: اسم حساب TikTok (بدون @)
        يتطلب FB_CROSS_PLATFORM_TIKTOK=true. النتائج استرشادية وقد تتعطّل.
        """
        try:
            from src.core.services import Services
            from src.services.cross_platform_service import CrossPlatformService
            svc = CrossPlatformService(services) if services is not None else CrossPlatformService(Services.default())
            return json_dumps(svc.tiktok_profile(handle))
        except Exception as e:
            return json_dumps(handle_error(e, "tiktok_profile"))

    @mcp.tool()
    @concurrency_limit()
    def whatsapp_business_link(phone: str, message: str = "مرحباً، أود الاستفسار عن منتجاتكم") -> str:
        """توليد رابط WhatsApp Click-to-Chat (wa.me) لرقم (Yemen +967 default)."""
        try:
            from src.core.services import Services
            from src.services.cross_platform_service import CrossPlatformService
            svc = CrossPlatformService(services) if services is not None else CrossPlatformService(Services.default())
            return json_dumps(svc.whatsapp_link(phone, message))
        except Exception as e:
            return json_dumps(handle_error(e, "whatsapp_business_link"))

    @mcp.tool()
    @concurrency_limit()
    def competitor_360(handle: str, page_id: str = "", phone: str = "") -> str:
        """عرض 360° لمنافس across platforms: Instagram (Meta) + Facebook page + TikTok (if enabled) + WhatsApp link.

        handle: اسم حساب IG/TikTok (بدون @)
        page_id: معرف صفحة FB (اختياري)
        phone: رقم WhatsApp (اختياري) لتوليد wa.me link
        """
        try:
            from src.core.services import Services
            from src.services.cross_platform_service import CrossPlatformService
            svc = CrossPlatformService(services) if services is not None else CrossPlatformService(Services.default())
            result = svc.competitor_360(handle, page_id, phone)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "competitor_360"))
