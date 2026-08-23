import logging

from src.config import AD_ACCOUNT_ID, resolve_ad_account_id

logger = logging.getLogger(__name__)

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
    from src.utils import cached

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
    @cached(ttl=60.0)
    @concurrency_limit()
    def get_account_insights(date_preset: str = "last_30d", metrics: str = ",".join(DEFAULT_METRICS), ad_account_id: str = "") -> str:
        """تحليلات على مستوى الحساب الإعلاني."""
        try:
            fields = _validate(date_preset, metrics)
            account = AdAccount(resolve_ad_account_id(ad_account_id))
            insights = account.get_insights(params={"date_preset": date_preset, "fields": fields})
            return _respond(insights)
        except Exception as e:
            return json_dumps(handle_error(e, "get_account_insights"))

    @mcp.tool()
    @cached(ttl=60.0)
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
    @cached(ttl=60.0)
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
    @cached(ttl=60.0)
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
    @cached(ttl=60.0)
    @concurrency_limit()
    def get_account_insights_trend(
        date_preset: str = "last_30d",
        metrics: str = "spend,impressions,clicks,ctr,cpc,reach",
        time_increment: int = 1,
        ad_account_id: str = "",
    ) -> str:
        """
        تحليلات الحساب على مدار الفترة (يومية/أسبوعية).
        time_increment: 1=يومي، 7=أسبوعي، 0=إجمالي واحد.
        يُرجع سلسلة زمنية من البيانات.
        """
        try:
            fields = _validate(date_preset, metrics)
            account = AdAccount(resolve_ad_account_id("") if "ad_account_id" not in locals() else resolve_ad_account_id(ad_account_id) if "ad_account_id" in dir() else AdAccount(AD_ACCOUNT_ID))
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

    @mcp.tool()
    @concurrency_limit()
    def detect_insights_anomaly(
        date_preset_current: str = "last_7d",
        date_preset_previous: str = "last_14d",
        metrics: str = "spend,impressions,clicks,ctr,cpc,reach",
        threshold: float = 20.0,
    ) -> str:
        """
        كشف الشذوذ في التحليلات (CTR/CPC drop > threshold%).
        يقارن فترتين ويكشف انخفاض CTR أو ارتفاع CPC.
        threshold: نسبة مئوية للتنبيه (افتراضي 20%)
        """
        try:
            fields = _validate(date_preset_current, metrics)
            account = AdAccount(AD_ACCOUNT_ID)
            cur = account.get_insights(params={"date_preset": date_preset_current, "fields": fields})
            cur_rows = [to_dict(i) for i in cur]
            prev = account.get_insights(params={"date_preset": date_preset_previous, "fields": fields})
            prev_rows = [to_dict(i) for i in prev]

            def avg(m, rows):
                vals = []
                for r in rows:
                    try:
                        vals.append(float(r.get(m, 0)))
                    except Exception:
                        pass
                return sum(vals) / len(vals) if vals else 0

            anomalies = []
            for m in fields:
                c = avg(m, cur_rows)
                p = avg(m, prev_rows)
                if p == 0:
                    continue
                change = ((c - p) / p) * 100
                is_anomaly = False
                if (
                    m == "ctr"
                    and change < -threshold
                    or m == "cpc"
                    and change > threshold
                    or (m == "cpm" and change > threshold or abs(change) > threshold * 1.5)
                ):
                    is_anomaly = True
                if is_anomaly:
                    anomalies.append(
                        {"metric": m, "current": round(c, 3), "previous": round(p, 3), "change_pct": round(change, 1)}
                    )

            llm_summary = None
            if anomalies:
                try:
                    from src.llm import call_llm

                    prompt = f"Analyze Meta ads anomalies: {anomalies} between {date_preset_previous} and {date_preset_current}. Provide 2-3 concise recommendations in Arabic."
                    llm_summary = call_llm(prompt, system="You are a Meta ads analyst. Be concise and actionable.")
                except Exception:
                    pass

            return json_dumps(
                {
                    "current_period": date_preset_current,
                    "previous_period": date_preset_previous,
                    "anomalies": anomalies,
                    "anomaly_count": len(anomalies),
                    "threshold": threshold,
                    "llm_summary": llm_summary,
                    "note": "إيجابي يعني ارتفاع، سلبي انخفاض. CTR ↓ و CPC ↑ يعتبران شذوذ.",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "detect_insights_anomaly"))

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

    @mcp.prompt()
    def report_insight_prompt(date_range: str) -> str:
        """تحليل تقرير وتوصيات."""
        return (
            f"حلّل تقرير الفترة {date_range} (generate_campaign_report + account_summary + get_metrics). "
            "استخرج: أفضل/أسوأ حملة، CTR/CPC، تكلفة، توصيات إيقاف/زيادة ميزانية. أرجع جدول توصيات."
        )

    @mcp.resource("insights://templates")
    async def insights_extra_resource() -> str:
        """قوالب الرؤى."""
        try:
            return json_dumps({"module": "insights", "resource": "insights://templates", "hint": "قوالب الرؤى"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "insights://templates"))

    @mcp.prompt()
    def insights_compare_prompt(topic: str = "insights") -> str:
        """مقارنة رؤى."""
        return "ساعد في مقارنة رؤى لـ " + topic + " — قارن رؤى {campaign} (وحدة insights)"
