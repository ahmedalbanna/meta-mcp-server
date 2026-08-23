import asyncio
import logging
import time

from src.config import BUSINESS_ID, COMMERCE_ACCOUNT_ID

logger = logging.getLogger(__name__)


def register(mcp):
    """Register catalog & commerce tools."""

    import json as _json

    from facebook_business.adobjects.business import Business
    from facebook_business.adobjects.commercemerchantsettings import CommerceMerchantSettings
    from facebook_business.adobjects.commerceorder import CommerceOrder
    from facebook_business.adobjects.productcatalog import ProductCatalog
    from facebook_business.adobjects.productfeed import ProductFeed
    from facebook_business.adobjects.productitem import ProductItem
    from facebook_business.adobjects.productset import ProductSet

    from src.helpers import api_call, handle_error, json_dumps, to_dict, write_guard
    from src.throttle import concurrency_limit
    from src.utils import paginate

    CATALOG_FIELDS = [
        ProductCatalog.Field.id,
        ProductCatalog.Field.name,
        ProductCatalog.Field.product_count,
        ProductCatalog.Field.feed_count,
        ProductCatalog.Field.business,
        ProductCatalog.Field.is_local_catalog,
        ProductCatalog.Field.default_image_url,
        ProductCatalog.Field.fallback_image_url,
    ]
    SET_FIELDS = [
        ProductSet.Field.id,
        ProductSet.Field.name,
        ProductSet.Field.filter,
        ProductSet.Field.product_count,
    ]
    PRODUCT_FIELDS = [
        ProductItem.Field.id,
        ProductItem.Field.retailer_id,
        ProductItem.Field.name,
        ProductItem.Field.description,
        ProductItem.Field.brand,
        ProductItem.Field.price,
        ProductItem.Field.currency,
        ProductItem.Field.availability,
        ProductItem.Field.image_url,
        "images",
        ProductItem.Field.url,
        ProductItem.Field.status,
        ProductItem.Field.product_catalog,
    ]

    def _require_business_id(business_id: str) -> str:
        return business_id or BUSINESS_ID

    def _require_commerce_account(commerce_account_id: str) -> str:
        return commerce_account_id or COMMERCE_ACCOUNT_ID

    # ------------------------------------------------------------------
    # الكتالوجات Catalogs
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_catalogs(business_id: str = "", limit: int = 25) -> str:
        """قائمة كتالوجات المنتجات التابعة لنشاط تجاري."""
        try:
            bid = _require_business_id(business_id)
            if not bid:
                return json_dumps({"error": "حدد FB_BUSINESS_ID في .env أو مرّر business_id"})
            rows = paginate(
                lambda params: Business(bid).get_owned_product_catalogs(params=params),
                fields=CATALOG_FIELDS,
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_catalogs"))

    @mcp.tool()
    @concurrency_limit()
    def get_catalog(catalog_id: str) -> str:
        """تفاصيل كتالوج واحد."""
        try:
            info = ProductCatalog(catalog_id).api_get(fields=CATALOG_FIELDS)
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_catalog"))

    @mcp.tool()
    @concurrency_limit()
    def get_catalog_settings(catalog_id: str) -> str:
        """إعدادات الكتالوج (الصور الافتراضية، المتجر، الفئات...)."""
        try:
            info = ProductCatalog(catalog_id).api_get(
                fields=[
                    ProductCatalog.Field.store_catalog_settings,
                    ProductCatalog.Field.default_image_url,
                    ProductCatalog.Field.fallback_image_url,
                    ProductCatalog.Field.da_display_settings,
                    ProductCatalog.Field.catalog_store,
                    ProductCatalog.Field.feed_count,
                    ProductCatalog.Field.product_count,
                    ProductCatalog.Field.is_catalog_segment,
                    ProductCatalog.Field.is_local_catalog,
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_catalog_settings"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_catalog(name: str, business_id: str = "") -> str:
        """إنشاء كتالوج منتجات جديد."""
        try:
            bid = _require_business_id(business_id)
            if not bid:
                return json_dumps({"error": "حدد FB_BUSINESS_ID في .env أو مرّر business_id"})
            catalog = Business(bid).create_owned_product_catalog(params={ProductCatalog.Field.name: name})
            return json_dumps(to_dict(catalog))
        except Exception as e:
            return json_dumps(handle_error(e, "create_catalog"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_catalog(catalog_id: str) -> str:
        """حذف كتالوج نهائيًا."""
        try:
            result = ProductCatalog(catalog_id).api_delete()
            return json_dumps({"success": True, "catalog_id": catalog_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_catalog"))

    # ------------------------------------------------------------------
    # مجموعات المنتجات Product Sets
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_product_sets(catalog_id: str, limit: int = 25) -> str:
        """قائمة مجموعات المنتجات داخل كتالوج."""
        try:
            rows = paginate(
                lambda params: ProductCatalog(catalog_id).get_product_sets(params=params),
                fields=SET_FIELDS,
                limit=limit,
            )
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_product_sets"))

    @mcp.tool()
    @concurrency_limit()
    def get_product_set(product_set_id: str) -> str:
        """تفاصيل مجموعة منتجات (تتضمن فلتر الاختيار)."""
        try:
            info = ProductSet(product_set_id).api_get(fields=SET_FIELDS)
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_product_set"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_product_set(catalog_id: str, name: str, filters_json: str = "") -> str:
        """
        إنشاء مجموعة منتجات في كتالوج.
        filters_json: فلتر JSON اختياري، مثال:
        [{"product_type": {"i_contains": "ملابس"}}] أو {"price": {"less_than": 100}}
        """
        try:
            params = {ProductSet.Field.name: name}
            if filters_json:
                params[ProductSet.Field.filter] = filters_json
            product_set = ProductCatalog(catalog_id).create_product_set(params=params)
            return json_dumps(to_dict(product_set))
        except Exception as e:
            return json_dumps(handle_error(e, "create_product_set"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_product_set(product_set_id: str) -> str:
        """حذف مجموعة منتجات."""
        try:
            result = ProductSet(product_set_id).api_delete()
            return json_dumps({"success": True, "product_set_id": product_set_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_product_set"))

    # ------------------------------------------------------------------
    # المنتجات Products
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def list_products(catalog_id: str, limit: int = 25, filter: str = "") -> str:
        """قائمة المنتجات في كتالوج (يمكن إضافة فلتر JSON)."""
        try:

            def getter(params):
                if filter:
                    params["filter"] = filter
                return ProductCatalog(catalog_id).get_products(params=params)

            rows = paginate(getter, fields=PRODUCT_FIELDS, limit=limit)
            return json_dumps(rows)
        except Exception as e:
            return json_dumps(handle_error(e, "list_products"))

    @mcp.tool()
    @concurrency_limit()
    def get_product(product_id: str) -> str:
        """تفاصيل منتج واحد."""
        try:
            info = ProductItem(product_id).api_get(fields=PRODUCT_FIELDS)
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_product"))

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
        """إنشاء منتج داخل كتالوج.

        price / sale_price بالعملة العادية (مثال 19.99). availability: in stock | out of stock.
        """
        try:
            params = {
                ProductItem.Field.name: name,
                ProductItem.Field.price: str(round(price, 2)) if price else "0",
                ProductItem.Field.currency: currency,
            }
            optional = {
                ProductItem.Field.description: description,
                ProductItem.Field.image_url: image_url,
                ProductItem.Field.url: url,
                ProductItem.Field.availability: availability,
                ProductItem.Field.brand: brand,
                ProductItem.Field.retailer_id: retailer_id,
                ProductItem.Field.gtin: gtin,
                ProductItem.Field.condition: condition,
                ProductItem.Field.product_type: product_type,
                ProductItem.Field.category: category,
                ProductItem.Field.custom_label_0: custom_label_0,
            }
            if sale_price:
                optional[ProductItem.Field.sale_price] = str(sale_price)
            params.update({k: v for k, v in optional.items() if v})
            product = ProductCatalog(catalog_id).create_product(params=params)
            return json_dumps(to_dict(product))
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
        """تعديل بيانات منتج. الحقول المُرسلة فقط تُحدّث. لمسح حقل أرسله كـ فارغ ("")."""
        try:
            params = {}
            _str_fields = [
                (name, ProductItem.Field.name),
                (currency, ProductItem.Field.currency),
                (description, ProductItem.Field.description),
                (image_url, ProductItem.Field.image_url),
                (url, ProductItem.Field.url),
                (availability, ProductItem.Field.availability),
                (brand, ProductItem.Field.brand),
                (retailer_id, ProductItem.Field.retailer_id),
                (gtin, ProductItem.Field.gtin),
                (condition, ProductItem.Field.condition),
                (product_type, ProductItem.Field.product_type),
                (category, ProductItem.Field.category),
                (custom_label_0, ProductItem.Field.custom_label_0),
            ]
            for val, field in _str_fields:
                if val:
                    params[field] = val
            if price:
                params[ProductItem.Field.price] = str(round(price, 2))
            if sale_price:
                params[ProductItem.Field.sale_price] = str(round(sale_price, 2))
            if not params:
                return json_dumps({"error": "حدد حقلًا واحدًا على الأقل للتعديل"})
            result = ProductItem(product_id).api_update(params=params)
            return json_dumps({"success": True, "product_id": product_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "update_product"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_product(product_id: str) -> str:
        """حذف منتج من الكتالوج."""
        try:
            result = ProductItem(product_id).api_delete()
            return json_dumps({"success": True, "product_id": product_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_product"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def batch_create_products(catalog_id: str, items_json: str) -> str:
        """
        إنشاء عدة منتجات دفعة واحدة عبر Batch API.
        items_json: مصفوفة JSON من عناصر المنتج، مثال:
        [{"name":"قميص","price":"49.99","currency":"USD","availability":"in stock"}]
        """
        try:
            items = _json.loads(items_json)
            if not isinstance(items, list):
                return json_dumps({"error": "items_json يجب أن يكون مصفوفة JSON"})
            result = ProductCatalog(catalog_id).create_items_batch(params={"items": _json.dumps(items)})
            return json_dumps({"success": True, "batch": to_dict(result), "count": len(items)})
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
                ProductFeed.Field.name: name,
                ProductFeed.Field.file_type: file_type,
            }
            if url:
                params[ProductFeed.Field.schedule] = json_dumps({"interval": "DAILY", "url": url})
            if default_currency:
                params[ProductFeed.Field.default_currency] = default_currency
            if country:
                params[ProductFeed.Field.country] = country
            feed = ProductCatalog(catalog_id).create_product_feed(params=params)
            return json_dumps(to_dict(feed))
        except Exception as e:
            return json_dumps(handle_error(e, "create_product_feed"))

    @mcp.tool()
    @concurrency_limit()
    def get_feed_uploads(feed_id: str, limit: int = 25) -> str:
        """حالة رفع الخلاصة الأخيرة (أخطاء/تحديثات/حذف)."""
        try:
            rows = paginate(
                lambda params: ProductFeed(feed_id).get_uploads(params=params),
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
            result = ProductFeed(feed_id).api_delete()
            return json_dumps({"success": True, "feed_id": feed_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_product_feed"))

    @mcp.tool()
    @concurrency_limit()
    def get_product_feed(feed_id: str) -> str:
        """تفاصيل خلاصة منتجات واحدة (الجدولة، الحالة، الرابط)."""
        try:
            info = ProductFeed(feed_id).api_get(
                fields=[
                    "id",
                    "name",
                    "schedule",
                    "latest_upload",
                    "filter",
                    "country",
                    "default_currency",
                    "file_type",
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_product_feed"))

    @mcp.tool()
    @concurrency_limit()
    def get_product_feed_diagnostics(feed_id: str, limit: int = 5) -> str:
        """تشخيص خلاصة منتجات: ملخص أخطاء وتحذيرات آخر رفع + تفاصيل الخلاصة."""
        try:
            feed_info = ProductFeed(feed_id).api_get(fields=["id", "name", "schedule", "latest_upload", "file_type"])
            feed_dict = to_dict(feed_info)
            uploads = paginate(
                lambda params: ProductFeed(feed_id).get_uploads(params=params),
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
                    "error_report",
                ],
                limit=limit,
            )
            total_errors = sum(int(u.get("error_count") or 0) for u in uploads)
            total_warnings = sum(int(u.get("warning_count") or 0) for u in uploads)
            return json_dumps(
                {
                    "feed": feed_dict,
                    "uploads": uploads,
                    "summary": {
                        "total_errors": total_errors,
                        "total_warnings": total_warnings,
                        "last_status": uploads[0].get("status") if uploads else "unknown",
                    },
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "get_product_feed_diagnostics"))

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
                params[ProductFeed.Field.schedule] = json_dumps({"interval": interval, "url": url})
            elif interval:
                # interval-only update needs at least placeholder; fetch existing schedule
                params[ProductFeed.Field.schedule] = json_dumps({"interval": interval})
            if not params:
                return json_dumps({"error": "حدد url أو interval"})
            result = ProductFeed(feed_id).api_update(params=params)
            return json_dumps({"success": True, "feed_id": feed_id, "result": to_dict(result)})
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
            bid = _require_business_id(business_id)
            if not bid:
                return json_dumps({"error": "حدد FB_BUSINESS_ID في .env أو مرّر business_id"})
            rows = paginate(
                lambda params: Business(bid).get_commerce_merchant_settings(params=params),
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
            return json_dumps(rows)
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
                lambda params: CommerceMerchantSettings(cid).get_commerce_orders(params=params),
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
            info = CommerceOrder(order_id).api_get(
                fields=[
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
            )
            return json_dumps(to_dict(info))
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
            data = api_call("GET", f"{catalog_id}/insights", params)
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
                    product = ProductItem(pid)
                    params = {}
                    if "name" in item:
                        params[ProductItem.Field.name] = item["name"]
                    if "price" in item:
                        params[ProductItem.Field.price] = str(round(float(item["price"]), 2))
                    if "sale_price" in item:
                        params[ProductItem.Field.sale_price] = str(round(float(item["sale_price"]), 2))
                    if "currency" in item:
                        params[ProductItem.Field.currency] = item["currency"]
                    if "description" in item:
                        params[ProductItem.Field.description] = item["description"]
                    if "image_url" in item:
                        params[ProductItem.Field.image_url] = item["image_url"]
                    if "url" in item:
                        params[ProductItem.Field.url] = item["url"]
                    if "availability" in item:
                        params[ProductItem.Field.availability] = item["availability"]
                    if "brand" in item:
                        params[ProductItem.Field.brand] = item["brand"]
                    if "product_type" in item:
                        params[ProductItem.Field.product_type] = item["product_type"]
                    if "category" in item:
                        params[ProductItem.Field.category] = item["category"]
                    if "custom_label_0" in item:
                        params[ProductItem.Field.custom_label_0] = item["custom_label_0"]
                    if params:
                        product.api_update(params=params)
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
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "catalog://overview"))

    @mcp.prompt()
    def catalog_optimization_prompt(topic: str = "catalog") -> str:
        """تحسين كتالوج."""
        return "ساعد في تحسين كتالوج لـ " + topic + " — حسن كتالوج {catalog_id} (وحدة catalog)"

    @mcp.resource("catalogs://list")
    async def catalogs_list_resource() -> str:
        """قائمة كتالوجات المنتجات."""
        try:
            from facebook_business.adobjects.business import Business

            from src.config import BUSINESS_ID

            def _fetch():
                bid = BUSINESS_ID
                if not bid:
                    return []
                return Business(bid).get_owned_product_catalogs(params={"fields": ["id", "name", "product_count"]})

            t0 = time.monotonic()
            rows = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("catalogs://list fetched in %.2fs", elapsed)
            return json_dumps([to_dict(c) for c in rows])
        except Exception as e:
            from src.helpers import handle_error

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
