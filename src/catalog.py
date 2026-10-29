import asyncio
import json as _json
import logging
import time

logger = logging.getLogger(__name__)


def register(mcp, services):
    """Register catalog & commerce tools."""

    from src.throttle import concurrency_limit
    from src.utils import handle_error, json_dumps, paginate, to_dict, write_guard

    def _require_business_id(business_id: str) -> str:
        return business_id or services.config.business_id

    def _require_commerce_account(commerce_account_id: str) -> str:
        return commerce_account_id or services.config.commerce_account_id

    # ------------------------------------------------------------------
    # الكتالوجات Catalogs
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_catalogs(business_id: str = "", limit: int = 25) -> str:
        """قائمة كتالوجات المنتجات التابعة لنشاط تجاري."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.list_catalogs(business_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_catalogs"))

    @mcp.tool()
    @concurrency_limit()
    def get_catalog(catalog_id: str) -> str:
        """تفاصيل كتالوج واحد."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_catalog(catalog_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_catalog"))

    @mcp.tool()
    @concurrency_limit()
    def get_catalog_settings(catalog_id: str) -> str:
        """إعدادات كتالوج واحد."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_catalog_settings(catalog_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_catalog_settings"))

    @mcp.tool()
    @concurrency_limit()
    def list_product_sets(catalog_id: str, limit: int = 25) -> str:
        """قائمة مجموعات المنتجات في كتالوج."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            rows = svc.list_product_sets(catalog_id, limit)
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_product_sets"))

    @mcp.tool()
    @concurrency_limit()
    def get_product_set(product_set_id: str) -> str:
        """تفاصيل مجموعة منتجات واحدة."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_product_set(product_set_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_product_set"))

    @mcp.tool()
    @concurrency_limit()
    def list_products(catalog_id: str, limit: int = 25, filter: str = "") -> str:
        """قائمة منتجات كتالوج."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.list_products(catalog_id, limit, filter)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_products"))

    @mcp.tool()
    @concurrency_limit()
    def get_product(product_id: str) -> str:
        """تفاصيل منتج واحد."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_product(product_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_product"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_catalog(name: str, business_id: str = "") -> str:
        """إنشاء كتالوج منتجات جديد."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.create_catalog(name, business_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_catalog"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_catalog(catalog_id: str) -> str:
        """حذف كتالوج نهائيًا."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.delete_catalog(catalog_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "delete_catalog"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_product_set(catalog_id: str, name: str, filters_json: str = "") -> str:
        """إنشاء مجموعة منتجات في كتالوج."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.create_product_set(catalog_id, name, filters_json)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_product_set"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_product_set(product_set_id: str) -> str:
        """حذف مجموعة منتجات."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.delete_product_set(product_set_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "delete_product_set"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_product(
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
    ) -> str:
        """إنشاء منتج في كتالوج."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.create_product(
                catalog_id,
                name,
                price,
                currency,
                description,
                image_url,
                url,
                availability,
                brand,
                retailer_id,
                gtin,
                condition,
                sale_price,
                product_type,
                category,
                custom_label_0,
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "create_product"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_product(
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
    ) -> str:
        """تعديل منتج موجود."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.update_product(
                product_id,
                name,
                price,
                currency,
                description,
                image_url,
                url,
                availability,
                brand,
                retailer_id,
                gtin,
                condition,
                sale_price,
                product_type,
                category,
                custom_label_0,
            )
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "update_product"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_product(product_id: str) -> str:
        """حذف منتج نهائيًا."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.delete_product(product_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "delete_product"))

    @mcp.tool()
    @concurrency_limit()
    def get_product_feed(feed_id: str) -> str:
        """تفاصيل خلاصة منتجات واحدة (الجدولة، الحالة، الرابط)."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_product_feed(feed_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_product_feed"))

    @mcp.tool()
    @concurrency_limit()
    def get_product_feed_diagnostics(feed_id: str, limit: int = 5) -> str:
        """تشخيص خلاصة منتجات: ملخص أخطاء وتحذيرات آخر رفع + تفاصيل الخلاصة."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_product_feed_diagnostics(feed_id, limit)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_product_feed_diagnostics"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def batch_create_products(catalog_id: str, items_json: str) -> str:
        """
        إنشاء عدة منتجات دفعة واحدة عبر Batch API (يدعم حتى 1000 منتج، مقسم تلقائيًا).
        items_json: مصفوفة JSON من عناصر المنتج، مثال:
        [{"name":"قميص","price":"49.99","currency":"USD","availability":"in stock"}]
        يُقسم تلقائيًا إلى دفعات 500 عنصر (حد Batch API) مع تجميع النتائج.
        """
        try:
            items = _json.loads(items_json)
            if not isinstance(items, list):
                return json_dumps({"error": "items_json يجب أن يكون مصفوفة JSON"})
            if not items:
                return json_dumps({"error": "items_json فارغ"})
            if len(items) > 1000:
                return json_dumps({"error": f"الحد الأقصى 1000 منتج (تلقيت {len(items)})"})
            # Chunked Batch API (Phase 6.2): 500 per batch (Meta limit ~100-500)
            CHUNK = 500
            batches = []
            total = len(items)
            for i in range(0, total, CHUNK):
                chunk = items[i : i + CHUNK]
                result = services.api.post(f"{catalog_id}/items_batch", {"items": _json.dumps(chunk)})
                batches.append(result if isinstance(result, dict) else {"chunk": i // CHUNK + 1, "count": len(chunk)})
            return json_dumps(
                {
                    "success": True,
                    "chunks": len(batches),
                    "count": total,
                    "batches": batches,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "batch_create_products"))

    # ------------------------------------------------------------------
    # خلاصات المنتجات Product Feeds
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_product_feed(
        catalog_id: str,
        name: str,
        url: str = "",
        file_type: str = "XML",
        default_currency: str = "",
        country: str = "",
    ) -> str:
        """
        إنشاء خلاصة (Feed) لكتالوج منتجات.
        file_type: XML | CSV | TSV | GOOGLE_SHEETS. url: رابط الخلاصة.
        """
        try:
            params = {
                "name": name,
                "file_type": file_type,
            }
            if url:
                params["schedule"] = _json.dumps({"interval": "DAILY", "url": url})
            if default_currency:
                params["default_currency"] = default_currency
            if country:
                params["country"] = country
            feed = services.api.post(f"{catalog_id}/productfeeds", params)
            return json_dumps(feed if isinstance(feed, dict) else {})
        except Exception as e:
            return json_dumps(handle_error(e, "create_product_feed"))

    @mcp.tool()
    @concurrency_limit()
    def get_feed_uploads(feed_id: str, limit: int = 25) -> str:
        """حالة رفع الخلاصة الأخيرة (أخطاء/تحديثات/حذف)."""
        try:
            rows = paginate(
                lambda params: services.api.get(f"{feed_id}/uploads", params),
                fields=[
                    "id",
                    "status",
                    "start_time",
                    "end_time",
                    "error_count",
                    "warning_count",
                    "num_deleted_items",
                    "num_updated_items",
                    "num_hidden_items",
                ],
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "get_feed_uploads"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_product_feed(feed_id: str) -> str:
        """حذف خلاصة منتجات."""
        try:
            result = services.api.delete(feed_id)
            return json_dumps(
                {"success": True, "feed_id": feed_id, "result": result if isinstance(result, dict) else {}}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "delete_product_feed"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_product_feed_schedule(feed_id: str, url: str = "", interval: str = "DAILY") -> str:
        """تحديث جدولة خلاصة منتجات (الرابط والفترة). interval: HOURLY | DAILY | WEEKLY"""
        try:
            valid = {"HOURLY", "DAILY", "WEEKLY"}
            interval = interval.upper()
            if interval not in valid:
                return json_dumps({"error": f"interval غير صالح. اختر من: {', '.join(sorted(valid))}"})
            params = {}
            if url:
                params["schedule"] = _json.dumps({"interval": interval, "url": url})
            elif interval:
                # interval-only update needs at least placeholder; fetch existing schedule
                params["schedule"] = _json.dumps({"interval": interval})
            if not params:
                return json_dumps({"error": "حدد url أو interval"})
            result = services.api.post(f"{feed_id}", params)
            return json_dumps(
                {"success": True, "feed_id": feed_id, "result": result if isinstance(result, dict) else {}}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_product_feed_schedule"))

    # ------------------------------------------------------------------
    # التجارة الإلكترونية Commerce / Orders
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def get_commerce_merchant_settings(business_id: str = "") -> str:
        """إعدادات التجارة (المتجر) المرتبطة بنشاط تجاري."""
        try:
            from src.services.catalog_service import CatalogService

            svc = CatalogService(services)
            data = svc.get_commerce_merchant_settings(business_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_commerce_merchant_settings"))

    @mcp.tool()
    @concurrency_limit()
    def list_commerce_orders(commerce_account_id: str = "", limit: int = 25) -> str:
        """قائمة طلبات المتجر (يتطلب Commerce Account ID)."""
        try:
            cid = _require_commerce_account(commerce_account_id)
            if not cid:
                return json_dumps({"error": "حدد FB_COMMERCE_ACCOUNT_ID في .env أو مرّر commerce_account_id"})
            rows = paginate(
                lambda params: services.api.get(f"{cid}/commerce_orders", params),
                fields=[
                    "id",
                    "created",
                    "last_updated",
                    "status",
                    "channel",
                    "buyer_details",
                    "payment_details",
                    "estimated_payment_details",
                ],
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_commerce_orders"))

    @mcp.tool()
    @concurrency_limit()
    def get_commerce_order(order_id: str) -> str:
        """تفاصيل طلب واحد (منتجات، عنوان شحن، حالة)."""
        try:
            info = services.api.get(
                order_id,
                {
                    "fields": [
                        "id",
                        "created",
                        "last_updated",
                        "status",
                        "channel",
                        "buyer_details",
                        "payment_details",
                        "shipping_address",
                        "selected_shipping_option",
                        "order_items",
                    ]
                },
            )
            return json_dumps(info if isinstance(info, dict) else {})
        except Exception as e:
            return json_dumps(handle_error(e, "get_commerce_order"))

    @mcp.tool()
    @concurrency_limit()
    def get_catalog_insights(catalog_id: str, metrics: str = "", date_preset: str = "last_30d") -> str:
        """
        تحليلات الكتالوج (مقاييس الأداء).
        metrics مفصولة بفواصل، مثال: product_catalog_impressions, product_catalog_clicks, product_catalog_checkouts
        """
        try:
            params = {"date_preset": date_preset}
            if metrics:
                params["metrics"] = metrics
            data = services.api.get(f"{catalog_id}/insights", params)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_catalog_insights"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def bulk_update_products(updates_json: str) -> str:
        """
        تعديل عدة منتجات دفعة واحدة.
        updates_json: مصفوفة JSON من التعديلات، مثال:
        [{"product_id":"xxx","price":50.00,"name":"قميص جديد"},{"product_id":"yyy","availability":"out of stock"}]
        """
        try:
            updates = _json.loads(updates_json)
            if not isinstance(updates, list):
                return json_dumps({"error": "updates_json يجب أن يكون مصفوفة"})
            results: list[dict[str, object]] = []
            for item in updates:
                pid = item.pop("product_id", None)
                if not pid:
                    results.append({"error": "product_id مفقود"})
                    continue
                try:
                    params = {}
                    if "name" in item:
                        params["name"] = item["name"]
                    if "price" in item:
                        params["price"] = str(round(float(item["price"]), 2))
                    if "sale_price" in item:
                        params["sale_price"] = str(round(float(item["sale_price"]), 2))
                    if "currency" in item:
                        params["currency"] = item["currency"]
                    if "description" in item:
                        params["description"] = item["description"]
                    if "image_url" in item:
                        params["image_url"] = item["image_url"]
                    if "url" in item:
                        params["url"] = item["url"]
                    if "availability" in item:
                        params["availability"] = item["availability"]
                    if "brand" in item:
                        params["brand"] = item["brand"]
                    if "product_type" in item:
                        params["product_type"] = item["product_type"]
                    if "category" in item:
                        params["category"] = item["category"]
                    if "custom_label_0" in item:
                        params["custom_label_0"] = item["custom_label_0"]
                    if params:
                        services.api.post(f"{pid}", params)
                    results.append({"product_id": pid, "success": True})
                except Exception as ex:
                    results.append({"product_id": pid, "error": str(ex)})
            return json_dumps({"results": results, "total": len(results)})
        except Exception as e:
            return json_dumps(handle_error(e, "bulk_update_products"))

    @mcp.resource("catalog://overview")
    async def catalog_resource() -> str:
        """نظرة عامة على الكتالوجات."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "catalog", "resource": "catalog://overview", "hint": "نظرة عامة على الكتالوجات"}
            )
        except Exception as e:
            from src.utils import handle_error

            return json_dumps(handle_error(e, "catalog://overview"))

    @mcp.prompt()
    def catalog_optimization_prompt(topic: str = "catalog") -> str:
        """تحسين كتالوج."""
        return "ساعد في تحسين كتالوج لـ " + topic + " — حسن كتالوج {catalog_id} (وحدة catalog)"

    @mcp.resource("catalogs://list")
    async def catalogs_list_resource() -> str:
        """قائمة كتالوجات المنتجات."""
        try:

            def _fetch():
                bid = services.config.business_id
                if not bid:
                    return []
                return services.api.get(
                    f"{bid}/owned_product_catalogs",
                    params={"fields": ["id", "name", "product_count"]},
                )

            t0 = time.monotonic()
            data = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            rows = data.get("data", []) if isinstance(data, dict) else []
            logger.info("catalogs://list fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.utils import handle_error

            logger.exception("catalogs://list failed")
            return json_dumps(handle_error(e, "catalogs://list"))

    @mcp.prompt()
    def catalog_product_prompt(product_name: str, price: str = "") -> str:
        """وصف منتج لكتالوج."""
        price_line = f" بسعر {price}" if price else ""
        return (
            f"اكتب وصف منتج مقنع لـ {product_name}{price_line} لكتالوج فيسبوك: "
            "العنوان، الوصف، brand، availability، product_type، custom_label_0. "
            "استخدم create_product."
        )
