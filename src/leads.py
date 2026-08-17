"""Lead Ads & Forms: lead-gen forms, leads and campaign-lead management."""

from src.config import PAGE_ID
from src.helpers import get_page_api, handle_error, json_dumps, to_dict, write_guard
from src.utils import paginate

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


def register(mcp):
    """Register lead ads & forms tools (page-scoped token)."""

    from facebook_business.adobjects.lead import Lead
    from facebook_business.adobjects.leadgenform import LeadgenForm
    from facebook_business.adobjects.page import Page

    def _page(node_id: str = "") -> Page:
        return Page(node_id or PAGE_ID, api=get_page_api())

    @mcp.tool()
    def list_lead_gen_forms(page_id: str = "", limit: int = 25) -> str:
        """قائمة نماذج جذب العملاء (Lead Gen Forms) على الصفحة."""
        try:
            rows = paginate(
                lambda params: _page(page_id).get_lead_gen_forms(params=params),
                fields=LEAD_FORM_FIELDS,
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_lead_gen_forms"))

    @mcp.tool()
    def get_lead_gen_form(form_id: str) -> str:
        """تفاصيل نموذج جذب عملاء واحد (الأسئلة، الإخلاء القانوني، الصفحة...)."""
        try:
            info = LeadgenForm(form_id, api=get_page_api()).api_get(
                fields=[
                    "id",
                    "name",
                    "status",
                    "locale",
                    "created_time",
                    "page",
                    "questions",
                    "context_card",
                    "legal_content",
                    "privacy_policy",
                    "thankyou_page",
                    "qualified_lead_count",
                    "disqualified_lead_count",
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_lead_gen_form"))

    @mcp.tool()
    def get_form_leads(form_id: str, limit: int = 25) -> str:
        """الرصاصات (Leads) المسجّلة عبر نموذج جذب عملاء معيّن."""
        try:
            rows = paginate(
                lambda params: LeadgenForm(form_id, api=get_page_api()).get_leads(params=params),
                fields=LEAD_FIELDS,
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_form_leads"))

    @mcp.tool()
    def get_lead(lead_id: str) -> str:
        """تفاصيل رصاصة واحدة (إجابات الحقول: الاسم، الهاتف، البريد...)."""
        try:
            info = Lead(lead_id, api=get_page_api()).api_get(fields=LEAD_FIELDS)
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_lead"))

    @mcp.tool()
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
            params = {
                "name": name,
                "privacy_policy": {"url": privacy_policy_url},
                "question_page_custom_headline": question_page_headline,
                "locale": locale,
            }
            if thankyou_page_headline or thankyou_page_body:
                thankyou = {}
                if thankyou_page_headline:
                    thankyou["message"] = thankyou_page_headline
                if thankyou_page_body:
                    thankyou["body"] = thankyou_page_body
                params["thankyou_page"] = thankyou
            form = _page(page_id).create_lead_gen_form(params=params)
            return json_dumps(to_dict(form))
        except Exception as e:
            return json_dumps(handle_error(e, "create_lead_gen_form"))
