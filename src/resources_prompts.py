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
                return account.get_custom_audiences(params={"fields": ["name", "subtype", "approximate_count", "id"]})

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

    @mcp.resource("ads://active")
    async def active_ads_resource() -> str:
        """قائمة الإعلانات النشطة."""
        try:

            def _fetch():
                account = AdAccount(AD_ACCOUNT_ID)
                return account.get_ads(
                    params={
                        "fields": ["name", "status", "creative", "id"],
                        "filtering": json_dumps([{"field": "status", "operator": "EQUAL", "value": "ACTIVE"}]),
                    }
                )

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("ads://active fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("ads://active failed")
            return json_dumps(handle_error(e, "ads://active"))

    @mcp.resource("catalogs://list")
    async def catalogs_list_resource() -> str:
        """قائمة كتالوجات المنتجات."""
        try:
            from facebook_business.adobjects.business import Business

            from src.config import BUSINESS_ID

            def _fetch():
                bid = BUSINESS_ID
                if not bid:
                    return []
                return Business(bid).get_owned_product_catalogs(params={"fields": ["id", "name", "product_count"]})

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("catalogs://list fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("catalogs://list failed")
            return json_dumps(handle_error(e, "catalogs://list"))

    @mcp.resource("leads://recent")
    async def recent_leads_resource() -> str:
        """آخر الرصاصات (Leads) من النماذج."""
        try:
            from facebook_business.adobjects.page import Page

            from src.config import PAGE_ID
            from src.helpers import get_page_api

            def _fetch():
                page = Page(PAGE_ID, api=get_page_api())
                forms = page.get_lead_gen_forms(params={"fields": ["id"], "limit": 3})
                out = []
                for f in list(forms)[:2]:
                    fid = f.get("id") if isinstance(f, dict) else f.export_all_data().get("id")
                    try:
                        from facebook_business.adobjects.leadgenform import LeadgenForm

                        leads = LeadgenForm(fid, api=get_page_api()).get_leads(params={"limit": 5})
                        out.extend([to_dict(lead) for lead in leads])
                    except Exception:
                        continue
                return out

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("leads://recent fetched %d leads in %.2fs", len(rows), elapsed)
            return json_dumps(rows)
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("leads://recent failed")
            return json_dumps(handle_error(e, "leads://recent"))

    @mcp.resource("instagram://recent")
    async def recent_instagram_resource() -> str:
        """آخر منشورات إنستغرام."""
        try:
            from src.config import INSTAGRAM_BUSINESS_ID
            from src.helpers import api_call

            def _fetch():
                ig_id = INSTAGRAM_BUSINESS_ID
                if not ig_id:
                    return {"data": []}
                return api_call("GET", f"{ig_id}/media", {"fields": "id,caption,media_type,timestamp", "limit": 10})

            t0 = time.monotonic()
            data = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("instagram://recent fetched in %.2fs", elapsed)
            return json_dumps(data)
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("instagram://recent failed")
            return json_dumps(handle_error(e, "instagram://recent"))

    @mcp.resource("metrics://snapshot")
    async def metrics_snapshot_resource() -> str:
        """لقطة مقاييس الأداء (MCP + API)."""
        try:
            from src.metrics import get_snapshot

            def _fetch():
                return get_snapshot()

            t0 = time.monotonic()
            snap = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("metrics://snapshot fetched in %.2fs", elapsed)
            # Convert tuple keys for JSON
            tool_calls = {f"{k[0]}:{k[1]}": v for k, v in snap.get("tool_calls", {}).items()}
            snap["tool_calls"] = tool_calls
            snap["tool_duration"] = {k: len(v) for k, v in snap.get("tool_duration", {}).items()}
            return json_dumps(snap)
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("metrics://snapshot failed")
            return json_dumps(handle_error(e, "metrics://snapshot"))

    @mcp.resource("scheduler://tasks")
    async def scheduler_tasks_resource() -> str:
        """قائمة المهام المجدولة."""
        try:
            from src.scheduler import _load_tasks

            def _fetch():
                return _load_tasks()

            t0 = time.monotonic()
            tasks = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("scheduler://tasks fetched %d tasks in %.2fs", len(tasks), elapsed)
            return json_dumps({"tasks": tasks, "count": len(tasks)})
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("scheduler://tasks failed")
            return json_dumps(handle_error(e, "scheduler://tasks"))

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

    @mcp.prompt()
    def adset_targeting_prompt(product: str, country: str = "EG", age: str = "18-65") -> str:
        """مساعد استهداف مجموعة إعلانية."""
        return (
            f"اقترح استهدافًا لمجموعة إعلانية لمنتج {product} في {country} للعمر {age}. "
            "اذكر: geo_locations، age_min/max، gender، interests/behaviors، "
            "وأعداد Advantage+ Audience (0=دقيق، 1=موسع). أرجع JSON جاهز لـ create_adset."
        )

    @mcp.prompt()
    def instagram_caption_prompt(image_desc: str, style: str = "engaging") -> str:
        """توليد كابشن إنستغرام من وصف الصورة."""
        return (
            f"اكتب كابشن {style} لإنستغرام لصورة وصفها: {image_desc}. "
            "أضف 3 هاشتاغات عربية/إنجليزية ودعوة للتفاعل. استخدم generate_caption_from_image إن توفر رابط الصورة."
        )

    @mcp.prompt()
    def lead_nurture_prompt(lead_name: str, product: str = "") -> str:
        """سلسلة متابعة رصاصة (Lead Nurture)."""
        prod = f" حول {product}" if product else ""
        return (
            f"صمم سلسلة متابعة 3 رسائل واتساب/ماسنجر للرصاصة {lead_name}{prod}: "
            "رسالة ترحيب + تذكير بعد 24 ساعة + عرض نهائي. استخدم send_whatsapp_template_message / send_messenger_message."
        )

    @mcp.prompt()
    def whatsapp_template_prompt(business: str, goal: str = "تأكيد طلب") -> str:
        """صياغة قالب واتساب معتمد."""
        return (
            f"صغ قالب واتساب لفعالية {goal} لنشاط {business}. "
            "اذكر: language, category (UTILITY/MARKETING), body_text, header_text. "
            "استخدم create_whatsapp_message_template ثم send_whatsapp_template_message."
        )

    @mcp.prompt()
    def catalog_product_prompt(product_name: str, price: str = "") -> str:
        """وصف منتج لكتالوج."""
        price_line = f" بسعر {price}" if price else ""
        return (
            f"اكتب وصف منتج مقنع لـ {product_name}{price_line} لكتالوج فيسبوك: "
            "العنوان، الوصف، brand، availability، product_type، custom_label_0. "
            "استخدم create_product."
        )

    @mcp.prompt()
    def automation_rule_prompt(metric: str = "spend", threshold: str = "100") -> str:
        """شرح قاعدة أتمتة إعلانات."""
        return (
            f"اشرح قاعدة أتمتة: عند {metric} > {threshold} أوقف الحملة. "
            "اذكر: evaluation_spec و execution_spec JSON لـ create_auto_rule / create_simple_auto_rule."
        )

    @mcp.prompt()
    def report_insight_prompt(date_range: str) -> str:
        """تحليل تقرير وتوصيات."""
        return (
            f"حلّل تقرير الفترة {date_range} (generate_campaign_report + account_summary + get_metrics). "
            "استخرج: أفضل/أسوأ حملة، CTR/CPC، تكلفة، توصيات إيقاف/زيادة ميزانية. أرجع جدول توصيات."
        )
