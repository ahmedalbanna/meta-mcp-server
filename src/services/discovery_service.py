"""Discovery service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services


class DiscoveryService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def list_pages(self, limit: int = 25) -> Any:
        return self.api.get("me/accounts", {"fields": "name,id,category,link,access_token", "limit": limit})

    def list_ad_accounts(self, limit: int = 25) -> Any:
        return self.api.get("me/adaccounts", {
            "fields": "name,account_id,currency,account_status,amount_spent",
            "limit": limit,
        })

    def discover_ig_user(self, page_id: str = "") -> Any:
        if page_id:
            return self.api.get(page_id, {"fields": "name,instagram_business_account{id,username}"})
        pages = self.api.get("me/accounts", {"fields": "name,id"})
        out = []
        for p in pages.get("data", []) if isinstance(pages, dict) else []:
            row = {"page_id": p.get("id"), "page_name": p.get("name"), "instagram": None}
            try:
                detail = self.api.get(p["id"], {"fields": "instagram_business_account{id,username}"})
                ig = detail.get("instagram_business_account") or {}
                row["instagram"] = {"id": ig.get("id"), "username": ig.get("username")}
            except Exception:
                row["instagram"] = "غير مرتبط أو بدون صلاحية"
            out.append(row)
        return out

    def debug_access_token(self, input_token: str = "") -> Any:
        from src.config import APP_ID, APP_SECRET, META_ACCESS_TOKEN
        token = input_token or META_ACCESS_TOKEN
        if not APP_ID or not APP_SECRET:
            raise ValueError("حدد FB_APP_ID و FB_APP_SECRET في .env")
        return self.api.get("debug_token", {
            "input_token": token,
            "access_token": f"{APP_ID}|{APP_SECRET}",
        })
