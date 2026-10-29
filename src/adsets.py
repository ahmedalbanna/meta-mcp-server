import asyncio
import logging
import time

logger = logging.getLogger(__name__)


def register(mcp, services):
    """Register ad set tools."""

    from src.throttle import concurrency_limit
    from src.utils import handle_error, json_dumps, to_dict, write_guard

    @mcp.tool()
    @concurrency_limit()
    def list_adsets(campaign_id: str = "", limit: int = 25, ad_account_id: str = "") -> str:
        """قائمة المجموعات الإعلانية (يمكن تحديد حملة معينة)."""
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            data = svc.list_adsets(campaign_id, limit, ad_account_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_adsets"))

    @mcp.tool()
    @concurrency_limit()
    def get_adset(adset_id: str) -> str:
        """تفاصيل مجموعة إعلانية واحدة."""
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            data = svc.get_adset(adset_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_adset"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_adset(
        campaign_id: str,
        name: str,
        daily_budget: int = 0,
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        targeting: str = "",
        status: str = "PAUSED",
        bid_amount: int = 0,
        advantage_audience: bool = False,
        ad_account_id: str = "",
    ) -> str:
        """
        إنشاء مجموعة إعلانية داخل حملة.
        targeting: JSON نصي مثل {"geo_locations":{"countries":["US"]},"age_min":18,"age_max":65}
        bid_amount: سقف عرض إلزامي لهذه الحسابات (بالعملة الصغرى). 0 يستخدم LOWEST_COST_WITHOUT_CAP.
        advantage_audience: تفعيل Advantage+ Audience (توسيع الاستهداف تلقائيًا) — افتراضي false للتحكم الدقيق.
        """
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            data = svc.create_adset(
                name,
                campaign_id,
                daily_budget,
                optimization_goal,
                billing_event,
                targeting,
                status,
                bid_amount,
                advantage_audience,
                ad_account_id,
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_adset"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_status(adset_id: str, status: str) -> str:
        """تغيير حالة مجموعة إعلانية (ACTIVE, PAUSED, DELETED, ARCHIVED)."""
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            return json_dumps(svc.update_status(adset_id, status))
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_budget(adset_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> str:
        """تعديل ميزانية مجموعة إعلانية (بالعملة الصغرى)."""
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            return json_dumps(svc.update_budget(adset_id, daily_budget, lifetime_budget))
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_budget"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_targeting(adset_id: str, targeting: str, advantage_audience: bool | None = None) -> str:
        """
        تعديل استهداف مجموعة إعلانية.
        targeting: JSON نصي مثل {"geo_locations":{"countries":["EG"]},"age_min":18,"interests":[]}
        advantage_audience: None=عدم تغيير، true/false لضبط Advantage+ Audience
        """
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            return json_dumps(svc.update_targeting(adset_id, targeting, advantage_audience))
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_targeting"))

    @mcp.tool()
    @concurrency_limit()
    def get_adset_delivery_insights(
        adset_id: str,
        date_preset: str = "last_7d",
        metrics: str = "spend,impressions,reach,frequency,cpm,ctr,cpc",
    ) -> str:
        """تحليلات التسليم لمجموعة إعلانية (delivery insights: spend/reach/frequency)."""
        try:
            from src.services.adsets_service import AdsetsService

            svc = AdsetsService(services)
            rows = svc.get_delivery_insights(adset_id, date_preset, metrics)
            if not rows:
                return json_dumps({"data": [], "count": 0, "message": "لا توجد بيانات", "adset_id": adset_id})
            return json_dumps({"data": rows, "count": len(rows), "adset_id": adset_id})
        except Exception as e:
            return json_dumps(handle_error(e, "get_adset_delivery_insights"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def schedule_adset(
        adset_id: str,
        start_time: str = "",
        end_time: str = "",
    ) -> str:
        """
        جدولة مجموعة إعلانية: تعيين وقت بدء و/أو انتهاء.
        start_time / end_time بصيغة ISO مثل 2026-09-01T18:00:00+0300
        """
        try:
            params = {}
            if start_time:
                params["start_time"] = start_time
            if end_time:
                params["end_time"] = end_time
            if not params:
                return json_dumps({"error": "حدد start_time و/أو end_time"})
            services.api.post(f"{adset_id}", params)
            return json_dumps({"success": True, "adset_id": adset_id, "scheduled": params})
        except Exception as e:
            return json_dumps(handle_error(e, "schedule_adset"))

    @mcp.resource("adsets://overview")
    async def adsets_resource() -> str:
        """نظرة عامة على المجموعات الإعلانية."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "adsets", "resource": "adsets://overview", "hint": "نظرة عامة على المجموعات الإعلانية"}
            )
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "adsets://overview"))

    @mcp.prompt()
    def adset_strategy_prompt(topic: str = "adsets") -> str:
        """استراتيجية مجموعة إعلانية."""
        return "ساعد في استراتيجية مجموعة إعلانية لـ " + topic + " — اقترح مجموعة إعلانية لمنتج {product} (وحدة adsets)"

    @mcp.resource("adsets://active")
    async def active_adsets_resource() -> str:
        """قائمة المجموعات الإعلانية النشطة."""
        try:

            def _fetch():
                acct = services.config.fb_ad_account_id
                return services.api.get(
                    f"{acct}/adsets",
                    params={
                        "fields": ["name", "status", "daily_budget", "id"],
                        "filtering": json_dumps([{"field": "status", "operator": "EQUAL", "value": "ACTIVE"}]),
                    },
                )

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("adsets://active fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.utils import handle_error

            logger.exception("adsets://active failed")
            return json_dumps(handle_error(e, "adsets://active"))

    @mcp.prompt()
    def adset_targeting_prompt(product: str, country: str = "EG", age: str = "18-65") -> str:
        """مساعد استهداف مجموعة إعلانية."""
        return (
            f"اقترح استهدافًا لمجموعة إعلانية لمنتج {product} في {country} للعمر {age}. "
            "اذكر: geo_locations، age_min/max، gender، interests/behaviors، "
            "وأعداد Advantage+ Audience (0=دقيق، 1=موسع). أرجع JSON جاهز لـ create_adset."
        )
