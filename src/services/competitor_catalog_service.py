"""Competitor catalog service (Phase B)."""

from __future__ import annotations

import json
from typing import Any

from src.core.services import Services


class CompetitorCatalogService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def publish_drafts(self, catalog_id: str, product_ids: str = "") -> dict[str, Any]:
        if not catalog_id:
            raise ValueError("catalog_id مطلوب")
        ids = [p.strip() for p in product_ids.split(",") if p.strip()]
        if not ids:
            data = self.api.get(
                f"{catalog_id}/products",
                {
                    "fields": "id,name,visibility",
                    "filter": json.dumps({"visibility": {"eq": "staging"}}),
                },
            )
            ids = [str(p.get("id")) for p in (data.get("data") or []) if p.get("id")]
            if not ids:
                return {"message": "لا توجد منتجات مسودة (staging) في هذا الكتالوج"}
        results = []
        for pid in ids[:100]:
            try:
                res = self.api.post(pid, {"visibility": "published"})
                results.append({"id": pid, "published": bool(res.get("success", True)), "result": res})
            except Exception as e:
                results.append({"id": pid, "error": str(e)[:150]})
        ok = sum(1 for r in results if r.get("published"))
        return {
            "catalog_id": catalog_id,
            "attempted": len(results),
            "published": ok,
            "results": results,
            "warning": "تأكدي أن الصور منتجاتكِ قبل النشر",
        }

    def list_drafts(self, catalog_id: str, limit: int = 50) -> dict[str, Any]:
        if not catalog_id:
            raise ValueError("catalog_id مطلوب")
        data = self.api.get(
            f"{catalog_id}/products",
            {
                "fields": "id,name,price,currency,image_url,visibility,description",
                "filter": json.dumps({"visibility": {"eq": "staging"}}),
                "limit": max(1, min(limit, 100)),
            },
        )
        rows = data.get("data") or []
        return {
            "catalog_id": catalog_id,
            "draft_count": len(rows),
            "products": rows,
            "hint": "publish_catalog_draft(catalog_id) لنشرها بعد مراجعتها",
        }
