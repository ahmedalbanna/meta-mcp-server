"""Business service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.utils import paginate, to_dict

USER_FIELDS = ["id", "first_name", "last_name", "email", "role", "title"]
USER_ROLES = {"ADMIN", "EMPLOYEE", "AGENCY", "SYSTEM_USER"}


class BusinessService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _require_business_id(self, business_id: str) -> str:
        return business_id or self.config.business_id

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
            lambda params: self.services.api.get(f"{bid}/business_users", params),
            fields=USER_FIELDS,
            limit=limit,
        )
        return rows

    def get_user(self, user_id: str) -> Any:
        data = self.services.api.get(f"{user_id}", {"fields": ",".join(USER_FIELDS)})
        return to_dict(data)

    def invite_user(self, email: str, role: str = "EMPLOYEE", name: str = "", business_id: str = "") -> Any:
        bid = self._require_business_id(business_id)
        if not bid:
            raise ValueError("حدد FB_BUSINESS_ID في .env أو مرّر business_id")
        r = self._validate_role(role)
        params: dict[str, Any] = {"email": email, "role": r}
        if name:
            params["name"] = name
        data = self.services.api.post(f"{bid}/business_users", params)
        return to_dict(data)

    def update_role(self, user_id: str, role: str) -> dict[str, Any]:
        r = self._validate_role(role)
        self.services.api.post(f"{user_id}", {"role": r})
        return {"user_id": user_id, "role": r, "result": {}}

    def delete_user(self, user_id: str) -> dict[str, Any]:
        self.services.api.delete(f"{user_id}")
        return {"user_id": user_id, "deleted": True, "result": {}}
