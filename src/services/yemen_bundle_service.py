"""Yemen bundle service (Phase B)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.core.services import Services
from src.utils import handle_error, to_dict


class YemenBundleService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def get_status(self, catalog_id: str = "", limit: int = 5) -> dict[str, Any]:
        out: dict[str, Any] = {}
        bid = self.config.business_id
        if bid:
            try:
                data = self.api.get(f"{bid}/owned_product_catalogs", {"fields": "id,name,product_count"})
                cats = data.get("data", []) if isinstance(data, dict) else []
                out["catalogs"] = [to_dict(c) for c in cats]
                if cats and not catalog_id:
                    cid = cats[0]["id"] if isinstance(cats[0], dict) else to_dict(cats[0])["id"]
                else:
                    cid = catalog_id
                if cid:
                    prods_data = self.api.get(f"{cid}/products", {"fields": "id,name,price,currency"})
                    prods = prods_data.get("data", []) if isinstance(prods_data, dict) else []
                    out["recent_products"] = [to_dict(p) for p in prods[:limit]]
            except Exception as e:
                out["catalog_error"] = str(e)
        ig_id = self.config.instagram_business_id
        if ig_id:
            try:
                out["instagram_recent"] = self.api.get(
                    f"{ig_id}/media",
                    {"fields": "id,media_type,permalink,timestamp,caption", "limit": limit},
                )
            except Exception as e:
                out["instagram_error"] = str(e)
        try:
            pid = self.config.page_id
            data = self.api.page_get(
                f"{pid}/posts",
                {"fields": "id,message,permalink_url,created_time", "limit": limit},
            )
            posts = data.get("data", []) if isinstance(data, dict) else []
            out["facebook_recent"] = [to_dict(p) for p in posts]
        except Exception as e:
            out["facebook_error"] = str(e)
        return out

    def _host_local(self, path: Path) -> str:
        try:
            from src.media_hosting import host_image

            return host_image(path)
        except Exception:
            import requests  # type: ignore[import-untyped]

            with open(path, "rb") as f:
                r = requests.post("https://uguu.se/upload.php", files={"files[]": f}, timeout=60)
                r.raise_for_status()
                data = r.json()
                if not data.get("success"):
                    raise RuntimeError(f"host fail: {data}") from None
                return str(data["files"][0]["url"]).replace("http://", "https://")

    def _collect_media(self, media_dir: str = "media", limit: int = 10):
        base = Path(__file__).resolve().parent.parent.parent / media_dir
        # adjust: service is in src/services, media is at project root/media
        if not base.exists():
            # try relative to project root
            base = Path(media_dir)
        if not base.exists():
            raise FileNotFoundError(f"المجلد غير موجود: {base}")
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        files = sorted([p for p in base.iterdir() if p.suffix.lower() in exts])
        if not files:
            raise FileNotFoundError(f"لا توجد صور في {base}")
        return files[:limit]

    def publish(
        self,
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
    ) -> dict[str, Any]:
        import json as _json

        pid = page_id or self.config.page_id
        ig_id = instagram_business_id or self.config.instagram_business_id

        files = self._collect_media(media_dir, 10)
        if len(files) < 2:
            return {"error": f"وجد {len(files)} صور فقط — يلزم 2-10"}

        hosted = []
        for f in files:
            hosted.append(self._host_local(f))

        captions = {
            "luxury": f"""الأناقة لا تكتمل إلا بالتفاصيل... تألقي بلمسة من السحر والرخاء! ✨

لكِ ولِكل مَن تدرك قيمة الفخامة، نقدم لكِ تشكيلة راقية مستوحاة من أحدث أطقم ديور و كارتير. أطقم متكاملة بتصاميم ساحرة، مطلية بذهب صيني عالي الجودة ليمنحكِ بريقاً لا يذبل.

⏳ عرض خاص ومحدود:
💰 السعر: {int(price)} {currency} فقط
⚡ التسليم: فوري حتى باب بيتك!
⏱️ المدة: العرض سارٍ لمدة {offer_days} أيام فقط أو حتى نفاذ الكمية.
🛍️ اطلبي الآن عبر DM

{description}

