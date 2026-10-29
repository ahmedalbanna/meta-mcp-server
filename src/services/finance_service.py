"""Finance service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.business import Business

from src.config import AD_ACCOUNT_ID, BUSINESS_ID, resolve_ad_account_id
from src.core.services import Services
from src.helpers import to_dict


class FinanceService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def get_account_balance(self, ad_account_id: str = "") -> Any:
        BALANCE_FIELDS = ["balance", "spend_cap", "amount_spent", "currency"]
        account = AdAccount(resolve_ad_account_id(ad_account_id))
        info = account.api_get(fields=BALANCE_FIELDS)
        return to_dict(info)

    def get_spend_cap(self, ad_account_id: str = "") -> Any:
        acct = ad_account_id or AD_ACCOUNT_ID
        account = AdAccount(acct)
        info = account.api_get(fields=["spend_cap", "amount_spent", "balance", "currency"])
        return to_dict(info)

    def get_transactions(self, limit: int = 25) -> Any:
        account = AdAccount(AD_ACCOUNT_ID)
        info = account.api_get(fields=["funding_source_details", "spend_cap", "balance"])
        return {
            "account_financials": to_dict(info),
            "note": "حافة act_x/transactions أزيلت من Graph API من Meta (تعود بـ error 100 في كل الإصدارات). المعاملات التفصيلية متاحة يدويًا من Business Manager > Billing > Transactions.",
        }

    def get_payment_methods(self) -> Any:
        account = AdAccount(AD_ACCOUNT_ID)
        info = account.api_get(fields=["funding_source", "funding_source_details", "extended_credit_invoice_group", "is_prepay_account"])
        return {
            "funding": to_dict(info),
            "note": "إضافة/حذف بطاقات دفع غير مدعومة عبر API؛ تتم يدويًا من Business Manager > Settings > Payment Methods",
        }


    def update_spend_cap(self, spend_cap: int) -> dict[str, Any]:
        account = AdAccount(AD_ACCOUNT_ID)
        params = {"spend_cap": spend_cap} if spend_cap > 0 else {"spend_cap": 0}
        result = account.api_update(params=params)
        return {"success": True, "spend_cap": spend_cap, "result": to_dict(result)}

    def list_account_users(self) -> list:
        account = AdAccount(AD_ACCOUNT_ID)
        params = {"fields": ["id", "name", "tasks"]}
        if BUSINESS_ID:
            params["business"] = BUSINESS_ID  # type: ignore[assignment]
        users = account.get_assigned_users(params=params)
        return [to_dict(u) for u in users]

    def assign_user(self, user_id: int, tasks: str = "ADVERTISE,MANAGE") -> dict[str, Any]:
        account = AdAccount(AD_ACCOUNT_ID)
        task_list = [t.strip() for t in tasks.split(",") if t.strip()]
        account.create_assigned_user(params={"user": user_id, "tasks": task_list})
        return {"success": True, "user_id": user_id, "tasks": task_list}

    def remove_user(self, user_id: int) -> dict[str, Any]:
        account = AdAccount(AD_ACCOUNT_ID)
        account.delete_assigned_users(params={"user": user_id})
        return {"success": True, "user_id": user_id}

    def get_business_info(self, business_id: str = "") -> Any:
        bid = business_id or self.config.business_id
        if not bid:
            raise ValueError("حدد BUSINESS_ID في ملف .env")
        biz = Business(bid)
        info = biz.api_get(fields=["id", "name", "verification_status", "timezone_id"])
        return to_dict(info)
