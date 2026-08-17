"""Business Manager users: list, invite, roles and removal."""

from src.config import BUSINESS_ID
from src.helpers import handle_error, json_dumps, to_dict, write_guard
from src.throttle import concurrency_limit
from src.utils import paginate

USER_ROLES = [
    "ADMIN",
    "EMPLOYEE",
    "AGENCY",
    "FB_EMPLOYEE_MANAGER",
    "FB_EMPLOYEE",
    "SYSTEM_USER",
]

USER_FIELDS = [
    "id",
    "name",
    "email",
    "first_name",
    "last_name",
    "role",
    "pending_email",
    "business",
]


def register(mcp):
    """Register Business Manager user tools."""

    from facebook_business.adobjects.business import Business
    from facebook_business.adobjects.businessuser import BusinessUser

    def _require_business_id(business_id: str) -> str:
        return business_id or BUSINESS_ID

    def _validate_role(role: str) -> str:
        r = role.strip().upper()
        if r not in USER_ROLES:
            raise ValueError(f"role غير صالح: {role}. الاختيارات: {', '.join(USER_ROLES)}")
        return r

    @mcp.tool()
    @concurrency_limit()
    def list_business_users(business_id: str = "", limit: int = 25) -> str:
        """قائمة مستخدمي Business Manager وأدوارهم."""
        try:
            bid = _require_business_id(business_id)
            if not bid:
                return json_dumps({"error": "حدد FB_BUSINESS_ID في .env أو مرّر business_id"})
            rows = paginate(
                lambda params: Business(bid).get_business_users(params=params),
                fields=USER_FIELDS,
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_business_users"))

    @mcp.tool()
    @concurrency_limit()
    def get_business_user(user_id: str) -> str:
        """تفاصيل مستخدم Business Manager واحد."""
        try:
            info = BusinessUser(user_id).api_get(fields=USER_FIELDS)
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_business_user"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def invite_business_user(email: str, role: str = "EMPLOYEE", name: str = "", business_id: str = "") -> str:
        """
        دعوة مستخدم جديد إلى Business Manager.
        role: ADMIN | EMPLOYEE | AGENCY | SYSTEM_USER.
        """
        try:
            bid = _require_business_id(business_id)
            if not bid:
                return json_dumps({"error": "حدد FB_BUSINESS_ID في .env أو مرّر business_id"})
            r = _validate_role(role)
            params = {"email": email, "role": r}
            if name:
                params["name"] = name
            user = Business(bid).create_business_user(params=params)
            return json_dumps(to_dict(user))
        except Exception as e:
            return json_dumps(handle_error(e, "invite_business_user"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_business_user_role(user_id: str, role: str) -> str:
        """تغيير دور مستخدم في Business Manager."""
        try:
            r = _validate_role(role)
            result = BusinessUser(user_id).api_update(params={"role": r})
            return json_dumps({"user_id": user_id, "role": r, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "update_business_user_role"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_business_user(user_id: str) -> str:
        """إزالة مستخدم من Business Manager نهائيًا."""
        try:
            result = BusinessUser(user_id).api_delete()
            return json_dumps({"user_id": user_id, "deleted": True, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_business_user"))
