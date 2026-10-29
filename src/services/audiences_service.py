"""Audiences service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.customaudience import CustomAudience

from src.config import resolve_ad_account_id
from src.core.services import Services
from src.helpers import to_dict
from src.utils import paginate


class AudiencesService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list_custom_audiences(self, limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [CustomAudience.Field.name, CustomAudience.Field.subtype, "approximate_count", CustomAudience.Field.id]
        rows = paginate(
            lambda params: AdAccount(resolve_ad_account_id(ad_account_id)).get_custom_audiences(params=params),
            fields=fields, limit=limit,
        )
        return rows

    def get_custom_audience_insights(self, audience_id: str) -> Any:
        aud = CustomAudience(audience_id)
        info = aud.api_get(fields=[CustomAudience.Field.name, CustomAudience.Field.subtype,
                                  CustomAudience.Field.approximate_count, CustomAudience.Field.id])
        return to_dict(info)

    @staticmethod
    def _split(items: str) -> list:
        return [i.strip() for i in (items or "").split(",") if i.strip()]

    def _build_user_schema(self, emails: str, phone_numbers: str, user_ids: str, hash_pii: bool):
        from src.utils import normalize_pii
        schema = []
        users = []
        if emails:
            email_list = self._split(emails)
            if hash_pii:
                schema.append("EMAIL_SHA256")
                users.extend(normalize_pii(email_list, "email"))
            else:
                schema.append("EMAIL")
                users.extend(email_list)
        if phone_numbers:
            phone_list = self._split(phone_numbers)
            if hash_pii:
                schema.append("PHONE_SHA256")
                users.extend(normalize_pii(phone_list, "phone"))
            else:
                schema.append("PHONE")
                users.extend(phone_list)
        if user_ids:
            schema.append("ID")
            users.extend(self._split(user_ids))
        return schema, users

    def create_custom_audience(self, name: str, description: str = "",
                               customer_file_source: str = "BOTH_USER_AND_PARTNER_PROVIDED",
                               ad_account_id: str = "") -> Any:
        account = AdAccount(resolve_ad_account_id(ad_account_id))
        audience = account.create_custom_audience(params={
            CustomAudience.Field.name: name,
            CustomAudience.Field.subtype: "CUSTOM",
            CustomAudience.Field.description: description,
            "customer_file_source": customer_file_source,
        })
        return to_dict(audience)

    def add_users(self, audience_id: str, emails: str = "", phone_numbers: str = "",
                  user_ids: str = "", hash_pii: bool = True) -> dict[str, Any]:
        audience = CustomAudience(audience_id)
        schema, users = self._build_user_schema(emails, phone_numbers, user_ids, hash_pii)
        if not users:
            raise ValueError("قدّم بريدًا أو أرقام هواتف أو معرفات")
        result = audience.add_users(schema=schema, users=users)
        return {"success": True, "audience_id": audience_id, "added": len(users),
                "hashed": hash_pii, "result": to_dict(result)}

    def remove_users(self, audience_id: str, emails: str = "", phone_numbers: str = "",
                     user_ids: str = "", hash_pii: bool = True) -> dict[str, Any]:
        audience = CustomAudience(audience_id)
        schema, users = self._build_user_schema(emails, phone_numbers, user_ids, hash_pii)
        if not users:
            raise ValueError("قدّم بريدًا أو أرقام هواتف أو معرفات")
        result = audience.remove_users(schema=schema, users=users)
        return {"success": True, "audience_id": audience_id, "removed": len(users),
                "hashed": hash_pii, "result": to_dict(result)}
