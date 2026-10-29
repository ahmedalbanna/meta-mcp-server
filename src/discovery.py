"""Discovery tools: find the correct Page / Ad Account / Instagram IDs for .env.

Run these first to confirm object ids before wiring FB_PAGE_ID / FB_AD_ACCOUNT_ID
/ FB_IG_USER_ID in .env.
"""

import logging

from src.core.config import APP_ID, APP_SECRET, META_ACCESS_TOKEN

logger = logging.getLogger(__name__)
from src.throttle import concurrency_limit
from src.utils import api_call, handle_error, json_dumps


def register(mcp, services):
    """Register discovery + config tools."""

    @mcp.tool()
    @concurrency_limit()
    def list_pages(limit: int = 25) -> str:
        """قائمة صفحات فيسبوك التي تديرها الحسابات المرتبطة بالتوكن."""
        try:
            from src.core.services import Services
            from src.services.discovery_service import DiscoveryService
            svc = DiscoveryService(services)
            data = svc.list_pages(limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_pages"))

    @mcp.tool()
    @concurrency_limit()
    def list_ad_accounts(limit: int = 25) -> str:
        """قائمة الحسابات الإعلانية المتاحة لهذا التوكن."""
        try:
            from src.core.services import Services
            from src.services.discovery_service import DiscoveryService
            svc = DiscoveryService(services)
            data = svc.list_ad_accounts(limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_ad_accounts"))

    @mcp.tool()
    @concurrency_limit()
    def discover_ig_user(page_id: str = "") -> str:
        """
        اكتشاف حساب إنستغرام المرتبط بصفحة فيسبوك.
        page_id اختياري؛ إن تُرك فارغًا يفحص كل الصفحات المتاحة.
        """
        try:
            from src.core.services import Services
            from src.services.discovery_service import DiscoveryService
            svc = DiscoveryService(services)
            data = svc.discover_ig_user(page_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "discover_ig_user"))

    @mcp.tool()
    @concurrency_limit()
    def debug_access_token(input_token: str = "") -> str:
        """
        فحص نوع التوكن وصلاحياته وتاريخ انتهائه.
        input_token اختياري؛ إن تُرك فارغًا يُفحص توكن .env الحالي.
        """
        try:
            from src.core.services import Services
            from src.services.discovery_service import DiscoveryService
            svc = DiscoveryService(services)
            data = svc.debug_access_token(input_token)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "debug_access_token"))

    @mcp.tool()
    @concurrency_limit()
    def config_status() -> str:
        """حالة الإعداد الحالية (أي معرفات مملوءة في .env) بدون كشف الأسرار."""
        from src.core.config import (
            AD_ACCOUNT_ID,
            ADS_ALLOW_ACTIVATE,
            ANALYTICS_TZ,
            BUSINESS_ID,
            DRY_RUN,
            ENABLE_WRITES,
            FB_CROSS_PLATFORM_TIKTOK,
            FB_CURRENCY_DEFAULT,
            FB_ENABLE_OCR,
            FB_PHONE_COUNTRY_CODE,
            GRAPH_VERSION,
            INSTAGRAM_BUSINESS_ID,
            MAX_DAILY_BUDGET,
            MAX_LIFETIME_BUDGET,
            PAGE_ACCESS_TOKEN,
            PAGE_ID,
        )
        from src.utils import get_page_access_token

        page_token = ""
        try:
            page_token = "مضبوط (مشتق تلقائيًا)" if get_page_access_token() else "ناقص"
        except Exception:
            page_token = "تعذّر الاشتقاق (تحقق من صلاحيات الصفحة)"

        return json_dumps(
            {
                "token": "مضبوط" if META_ACCESS_TOKEN else "ناقص",
                "page_token": page_token,
                "page_token_override": "نعم" if PAGE_ACCESS_TOKEN else "لا (تلقائي)",
                "api_version": GRAPH_VERSION,
                "ad_account_id": AD_ACCOUNT_ID or "غير محدد",
                "page_id": PAGE_ID or "غير محدد",
                "instagram_business_id": INSTAGRAM_BUSINESS_ID or "غير محدد",
                "business_id": BUSINESS_ID or "غير محدد",
                "app_id": APP_ID or "غير محدد",
                "analytics": {
                    "tz": ANALYTICS_TZ,
                    "currency_default": FB_CURRENCY_DEFAULT,
                    "phone_country_code": FB_PHONE_COUNTRY_CODE,
                    "ocr_enabled": FB_ENABLE_OCR,
                    "cross_platform_tiktok": FB_CROSS_PLATFORM_TIKTOK,
                },
                "guardrails": {
                    "enable_writes": ENABLE_WRITES,
                    "dry_run": DRY_RUN,
                    "allow_activate": ADS_ALLOW_ACTIVATE,
                    "max_daily_budget": MAX_DAILY_BUDGET or "بدون حد",
                    "max_lifetime_budget": MAX_LIFETIME_BUDGET or "بدون حد",
                },
                "hint": "استخدم list_pages و list_ad_accounts و discover_ig_user لاكتشاف المعرفات ثم عبّئ .env وأعد التشغيل",
            }
        )

    @mcp.resource("discovery://status")
    async def discovery_resource() -> str:
        """حالة الاكتشاف."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "discovery", "resource": "discovery://status", "hint": "حالة الاكتشاف"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "discovery://status"))

    @mcp.prompt()
    def discovery_guide_prompt(topic: str = "discovery") -> str:
        """دليل اكتشاف."""
        return "ساعد في دليل اكتشاف لـ " + topic + " — اشرح كيفية اكتشاف {what} (وحدة discovery)"

    @mcp.resource("discovery://templates")
    async def discovery_extra_resource() -> str:
        """قوالب الاكتشاف."""
        try:
            return json_dumps({"module": "discovery", "resource": "discovery://templates", "hint": "قوالب الاكتشاف"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "discovery://templates"))

    @mcp.prompt()
    def discovery_check_prompt(topic: str = "discovery") -> str:
        """فحص اكتشاف."""
        return "ساعد في فحص اكتشاف لـ " + topic + " — تحقق من اكتشاف {resource} (وحدة discovery)"
