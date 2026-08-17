"""MCP resources (read-only data) and prompts (reusable templates)."""

import asyncio
import logging
import time

from src.config import AD_ACCOUNT_ID
from src.helpers import json_dumps, to_dict

logger = logging.getLogger(__name__)


def register(mcp):
    """Register resources and prompts on the FastMCP instance."""

    from facebook_business.adobjects.adaccount import AdAccount

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

    @mcp.resource("account://summary")
    async def account_summary_resource() -> str:
        """ملخص أداء الحساب الإعلاني."""
        try:

            def _fetch():
                account = AdAccount(AD_ACCOUNT_ID)
                info = account.api_get(
                    fields=[
                        "name",
                        "account_status",
                        "currency",
                        "balance",
                        "amount_spent",
                        "spend_cap",
                    ]
                )
                insights = account.get_insights(
                    params={
                        "date_preset": "last_30d",
                        "fields": ["spend", "impressions", "clicks"],
                    }
                )
                return info, insights

            t0 = time.monotonic()
            info, insights = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("account://summary fetched in %.2fs", elapsed)
            data = to_dict(info)
            if insights:
                data["insights_30d"] = to_dict(insights[0])
            return json_dumps(data)
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("account://summary failed")
            return json_dumps(handle_error(e, "account://summary"))

    @mcp.resource("audiences://list")
    async def audiences_list_resource() -> str:
        """قائمة الجماهير المخصصة."""
        try:

            def _fetch():
                account = AdAccount(AD_ACCOUNT_ID)
                return account.get_custom_audiences(
                    params={"fields": ["name", "subtype", "approximate_count", "id"]}
                )

            t0 = time.monotonic()
            audiences = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info(
                "audiences://list fetched %d audiences in %.2fs",
                len(list(audiences)),
                elapsed,
            )
            return json_dumps([to_dict(a) for a in audiences])
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("audiences://list failed")
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
