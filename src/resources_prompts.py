"""MCP resources (read-only data) and prompts (reusable templates)."""

from src.config import AD_ACCOUNT_ID
from src.helpers import json_dumps, to_dict


def register(mcp):
    """Register resources and prompts on the FastMCP instance."""

    from facebook_business.adobjects.adaccount import AdAccount

    @mcp.resource("campaigns://active")
    async def active_campaigns_resource() -> str:
        """قائمة الحملات النشطة كـ JSON."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            campaigns = account.get_campaigns(
                params={
                    "fields": ["name", "status", "id"],
                    "filtering": json_dumps(
                        [{"field": "status", "operator": "EQUAL", "value": "ACTIVE"}]
                    ),
                }
            )
            return json_dumps([to_dict(c) for c in campaigns])
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "campaigns://active"))

    @mcp.resource("account://summary")
    async def account_summary_resource() -> str:
        """ملخص أداء الحساب الإعلاني."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            info = account.api_get(
                fields=["name", "account_status", "currency", "balance", "amount_spent", "spend_cap"]
            )
            insights = account.get_insights(
                params={"date_preset": "last_30d", "fields": ["spend", "impressions", "clicks"]}
            )
            data = to_dict(info)
            if insights:
                data["insights_30d"] = to_dict(insights[0])
            return json_dumps(data)
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "account://summary"))

    @mcp.resource("audiences://list")
    async def audiences_list_resource() -> str:
        """قائمة الجماهير المخصصة."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            audiences = account.get_custom_audiences(
                params={"fields": ["name", "subtype", "approximate_count", "id"]}
            )
            return json_dumps([to_dict(a) for a in audiences])
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "audiences://list"))

    @mcp.prompt()
    def ad_copy_prompt(product: str, audience: str = "") -> str:
        """إنشاء نصوص إعلانية جذابة."""
        audience_line = f" للجمهور المستهدف: {audience}" if audience else ""
        return (
            f"اكتب 5 نصوص إعلانية بالعربية لمنتج: {product}{audience_line}، "
            "مع عناوين جذابة (primary text)، ووصف قصير، ودعوة واضحة لاتخاذ إجراء (CTA)."
        )

    @mcp.prompt()
    def marketing_report_prompt(date_range: str) -> str:
        """إنشاء تقرير أداء تسويقي."""
        return (
            f"أُنشئ تقرير أداء تسويقي مفصل للفترة: {date_range}. "
            "استخدم أدوات التحليلات (get_campaign_insights وغيرها) واذكر: الإنفاق، النقرات، "
            "نسبة النقر (CTR)، التكلفة لكل نقرة (CPC)، وأفضل الحملات أداءً، مع توصيات للتحسين."
        )
