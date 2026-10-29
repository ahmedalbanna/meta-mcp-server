"""Yemen bundle service (Phase B)."""

from __future__ import annotations

from typing import Any

from facebook_business.adobjects.page import Page

from src.config import BUSINESS_ID, INSTAGRAM_BUSINESS_ID, PAGE_ID
from src.core.services import Services
from src.helpers import get_page_api, to_dict


class YemenBundleService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def get_status(self, catalog_id: str = "", limit: int = 5) -> dict[str, Any]:
        out: dict[str, Any] = {}
        bid = BUSINESS_ID
        if bid:
            try:
                from facebook_business.adobjects.business import Business
                cats = list(Business(bid).get_owned_product_catalogs(params={"fields": ["id", "name", "product_count"]}))
                out["catalogs"] = [to_dict(c) for c in cats]
                if cats and not catalog_id:
                    cid = cats[0]["id"] if isinstance(cats[0], dict) else to_dict(cats[0])["id"]
                else:
                    cid = catalog_id
                if cid:
                    from facebook_business.adobjects.productcatalog import ProductCatalog
                    prods = list(ProductCatalog(cid).get_products(params={"fields": ["id", "name", "price", "currency"]}))
                    out["recent_products"] = [to_dict(p) for p in prods[:limit]]
            except Exception as e:
                out["catalog_error"] = str(e)
        ig_id = INSTAGRAM_BUSINESS_ID
        if ig_id:
            try:
                out["instagram_recent"] = self.api.get(f"{ig_id}/media", {"fields": "id,media_type,permalink,timestamp,caption", "limit": limit})
            except Exception as e:
                out["instagram_error"] = str(e)
        try:
            page = Page(PAGE_ID, api=get_page_api())
            posts = page.get_posts(params={"fields": ["id", "message", "permalink_url", "created_time"], "limit": limit})
            out["facebook_recent"] = [to_dict(p) for p in posts]
        except Exception as e:
            out["facebook_error"] = str(e)
        return out