#أناقة #فخامة #ديور #كارتير #ذهب_صيني #تسليم_فوري #موضة_واناقة""",
            "interactive": f"""3 أيام فقط تفصلكِ عن إطلالة ملكية! 👑✨
أجمل تشكيلات Dior & Cartier بطلاء الذهب الصيني الفاخر!

🌟 لماذا ستعشقينها؟
✔️ تصميم عصري وفخم
✔️ جودة عالية ولمعة ساحرة
✔️ تسليم فوري دون انتظار!

💎 السعر: {int(price)} {currency} فقط (لمدة {offer_days} أيام)!
📥 علّقي بـ "تم" أو راسلينا للحجز

{description}
#عروض_خاصة #ديور_وكارتير #تسوق_اونلاين""",
            "direct": f"""فرصة لا تُفوّت لبيت الأناقة! 💎
تشكلات ديور وكارتير (مطلي ذهب صيني) — {int(price)} {currency}
التوصيل: تسليم فوري | العرض: {offer_days} أيام فقط!
📲 راسلينا الآن

{description}
#ديور #كارتير #تسليم_فوري""",
        }
        caption = captions.get(caption_style, captions["luxury"])

        results: dict[str, Any] = {
            "media_files": [str(f) for f in files],
            "hosted_urls": hosted,
            "caption_style": caption_style,
        }

        # Catalog product
        cid = catalog_id
        if not cid:
            bid = self.config.business_id
            if bid:
                data = self.api.get(f"{bid}/owned_product_catalogs", {"fields": "id"})
                cats = data.get("data", []) if isinstance(data, dict) else []
                if cats:
                    cid = cats[0]["id"] if isinstance(cats[0], dict) else to_dict(cats[0])["id"]
        catalog_result = None
        if cid:
            try:
                retailer = f"BUT-YEMEN-{int(time.time())}"
                params: dict[str, Any] = {
                    "name": name,
                    "price": str(int(price)),
                    "currency": currency,
                    "description": description + f" | عرض {offer_days} أيام - تسليم فوري - اليمن",
                    "image_url": hosted[0],
                    "availability": "in stock",
                    "brand": "Dior Cartier",
                    "retailer_id": retailer,
                    "condition": "new",
                    "product_type": "accessories",
                    "custom_label_0": f"Yemen-{offer_days}days",
                }
                prod_data = self.api.post(f"{cid}/products", params)
                catalog_result = to_dict(prod_data)
                results["catalog"] = {"catalog_id": cid, "product": catalog_result}
            except Exception as e:
                results["catalog"] = {"error": str(e), "context": "create_product"}

        # Facebook album
        fb_result = None
        try:
            photo_ids = []
            for url in hosted:
                photo_data = self.api.page_post(f"{pid}/photos", {"url": url, "published": False})
                d = to_dict(photo_data)
                photo_ids.append(d.get("id"))
                time.sleep(0.4)
            attached = [{"media_fbid": x} for x in photo_ids]
            post_data = self.api.page_post(f"{pid}/feed", {"message": caption, "attached_media": attached})
            fb_dict = to_dict(post_data)
            fb_result = {
                "post_id": fb_dict.get("id"),
                "photo_ids": photo_ids,
                "result": fb_dict,
                "permalink": f"https://www.facebook.com/{fb_dict.get('id', '')}",
            }
            results["facebook_album"] = fb_result
        except Exception as e:
            results["facebook_album"] = handle_error(e, "publish_yemen_product_bundle:facebook")

        # Instagram carousel
        ig_result = None
        try:
            _pids = [p.strip() for p in (product_ids or "").split(",") if p.strip()]
            if not _pids and tag_products and catalog_result and catalog_result.get("id"):
                _pids = [str(catalog_result.get("id"))]
            child_ids = []
            for idx, url in enumerate(hosted):
                params = {"image_url": url, "is_carousel_item": "true"}
                if _pids and tag_products:
                    if len(_pids) == 1:
                        tags = [{"product_id": _pids[0], "x": 0.5, "y": 0.5}]
                    else:
                        tags = [{"product_id": _pids[idx % len(_pids)], "x": 0.5, "y": 0.5}]
                    params["product_tags"] = _json.dumps(tags)
                child = self.api.post(f"{ig_id}/media", params)
                cid_child = child.get("id")
                if not cid_child:
                    raise RuntimeError(f"IG child fail: {child}")
                child_ids.append(cid_child)
                time.sleep(0.4)
            container = self.api.post(
                f"{ig_id}/media",
                {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption},
            )
            creation_id = container.get("id")
            if not creation_id:
                raise RuntimeError(f"IG container fail: {container}")
            time.sleep(2)
            pub = self.api.post(f"{ig_id}/media_publish", {"creation_id": creation_id})
            ig_result = {
                "children": child_ids,
                "container": container,
                "publish": pub,
                "permalink": pub.get("id"),
            }
            try:
                info = self.api.get(f"{pub.get('id')}", {"fields": "permalink,caption"})
                ig_result["permalink_url"] = info.get("permalink")
            except Exception:
                pass
            results["instagram_carousel"] = ig_result
        except Exception as e:
            results["instagram_carousel"] = handle_error(e, "publish_yemen_product_bundle:instagram")

        results["success"] = True
        return results
