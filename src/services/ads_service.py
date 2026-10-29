"""Ads service (Phase B)."""

from __future__ import annotations

import json
from typing import Any

from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet

from src.config import resolve_ad_account_id
from src.core.services import Services
from src.helpers import to_dict
from src.utils import paginate


class AdsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list_ads(self, adset_id: str = "", limit: int = 25, ad_account_id: str = "") -> Any:
        fields = [Ad.Field.name, Ad.Field.status, Ad.Field.creative, Ad.Field.adset_id,
                  Ad.Field.created_time, Ad.Field.id]

        def _getter(params):
            if adset_id:
                return AdSet(adset_id).get_ads(params=params)
            return AdAccount(resolve_ad_account_id(ad_account_id)).get_ads(params=params)

        return paginate(_getter, fields=fields, limit=limit)

    def get_ad(self, ad_id: str) -> Any:
        ad = Ad(ad_id)
        info = ad.api_get(fields=[Ad.Field.name, Ad.Field.status, Ad.Field.creative,
                                  Ad.Field.adset_id, Ad.Field.created_time, Ad.Field.updated_time])
        return to_dict(info)

    def update_status(self, ad_id: str, status: str) -> dict[str, Any]:
        valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
        status = status.upper()
        if status not in valid:
            raise ValueError(f"status غير صالح. القيم: {', '.join(sorted(valid))}")
        ad = Ad(ad_id)
        ad.api_update(params={Ad.Field.status: status})
        return {"success": True, "ad_id": ad_id, "new_status": status}

    def upload_image(self, name: str = "", image_url: str = "", file_path: str = "") -> Any:

        from src.config import AD_ACCOUNT_ID as _acct
        from src.config import BASE_DIR
        from src.helpers import sanitize_path
        if not image_url and not file_path:
            raise ValueError("قدّم image_url أو file_path")
        from facebook_business.adobjects.adimage import AdImage
        image = AdImage(parent_id=_acct)
        params = {}
        if image_url:
            params[AdImage.Field.url] = image_url
        if file_path:
            resolved = sanitize_path(file_path, BASE_DIR)
            if not resolved.is_file():
                raise FileNotFoundError(f"الملف غير موجود: {file_path}")
            params[AdImage.Field.filename] = str(resolved)
        if name:
            params[AdImage.Field.name] = name
        result = image.api_create(parent_id=_acct, params=params)
        data = to_dict(result) if result is not None else {}
        return {"hash": data.get("hash"), "image_id": data.get("id"), "details": data}

    def upload_video(self, title: str = "", file_path: str = "", video_url: str = "") -> Any:
        from src.config import AD_ACCOUNT_ID as _acct
        from src.config import BASE_DIR
        from src.helpers import sanitize_path
        if not file_path and not video_url:
            raise ValueError("قدّم file_path أو video_url")
        from facebook_business.adobjects.advideo import AdVideo
        video = AdVideo(parent_id=_acct)
        params = {}
        if file_path:
            resolved = sanitize_path(file_path, BASE_DIR)
            if not resolved.is_file():
                raise FileNotFoundError(f"الملف غير موجود: {file_path}")
            params[AdVideo.Field.filename] = str(resolved)
        if video_url:
            params[AdVideo.Field.file_url] = video_url
        if title:
            params[AdVideo.Field.title] = title
        video.api_create(parent_id=_acct, params=params)
        return {"video_id": video.get_id(), "title": title}

    def create_ad_creative(self, name: str, page_id: str, message: str, image_hash: str = "",
                           image_url: str = "", video_id: str = "", link: str = "",
                           headline: str = "", call_to_action: str = "") -> Any:
        from facebook_business.adobjects.adaccount import AdAccount
        from facebook_business.adobjects.adcreative import AdCreative

        from src.ads import _build_object_story_spec  # module-level
        from src.config import AD_ACCOUNT_ID
        account = AdAccount(AD_ACCOUNT_ID)
        object_story_spec = _build_object_story_spec(page_id, message, image_hash, image_url, video_id, link, headline, call_to_action)
        creative = account.create_ad_creative(params={
            AdCreative.Field.name: name,
            AdCreative.Field.object_story_spec: json.dumps(object_story_spec),
        })
        return to_dict(creative)

    def create_ad(self, adset_id: str, name: str, creative_name: str, page_id: str, message: str,
                  image_hash: str = "", image_url: str = "", video_id: str = "", link: str = "",
                  headline: str = "", call_to_action: str = "", status: str = "PAUSED") -> Any:
        import json as _json

        from facebook_business.adobjects.ad import Ad
        from facebook_business.adobjects.adaccount import AdAccount
        from facebook_business.adobjects.adcreative import AdCreative

        from src.ads import _build_object_story_spec  # module-level
        from src.config import resolve_ad_account_id
        account = AdAccount(resolve_ad_account_id(""))
        object_story_spec = _build_object_story_spec(page_id, message, image_hash, image_url, video_id, link, headline, call_to_action)
        creative = account.create_ad_creative(params={
            AdCreative.Field.name: creative_name,
            AdCreative.Field.object_story_spec: _json.dumps(object_story_spec),
        })
        params = {
            Ad.Field.name: name,
            "adset_id": adset_id,
            "creative_id": creative.get_id(),
            Ad.Field.status: status,
        }
        ad = account.create_ad(params=params)
        return to_dict(ad)
