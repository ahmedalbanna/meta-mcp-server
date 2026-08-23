from src.config import AD_ACCOUNT_ID

DEFAULT_METRICS = [
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "actions",
    "reach",
]
DATE_PRESETS = [
    "today",
    "yesterday",
    "last_3d",
    "last_7d",
    "last_14d",
    "last_28d",
    "last_30d",
    "last_90d",
    "this_month",
    "last_month",
    "this_quarter",
    "this_year",
    "lifetime",
]


def register(mcp):
    """Register insights tools."""

    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.campaign import Campaign

    from src.helpers import handle_error, json_dumps, to_dict
    from src.throttle import concurrency_limit

    def _validate(preset: str, metrics: str) -> list:
        if preset not in DATE_PRESETS:
            raise ValueError(f"date_preset غير صالح. اختر من: {', '.join(DATE_PRESETS)}")
        return [m.strip() for m in metrics.split(",") if m.strip()]

    def _respond(insights) -> str:
        rows = [to_dict(i) for i in insights]
        if not rows:
            return json_dumps({"data": [], "count": 0, "message": "لا توجد بيانات"})
        return json_dumps({"data": rows, "count": len(rows)})

    @mcp.tool()
    @concurrency_limit()
    def get_account_insights(date_preset: str = "last_30d", metrics: str = ",".join(DEFAULT_METRICS)) -> str:
        """تحليلات على مستوى الحساب الإعلاني."""
        try:
            fields = _validate(date_preset, metrics)
            account = AdAccount(AD_ACCOUNT_ID)
            insights = account.get_insights(params={"date_preset": date_preset, "fields": fields})
            return _respond(insights)
        except Exception as e:
            return json_dumps(handle_error(e, "get_account_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_campaign_insights(
        campaign_id: str,
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
    ) -> str:
        """تحليلات حملة معينة."""
        try:
            fields = _validate(date_preset, metrics)
            insights = Campaign(campaign_id).get_insights(params={"date_preset": date_preset, "fields": fields})
            return _respond(insights)
        except Exception as e:
            return json_dumps(handle_error(e, "get_campaign_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_adset_insights(
        adset_id: str,
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
    ) -> str:
        """تحليلات مجموعة إعلانية معينة."""
        try:
            fields = _validate(date_preset, metrics)
            insights = AdSet(adset_id).get_insights(params={"date_preset": date_preset, "fields": fields})
            return _respond(insights)
        except Exception as e:
            return json_dumps(handle_error(e, "get_adset_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_ad_insights(
        ad_id: str,
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
    ) -> str:
        """تحليلات إعلان معين."""
        try:
            fields = _validate(date_preset, metrics)
            insights = Ad(ad_id).get_insights(params={"date_preset": date_preset, "fields": fields})
            return _respond(insights)
        except Exception as e:
            return json_dumps(handle_error(e, "get_ad_insights"))

    @mcp.tool()
    @concurrency_limit()
    def get_account_insights_trend(
        date_preset: str = "last_30d",
        metrics: str = "spend,impressions,clicks,ctr,cpc,reach",
        time_increment: int = 1,
    ) -> str:
        """
        تحليلات الحساب على مدار الفترة (يومية/أسبوعية).
        time_increment: 1=يومي، 7=أسبوعي، 0=إجمالي واحد.
        يُرجع سلسلة زمنية من البيانات.
        """
        try:
            fields = _validate(date_preset, metrics)
            account = AdAccount(AD_ACCOUNT_ID)
            params = {
                "date_preset": date_preset,
                "fields": fields,
                "time_increment": time_increment,
            }
            insights = account.get_insights(params=params)
            rows = [to_dict(i) for i in insights]
            if not rows:
                return json_dumps({"data": [], "count": 0, "message": "لا توجد بيانات"})
            return json_dumps(
                {
                    "data": rows,
                    "count": len(rows),
                    "time_increment": time_increment,
                    "period": "daily" if time_increment == 1 else "weekly" if time_increment == 7 else "total",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "get_account_insights_trend"))

    @mcp.resource("insights://overview")
    async def insights_resource() -> str:
        """قوالب التحليلات."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "insights", "resource": "insights://overview", "hint": "قوالب التحليلات"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "insights://overview"))

    @mcp.prompt()
    def insights_analysis_prompt(topic: str = "insights") -> str:
        """تحليل رؤى."""
        return "ساعد في تحليل رؤى لـ " + topic + " — حلل رؤى {level} (وحدة insights)"
