"""Ads service (Phase B)."""

from __future__ import annotations

import json
from typing import Any

from src.core.services import Services
from src.utils import paginate, to_dict


class AdsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def _acct(self, ad_account_id: str = "") -> str:
        return self.config.resolve_ad_account_id(ad_account_id)

    def list_ads(self, adset_id: str = "", limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [
            "name",
            "status",
            "creative",
            "adset_id",
            "created_time",
            "id",
        ]

        def _getter(params):
            path = f"{adset_id}/ads" if adset_id else f"{self._acct(ad_account_id)}/ads"
            return self.services.api.get(path, params)

        return paginate(_getter, fields=fields, limit=limit)

    def get_ad(self, ad_id: str) -> Any:
        fields = [
            "name",
            "status",
            "creative",
            "adset_id",
            "created_time",
            "updated_time",
        ]
        data = self.services.api.get(f"{ad_id}", {"fields": ",".join(fields)})
        return to_dict(data)

    def update_status(self, ad_id: str, status: str) -> dict[str, Any]:
        valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
        status = status.upper()
        if status not in valid:
            raise ValueError(f"status غير صالح. القيم: {', '.join(sorted(valid))}")
        self.services.api.post(f"{ad_id}", {"status": status})
        return {"success": True, "ad_id": ad_id, "new_status": status}

    def upload_image(self, name: str = "", image_url: str = "", file_path: str = "") -> Any:

        from src.utils import sanitize_path

        if not image_url and not file_path:
            raise ValueError("قدّم image_url أو file_path")
        acct = self.config.fb_ad_account_id
        params: dict[str, Any] = {}
        if image_url:
            params["url"] = image_url
        if file_path:
            resolved = sanitize_path(file_path, self.config.base_dir)
            if not resolved.is_file():
                raise FileNotFoundError(f"الملف غير موجود: {file_path}")
            params["filename"] = str(resolved)
        if name:
            params["name"] = name
        result = self.services.api.post(f"{acct}/adimages", params)
        data = to_dict(result) if result is not None else {}
        return {"hash": data.get("hash"), "image_id": data.get("id"), "details": data}

    def upload_video(self, title: str = "", file_path: str = "", video_url: str = "") -> Any:
        from src.utils import sanitize_path

        if not file_path and not video_url:
            raise ValueError("قدّم file_path أو video_url")
        acct = self.config.fb_ad_account_id
        params: dict[str, Any] = {}
        if file_path:
            resolved = sanitize_path(file_path, self.config.base_dir)
            if not resolved.is_file():
                raise FileNotFoundError(f"الملف غير موجود: {file_path}")
            params["filename"] = str(resolved)
        if video_url:
            params["file_url"] = video_url
        if title:
            params["title"] = title
        result = self.services.api.post(f"{acct}/advideos", params)
        data = to_dict(result) if result is not None else {}
        return {"video_id": data.get("id"), "title": title}

    def create_ad_creative(
        self,
        name: str,
        page_id: str,
        message: str,
        image_hash: str = "",
        image_url: str = "",
        video_id: str = "",
        link: str = "",
        headline: str = "",
        call_to_action: str = "",
    ) -> Any:
        from src.ads import _build_object_story_spec  # module-level

        acct = self.config.fb_ad_account_id
        object_story_spec = _build_object_story_spec(
            page_id, message, image_hash, image_url, video_id, link, headline, call_to_action
        )
        params: dict[str, Any] = {
            "name": name,
            "object_story_spec": json.dumps(object_story_spec),
        }
        data = self.services.api.post(f"{acct}/adcreatives", params)
        return to_dict(data)

    def create_ad(
        self,
        adset_id: str,
        name: str,
        creative_name: str,
        page_id: str,
        message: str,
        image_hash: str = "",
        image_url: str = "",
        video_id: str = "",
        link: str = "",
        headline: str = "",
        call_to_action: str = "",
        status: str = "PAUSED",
    ) -> Any:
        from src.ads import _build_object_story_spec  # module-level

        acct = self.config.resolve_ad_account_id("")
        object_story_spec = _build_object_story_spec(
            page_id, message, image_hash, image_url, video_id, link, headline, call_to_action
        )
        creative_data = self.services.api.post(
            f"{acct}/adcreatives",
            {
                "name": creative_name,
                "object_story_spec": json.dumps(object_story_spec),
            },
        )
        creative = to_dict(creative_data) if isinstance(creative_data, dict) else {}
        params = {
            "name": name,
            "adset_id": adset_id,
            "creative_id": creative.get("id"),
            "status": status,
        }
        data = self.services.api.post(f"{acct}/ads", params)
        return to_dict(data)
