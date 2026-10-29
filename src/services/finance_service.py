"""Finance service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.utils import to_dict


class FinanceService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _acct(self, ad_account_id: str = "") -> str:
        return self.config.resolve_ad_account_id(ad_account_id)

    def get_account_balance(self, ad_account_id: str = "") -> Any:
        BALANCE_FIELDS = ["balance", "spend_cap", "amount_spent", "currency"]
        acct = self._acct(ad_account_id)
        data = self.services.api.get(f"{acct}", {"fields": ",".join(BALANCE_FIELDS)})
        return to_dict(data)

    def get_spend_cap(self, ad_account_id: str = "") -> Any:
        acct = ad_account_id or self.config.fb_ad_account_id
        data = self.services.api.get(f"{acct}", {"fields": "spend_cap,amount_spent,balance,currency"})
        return to_dict(data)

    def get_transactions(self, limit: int = 25) -> Any:
        acct = self.config.fb_ad_account_id
        data = self.services.api.get(f"{acct}", {"fields": "funding_source_details,spend_cap,balance"})
        return {
            "account_financials": to_dict(data),
            "note": "حافة act_x/transactions أزيلت من Graph API من Meta (تعود بـ error 100 في كل الإصدارات). المعاملات التفصيلية متاحة يدويًا من Business Manager > Billing > Transactions.",
        }

    def get_payment_methods(self) -> Any:
        acct = self.config.fb_ad_account_id
        data = self.services.api.get(
            f"{acct}",
            {"fields": "funding_source,funding_source_details,extended_credit_invoice_group,is_prepay_account"},
        )
        return {
            "funding": to_dict(data),
            "note": "إضافة/حذف بطاقات دفع غير مدعومة عبر API؛ تتم يدويًا من Business Manager > Settings > Payment Methods",
        }

    def update_spend_cap(self, spend_cap: int) -> dict[str, Any]:
        acct = self.config.fb_ad_account_id
        params = {"spend_cap": spend_cap} if spend_cap > 0 else {"spend_cap": 0}
        self.services.api.post(f"{acct}", params)
        return {"success": True, "spend_cap": spend_cap, "result": {}}

    def list_account_users(self) -> list:
        acct = self.config.fb_ad_account_id
        params: dict[str, Any] = {"fields": "id,name,tasks"}
        if self.config.business_id:
            params["business"] = self.config.business_id
        data = self.services.api.get(f"{acct}/assignedusers", params)
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [to_dict(u) for u in rows]

    def assign_user(self, user_id: int, tasks: str = "ADVERTISE,MANAGE") -> dict[str, Any]:
        acct = self.config.fb_ad_account_id
        task_list = [t.strip() for t in tasks.split(",") if t.strip()]
        self.services.api.post(f"{acct}/assignedusers", {"user": user_id, "tasks": task_list})
        return {"success": True, "user_id": user_id, "tasks": task_list}

    def remove_user(self, user_id: int) -> dict[str, Any]:
        acct = self.config.fb_ad_account_id
        self.services.api.delete(f"{acct}/assignedusers", params={"user": user_id})
        return {"success": True, "user_id": user_id}

    def get_business_info(self, business_id: str = "") -> Any:
        bid = business_id or self.config.business_id
        if not bid:
            raise ValueError("حدد FB_BUSINESS_ID في ملف .env")
        data = self.services.api.get(f"{bid}", {"fields": "id,name,verification_status,timezone_id"})
        return to_dict(data)
