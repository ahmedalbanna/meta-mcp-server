import asyncio
import logging
import time

from src.config import AD_ACCOUNT_ID

logger = logging.getLogger(__name__)


def register(mcp, services=None):
    """Register campaigns tools."""

    from facebook_business.adobjects.adaccount import AdAccount

    from src.helpers import handle_error, json_dumps, to_dict, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_campaigns(status: str = "", limit: int = 25, ad_account_id: str = "") -> str:
        """
        قائمة الحملات الإعلانية في الحساب.
        status اختياري: ACTIVE, PAUSED, DELETED, ARCHIVED
        ad_account_id: معرف حساب إعلاني بديل (اختياري — افتراضي FB_AD_ACCOUNT_ID / الأول في FB_AD_ACCOUNT_IDS)
        """
        try:
            from src.core.services import Services
            from src.services.campaigns_service import CampaignsService
            svc = CampaignsService(services) if services is not None else CampaignsService(Services.default())
            data = svc.list_campaigns(status, limit, ad_account_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_campaigns"))

    @mcp.tool()
    @concurrency_limit()
    def get_campaign(campaign_id: str) -> str:
        """تفاصيل حملة واحدة."""
        try:
            from src.core.services import Services
            from src.services.campaigns_service import CampaignsService
            svc = CampaignsService(services) if services is not None else CampaignsService(Services.default())
            data = svc.get_campaign(campaign_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_campaign"))

    # Phase 5.3 — v27 deprecation watch
    _DEPRECATED_OBJECTIVES = {
        "LINK_CLICKS": "OUTCOME_TRAFFIC",
        "CONVERSIONS": "OUTCOME_SALES",
        "LEAD_GENERATION": "OUTCOME_LEADS",
        "REACH": "OUTCOME_AWARENESS",
        "BRAND_AWARENESS": "OUTCOME_AWARENESS",
        "APP_INSTALLS": "OUTCOME_APP_PROMOTION",
        "VIDEO_VIEWS": "OUTCOME_ENGAGEMENT",
        "MESSAGES": "OUTCOME_ENGAGEMENT",
        "ENGAGEMENT": "OUTCOME_ENGAGEMENT",
    }

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_campaign(
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        daily_budget: int = 0,
        lifetime_budget: int = 0,
        status: str = "PAUSED",
        ad_account_id: str = "",
    ) -> str:
        """
        إنشاء حملة جديدة.
        objective: OUTCOME_TRAFFIC, OUTCOME_ENGAGEMENT, OUTCOME_AWARENESS,
                   CONVERSIONS, LEAD_GENERATION, OUTCOME_SALES... (يدعم أسماء قديمة مع تحويل تلقائي)
        الميزانية بالعملة الصغرى (مثال 1000 = 10 دولار). حدد daily_budget أو lifetime_budget.
        ad_account_id: معرف حساب إعلاني بديل (اختياري)
        """
        try:
            from src.core.services import Services
            from src.services.campaigns_service import CampaignsService
            svc = CampaignsService(services) if services is not None else CampaignsService(Services.default())
            data = svc.create_campaign(name, objective, daily_budget, lifetime_budget, status, ad_account_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_campaign"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_campaign_status(campaign_id: str, status: str) -> str:
        """
        تغيير حالة حملة.
        status: ACTIVE, PAUSED, DELETED, ARCHIVED
        """
        try:
            from src.core.services import Services
            from src.services.campaigns_service import CampaignsService
            svc = CampaignsService(services) if services is not None else CampaignsService(Services.default())
            data = svc.update_status(campaign_id, status)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "update_campaign_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_campaign_budget(campaign_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> str:
        """تعديل ميزانية حملة (بالعملة الصغرى)."""
        try:
            from src.core.services import Services
            from src.services.campaigns_service import CampaignsService
            svc = CampaignsService(services) if services is not None else CampaignsService(Services.default())
            data = svc.update_budget(campaign_id, daily_budget, lifetime_budget)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "update_campaign_budget"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_campaign(campaign_id: str) -> str:
        """حذف حملة نهائيًا."""
        try:
            from src.core.services import Services
            from src.services.campaigns_service import CampaignsService
            svc = CampaignsService(services) if services is not None else CampaignsService(Services.default())
            data = svc.delete(campaign_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "delete_campaign"))

    @mcp.resource("campaigns://overview")
    async def campaigns_resource() -> str:
        """نظرة عامة على الحملات مع ملخص سريع."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {
                    "module": "campaigns",
                    "resource": "campaigns://overview",
                    "hint": "نظرة عامة على الحملات مع ملخص سريع",
                }
            )
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "campaigns://overview"))

    @mcp.prompt()
    def campaign_strategy_prompt(topic: str = "campaigns") -> str:
        """استراتيجية حملة."""
        return (
            "ساعد في استراتيجية حملة لـ "
            + topic
            + " — اكتب استراتيجية حملة لمنتج {product} بهدف {objective} (وحدة campaigns)"
        )

    @mcp.resource("campaigns://active")
    async def active_campaigns_resource() -> str:
        """قائمة الحملات النشطة كـ JSON."""
        try:

            def _fetch():
                account = AdAccount(AD_ACCOUNT_ID)
                return account.get_campaigns(
                    params={
                        "fields": ["name", "status", "id"],
                        "filtering": json_dumps(
                            [
                                {
                                    "field": "status",
                                    "operator": "EQUAL",
                                    "value": "ACTIVE",
                                }
                            ]
                        ),
                    }
                )

            t0 = time.monotonic()
            campaigns = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info(
                "campaigns://active fetched %d campaigns in %.2fs",
                len(list(campaigns)),
                elapsed,
            )
            return json_dumps([to_dict(c) for c in campaigns])
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("campaigns://active failed")
            return json_dumps(handle_error(e, "campaigns://active"))

    @mcp.prompt()
    def campaign_creation_prompt(objective: str, product: str, budget: str = "") -> str:
        """مساعد إنشاء حملة كاملة (objective → adset → ad)."""
        budget_line = f" بميزانية {budget}" if budget else ""
        return (
            f"أنشئ حملة جديدة بهدف {objective} لمنتج {product}{budget_line}. "
            "حدد: الاسم، الميزانية، الاستهداف (الدولة/العمر/الاهتمامات)، "
            "والمجموعة الإعلانية (Advantage+ Audience)، ثم الإبداع (صورة/فيديو + نص + CTA). "
            "استخدم create_campaign → create_adset → create_ad."
        )
