"""Creatives service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.creatives import _TEMPLATES, AD_FORMATS, CTA_OPTIONS
from src.utils import to_dict


class CreativesService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def _validate_format(self, ad_format: str) -> str:
        fmt = ad_format.strip().upper()
        if fmt not in AD_FORMATS:
            raise ValueError(f"ad_format غير صالح: {ad_format}. الاختيارات: {', '.join(AD_FORMATS)}")
        return fmt

    def generate_ad_preview(self, ad_id: str, ad_format: str = "DESKTOP_FEED_STANDARD") -> Any:
        fmt = self._validate_format(ad_format)
        data = self.api.post(f"{ad_id}/previews", {"ad_format": fmt})
        return to_dict(data)

    def generate_creative_preview(self, ad_creative_id: str, ad_format: str = "DESKTOP_FEED_STANDARD") -> Any:
        fmt = self._validate_format(ad_format)
        data = self.api.post(f"{ad_creative_id}/previews", {"ad_format": fmt})
        return to_dict(data)

    def generate_creative_template(self, objective: str = "OUTCOME_SALES", business_name: str = "",
                                   product_name: str = "", offer: str = "", audience: str = "") -> Any:
        obj = objective.strip().upper()
        if obj not in _TEMPLATES:
            raise ValueError(f"objective غير صالح: {objective}. الاختيارات: {', '.join(sorted(_TEMPLATES))}")
        tpl = _TEMPLATES[obj]
        fill = {
            "business": business_name or "علامتك التجارية",
            "product": product_name or "منتجك",
            "offer": offer or "عرض خاص",
        }
        return {
            "objective": obj,
            "creative_type": tpl["creative_type"],
            "suggested_format": tpl["format"],
            "primary_text": tpl["primary_text"].format(**fill),
            "headline": tpl["headline"].format(**fill),
            "description": tpl["description"].format(**fill),
            "cta": tpl["cta"],
            "cta_options": CTA_OPTIONS.get(obj, []),
            "audience": audience or "الجمهور المستهدف",
            "note": "هذه نصيحة تلقائية — راجعها وعدّلها قبل النشر.",
        }
