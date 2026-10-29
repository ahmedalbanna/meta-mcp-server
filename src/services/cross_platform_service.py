"""Cross-platform service (Phase B)."""

from __future__ import annotations

import os
import re
from typing import Any

import requests  # type: ignore[import-untyped]

from src.config import FB_CROSS_PLATFORM_TIKTOK, FB_PHONE_COUNTRY_CODE
from src.core.services import Services
from src.services.page_builder_service import normalize_phone as _normalize_phone

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}


def _og(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
    if m:
        return m.group(1)
    m = re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:{prop}["\']', html, re.I)
    return m.group(1) if m else None


class CrossPlatformService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def tiktok_profile(self, handle: str) -> dict[str, Any]:
        if os.getenv("FB_CROSS_PLATFORM_TIKTOK", "false").lower() not in ("1", "true", "yes", "on") and not FB_CROSS_PLATFORM_TIKTOK:
            return {"error": "FB_CROSS_PLATFORM_TIKTOK=false", "guard": "disabled"}
        handle = (handle or "").strip().lstrip("@")
        if not handle:
            return {"error": "handle مطلوب"}
        url = f"https://www.tiktok.com/@{handle}"
        r = requests.get(url, headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "handle": handle, "url": url}
        html = r.text
        followers = None
        m = re.search(r'"followerCount"\s*:\s*(\d+)', html)
        if m:
            followers = int(m.group(1))
        following = None
        m = re.search(r'"followingCount"\s*:\s*(\d+)', html)
        if m:
            following = int(m.group(1))
        likes = None
        m = re.search(r'"heartCount"\s*:\s*(\d+)', html)
        if m:
            likes = int(m.group(1))
        return {
            "platform": "tiktok",
            "handle": handle,
            "url": url,
            "title": _og(html, "title"),
            "description": _og(html, "description"),
            "image": _og(html, "image"),
            "followers": followers,
            "following": following,
            "likes": likes,
            "note": "بيانات من scraping — قد تكون ناقصة أو قديمة",
        }

    def whatsapp_link(self, phone: str, message: str = "مرحباً، أود الاستفسار عن منتجاتكم") -> dict[str, Any]:
        norm = _normalize_phone(phone, FB_PHONE_COUNTRY_CODE)
        if norm is None:
            return {"error": "رقم هاتف غير صالح", "phone": phone}
        from urllib.parse import quote
        return {"phone": norm, "link": f"https://wa.me/{norm.lstrip('+')}?text={quote(message)}",
                "note": "للتحقق من وجود حساب WhatsApp Business استخدم wa.me link (Meta لا يوفّر API عام)"}

    def competitor_360(self, handle: str, page_id: str = "", phone: str = "") -> dict[str, Any]:
        handle = (handle or "").strip().lstrip("@")
        if not handle:
            return {"error": "handle مطلوب"}
        out: dict[str, Any] = {"handle": handle, "platforms": {}}

        # Instagram
        ig_id = self.config.instagram_business_id
        if ig_id:
            try:
                ig = self.api.get(ig_id, {
                    "fields": (
                        f"business_discovery.username({handle})"
                        "{username,name,followers_count,media_count,"
                        "media.limit(5){like_count,comments_count}}"
                    ),
                })
                biz = ig.get("business_discovery") or {}
                media = (biz.get("media") or {}).get("data", [])
                likes = [m.get("like_count") or 0 for m in media]
                comments = [m.get("comments_count") or 0 for m in media]
                out["platforms"]["instagram"] = {
                    "username": biz.get("username"),
                    "name": biz.get("name"),
                    "followers": biz.get("followers_count"),
                    "media_count": biz.get("media_count"),
                    "avg_likes": round(sum(likes) / len(likes), 1) if likes else 0,
                    "avg_comments": round(sum(comments) / len(comments), 1) if comments else 0,
                }
            except Exception as e:
                out["platforms"]["instagram"] = {"error": str(e)[:150]}
        else:
            out["platforms"]["instagram"] = {"error": "FB_IG_USER_ID غير مضبوط"}

        # Facebook page
        if page_id:
            try:
                data = self.api.page_get(page_id, {"fields": "name,fan_count,category,link,about"})
                out["platforms"]["facebook"] = data if isinstance(data, dict) else {"raw": data}
            except Exception as e:
                out["platforms"]["facebook"] = {"error": str(e)[:150]}

        # TikTok
        if FB_CROSS_PLATFORM_TIKTOK or os.getenv("FB_CROSS_PLATFORM_TIKTOK", "false").lower() in ("1", "true", "yes", "on"):
            try:
                url = f"https://www.tiktok.com/@{handle}"
                r = requests.get(url, headers=_HEADERS, timeout=20)
                if r.status_code == 200:
                    html = r.text
                    followers = None
                    m = re.search(r'"followerCount"\s*:\s*(\d+)', html)
                    if m:
                        followers = int(m.group(1))
                    out["platforms"]["tiktok"] = {
                        "handle": handle,
                        "url": url,
                        "followers": followers,
                        "title": _og(html, "title"),
                        "description": _og(html, "description"),
                    }
                else:
                    out["platforms"]["tiktok"] = {"error": f"HTTP {r.status_code}"}
            except Exception as e:
                out["platforms"]["tiktok"] = {"error": str(e)[:150]}
        else:
            out["platforms"]["tiktok"] = {"disabled": True, "hint": "FB_CROSS_PLATFORM_TIKTOK=true لتفعيل"}

        # WhatsApp
        if phone:
            norm = _normalize_phone(phone, self.config.phone_country_code)
            if norm:
                out["platforms"]["whatsapp"] = {
                    "phone": norm,
                    "link": f"https://wa.me/{norm.lstrip('+')}?text=مرحباً",
                }
            else:
                out["platforms"]["whatsapp"] = {"error": "رقم غير صالح", "phone": phone}
        else:
            out["platforms"]["whatsapp"] = {"note": "أضف phone لتوليد wa.me link"}

        return out
