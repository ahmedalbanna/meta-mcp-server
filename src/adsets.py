import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

from src.config import AD_ACCOUNT_ID


def register(mcp):
    """Register ad set tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.campaign import Campaign

    from src.helpers import handle_error, json_dumps, to_dict, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_adsets(campaign_id: str = "", limit: int = 25) -> str:
        """قائمة المجموعات الإعلانية (يمكن تحديد حملة معينة)."""
        try:
            from src.utils import paginate

            fields = [
                AdSet.Field.name,
                AdSet.Field.status,
                AdSet.Field.targeting,
                AdSet.Field.daily_budget,
                AdSet.Field.lifetime_budget,
                AdSet.Field.optimization_goal,
                AdSet.Field.billing_event,
                AdSet.Field.id,
            ]

            def _getter(params):
                if campaign_id:
                    return Campaign(campaign_id).get_ad_sets(params=params)
                return AdAccount(AD_ACCOUNT_ID).get_ad_sets(params=params)

            rows = paginate(_getter, fields=fields, limit=limit)
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_adsets"))

    @mcp.tool()
    @concurrency_limit()
    def get_adset(adset_id: str) -> str:
        """تفاصيل مجموعة إعلانية واحدة."""
        try:
            adset = AdSet(adset_id)
            info = adset.api_get(
                fields=[
                    AdSet.Field.name,
                    AdSet.Field.status,
                    AdSet.Field.targeting,
                    AdSet.Field.daily_budget,
                    AdSet.Field.lifetime_budget,
                    AdSet.Field.optimization_goal,
                    AdSet.Field.billing_event,
                    AdSet.Field.bid_amount,
                    AdSet.Field.pacing_type,
                    AdSet.Field.start_time,
                    AdSet.Field.end_time,
                ]
            )
            return json_dumps(to_dict(info))
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
    ) -> str:
        """
        إنشاء مجموعة إعلانية داخل حملة.
        targeting: JSON نصي مثل {"geo_locations":{"countries":["US"]},"age_min":18,"age_max":65}
        bid_amount: سقف عرض إلزامي لهذه الحسابات (بالعملة الصغرى). 0 يستخدم LOWEST_COST_WITHOUT_CAP.
        advantage_audience: تفعيل Advantage+ Audience (توسيع الاستهداف تلقائيًا) — افتراضي false للتحكم الدقيق.
        """
        try:
            if not targeting:
                targeting = json_dumps({"geo_locations": {"countries": ["US"]}})
            target = json.loads(targeting)
            # Phase 2.3: explicit Advantage+ toggle (default 0 = off for deterministic tests)
            target["targeting_automation"] = {"advantage_audience": 1 if advantage_audience else 0}
            targeting = json_dumps(target)
            account = AdAccount(AD_ACCOUNT_ID)
            params = {
                AdSet.Field.name: name,
                AdSet.Field.optimization_goal: optimization_goal,
                AdSet.Field.billing_event: billing_event,
                AdSet.Field.targeting: targeting,
                AdSet.Field.status: status,
                "campaign_id": campaign_id,
            }
            if daily_budget and daily_budget > 0:
                params[AdSet.Field.daily_budget] = str(daily_budget)
            if bid_amount and bid_amount > 0:
                params[AdSet.Field.bid_strategy] = "LOWEST_COST_WITH_BID_CAP"
                params[AdSet.Field.bid_amount] = str(bid_amount)
            else:
                params[AdSet.Field.bid_strategy] = "LOWEST_COST_WITHOUT_CAP"
            adset = account.create_ad_set(params=params)
            return json_dumps(to_dict(adset))
        except Exception as e:
            return json_dumps(handle_error(e, "create_adset"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_status(adset_id: str, status: str) -> str:
        """تغيير حالة مجموعة إعلانية (ACTIVE, PAUSED, DELETED, ARCHIVED)."""
        try:
            valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
            status = status.upper()
            if status not in valid:
                return json_dumps({"error": f"status غير صالح. القيم: {', '.join(sorted(valid))}"})
            adset = AdSet(adset_id)
            adset.api_update(params={AdSet.Field.status: status})
            return json_dumps({"success": True, "adset_id": adset_id, "new_status": status})
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_budget(adset_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> str:
        """تعديل ميزانية مجموعة إعلانية (بالعملة الصغرى)."""
        try:
            adset = AdSet(adset_id)
            params = {}
            if daily_budget and daily_budget > 0:
                params[AdSet.Field.daily_budget] = daily_budget
            if lifetime_budget and lifetime_budget > 0:
                params[AdSet.Field.lifetime_budget] = lifetime_budget
            if not params:
                return json_dumps({"error": "حدد ميزانية يومية أو إجمالية"})
            adset.api_update(params=params)
            return json_dumps({"success": True, "adset_id": adset_id, "result": params})
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
            target = json.loads(targeting)
            if advantage_audience is not None:
                target["targeting_automation"] = {"advantage_audience": 1 if advantage_audience else 0}
            else:
                target.setdefault("targeting_automation", {"advantage_audience": 0})
            adset = AdSet(adset_id)
            adset.api_update(params={AdSet.Field.targeting: json_dumps(target)})
            return json_dumps({"success": True, "adset_id": adset_id, "targeting": target})
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
            fields = [m.strip() for m in metrics.split(",") if m.strip()]
            insights = AdSet(adset_id).get_insights(params={"date_preset": date_preset, "fields": fields})
            rows = [__import__("src.helpers", fromlist=["to_dict"]).to_dict(i) for i in insights]
            if not rows:
                return json_dumps({"data": [], "count": 0, "message": "لا توجد بيانات"})
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
                params[AdSet.Field.start_time] = start_time
            if end_time:
                params[AdSet.Field.end_time] = end_time
            if not params:
                return json_dumps({"error": "حدد start_time و/أو end_time"})
            adset = AdSet(adset_id)
            adset.api_update(params=params)
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
            from src.helpers import handle_error

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
                account = AdAccount(AD_ACCOUNT_ID)
                return account.get_ad_sets(
                    params={
                        "fields": ["name", "status", "daily_budget", "id"],
                        "filtering": json_dumps([{"field": "status", "operator": "EQUAL", "value": "ACTIVE"}]),
                    }
                )

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("adsets://active fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.helpers import handle_error

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
