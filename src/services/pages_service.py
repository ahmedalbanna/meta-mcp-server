"""Pages service (Phase B)."""

from __future__ import annotations

import time
from typing import Any

from facebook_business.adobjects.page import Page

from src.core.services import Services
from src.helpers import get_page_api, to_dict


class PagesService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _page(self, node_id: str = "") -> Page:
        return Page(node_id or self.config.page_id, api=get_page_api())

    def get_page_info(self, page_id: str = "") -> Any:
        info = self._page(page_id).api_get(fields=[
            Page.Field.name, Page.Field.fan_count, Page.Field.link, Page.Field.category,
        ])
        return to_dict(info)

    def list_posts(self, page_id: str = "", limit: int = 25) -> Any:
        posts = self._page(page_id).get_posts(params={
            "fields": ["message", "created_time", "permalink_url", "shares", "id"],
            "limit": limit,
        })
        return [to_dict(p) for p in posts]

    def get_page_insights(self, page_id: str = "", period: str = "day", days: int = 7,
                          metrics: str = "page_views_total,page_post_engagements,page_actions_post_reactions_total") -> Any:
        since = int(time.time()) - days * 86400
        results = self._page(page_id).get_insights(params={
            "metric": [m.strip() for m in metrics.split(",") if m.strip()],
            "period": period,
            "since": since,
        })
        return [to_dict(i) for i in results]

    def get_page_cta(self, page_id: str = "") -> Any:
        return self.api.page_get((page_id or self.config.page_id) + "/call_to_actions", {})

    def update_page_cover(self, photo_id: str, page_id: str = "") -> Any:
        return self.api.page_post(page_id or self.config.page_id, {"cover": photo_id})

    def publish_post(self, message: str, page_id: str = "") -> Any:
        post = self._page(page_id).create_feed(params={"message": message})
        return to_dict(post)

    def publish_photo(self, image_url: str, message: str = "", page_id: str = "") -> Any:
        params: dict[str, Any] = {"url": image_url}
        if message:
            params["caption"] = message
        photo = self._page(page_id).create_photo(params=params)
        return to_dict(photo)

    def host_local_image(self, file_path: str) -> str:
        try:
            from src.media_hosting import host_image
            return host_image(file_path)
        except Exception:
            from pathlib import Path

            import requests  # type: ignore[import-untyped]
            p = Path(file_path)
            if not p.exists():
                raise FileNotFoundError(f"الملف غير موجود: {file_path}") from None
            with open(p, "rb") as f:
                r = requests.post("https://uguu.se/upload.php", files={"files[]": f}, timeout=60)
                r.raise_for_status()
                data = r.json()
                if not data.get("success") or not data.get("files"):
                    raise RuntimeError(f"فشل الرفع: {data}") from None
                url = data["files"][0]["url"]
                return url.replace("http://", "https://")  # type: ignore[no-any-return]

    def publish_album(self, image_urls: str, message: str = "", page_id: str = "",
                      product_ids: str = "") -> dict[str, Any]:
        import time
        pid = page_id or self.config.page_id
        if not pid:
            raise ValueError("PAGE_ID غير مضبوط في .env")
        urls = [u.strip() for u in image_urls.split(",") if u.strip()]
        if len(urls) < 2:
            raise ValueError("الألبوم يتطلب 2-10 صور. لصورة واحدة استخدم publish_page_photo")
        if len(urls) > 10:
            raise ValueError(f"الحد الأقصى 10 صور للألبوم (أرسلت {len(urls)})")
        photo_ids = []
        for url in urls:
            if url.startswith("media/") or url.startswith("/") or (
                url.endswith((".jpg", ".jpeg", ".png", ".webp")) and not url.startswith("http")
            ):
                try:
                    url = self.host_local_image(url)
                except Exception as e:
                    raise ValueError(f"فشل رفع الصورة المحلية {url}: {e}") from None
            photo = self._page(pid).create_photo(params={"url": url, "published": False})
            d = to_dict(photo)
            pid_photo = d.get("id")
            if not pid_photo:
                raise ValueError(f"فشل رفع الصورة {url}")
            photo_ids.append(pid_photo)
            time.sleep(0.5)
        attached = [{"media_fbid": p} for p in photo_ids]
        post = self._page(pid).create_feed(params={"message": message, "attached_media": attached})
        res = to_dict(post)
        pids = [p.strip() for p in (product_ids or "").split(",") if p.strip()]
        if pids and res.get("id"):
            try:
                from facebook_business.adobjects.post import Post
                from facebook_business.adobjects.productitem import ProductItem

                from src.helpers import get_page_api as _gpa
                links = []
                for pid_prod in pids[:3]:
                    try:
                        prod = ProductItem(pid_prod).api_get(fields=["id", "name", "url"])
                        dd = to_dict(prod)
                        name = dd.get("name", pid_prod)
                        url = dd.get("url", "")
                        links.append(f"{name}: {url}" if url else name)
                    except Exception:
                        links.append(pid_prod)
                if links:
                    comment = "🛍️ المنتجات الموسومة:\n" + "\n".join(links)
                    Post(res.get("id"), api=_gpa()).create_comment(params={"message": comment})
            except Exception:
                pass
        return {"success": True, "post_id": res.get("id"),
                "permalink": f"https://www.facebook.com/{res.get('id', '')}",
                "photo_ids": photo_ids, "product_ids": pids, "result": res}

    def update_post_caption(self, post_id: str, message: str) -> dict[str, Any]:
        from facebook_business.adobjects.post import Post
        post = Post(post_id, api=get_page_api())
        data = post.api_update(params={"message": message})
        return {"id": post_id, "updated": True, "result": to_dict(data)}

    def delete_post(self, post_id: str) -> dict[str, Any]:
        from facebook_business.adobjects.post import Post
        result = Post(post_id, api=get_page_api()).api_delete()
        return {"id": post_id, "deleted": True, "result": result if isinstance(result, dict) else {}}

    def get_post_insights(self, post_id: str, metrics: str = "post_media_view,post_engaged_users,post_reactions_by_type_total,post_comments,post_shares,post_saves") -> Any:
        from facebook_business.adobjects.post import Post
        insights = Post(post_id, api=get_page_api()).get_insights(params={"metric": metrics})
        return [to_dict(i) for i in insights]

    def list_albums(self, page_id: str = "", limit: int = 25) -> Any:
        pid = page_id or self.config.page_id
        return self.api.page_get(f"{pid}/albums", {"fields": "id,name,photo_count,created_time", "limit": limit})

    def get_album_photos(self, album_id: str, limit: int = 25) -> Any:
        return self.api.page_get(f"{album_id}/photos", {"fields": "id,name,source,created_time", "limit": limit})

    def list_events(self, page_id: str = "", limit: int = 25) -> Any:
        pid = page_id or self.config.page_id
        return self.api.page_get(f"{pid}/events", {"fields": "id,name,start_time,end_time,place,description", "limit": limit})

    def list_ratings(self, page_id: str = "", limit: int = 25) -> Any:
        pid = page_id or self.config.page_id
        return self.api.page_get(f"{pid}/ratings", {"fields": "reviewer,rating,review_text,created_time", "limit": limit})

    def update_page_cta(self, cta_type: str, cta_link: str, page_id: str = "") -> dict[str, Any]:
        pid = page_id or self.config.page_id
        result = self.api.page_post(f"{pid}/call_to_actions", {"type": cta_type, "link": cta_link})
        return {"page_id": pid, "cta_type": cta_type, "result": result if isinstance(result, dict) else {}}
