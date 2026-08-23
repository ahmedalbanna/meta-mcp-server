#!/usr/bin/env python3
"""Validate the .env configuration without printing any secret values.

Prints which required/optional keys are missing or malformed and exits with a
non-zero status only when a required key is missing or unparseable.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import BASE_DIR, REQUIRED_KEYS, validate_config

OPTIONAL_KEYS = {
    "FB_APP_ID": "debug_access_token",
    "FB_APP_SECRET": "debug_access_token",
    "FB_API_VERSION": "إصدار Graph API (افتراضي v26.0)",
    "FB_PAGE_ID": "أدوات الصفحات / الرصاص",
    "FB_AD_ACCOUNT_ID": "الحملات / الإعلانات / التقارير",
    "FB_IG_USER_ID": "أدوات إنستغرام",
    "FB_WABA_ID": "مراسلات واتساب للأعمال",
    "FB_WHATSAPP_PHONE_NUMBER_ID": "مراسلات واتساب للأعمال",
    "FB_BUSINESS_ID": "الكتالوجات والتجارة / مستخدمو Business Manager",
    "FB_COMMERCE_ACCOUNT_ID": "طلبات التجارة (اختياري داخل أدوات التجارة)",
    "FB_META_WEBHOOK_VERIFY_TOKEN": "استقبال Webhooks (webhook_server.py)",
    "FB_PAGE_ACCESS_TOKEN": "توكن الصفحة الصريح (اختياري — يشتق تلقائيًا)",
}

INT_KEYS = {
    "FB_ADS_MAX_DAILY_BUDGET": "الحد الأقصى للميزانية اليومية",
    "FB_ADS_MAX_LIFETIME_BUDGET": "الحد الأقصى للميزانية الإجمالية",
    "FB_WEBHOOK_PORT": "منفذ خادم Webhooks",
    "FB_MAX_CONCURRENT": "حد التوازي لطلبات Graph API (افتراضي 4)",
}

BOOL_KEYS = {
    "FB_ENABLE_WRITES": "تفعيل عمليات الكتابة",
    "FB_DRY_RUN": "وضع المحاكاة",
    "FB_ADS_ALLOW_ACTIVATE": "السماح بتفعيل الحملات",
    "FB_CONFIRM_WRITES": "طلب تأكيد للحذف (FB_CONFIRM_WRITES)",
}


def _read_bool(key: str) -> bool:
    v = os.getenv(key, "false").strip().lower()
    return v in ("1", "true", "yes", "on")


def main() -> int:
    env_path = BASE_DIR / ".env"
    print(f"فحص ملف الإعدادات: {env_path}")
    if not env_path.exists():
        print("[!] ملف .env غير موجود. انسخ .env.example إلى .env وعبّئ القيم.")
        return 1

    exit_code = 0
    missing = validate_config()
    for key in REQUIRED_KEYS:
        if key in missing:
            print(f"[مفقود] {key}  — مطلوب")
            exit_code = 1
        else:
            print(f"[موجود] {key}  ✓")

    print("\nمفاتيح اختيارية:")
    for key, purpose in OPTIONAL_KEYS.items():
        if os.getenv(key):
            print(f"[موجود] {key}  ({purpose})")
        else:
            print(f"[فارغ]  {key}  ({purpose})")

    print("\nالتحقق من صيغ القيم:")
    for key, label in INT_KEYS.items():
        raw = os.getenv(key, "0").strip()
        try:
            v = int(raw)
            if key == "FB_MAX_CONCURRENT" and not (1 <= v <= 20):
                print(f"[تحذير] {key} = {raw} خارج النطاق الموصى (1-20)  ({label})")
            else:
                print(f"[جيد]   {key} = {raw}  ({label})")
        except ValueError:
            print(f"[خطأ]   {key} = '{raw}' ليس رقمًا صحيحًا  ({label})")
            exit_code = 1
    for key, label in BOOL_KEYS.items():
        value = "true" if _read_bool(key) else "false"
        print(f"[جيد]   {key} = {value}  ({label})")

    # Discovery hints (ROADMAP 1.5)
    print("\nتلميحات الاكتشاف:")
    if not os.getenv("FB_PAGE_ID"):
        print("[تلميح] FB_PAGE_ID فارغ — شغّل أداة list_pages ثم عبّئ .env")
    if not os.getenv("FB_AD_ACCOUNT_ID"):
        print("[تلميح] FB_AD_ACCOUNT_ID فارغ — شغّل أداة list_ad_accounts ثم عبّئ .env")
    if not os.getenv("FB_IG_USER_ID"):
        print("[تلميح] FB_IG_USER_ID فارغ — شغّل أداة discover_ig_user ثم عبّئ .env")
    if os.getenv("FB_ENABLE_WRITES", "false").lower() in ("1", "true", "yes", "on"):
        print("[تنبيه] FB_ENABLE_WRITES=true — عمليات الكتابة مفعّلة (تأكد من FB_DRY_RUN عند الاختبار)")

    # Auto-generate opencode.json snippet
    print("\nمقتطف opencode.json (انسخه إلى جذر مشروعك):")
    print('{ "mcp": { "meta-marketing-pro": { "type": "local", "command": ["python", "server.py"], "enabled": true } } }')

    if exit_code:
        print("\nالنتيجة: توجد أخطاء — أصلحها ثم أعد الفحص.")
    else:
        print("\nالنتيجة: الإعداد سليم ✓")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
