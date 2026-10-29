"""Yemen publishing bundle — one-click product to Catalog + FB Album + IG Carousel.

يلبي متطلبات Butterfly-ye: صور محلية في media/, سعر YER, عرض 3 أيام, تسليم فوري, ديور/كارتير.
"""

from src.helpers import handle_error, json_dumps, write_guard
from src.throttle import concurrency_limit


def register(mcp, services=None):
    """Register Yemen bundle tools."""

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_yemen_product_bundle(
        name: str = "تشكيلات ديور و كارتير",
        description: str = "تشميلات ديور و كارتير - مطلي ذهب صيني - تسليم فوري",
        price: float = 2500.0,
        currency: str = "YER",
        media_dir: str = "media",
        catalog_id: str = "",
        page_id: str = "",
        instagram_business_id: str = "",
        offer_days: int = 3,
        caption_style: str = "luxury",
        product_ids: str = "",
        tag_products: bool = True,
    ) -> str:
        """نشر منتج يمني (حزمة كاملة)."""
        try:
            from src.core.services import Services
            from src.services.yemen_bundle_service import YemenBundleService

            svc = YemenBundleService(services) if services is not None else YemenBundleService(Services.default())
            out = svc.publish(
                name,
                description,
                price,
                currency,
                media_dir,
                catalog_id,
                page_id,
                instagram_business_id,
                offer_days,
                caption_style,
                product_ids,
                tag_products,
            )
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "publish_yemen_product_bundle"))

    @mcp.tool()
    @concurrency_limit()
    def get_yemen_bundle_status(catalog_id: str = "", limit: int = 5) -> str:
        """حالة حزمة اليمن — آخر منتجات + آخر منشورات FB/IG للتحقق السريع."""
        try:
            from src.core.services import Services
            from src.services.yemen_bundle_service import YemenBundleService

            svc = YemenBundleService(services) if services is not None else YemenBundleService(Services.default())
            out = svc.get_status(catalog_id, limit)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "get_yemen_bundle_status"))

    @mcp.resource("yemen://overview")
    async def yemen_resource() -> str:
        return json_dumps(
            {
                "module": "yemen_bundle",
                "hint": "حزمة اليمن: catalog + FB album + IG carousel",
                "media_dir": "media",
                "currency": "YER",
            }
        )

    @mcp.prompt()
    def yemen_publish_prompt(product: str = "تشكيلات ديور و كارتير") -> str:
        return f"ساعد في نشر منتج يمني {product} — استخدم publish_yemen_product_bundle مع media_dir='media' وسعر YER وعرض 3 أيام"
