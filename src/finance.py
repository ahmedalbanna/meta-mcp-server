"""Wallet (finance) module: account balance, spend caps, transactions, payment methods, users."""

from src.config import AD_ACCOUNT_ID, BUSINESS_ID
from src.helpers import api_call, handle_error, json_dumps, to_dict, write_guard
from src.throttle import concurrency_limit

BALANCE_FIELDS = [
    "name",
    "account_status",
    "currency",
    "balance",
    "amount_spent",
    "spend_cap",
    "funding_source",
    "funding_source_details",
    "is_prepay_account",
    "timezone_name",
]


def register(mcp):
    """Register wallet/finance tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.business import Business

    @mcp.tool()
    @concurrency_limit()
    def get_account_balance() -> str:
        """رصيد الحساب الإعلاني والإنفاق وحد الإنفاق والعملة."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            info = account.api_get(fields=BALANCE_FIELDS)
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_account_balance"))

    @mcp.tool()
    @concurrency_limit()
    def get_spend_cap() -> str:
        """حدود الإنفاق الحالية للحساب الإعلاني."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            info = account.api_get(
                fields=["spend_cap", "amount_spent", "balance", "currency"]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_spend_cap"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_spend_cap(spend_cap: int) -> str:
        """
        تعديل حد الإنفاق الكلي للحساب (بالعملة الصغرى).
        مثال: 100000 = 1000 دولار. ضع 0 لإزالة الحد.
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            params = {"spend_cap": spend_cap} if spend_cap > 0 else {"spend_cap": 0}
            result = account.api_update(params=params)
            return json_dumps(
                {"success": True, "spend_cap": spend_cap, "result": to_dict(result)}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_spend_cap"))

    @mcp.tool()
    @concurrency_limit()
    def get_transactions(limit: int = 25) -> str:
        """آخر المعاملات المالية للحساب الإعلاني (فواتير/مدفوعات/إضافات)."""
        try:
            data = api_call(
                "GET",
                f"{AD_ACCOUNT_ID}/transactions",
                {
                    "fields": "type,amount,date,status,billing_reference_number",
                    "limit": limit,
                },
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(
                handle_error(
                    e,
                    "get_transactions: قد يتطلب صلاحية business_management ودور إداري. إن فشل، تحقق من صلاحية الحساب في Business Manager",
                )
            )

    @mcp.tool()
    @concurrency_limit()
    def get_payment_methods() -> str:
        """طرق الدفع المرتبطة بالحساب (مصدر التمويل)."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            info = account.api_get(
                fields=[
                    "funding_source",
                    "funding_source_details",
                    "extended_credit_invoice_group",
                    "is_prepay_account",
                ]
            )
            return json_dumps(
                {
                    "funding": to_dict(info),
                    "note": "إضافة/حذف بطاقات دفع غير مدعومة عبر API؛ تتم يدويًا من Business Manager > Settings > Payment Methods",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "get_payment_methods"))

    @mcp.tool()
    @concurrency_limit()
    def get_business_info(business_id: str = "") -> str:
        """معلومات Business Manager (الفوترة، اسم النشاط، الحالة)."""
        try:
            biz_id = business_id or BUSINESS_ID
            if not biz_id:
                return json_dumps({"error": "حدد BUSINESS_ID في ملف .env"})
            business = Business(biz_id)
            info = business.api_get(
                fields=[
                    Business.Field.name,
                    Business.Field.verification_status,
                    Business.Field.timezone_id,
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_business_info"))

    @mcp.tool()
    @concurrency_limit()
    def list_account_users() -> str:
        """المستخدمون المرتبطون بالحساب الإعلاني وصلاحياتهم."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            users = account.get_assigned_users(
                params={"fields": ["name", "role", "tasks", "id"]}
            )
            return json_dumps([to_dict(u) for u in users])
        except Exception as e:
            return json_dumps(handle_error(e, "list_account_users"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def assign_user_to_account(user_id: int, tasks: str = "ADVERTISE,MANAGE") -> str:
        """
        إضافة مستخدم إلى الحساب الإعلاني بصلاحيات محددة.
        tasks مفصولة بفواصل من: ADVERTISE, ANALYZE, MANAGE, DRAFT
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            task_list = [t.strip() for t in tasks.split(",") if t.strip()]
            account.create_assigned_user(params={"user": user_id, "tasks": task_list})
            return json_dumps({"success": True, "user_id": user_id, "tasks": task_list})
        except Exception as e:
            return json_dumps(handle_error(e, "assign_user_to_account"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def remove_user_from_account(user_id: int) -> str:
        """إزالة مستخدم من الحساب الإعلاني."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            account.delete_assigned_users(params={"user": user_id})
            return json_dumps({"success": True, "user_id": user_id})
        except Exception as e:
            return json_dumps(handle_error(e, "remove_user_from_account"))
