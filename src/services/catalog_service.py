"""Catalog service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.utils import paginate, to_dict

SET_FIELDS = ["id", "name", "filter"]


class CatalogService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _require_business_id(self, business_id: str) -> str:
        return business_id or self.config.business_id

    # --- read ---
    def list_catalogs(self, business_id: str = "", limit: int = 25) -> Any:
        bid = self._require_business_id(business_id)
        if not bid:
            return {"error": "business_id مطلوب"}
        return self.api.get(f"{bid}/owned_product_catalogs", {"fields": "id,name,product_count", "limit": limit})

    def get_catalog(self, catalog_id: str) -> Any:
        return self.api.get(catalog_id, {"fields": "id,name,product_count,vertical"})

    def get_catalog_settings(self, catalog_id: str) -> Any:
        return self.api.get(
            catalog_id,
            {
                "fields": "store_catalog_settings,default_image_url,fallback_image_url,da_display_settings,"
                "catalog_store,feed_count,product_count,is_catalog_segment,is_local_catalog"
            },
        )

    def list_product_sets(self, catalog_id: str, limit: int = 25) -> Any:
        rows = paginate(
            lambda params: self.services.api.get(f"{catalog_id}/productsets", params),
            fields=SET_FIELDS,
            limit=limit,
        )
        return rows

    def get_product_set(self, product_set_id: str) -> Any:
        data = self.services.api.get(product_set_id, {"fields": ",".join(SET_FIELDS)})
        return to_dict(data)

    def list_products(self, catalog_id: str, limit: int = 25, filter: str = "") -> Any:
        params: dict[str, Any] = {"fields": "id,name,price,currency,availability,image_url,url", "limit": limit}
        if filter:
            params["filter"] = filter
        return self.api.get(f"{catalog_id}/products", params)

    def get_product(self, product_id: str) -> Any:
        return self.api.get(
            product_id, {"fields": "id,name,price,currency,availability,image_url,url,description,brand"}
        )

    # --- write ---
    def create_catalog(self, name: str, business_id: str = "") -> Any:
        bid = self._require_business_id(business_id)
        if not bid:
            raise ValueError("حدد FB_BUSINESS_ID في .env أو مرّر business_id")
        data = self.services.api.post(f"{bid}/owned_product_catalogs", {"name": name})
        return to_dict(data)

    def delete_catalog(self, catalog_id: str) -> dict[str, Any]:
        self.services.api.delete(f"{catalog_id}")
        return {"success": True, "catalog_id": catalog_id, "result": {}}

    def create_product_set(self, catalog_id: str, name: str, filters_json: str = "") -> Any:
        params: dict[str, Any] = {"name": name}
        if filters_json:
            params["filter"] = filters_json
        data = self.services.api.post(f"{catalog_id}/productsets", params)
        return to_dict(data)

    def delete_product_set(self, product_set_id: str) -> dict[str, Any]:
        self.services.api.delete(f"{product_set_id}")
        return {"success": True, "product_set_id": product_set_id, "result": {}}

    def create_product(
        self,
        catalog_id: str,
        name: str,
        price: float = 0.0,
        currency: str = "USD",
        description: str = "",
        image_url: str = "",
        url: str = "",
        availability: str = "in stock",
        brand: str = "",
        retailer_id: str = "",
        gtin: str = "",
        condition: str = "new",
        sale_price: float = 0.0,
        product_type: str = "",
        category: str = "",
        custom_label_0: str = "",
    ) -> Any:
        params: dict[str, Any] = {
            "name": name,
            "price": str(round(price, 2)) if price else "0",
            "currency": currency,
        }
        optional = {
            "description": description,
            "image_url": image_url,
            "url": url,
            "availability": availability,
            "brand": brand,
            "retailer_id": retailer_id,
            "gtin": gtin,
            "condition": condition,
            "product_type": product_type,
            "category": category,
            "custom_label_0": custom_label_0,
        }
        if sale_price:
            optional["sale_price"] = str(sale_price)
        params.update({k: v for k, v in optional.items() if v})
        data = self.services.api.post(f"{catalog_id}/products", params)
        return to_dict(data)

    def update_product(
        self,
        product_id: str,
        name: str = "",
        price: float = 0.0,
        currency: str = "",
        description: str = "",
        image_url: str = "",
        url: str = "",
        availability: str = "",
        brand: str = "",
        retailer_id: str = "",
        gtin: str = "",
        condition: str = "",
        sale_price: float = 0.0,
        product_type: str = "",
        category: str = "",
        custom_label_0: str = "",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        _str_fields = [
            (name, "name"),
            (currency, "currency"),
            (description, "description"),
            (image_url, "image_url"),
            (url, "url"),
            (availability, "availability"),
            (brand, "brand"),
            (retailer_id, "retailer_id"),
            (gtin, "gtin"),
            (condition, "condition"),
            (product_type, "product_type"),
            (category, "category"),
            (custom_label_0, "custom_label_0"),
        ]
        for val, field in _str_fields:
            if val:
                params[field] = val
        if price:
            params["price"] = str(round(price, 2))
        if sale_price:
            params["sale_price"] = str(round(sale_price, 2))
        if not params:
            raise ValueError("حدد حقلًا واحدًا على الأقل للتعديل")
        self.services.api.post(f"{product_id}", params)
        return {"success": True, "product_id": product_id, "result": {}}

    def delete_product(self, product_id: str) -> dict[str, Any]:
        self.services.api.delete(f"{product_id}")
        return {"success": True, "product_id": product_id, "result": {}}

    def get_product_feed(self, feed_id: str) -> Any:
        fields = ["id", "name", "schedule", "latest_upload", "filter", "country", "default_currency", "file_type"]
        data = self.services.api.get(feed_id, {"fields": ",".join(fields)})
        return to_dict(data)

    def get_product_feed_diagnostics(self, feed_id: str, limit: int = 5) -> Any:
        feed_fields = ["id", "name", "schedule", "latest_upload", "file_type"]
        feed_data = self.services.api.get(feed_id, {"fields": ",".join(feed_fields)})
        feed_dict = to_dict(feed_data)
        upload_fields = [
            "id",
            "status",
            "start_time",
            "end_time",
            "error_count",
            "warning_count",
            "num_deleted_items",
            "num_updated_items",
            "num_hidden_items",
            "error_report",
        ]
        uploads = paginate(
            lambda params: self.services.api.get(f"{feed_id}/uploads", params),
            fields=upload_fields,
            limit=limit,
        )
        total_errors = sum(int(u.get("error_count") or 0) for u in uploads)
        total_warnings = sum(int(u.get("warning_count") or 0) for u in uploads)
        return {
            "feed": feed_dict,
            "uploads": uploads,
            "summary": {
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "last_status": uploads[0].get("status") if uploads else "unknown",
            },
        }

    def get_commerce_merchant_settings(self, business_id: str = "") -> Any:
        bid = business_id or self.config.business_id
        if not bid:
            raise ValueError("حدد FB_BUSINESS_ID في .env أو مرّر business_id")
        rows = paginate(
            lambda params: self.services.api.get(f"{bid}/commerce_merchant_settings", params),
            fields=[
                "id",
                "display_name",
                "contact_email",
                "merchant_page",
                "payment_provider",
                "merchant_status",
                "facebook_channel",
                "instagram_channel",
            ],
            limit=25,
        )
        return rows
