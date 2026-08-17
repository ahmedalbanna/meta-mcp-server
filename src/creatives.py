"""Creative tools: AdPreview generation + creative copy templates."""

AD_FORMATS = [
    "DESKTOP_FEED_STANDARD",
    "MOBILE_FEED_STANDARD",
    "FACEBOOK_STORY_STANDARD",
    "INSTAGRAM_STANDARD",
    "INSTAGRAM_STORY_STANDARD",
    "INSTAGRAM_REELS",
    "FACEBOOK_REELS",
    "AUDIENCE_NETWORK_STANDARD",
    "MESSENGER_STANDARD",
    "SUGGESTED_VIDEO_FORMAT",
    "MARKETPLACE_MOBILE_STANDARD",
]

CTA_OPTIONS = {
    "LINK_CLICKS": ["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "BUY_NOW", "DOWNLOAD", "GET_OFFER"],
    "CONVERSIONS": ["SHOP_NOW", "LEARN_MORE", "SIGN_UP", "BUY_NOW", "DOWNLOAD", "GET_OFFER"],
    "LEAD_GENERATION": ["SIGN_UP", "LEARN_MORE", "GET_OFFER", "SUBSCRIBE", "REGISTER_NOW"],
    "OUTCOME_TRAFFIC": ["LEARN_MORE", "SHOP_NOW", "READ_MORE", "DOWNLOAD"],
    "OUTCOME_ENGAGEMENT": ["LEARN_MORE", "SHOP_NOW", "MESSAGE_PAGE", "INSTALL_MOBILE_APP"],
    "OUTCOME_APP_PROMOTION": ["INSTALL_MOBILE_APP", "LEARN_MORE", "USE_APP"],
    "OUTCOME_AWARENESS": ["LEARN_MORE", "WATCH_MORE", "MESSAGE_PAGE"],
    "OUTCOME_SALES": ["SHOP_NOW", "BUY_NOW", "LEARN_MORE", "SIGN_UP"],
}

_TEMPLATES = {
    "LINK_CLICKS": {
        "format": "DESKTOP_FEED_STANDARD",
        "primary_text": "اكتشف {product} الآن — عرض {offer} لفترة محدودة!",
        "headline": "{product} | {offer}",
        "description": "جودة عالية بأسعار منافسة. اطلب الآن واستمتع بالتوصيل السريع.",
        "cta": "LEARN_MORE",
        "creative_type": "carousel",
    },
    "CONVERSIONS": {
        "format": "INSTAGRAM_STANDARD",
        "primary_text": "لا تفوّت فرصة {offer}! {product} بانتظارك اليوم.",
        "headline": "عرض {product}",
        "description": "أكمل الشراء الآن واحصل على {offer}.",
        "cta": "SHOP_NOW",
        "creative_type": "video",
    },
    "LEAD_GENERATION": {
        "format": "MOBILE_FEED_STANDARD",
        "primary_text": "سجّل الآن واحصل على {offer} من {business} مجانًا!",
        "headline": "احجز مكانك: {offer}",
        "description": "املأ النموذج وسيتواصل معك فريقنا خلال 24 ساعة.",
        "cta": "SIGN_UP",
        "creative_type": "lead_form",
    },
    "OUTCOME_AWARENESS": {
        "format": "FACEBOOK_STORY_STANDARD",
        "primary_text": "تعرف على قصة {business} و{product} في 15 ثانية.",
        "headline": "{product} من {business}",
        "description": "قصة ملهمة عن منتجاتنا وخدماتنا.",
        "cta": "WATCH_MORE",
        "creative_type": "story",
    },
    "OUTCOME_ENGAGEMENT": {
        "format": "INSTAGRAM_REELS",
        "primary_text": "شاهد هذا! كل ما تحتاجه عن {product} في 30 ثانية.",
        "headline": "هل جربت {product}؟",
        "description": "تفاعل معنا وشاركنا رأيك.",
        "cta": "MESSAGE_PAGE",
        "creative_type": "reel",
    },
    "OUTCOME_SALES": {
        "format": "DESKTOP_FEED_STANDARD",
        "primary_text": "عرض حصري: {offer} على {product} اليوم فقط!",
        "headline": "تسوق الآن - {product}",
        "description": "توصيل سريع ودفع آمن. اطلب الآن.",
        "cta": "BUY_NOW",
        "creative_type": "single_image",
    },
}


def register(mcp):
    """Register creative preview & template tools."""

    from src.helpers import api_call, handle_error, json_dumps, to_dict
    from src.throttle import concurrency_limit

    def _validate_format(ad_format: str) -> str:
        fmt = ad_format.strip().upper()
        if fmt not in AD_FORMATS:
            raise ValueError(f"ad_format غير صالح: {ad_format}. الاختيارات: {', '.join(AD_FORMATS)}")
        return fmt

    @mcp.tool()
    @concurrency_limit()
    def generate_ad_preview(ad_id: str, ad_format: str = "DESKTOP_FEED_STANDARD") -> str:
        """
        توليد معاينة إعلان (HTML + رابط) بالشكل المطلوب.
        ad_format: DESKTOP_FEED_STANDARD | MOBILE_FEED_STANDARD | INSTAGRAM_STANDARD | INSTAGRAM_STORY_STANDARD | INSTAGRAM_REELS ...
        """
        try:
            fmt = _validate_format(ad_format)
            data = api_call("POST", f"{ad_id}/previews", {"ad_format": fmt})
            return json_dumps(to_dict(data))
        except Exception as e:
            return json_dumps(handle_error(e, "generate_ad_preview"))

    @mcp.tool()
    @concurrency_limit()
    def generate_creative_preview(ad_creative_id: str, ad_format: str = "DESKTOP_FEED_STANDARD") -> str:
        """توليد معاينة إعلان من معرّف الإبداع (AdCreative) مباشرة."""
        try:
            fmt = _validate_format(ad_format)
            data = api_call("POST", f"{ad_creative_id}/previews", {"ad_format": fmt})
            return json_dumps(to_dict(data))
        except Exception as e:
            return json_dumps(handle_error(e, "generate_creative_preview"))

    @mcp.tool()
    @concurrency_limit()
    def generate_creative_template(
        objective: str = "OUTCOME_SALES",
        business_name: str = "",
        product_name: str = "",
        offer: str = "",
        audience: str = "",
    ) -> str:
        """
        توليد قالب إبداعي جاهز (نص أساسي، عنوان، وصف، CTA، نوع الإبداع) بناءً على الهدف.
        objective: LINK_CLICKS | CONVERSIONS | LEAD_GENERATION | OUTCOME_TRAFFIC |
                   OUTCOME_ENGAGEMENT | OUTCOME_APP_PROMOTION | OUTCOME_AWARENESS | OUTCOME_SALES
        """
        try:
            obj = objective.strip().upper()
            if obj not in _TEMPLATES:
                raise ValueError(
                    f"objective غير صالح: {objective}. الاختيارات: {', '.join(sorted(_TEMPLATES))}"
                )
            tpl = _TEMPLATES[obj]
            fill = {
                "business": business_name or "علامتك التجارية",
                "product": product_name or "منتجك",
                "offer": offer or "عرض خاص",
            }
            return json_dumps(
                {
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
            )
        except Exception as e:
            return json_dumps(handle_error(e, "generate_creative_template"))
