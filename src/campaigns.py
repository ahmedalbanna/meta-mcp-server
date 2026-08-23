import asyncio
import logging
import time

from src.config import AD_ACCOUNT_ID, resolve_ad_account_id

logger = logging.getLogger(__name__)


def register(mcp):
    """Register campaigns tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign

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
            from src.utils import paginate

            fields = [
                Campaign.Field.name,
                Campaign.Field.status,
                Campaign.Field.objective,
                Campaign.Field.daily_budget,
                Campaign.Field.lifetime_budget,
                Campaign.Field.created_time,
                Campaign.Field.id,
            ]
            extra = {}
            if status:
                extra["filtering"] = json_dumps([{"field": "status", "operator": "EQUAL", "value": status}])
            acct = resolve_ad_account_id(ad_account_id)
            rows = paginate(
                lambda params: AdAccount(acct).get_campaigns(params=params),
                fields=fields,
                params=extra or None,
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_campaigns"))

    @mcp.tool()
    @concurrency_limit()
    def get_campaign(campaign_id: str) -> str:
        """تفاصيل حملة واحدة."""
        try:
            campaign = Campaign(campaign_id)
            info = campaign.api_get(
                fields=[
                    Campaign.Field.name,
                    Campaign.Field.status,
                    Campaign.Field.objective,
                    Campaign.Field.daily_budget,
                    Campaign.Field.lifetime_budget,
                    Campaign.Field.buying_type,
                    Campaign.Field.created_time,
                    Campaign.Field.updated_time,
                ]
            )
            return json_dumps(to_dict(info))
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
            # v27 deprecation: map old objectives to new OUTCOME_* with warning
            orig_objective = objective
            objective = _DEPRECATED_OBJECTIVES.get(objective.strip().upper(), objective.strip().upper())
            if orig_objective.strip().upper() in _DEPRECATED_OBJECTIVES:
                import logging

                logging.getLogger(__name__).warning(
                    "objective '%s' deprecated — mapped to '%s' for Graph %s",
                    orig_objective,
                    objective,
                    __import__("src.config", fromlist=["GRAPH_VERSION"]).GRAPH_VERSION,
                )
            acct = resolve_ad_account_id(ad_account_id)
            account = AdAccount(acct)
            params = {
                Campaign.Field.name: name,
                Campaign.Field.objective: objective,
                Campaign.Field.status: status,
                Campaign.Field.special_ad_categories: [],
                "is_adset_budget_sharing_enabled": False,
            }
            if daily_budget and daily_budget > 0:
                params[Campaign.Field.daily_budget] = daily_budget
            if lifetime_budget and lifetime_budget > 0:
                params[Campaign.Field.lifetime_budget] = lifetime_budget
            if not (daily_budget or lifetime_budget):
                return json_dumps({"error": "يجب تحديد ميزانية يومية أو إجمالية"})
            campaign = account.create_campaign(params=params)
            return json_dumps(to_dict(campaign))
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
            valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
            status = status.upper()
            if status not in valid:
                return json_dumps({"error": f"status غير صالح. القيم: {', '.join(sorted(valid))}"})
            campaign = Campaign(campaign_id)
            result = campaign.api_update(params={Campaign.Field.status: status})
            return json_dumps(
                {"success": True, "campaign_id": campaign_id, "new_status": status, "result": to_dict(result)}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_campaign_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_campaign_budget(campaign_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> str:
        """تعديل ميزانية حملة (بالعملة الصغرى)."""
        try:
            campaign = Campaign(campaign_id)
            params = {}
            if daily_budget and daily_budget > 0:
                params[Campaign.Field.daily_budget] = daily_budget
            if lifetime_budget and lifetime_budget > 0:
                params[Campaign.Field.lifetime_budget] = lifetime_budget
            if not params:
                return json_dumps({"error": "حدد ميزانية يومية أو إجمالية"})
            result = campaign.api_update(params=params)
            return json_dumps({"success": True, "campaign_id": campaign_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "update_campaign_budget"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_campaign(campaign_id: str) -> str:
        """حذف حملة نهائيًا."""
        try:
            campaign = Campaign(campaign_id)
            result = campaign.api_delete()
            return json_dumps({"success": True, "campaign_id": campaign_id, "result": to_dict(result)})
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
