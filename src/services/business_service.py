"""Business service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.business import Business
from facebook_business.adobjects.businessuser import BusinessUser

from src.config import BUSINESS_ID
from src.core.services import Services
from src.helpers import to_dict
from src.utils import paginate

USER_FIELDS = ["id", "first_name", "last_name", "email", "role", "title"]
USER_ROLES = {"ADMIN", "EMPLOYEE", "AGENCY", "SYSTEM_USER"}


class BusinessService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _require_business_id(self, business_id: str) -> str:
        return business_id or BUSINESS_ID

    def _validate_role(self, role: str) -> str:
        r = role.strip().upper()
        if r not in USER_ROLES:
            raise ValueError(f"role غير صالح: {role}. الاختيارات: {', '.join(USER_ROLES)}")
        return r

    def list_users(self, business_id: str = "", limit: int = 25) -> Any:
        bid = self._require_business_id(business_id)
        if not bid:
            raise ValueError("حدد FB_BUSINESS_ID في .env أو مرّر business_id")
        rows = paginate(
            lambda params: Business(bid).get_business_users(params=params),
            fields=USER_FIELDS, limit=limit,
        )
        return rows

    def get_user(self, user_id: str) -> Any:
        return to_dict(BusinessUser(user_id).api_get(fields=USER_FIELDS))

    def invite_user(self, email: str, role: str = "EMPLOYEE", name: str = "", business_id: str = "") -> Any:
        bid = self._require_business_id(business_id)
        if not bid:
            raise ValueError("حدد FB_BUSINESS_ID في .env أو مرّر business_id")
        r = self._validate_role(role)
        params: dict[str, Any] = {"email": email, "role": r}
        if name:
            params["name"] = name
        return to_dict(Business(bid).create_business_user(params=params))

    def update_role(self, user_id: str, role: str) -> dict[str, Any]:
        r = self._validate_role(role)
        result = BusinessUser(user_id).api_update(params={"role": r})
        return {"user_id": user_id, "role": r, "result": to_dict(result)}

    def delete_user(self, user_id: str) -> dict[str, Any]:
        result = BusinessUser(user_id).api_delete()
        return {"user_id": user_id, "deleted": True, "result": to_dict(result)}
