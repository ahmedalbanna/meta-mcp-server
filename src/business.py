"""Business Manager users: list, invite, roles and removal."""

import logging

logger = logging.getLogger(__name__)
from src.throttle import concurrency_limit
from src.utils import handle_error, json_dumps, paginate, to_dict, write_guard

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


def register(mcp, services):
    """Register Business Manager user tools."""

    from facebook_business.adobjects.business import Business
    from facebook_business.adobjects.businessuser import BusinessUser

    def _require_business_id(business_id: str) -> str:
        return business_id or services.config.business_id

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
            from src.core.services import Services
            from src.services.business_service import BusinessService

            svc = BusinessService(services)
            rows = svc.list_users(business_id, limit)
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_business_users"))

    @mcp.tool()
    @concurrency_limit()
    def get_business_user(user_id: str) -> str:
        """تفاصيل مستخدم Business Manager واحد."""
        try:
            from src.core.services import Services
            from src.services.business_service import BusinessService

            svc = BusinessService(services)
            info = svc.get_user(user_id)
            return json_dumps(info)
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
            from src.core.services import Services
            from src.services.business_service import BusinessService

            svc = BusinessService(services)
            user = svc.invite_user(email, role, name, business_id)
            return json_dumps(user)
        except Exception as e:
            return json_dumps(handle_error(e, "invite_business_user"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_business_user_role(user_id: str, role: str) -> str:
        """تغيير دور مستخدم في Business Manager."""
        try:
            from src.core.services import Services
            from src.services.business_service import BusinessService

            svc = BusinessService(services)
            result = svc.update_role(user_id, role)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "update_business_user_role"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_business_user(user_id: str) -> str:
        """إزالة مستخدم من Business Manager نهائيًا."""
        try:
            from src.core.services import Services
            from src.services.business_service import BusinessService

            svc = BusinessService(services)
            result = svc.delete_user(user_id)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "delete_business_user"))

    @mcp.resource("business://overview")
    async def business_resource() -> str:
        """نظرة عامة على الأعمال."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "business", "resource": "business://overview", "hint": "نظرة عامة على الأعمال"}
            )
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "business://overview"))

    @mcp.prompt()
    def business_user_prompt(topic: str = "business") -> str:
        """إدارة مستخدمي الأعمال."""
        return "ساعد في إدارة مستخدمي الأعمال لـ " + topic + " — أضف مستخدم {email} بدور {role} (وحدة business)"

    @mcp.resource("business://templates")
    async def business_extra_resource() -> str:
        """قوالب الأعمال."""
        try:
            return json_dumps({"module": "business", "resource": "business://templates", "hint": "قوالب الأعمال"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "business://templates"))

    @mcp.prompt()
    def business_invite_prompt(topic: str = "business") -> str:
        """دعوة أعمال."""
        return "ساعد في دعوة أعمال لـ " + topic + " — ادع مستخدم {email} (وحدة business)"
