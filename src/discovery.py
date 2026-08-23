"""Discovery tools: find the correct Page / Ad Account / Instagram IDs for .env.

Run these first to confirm object ids before wiring FB_PAGE_ID / FB_AD_ACCOUNT_ID
/ FB_IG_USER_ID in .env.
"""

import logging

from src.config import APP_ID, APP_SECRET, META_ACCESS_TOKEN

logger = logging.getLogger(__name__)
from src.helpers import api_call, handle_error, json_dumps
from src.throttle import concurrency_limit


def register(mcp):
    """Register discovery + config tools."""

    @mcp.tool()
    @concurrency_limit()
    def list_pages(limit: int = 25) -> str:
        """قائمة صفحات فيسبوك التي تديرها الحسابات المرتبطة بالتوكن."""
        try:
            data = api_call(
                "GET",
                "me/accounts",
                {"fields": "name,id,category,link,access_token", "limit": limit},
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_pages"))

    @mcp.tool()
    @concurrency_limit()
    def list_ad_accounts(limit: int = 25) -> str:
        """قائمة الحسابات الإعلانية المتاحة لهذا التوكن."""
        try:
            data = api_call(
                "GET",
                "me/adaccounts",
                {
                    "fields": "name,account_id,currency,account_status,amount_spent",
                    "limit": limit,
                },
            )
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
            if page_id:
                data = api_call(
                    "GET",
                    page_id,
                    {"fields": "name,instagram_business_account{id,username}"},
                )
                return json_dumps(data)
            pages = api_call("GET", "me/accounts", {"fields": "name,id"})
            out = []
            for p in pages.get("data", []):
                row = {
                    "page_id": p.get("id"),
                    "page_name": p.get("name"),
                    "instagram": None,
                }
                try:
                    detail = api_call(
                        "GET",
                        p["id"],
                        {"fields": "instagram_business_account{id,username}"},
                    )
                    ig = detail.get("instagram_business_account") or {}
                    row["instagram"] = {
                        "id": ig.get("id"),
                        "username": ig.get("username"),
                    }
                except Exception:
                    row["instagram"] = "غير مرتبط أو بدون صلاحية"
                out.append(row)
            return json_dumps(out)
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
            token = input_token or META_ACCESS_TOKEN
            if not APP_ID or not APP_SECRET:
                return json_dumps({"error": "حدد FB_APP_ID و FB_APP_SECRET في .env"})
            data = api_call(
                "GET",
                "debug_token",
                {
                    "input_token": token,
                    "access_token": f"{APP_ID}|{APP_SECRET}",
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "debug_access_token"))

    @mcp.tool()
    @concurrency_limit()
    def config_status() -> str:
        """حالة الإعداد الحالية (أي معرفات مملوءة في .env) بدون كشف الأسرار."""
        from src.config import (
            AD_ACCOUNT_ID,
            ADS_ALLOW_ACTIVATE,
            APP_ID,
            BUSINESS_ID,
            DRY_RUN,
            ENABLE_WRITES,
            GRAPH_VERSION,
            INSTAGRAM_BUSINESS_ID,
            MAX_DAILY_BUDGET,
            MAX_LIFETIME_BUDGET,
            META_ACCESS_TOKEN,
            PAGE_ACCESS_TOKEN,
            PAGE_ID,
        )
        from src.helpers import get_page_access_token

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
            from src.helpers import handle_error

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
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "discovery://templates"))

    @mcp.prompt()
    def discovery_check_prompt(topic: str = "discovery") -> str:
        """فحص اكتشاف."""
        return "ساعد في فحص اكتشاف لـ " + topic + " — تحقق من اكتشاف {resource} (وحدة discovery)"
