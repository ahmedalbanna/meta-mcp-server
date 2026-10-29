"""Leads service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.utils import paginate, to_dict

LEAD_FORM_FIELDS = [
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
LEAD_FIELDS = ["id", "created_time", "field_data", "ad_id", "form_id"]


class LeadsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _pid(self, page_id: str = "") -> str:
        return page_id or self.config.page_id

    def list_lead_gen_forms(self, page_id: str = "", limit: int = 25) -> Any:
        pid = self._pid(page_id)
        rows = paginate(
            lambda params: self.api.page_get(f"{pid}/leadgenforms", params),
            fields=LEAD_FORM_FIELDS,
            limit=limit,
        )
        return rows

    def get_lead_gen_form(self, form_id: str) -> Any:
        data = self.api.page_get(f"{form_id}", {"fields": ",".join(LEAD_FORM_FIELDS)})
        return to_dict(data)

    def get_form_leads(self, form_id: str, limit: int = 25) -> Any:
        rows = paginate(
            lambda params: self.api.page_get(f"{form_id}/leads", params),
            fields=LEAD_FIELDS,
            limit=limit,
        )
        return rows

    def get_lead(self, lead_id: str) -> Any:
        data = self.api.page_get(f"{lead_id}", {"fields": ",".join(LEAD_FIELDS)})
        return to_dict(data)

    def create_lead_gen_form(
        self,
        name: str,
        privacy_policy_url: str,
        question_page_headline: str,
        page_id: str = "",
        thankyou_page_headline: str = "",
        thankyou_page_body: str = "",
        locale: str = "ar_AR",
    ) -> Any:
        pid = self._pid(page_id)
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
        data = self.api.page_post(f"{pid}/leadgenforms", params)
        return to_dict(data)

    def subscribe_leadgen_webhook(self, page_id: str = "", subscribed_fields: str = "leadgen") -> dict[str, Any]:
        pid = self._pid(page_id)
        if not pid:
            raise ValueError("page_id مطلوب (أو حدد FB_PAGE_ID في .env)")
        result = self.api.page_post(f"{pid}/subscribed_apps", {"subscribed_fields": subscribed_fields})
        return {
            "page_id": pid,
            "subscribed_fields": subscribed_fields,
            "result": result if isinstance(result, dict) else {},
        }

    def get_lead_field_mapping(self, lead_id: str) -> dict[str, Any]:
        data = self.api.page_get(f"{lead_id}", {"fields": ",".join(LEAD_FIELDS)})
        data_dict = to_dict(data)
        field_data = data_dict.get("field_data", [])
        mapping = {}
        for item in field_data:
            name = item.get("name", "unknown")
            values = item.get("values", [])
            if len(values) == 1:
                mapping[name] = values[0]
            else:
                mapping[name] = values
        return {"lead_id": lead_id, "mapping": mapping, "raw": data_dict}
