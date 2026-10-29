"""Page/store builder service (Phase B)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from src.core.config import FB_PHONE_COUNTRY_CODE as _DEFAULT_CC
from src.core.services import Services


def normalize_phone(phone: str, country_code: str = _DEFAULT_CC) -> str | None:
    if not phone:
        return None
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        digits = p[1:]
    elif p.startswith("00"):
        digits = p[2:]
    else:
        digits = p
    if not digits.isdigit():
        return None
    cc = country_code.lstrip("+")
    if not digits.startswith(cc):
        digits = cc + digits.lstrip("0")
    if len(digits) < 8 or len(digits) > 15:
        return None
    return "+" + digits


class PageBuilderService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def validate_phone(self, phone: str, country_code: str = "") -> dict[str, Any]:
        cc = country_code or self.config.phone_country_code
        norm = normalize_phone(phone, cc)
        if norm is None:
            return {"valid": False, "phone": phone, "country_code": cc, "error": "رقم غير صالح"}
        return {
            "valid": True,
            "phone": phone,
            "normalized": norm,
            "country_code": cc,
            "whatsapp_link": f"https://wa.me/{norm.lstrip('+')}?text=مرحبا",
        }

    def whatsapp_link(self, phone: str, message: str = "مرحباً، أود الاستفسار عن منتجاتكم") -> dict[str, Any]:
        norm = normalize_phone(phone, self.config.phone_country_code)
        if norm is None:
            return {"error": "رقم هاتف غير صالح", "phone": phone}
        return {"phone": norm, "link": f"https://wa.me/{norm.lstrip('+')}?text={quote(message)}"}

    def page_checklist(self, page_id: str = "") -> dict[str, Any]:
        pid = page_id or self.config.page_id
        if not pid:
            return {"error": "page_id غير مضبوط (FB_PAGE_ID)"}
        try:
            info = self.api.page_get(
                pid, {"fields": "name,about,category,cover,picture,location,hours,website,phone,emails"}
            )
            data = info if isinstance(info, dict) else {}
            checks = {
                "cover_photo": bool(data.get("cover")),
                "profile_picture": bool(data.get("picture")),
                "about": bool(data.get("about")),
                "category": bool(data.get("category")),
                "location": bool(data.get("location")),
                "hours": bool(data.get("hours")),
                "website": bool(data.get("website")),
                "phone": bool(data.get("phone")),
            }
            score = round(sum(1 for v in checks.values() if v) / len(checks) * 100)
            missing = [k for k, v in checks.items() if not v]
            return {
                "page_id": pid,
                "page_name": data.get("name"),
                "checks": checks,
                "completeness_score": score,
                "missing": missing,
                "recommendation": "أكمل الحقول الناقصة لتحسين ظهور Seite في البحث",
            }
        except Exception as e:
            return {"error": str(e)}

    def update_about(self, about: str, page_id: str = "") -> dict[str, Any]:
        pid = page_id or self.config.page_id
        if os.getenv("FB_ENABLE_WRITES", "false").lower() not in ("1", "true", "yes", "on"):
            return {"page_id": pid, "about": about, "result": {"dry_run": True}}
        res = self.api.page_post(pid, {"about": about})
        return {"page_id": pid, "about": about, "result": res if isinstance(res, dict) else {}}

    def update_cta_whatsapp(
        self, phone: str, page_id: str = "", welcome_message: str = "مرحباً، أود الاستفسار"
    ) -> dict[str, Any]:
        norm = normalize_phone(phone, self.config.phone_country_code)
        if norm is None:
            return {"error": "رقم هاتف غير صالح", "phone": phone}
        pid = page_id or self.config.page_id
        link = f"https://wa.me/{norm.lstrip('+')}?text={quote(welcome_message)}"
        if os.getenv("FB_ENABLE_WRITES", "false").lower() not in ("1", "true", "yes", "on"):
            return {
                "page_id": pid,
                "cta_type": "MESSAGE_PAGE (WhatsApp)",
                "phone": norm,
                "link": link,
                "result": {"dry_run": True},
            }
        res = self.api.page_post(pid + "/call_to_actions", {"type": "MESSAGE_PAGE", "link": link})
        return {
            "page_id": pid,
            "cta_type": "MESSAGE_PAGE (WhatsApp)",
            "phone": norm,
            "link": link,
            "result": res if isinstance(res, dict) else {},
        }

    def build_from_competitor(
        self,
        competitor_handle: str,
        our_page_id: str = "",
        cta_phone: str = "",
        about_override: str = "",
        sections: str = "about,cta,checklist",
    ) -> dict[str, Any]:
        pid = our_page_id or self.config.page_id
        if not pid:
            return {"error": "our_page_id / FB_PAGE_ID مطلوب"}
        handle = (competitor_handle or "").strip().lstrip("@")
        if not handle:
            return {"error": "competitor_handle مطلوب"}

        comp_data: dict[str, Any] = {}
        ig_id = self.config.instagram_business_id
        if ig_id:
            try:
                ig = self.api.get(
                    ig_id,
                    {
                        "fields": (
                            f"business_discovery.username({handle})"
                            "{username,name,biography,followers_count,media_count,"
                            "media.limit(12){caption,timestamp,like_count,comments_count,media_type,permalink}}"
                        ),
                    },
                )
                biz = ig.get("business_discovery") or {}
                media = (biz.get("media") or {}).get("data", [])
                likes = [m.get("like_count") or 0 for m in media]
                comments = [m.get("comments_count") or 0 for m in media]
                hashtags = []
                for m in media:
                    for tok in (m.get("caption") or "").split():
                        if tok.startswith("#"):
                            hashtags.append(tok)
                from collections import Counter

                top_tags = [t for t, _ in Counter(hashtags).most_common(8)]
                comp_data = {
                    "handle": handle,
                    "name": biz.get("name"),
                    "followers": biz.get("followers_count"),
                    "media_count": biz.get("media_count"),
                    "avg_likes": round(sum(likes) / len(likes), 1) if likes else 0,
                    "avg_comments": round(sum(comments) / len(comments), 1) if comments else 0,
                    "top_hashtags": top_tags,
                    "biography": (biz.get("biography") or "")[:200],
                }
            except Exception as e:
                comp_data = {"handle": handle, "error": str(e)[:150]}

        sec_list = [s.strip() for s in sections.split(",") if s.strip()]
        about_text = about_override
        if not about_text and "about" in sec_list and comp_data.get("top_hashtags"):
            about_text = f"{comp_data.get('name') or handle} — " + " ".join(comp_data["top_hashtags"][:4])

        results: dict[str, Any] = {"competitor": comp_data, "our_page_id": pid, "applied": [], "recommendations": []}

        if "about" in sec_list and about_text:
            if os.getenv("FB_ENABLE_WRITES", "false").lower() in ("1", "true", "yes", "on"):
                try:
                    self.api.page_post(pid, {"about": about_text})
                    results["applied"].append({"section": "about", "status": "applied", "value": about_text})
                except Exception as e:
                    results["applied"].append({"section": "about", "status": "error", "error": str(e)[:150]})
            else:
                results["applied"].append({"section": "about", "status": "dry_run", "value": about_text})

        if "cta" in sec_list and cta_phone:
            norm = normalize_phone(cta_phone, self.config.phone_country_code)
            if norm:
                link = f"https://wa.me/{norm.lstrip('+')}?text=مرحباً"
                if os.getenv("FB_ENABLE_WRITES", "false").lower() in ("1", "true", "yes", "on"):
                    try:
                        self.api.page_post(pid + "/call_to_actions", {"type": "MESSAGE_PAGE", "link": link})
                        results["applied"].append({"section": "cta", "status": "applied", "phone": norm, "link": link})
                    except Exception as e:
                        results["applied"].append({"section": "cta", "status": "error", "error": str(e)[:150]})
                else:
                    results["applied"].append({"section": "cta", "status": "dry_run", "phone": norm, "link": link})
            else:
                results["applied"].append({"section": "cta", "status": "invalid_phone", "phone": cta_phone})

        if "checklist" in sec_list:
            try:
                info = self.api.page_get(pid, {"fields": "name,about,cover,picture,location,hours,website,phone"})
                data = info if isinstance(info, dict) else {}
                checks = {
                    k: bool(data.get(k)) for k in ("cover", "picture", "about", "location", "hours", "website", "phone")
                }
                results["checklist"] = {"checks": checks, "score": round(sum(checks.values()) / len(checks) * 100)}
                if comp_data.get("top_hashtags"):
                    results["recommendations"].append(
                        "استخدم هاشتاقات المنافس: " + ", ".join(comp_data["top_hashtags"])
                    )
                if comp_data.get("avg_likes"):
                    results["recommendations"].append(
                        f"متوسط إعجابات المنافس: {comp_data['avg_likes']} — اهدف للتغلب عليه"
                    )
                if not data.get("about"):
                    results["recommendations"].append("أضف نبذة (about) — حالياً فارغة")
                if not data.get("cover"):
                    results["recommendations"].append("أضف صورة غلاف (cover)")
            except Exception as e:
                results["checklist"] = {"error": str(e)[:150]}

        return results
