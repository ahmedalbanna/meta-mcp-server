"""Insights breakdowns: age/gender/placement/country/device + time-series + attribution."""

import logging

from src.config import AD_ACCOUNT_ID

logger = logging.getLogger(__name__)
from src.insights import DATE_PRESETS, DEFAULT_METRICS

BREAKDOWN_VALUES = [
    "age",
    "gender",
    "country",
    "placement",
    "publisher_platform",
    "platform_position",
    "device_platform",
    "device_type",
    "impression_device",
    "region",
    "dma",
    "frequency_value",
    "hourly_stats_aggregated_by_advertiser_time_zone",
    "hourly_stats_aggregated_by_audience_time_zone",
    "objective",
    "product_id",
]

ATTRIBUTION_WINDOWS = [
    "1d_click",
    "7d_click",
    "28d_click",
    "1d_view",
    "7d_view",
    "28d_view",
    "7d_click_1d_view",
    "28d_click_7d_view",
]

ACTION_BREAKDOWN_VALUES = [
    "action_type",
    "action_target_id",
    "action_destination",
    "action_reaction",
    "post_reaction_type",
]


def register(mcp, services=None):
    """Register insights-breakdown tools."""

    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.campaign import Campaign

    from src.helpers import handle_error, json_dumps, to_dict
    from src.throttle import concurrency_limit

    def _validate(preset: str, metrics: str, breakdown: str) -> tuple:
        if preset not in DATE_PRESETS:
            raise ValueError(f"date_preset غير صالح. اختر من: {', '.join(DATE_PRESETS)}")
        breakdown_list = [b.strip() for b in breakdown.split(",") if b.strip()]
        for b in breakdown_list:
            if b not in BREAKDOWN_VALUES:
                raise ValueError(f"breakdown غير صالح: {b}. الاختيارات: {', '.join(BREAKDOWN_VALUES)}")
        return [m.strip() for m in metrics.split(",") if m.strip()], breakdown_list

    def _build_params(preset, fields, breakdown_list, time_increment, attribution, action_breakdowns):
        params = {"date_preset": preset, "fields": fields, "breakdowns": ",".join(breakdown_list)}
        if time_increment > 0:
            params["time_increment"] = time_increment
        if attribution:
            windows = [w.strip() for w in attribution.split(",") if w.strip()]
            for w in windows:
                if w not in ATTRIBUTION_WINDOWS:
                    raise ValueError(
                        f"action_attribution_windows غير صالح: {w}. الاختيارات: {', '.join(ATTRIBUTION_WINDOWS)}"
                    )
            params["action_attribution_windows"] = windows
        if action_breakdowns:
            items = [a.strip() for a in action_breakdowns.split(",") if a.strip()]
            for a in items:
                if a not in ACTION_BREAKDOWN_VALUES:
                    raise ValueError(
                        f"action_breakdowns غير صالح: {a}. الاختيارات: {', '.join(ACTION_BREAKDOWN_VALUES)}"
                    )
            params["action_breakdowns"] = items
        return params

    def _respond(insights) -> str:
        rows = [to_dict(i) for i in insights]
        if not rows:
            return json_dumps({"data": [], "count": 0, "message": "لا توجد بيانات"})
        return json_dumps({"data": rows, "count": len(rows)})

    @mcp.tool()
    @concurrency_limit()
    def get_account_insights_breakdown(
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> str:
        """
        تحليلات الحساب مجزأة (age, gender, country, placement, device_type...).
        time_increment: 1-90 لسلاسل زمنية يومية، أو 0 لإجمالي واحد.
        action_attribution_windows: مثال "7d_click,1d_view".
        """
        try:
            from src.core.services import Services
            from src.services.breakdowns_service import BreakdownsService
            svc = BreakdownsService(services) if services is not None else BreakdownsService(Services.default())
            rows = svc.get_account_breakdown(breakdown, date_preset, metrics, time_increment,
                                             action_attribution_windows, action_breakdowns)
            return _respond(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_account_insights_breakdown"))

    @mcp.tool()
    @concurrency_limit()
    def get_campaign_insights_breakdown(
        campaign_id: str,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> str:
        """تحليلات حملة مجزأة."""
        try:
            from src.core.services import Services
            from src.services.breakdowns_service import BreakdownsService
            svc = BreakdownsService(services) if services is not None else BreakdownsService(Services.default())
            rows = svc.get_campaign_breakdown(campaign_id, breakdown, date_preset, metrics, time_increment,
                                              action_attribution_windows, action_breakdowns)
            return _respond(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_campaign_insights_breakdown"))

    @mcp.tool()
    @concurrency_limit()
    def get_adset_insights_breakdown(
        adset_id: str,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> str:
        """تحليلات مجموعة إعلانية مجزأة."""
        try:
            from src.core.services import Services
            from src.services.breakdowns_service import BreakdownsService
            svc = BreakdownsService(services) if services is not None else BreakdownsService(Services.default())
            rows = svc.get_adset_breakdown(adset_id, breakdown, date_preset, metrics, time_increment,
                                           action_attribution_windows, action_breakdowns)
            return _respond(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_adset_insights_breakdown"))

    @mcp.tool()
    @concurrency_limit()
    def get_ad_insights_breakdown(
        ad_id: str,
        breakdown: str = "age,gender",
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        time_increment: int = 0,
        action_attribution_windows: str = "",
        action_breakdowns: str = "",
    ) -> str:
        """تحليلات إعلان مجزأة."""
        try:
            from src.core.services import Services
            from src.services.breakdowns_service import BreakdownsService
            svc = BreakdownsService(services) if services is not None else BreakdownsService(Services.default())
            rows = svc.get_ad_breakdown(ad_id, breakdown, date_preset, metrics, time_increment,
                                        action_attribution_windows, action_breakdowns)
            return _respond(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_ad_insights_breakdown"))

    @mcp.resource("breakdowns://overview")
    async def breakdowns_resource() -> str:
        """قوالب التحليلات المجزأة."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "breakdowns", "resource": "breakdowns://overview", "hint": "قوالب التحليلات المجزأة"}
            )
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "breakdowns://overview"))

    @mcp.prompt()
    def breakdown_analysis_prompt(topic: str = "breakdowns", breakdown: str = "age,gender") -> str:
        """تحليل مجزأ."""
        return f"ساعد في تحليل مجزأ لـ {topic} — حلل breakdown {breakdown} (وحدة breakdowns)"

    @mcp.resource("breakdowns://templates")
    async def breakdowns_extra_resource() -> str:
        """قوالب التحليلات."""
        try:
            return json_dumps({"module": "breakdowns", "resource": "breakdowns://templates", "hint": "قوالب التحليلات"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "breakdowns://templates"))

    @mcp.prompt()
    def breakdown_comparison_prompt(topic: str = "breakdowns", b1: str = "age", b2: str = "gender") -> str:
        """مقارنة تحليلات."""
        return f"ساعد في مقارنة تحليلات لـ {topic} — قارن breakdown {b1} و {b2} (وحدة breakdowns)"
