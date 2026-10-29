"""Instagram service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services


class InstagramService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def get_account(self, instagram_business_id: str = "") -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get(ig_id, {"fields": "id,username,media_count,followers_count,biography,profile_picture_url"})

    def list_media(self, instagram_business_id: str = "", limit: int = 25) -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get(f"{ig_id}/media", {
            "fields": "id,caption,media_type,media_url,permalink,timestamp",
            "limit": limit,
        })

    def get_media(self, media_id: str) -> Any:
        return self.api.get(media_id, {"fields": "id,caption,media_type,media_url,permalink,timestamp,username"})

    def search_hashtag(self, hashtag: str, instagram_business_id: str = "") -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get("ig_hashtag_search", {"user_id": ig_id, "q": hashtag})

    def get_hashtag_media(self, hashtag_id: str, media_type: str = "recent", limit: int = 25,
                          instagram_business_id: str = "") -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get(f"{hashtag_id}/{media_type}_media", {
            "user_id": ig_id,
            "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
            "limit": limit,
        })

    def get_mentions(self, instagram_business_id: str = "", limit: int = 25) -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get(f"{ig_id}/tags", {
            "fields": "id,media_type,media_url,permalink,timestamp,caption,like_count,comments_count",
            "limit": limit,
        })

    def get_media_children(self, media_id: str) -> Any:
        return self.api.get(f"{media_id}/children", {"fields": "id,media_type,media_url,permalink"})

    def get_media_insights(self, media_id: str, metric: str = "reach,likes,comments,saved,total_interactions,shares") -> Any:
        data = self.api.get(f"{media_id}/insights", {"metric": metric})
        out = []
        for i in data.get("data", []) if isinstance(data, dict) else []:
            out.append({"name": i.get("name"), "values": i.get("values")})
        return out or {"message": "لا توجد بيانات"}

    def get_account_insights(self, instagram_business_id: str = "", period: str = "days_28",
                             metric: str = "reach,follower_count,profile_views,accounts_engaged,total_interactions") -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        data = self.api.get(f"{ig_id}/insights", {"period": period, "metric": metric})
        return data.get("data", []) if isinstance(data, dict) else data

    def get_post_insights(self, media_id: str) -> Any:
        data = self.api.get(f"{media_id}/insights", {"metric": "reach,likes,comments,saved,total_interactions,shares"})
        return data.get("data", []) if isinstance(data, dict) else data

    def get_media_comments(self, media_id: str, limit: int = 25) -> Any:
        return self.api.get(f"{media_id}/comments", {"fields": "id,text,username,timestamp,hidden", "limit": limit})

    def reply_comment(self, comment_id: str, message: str) -> Any:
        return self.api.post(f"{comment_id}/replies", {"message": message})

    def delete_comment(self, comment_id: str) -> Any:
        return self.api.delete(comment_id)

    def hide_comment(self, comment_id: str, hide: bool = True) -> Any:
        return self.api.post(comment_id, {"hidden": "true" if hide else "false"})

    def list_stories(self, instagram_business_id: str = "", limit: int = 25) -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get(f"{ig_id}/stories", {"fields": "id,media_type,media_url,permalink,timestamp", "limit": limit})

    def list_conversations(self, instagram_business_id: str = "", limit: int = 25) -> Any:
        ig_id = instagram_business_id or self.config.instagram_business_id
        return self.api.get(f"{ig_id}/conversations", {"fields": "id,participants,messages,updated_time", "limit": limit})

    def get_conversation(self, conversation_id: str) -> Any:
        return self.api.get(conversation_id, {"fields": "id,participants,messages,updated_time"})

    def list_conversation_messages(self, conversation_id: str, limit: int = 25) -> Any:
        return self.api.get(f"{conversation_id}/messages", {"fields": "id,message,from,to,created_time", "limit": limit})

    def get_message(self, message_id: str) -> Any:
        return self.api.get(message_id, {"fields": "id,message,from,to,created_time"})

    def add_comment(self, media_id: str, message: str) -> Any:
        return self.api.post(f"{media_id}/comments", {"message": message})

    def delete_media(self, media_id: str) -> Any:
        return self.api.delete(media_id)

    def publish_photo(self, image_url: str, caption: str = "", instagram_business_id: str = "",
                      product_ids: str = "", product_x: float = 0.5, product_y: float = 0.5) -> dict:
        import json as _json
        ig_id = instagram_business_id or self.config.instagram_business_id
        params = {"image_url": image_url, "caption": caption}
        pids = [p.strip() for p in (product_ids or "").split(",") if p.strip()]
        if pids:
            tags = [{"product_id": pid, "x": product_x, "y": product_y} for pid in pids[:20]]
            params["product_tags"] = _json.dumps(tags)
        container = self.api.post(f"{ig_id}/media", params)
        creation_id = container.get("id") if isinstance(container, dict) else None
        if not creation_id:
            return container if isinstance(container, dict) else {"result": container}
        result = self.api.post(f"{ig_id}/media_publish", {"creation_id": creation_id})
        return {"container": container, "publish": result}

    def publish_video(self, video_url: str, caption: str = "", cover_url: str = "",
                      instagram_business_id: str = "") -> dict:
        ig_id = instagram_business_id or self.config.instagram_business_id
        params = {"video_url": video_url, "caption": caption}
        if cover_url:
            params["cover_url"] = cover_url
        container = self.api.post(f"{ig_id}/media", params)
        creation_id = container.get("id") if isinstance(container, dict) else None
        if not creation_id:
            return container if isinstance(container, dict) else {"result": container}
        result = self.api.post(f"{ig_id}/media_publish", {"creation_id": creation_id})
        return {"container": container, "publish": result}

    def publish_reel(self, video_url: str, caption: str = "", thumb_offset: int = 0,
                     share_to_feed: bool = True, instagram_business_id: str = "") -> dict:
        ig_id = instagram_business_id or self.config.instagram_business_id
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
            "thumb_offset_ms": thumb_offset,
        }
        container = self.api.post(f"{ig_id}/media", params)
        creation_id = container.get("id") if isinstance(container, dict) else None
        if not creation_id:
            return container if isinstance(container, dict) else {"result": container}
        result = self.api.post(f"{ig_id}/media_publish", {"creation_id": creation_id})
        return {"container": container, "publish": result}

    def publish_story(self, image_url: str = "", video_url: str = "", link: str = "",
                      instagram_business_id: str = "") -> dict:
        ig_id = instagram_business_id or self.config.instagram_business_id
        if not image_url and not video_url:
            raise ValueError("حدد image_url أو video_url")
        params = {}
        if video_url:
            params["media_type"] = "STORIES"
            params["video_url"] = video_url
        else:
            params["image_url"] = image_url
        if link:
            params["link"] = link
        container = self.api.post(f"{ig_id}/media", params)
        creation_id = container.get("id") if isinstance(container, dict) else None
        if not creation_id:
            return container if isinstance(container, dict) else {"result": container}
        result = self.api.post(f"{ig_id}/media_publish", {"creation_id": creation_id})
        return {"container": container, "publish": result}
