"""Page & store builder for our own account, inspired by competitor analysis.

Phase 3: improve/develop OUR page/store using competitor insights, with Yemen
defaults (YER, +967, Asia/Aden) and WhatsApp CTA validation.
"""

from __future__ import annotations

import logging

from src.throttle import concurrency_limit
from src.utils import handle_error, json_dumps, write_guard

logger = logging.getLogger(__name__)


def register(mcp, services):
    """Register page/store builder tools."""

    @mcp.tool()
    @concurrency_limit()
    def validate_phone_number(phone: str, country_code: str = "") -> str:
        """التحقق من رقم هاتف وتحويله إلى E.164 (افتراضي +967 اليمن)."""
        try:
            from src.services.page_builder_service import PageBuilderService

            svc = PageBuilderService(services)
            cc = country_code or services.config.phone_country_code
            return json_dumps(svc.validate_phone(phone, cc))
        except Exception as e:
            return json_dumps(handle_error(e, "validate_phone_number"))

    @mcp.tool()
    @concurrency_limit()
    def generate_whatsapp_cta_link(phone: str, message: str = "مرحباً، أود الاستفسار عن منتجاتكم") -> str:
        """توليد رابط wa.me (Click-to-Chat) لاستخدامه في CTA."""
        try:
            from src.services.page_builder_service import PageBuilderService

            svc = PageBuilderService(services)
            return json_dumps(svc.whatsapp_link(phone, message))
        except Exception as e:
            return json_dumps(handle_error(e, "generate_whatsapp_cta_link"))

    @mcp.tool()
    @concurrency_limit()
    def page_building_checklist(page_id: str = "") -> str:
        """قائمة تحقق لبناء/تحسين Seite: غلاف، صورة شخصية، CTA، نبذة، ساعات، موقع، منشور مثبت، وصف."""
        try:
            from src.services.page_builder_service import PageBuilderService

            svc = PageBuilderService(services)
            return json_dumps(svc.page_checklist(page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "page_building_checklist"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_page_about(about: str, page_id: str = "") -> str:
        """تحديث نبذة Seite (about)."""
        try:
            from src.services.page_builder_service import PageBuilderService

            svc = PageBuilderService(services)
            return json_dumps(svc.update_about(about, page_id))
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_about"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_page_cta_whatsapp(phone: str, page_id: str = "", welcome_message: str = "مرحباً، أود الاستفسار") -> str:
        """تعيين CTA Seite إلى WhatsApp (Click-to-Chat) مع التحقق من رقم +967."""
        try:
            from src.services.page_builder_service import PageBuilderService

            svc = PageBuilderService(services)
            return json_dumps(svc.update_cta_whatsapp(phone, page_id, welcome_message))
        except Exception as e:
            return json_dumps(handle_error(e, "update_page_cta_whatsapp"))

    @mcp.tool()
    @concurrency_limit()
    def build_page_from_competitor(
        competitor_handle: str,
        our_page_id: str = "",
        cta_phone: str = "",
        about_override: str = "",
        sections: str = "about,cta,checklist",
    ) -> str:
        """بناء/تحسين Seite ours مستوحى من منافس: سحب بياناته (متابعون، cadence، hashtags، أسعار) وتوليد توصيات + تطبيق التغييرات.

        competitor_handle: اسم حساب IG منافس (بدون @)
        our_page_id: صفحتنا (افتراضي FB_PAGE_ID)
        cta_phone: رقم WhatsApp (+967) لتعيين CTA (اختياري)
        about_override: نص نبذة مخصّص (اختياري — وإلا تُولَّد من بيانات المنافس)
        sections: about,cta,checklist (مفصولة بفواصل)

        يُرجع: توصيات + نتائج التطبيق (dry-run unless FB_ENABLE_WRITES).
        """
        try:
            from src.services.page_builder_service import PageBuilderService

            svc = PageBuilderService(services)
            result = svc.build_from_competitor(competitor_handle, our_page_id, cta_phone, about_override, sections)
            return json_dumps(result)
        except Exception as e:
            return json_dumps(handle_error(e, "build_page_from_competitor"))
