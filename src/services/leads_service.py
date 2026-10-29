"""Leads service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.lead import Lead
from facebook_business.adobjects.leadgenform import LeadgenForm
from facebook_business.adobjects.page import Page

from src.core.services import Services
from src.helpers import get_page_api, to_dict
from src.utils import paginate

LEAD_FORM_FIELDS = ["id", "name", "status", "locale", "created_time", "page", "questions",
                    "context_card", "legal_content", "privacy_policy", "thankyou_page",
                    "qualified_lead_count", "disqualified_lead_count"]
LEAD_FIELDS = ["id", "created_time", "field_data", "ad_id", "form_id"]


class LeadsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _page(self, node_id: str = ""):
        return Page(node_id or self.config.page_id, api=get_page_api())

    def list_lead_gen_forms(self, page_id: str = "", limit: int = 25) -> Any:
        rows = paginate(
            lambda params: self._page(page_id).get_lead_gen_forms(params=params),
            fields=LEAD_FORM_FIELDS, limit=limit,
        )
        return rows

    def get_lead_gen_form(self, form_id: str) -> Any:
        info = LeadgenForm(form_id, api=get_page_api()).api_get(fields=LEAD_FORM_FIELDS)
        return to_dict(info)

    def get_form_leads(self, form_id: str, limit: int = 25) -> Any:
        rows = paginate(
            lambda params: LeadgenForm(form_id, api=get_page_api()).get_leads(params=params),
            fields=LEAD_FIELDS, limit=limit,
        )
        return rows

    def get_lead(self, lead_id: str) -> Any:
        info = Lead(lead_id, api=get_page_api()).api_get(fields=LEAD_FIELDS)
        return to_dict(info)

    def create_lead_gen_form(self, name: str, privacy_policy_url: str,
                             question_page_headline: str, page_id: str = "",
                             thankyou_page_headline: str = "", thankyou_page_body: str = "",
                             locale: str = "ar_AR") -> Any:
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
        page = self._page(page_id)
        form = page.create_lead_gen_form(params=params)
        return to_dict(form)

    def subscribe_leadgen_webhook(self, page_id: str = "", subscribed_fields: str = "leadgen") -> dict[str, Any]:
        from src.config import PAGE_ID
        pid = page_id or PAGE_ID
        if not pid:
            raise ValueError("page_id مطلوب (أو حدد FB_PAGE_ID في .env)")
        result = self.api.page_post(f"{pid}/subscribed_apps", {"subscribed_fields": subscribed_fields})
        return {"page_id": pid, "subscribed_fields": subscribed_fields, "result": result if isinstance(result, dict) else {}}

    def get_lead_field_mapping(self, lead_id: str) -> dict[str, Any]:
        from src.helpers import get_page_api
        info = Lead(lead_id, api=get_page_api()).api_get(fields=LEAD_FIELDS)
        data = to_dict(info)
        field_data = data.get("field_data", [])
        mapping = {}
        for item in field_data:
            name = item.get("name", "unknown")
            values = item.get("values", [])
            if len(values) == 1:
                mapping[name] = values[0]
            else:
                mapping[name] = values
        return {"lead_id": lead_id, "mapping": mapping, "raw": data}
