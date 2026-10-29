"""Lead Ads & Forms: lead-gen forms, leads and campaign-lead management."""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)
from src.throttle import concurrency_limit
from src.utils import handle_error, json_dumps, write_guard

LEAD_FORM_FIELDS = [
    "id",
    "name",
    "status",
    "locale",
    "created_time",
    "page",
    "qualified_lead_count",
    "disqualified_lead_count",
    "is_optimized_for_quality",
    "leadgen_export_csv_url",
]

LEAD_FIELDS = [
    "id",
    "created_time",
    "field_data",
    "form_id",
    "ad_id",
    "campaign_id",
    "adgroup_id",
    "is_organic",
    "retail_product_item_id",
]


def register(mcp, services):
    """Register lead ads & forms tools (page-scoped token)."""


    @mcp.tool()
    @concurrency_limit()
    def list_lead_gen_forms(page_id: str = "", limit: int = 25) -> str:
        """قائمة نماذج جذب العملاء (Lead Gen Forms) على الصفحة."""
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            data = svc.list_lead_gen_forms(page_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_lead_gen_forms"))

    @mcp.tool()
    @concurrency_limit()
    def get_lead_gen_form(form_id: str) -> str:
        """تفاصيل نموذج جذب عملاء واحد (الأسئلة، الإخلاء القانوني، الصفحة...)."""
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            data = svc.get_lead_gen_form(form_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_lead_gen_form"))

    @mcp.tool()
    @concurrency_limit()
    def get_form_leads(form_id: str, limit: int = 25) -> str:
        """الرصاصات (Leads) المسجّلة عبر نموذج جذب عملاء معيّن."""
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            data = svc.get_form_leads(form_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_form_leads"))

    @mcp.tool()
    @concurrency_limit()
    def get_lead(lead_id: str) -> str:
        """تفاصيل رصاصة واحدة (إجابات الحقول: الاسم، الهاتف، البريد...)."""
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            data = svc.get_lead(lead_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_lead"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_lead_gen_form(
        name: str,
        privacy_policy_url: str,
        question_page_headline: str,
        page_id: str = "",
        thankyou_page_headline: str = "",
        thankyou_page_body: str = "",
        locale: str = "ar_AR",
    ) -> str:
        """
        إنشاء نموذج جذب عملاء على صفحة.
        privacy_policy_url: رابط سياسة الخصوصية (مطلوب).
        question_page_headline: عنوان صفحة الأسئلة (مطلوب).
        locale: مثال ar_AR أو en_US.
        """
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            data = svc.create_lead_gen_form(
                name,
                privacy_policy_url,
                question_page_headline,
                page_id,
                thankyou_page_headline,
                thankyou_page_body,
                locale,
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_lead_gen_form"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def subscribe_leadgen_webhook(page_id: str = "", subscribed_fields: str = "leadgen") -> str:
        """اشتراك الصفحة في Webhook الرصاص (leadgen). يتطلب صلاحيات pages_manage_metadata."""
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            return json_dumps(svc.subscribe_leadgen_webhook(page_id, subscribed_fields))
        except Exception as e:
            return json_dumps(handle_error(e, "subscribe_leadgen_webhook"))

    @mcp.tool()
    @concurrency_limit()
    def get_lead_field_mapping(lead_id: str) -> str:
        """تحويل field_data لرصاصة إلى قاموس مسطح {field_name: values} لتسهيل المعالجة."""
        try:
            from src.services.leads_service import LeadsService

            svc = LeadsService(services)
            return json_dumps(svc.get_lead_field_mapping(lead_id))
        except Exception as e:
            return json_dumps(handle_error(e, "get_lead_field_mapping"))

    @mcp.resource("leads://overview")
    async def leads_resource() -> str:
        """نظرة عامة على الرصاص."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "leads", "resource": "leads://overview", "hint": "نظرة عامة على الرصاص"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "leads://overview"))

    @mcp.prompt()
    def lead_qualification_prompt(topic: str = "leads") -> str:
        """تأهيل رصاصة."""
        return "ساعد في تأهيل رصاصة لـ " + topic + " — قيّم رصاصة {lead_id} (وحدة leads)"

    @mcp.resource("leads://recent")
    async def recent_leads_resource() -> str:
        """آخر الرصاصات (Leads) من النماذج."""
        try:

            def _fetch():
                page_id = services.config.page_id
                data = services.api.page_get(f"{page_id}/leadgenforms", {"fields": ["id"], "limit": 3})
                forms = data.get("data", []) if isinstance(data, dict) else []
                out = []
                for f in forms[:2]:
                    fid = f.get("id") if isinstance(f, dict) else None
                    if not fid:
                        continue
                    try:
                        lead_data = services.api.page_get(f"{fid}/leads", {"limit": 5})
                        lead_rows = lead_data.get("data", []) if isinstance(lead_data, dict) else []
                        out.extend(lead_rows)
                    except Exception:
                        continue
                return out

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("leads://recent fetched %d leads in %.2fs", len(rows), elapsed)
            return json_dumps(rows)
        except Exception as e:
            from src.utils import handle_error

            logger.exception("leads://recent failed")
            return json_dumps(handle_error(e, "leads://recent"))

    @mcp.prompt()
    def lead_nurture_prompt(lead_name: str, product: str = "") -> str:
        """سلسلة متابعة رصاصة (Lead Nurture)."""
        prod = f" حول {product}" if product else ""
        return (
            f"صمم سلسلة متابعة 3 رسائل واتساب/ماسنجر للرصاصة {lead_name}{prod}: "
            "رسالة ترحيب + تذكير بعد 24 ساعة + عرض نهائي. استخدم send_whatsapp_template_message / send_messenger_message."
        )
