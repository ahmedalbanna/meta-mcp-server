"""Wallet (finance) module: account balance, spend caps, transactions, payment methods, users."""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)
from src.throttle import concurrency_limit
from src.utils import handle_error, json_dumps, write_guard

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


def register(mcp, services):
    """Register wallet/finance tools."""

    @mcp.tool()
    @concurrency_limit()
    def get_account_balance(ad_account_id: str = "") -> str:
        """رصيد الحساب الإعلاني والإنفاق وحد الإنفاق والعملة."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            data = svc.get_account_balance(ad_account_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_account_balance"))

    @mcp.tool()
    @concurrency_limit()
    def get_spend_cap(ad_account_id: str = "") -> str:
        """حدود الإنفاق الحالية للحساب الإعلاني."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            data = svc.get_spend_cap(ad_account_id)
            return json_dumps(data)
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
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            return json_dumps(svc.update_spend_cap(spend_cap))
        except Exception as e:
            return json_dumps(handle_error(e, "update_spend_cap"))

    @mcp.tool()
    @concurrency_limit()
    def get_transactions(limit: int = 25) -> str:
        """سجل معاملات الحساب الإعلاني. ملاحظة: أزالت Meta حافة /transactions من Graph API بالكامل — الفواتير متاحة من Business Manager > Billing."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            data = svc.get_transactions(limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_transactions"))

    @mcp.tool()
    @concurrency_limit()
    def get_payment_methods() -> str:
        """طرق الدفع المرتبطة بالحساب (مصدر التمويل)."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            data = svc.get_payment_methods()
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_payment_methods"))

    @mcp.tool()
    @concurrency_limit()
    def get_business_info(business_id: str = "") -> str:
        """معلومات Business Manager (الفوترة، اسم النشاط، الحالة)."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            return json_dumps(svc.get_business_info(business_id))
        except Exception as e:
            return json_dumps(handle_error(e, "get_business_info"))

    @mcp.tool()
    @concurrency_limit()
    def list_account_users() -> str:
        """المستخدمون المرتبطون بالحساب الإعلاني وصلاحياتهم."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            return json_dumps(svc.list_account_users())
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
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            return json_dumps(svc.assign_user(user_id, tasks))
        except Exception as e:
            return json_dumps(handle_error(e, "assign_user_to_account"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def remove_user_from_account(user_id: int) -> str:
        """إزالة مستخدم من الحساب الإعلاني."""
        try:
            from src.services.finance_service import FinanceService

            svc = FinanceService(services)
            return json_dumps(svc.remove_user(user_id))
        except Exception as e:
            return json_dumps(handle_error(e, "remove_user_from_account"))

    @mcp.resource("finance://overview")
    async def finance_resource() -> str:
        """ملخص المحفظة."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "finance", "resource": "finance://overview", "hint": "ملخص المحفظة"})
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "finance://overview"))

    @mcp.prompt()
    def finance_report_prompt(topic: str = "finance") -> str:
        """تقرير مالي."""
        return "ساعد في تقرير مالي لـ " + topic + " — أنشئ تقرير مالي للفترة {date_range} (وحدة finance)"

    @mcp.resource("account://summary")
    async def account_summary_resource() -> str:
        """ملخص أداء الحساب الإعلاني."""
        try:

            def _fetch():
                acct = services.config.fb_ad_account_id
                info = services.api.get(
                    acct,
                    {
                        "fields": [
                            "name",
                            "account_status",
                            "currency",
                            "balance",
                            "amount_spent",
                            "spend_cap",
                        ]
                    },
                )
                insights = services.api.get(
                    f"{acct}/insights",
                    {
                        "date_preset": "last_30d",
                        "fields": "spend,impressions,clicks",
                    },
                )
                return info, insights

            t0 = time.monotonic()
            info, insights = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("account://summary fetched in %.2fs", elapsed)
            data = info if isinstance(info, dict) else {}
            if isinstance(insights, dict) and insights.get("data"):
                data["insights_30d"] = insights["data"][0]
            return json_dumps(data)
        except Exception as e:
            from src.utils import handle_error

            logger.exception("account://summary failed")
            return json_dumps(handle_error(e, "account://summary"))
