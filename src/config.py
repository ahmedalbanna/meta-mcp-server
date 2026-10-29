"""Compatibility shim -> src.core.config (Pydantic). New code should import Config."""

from __future__ import annotations

# Singleton config loaded from env
import os

from src.core.config import Config


def _get(*names, default=''):
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    return default
def _get_int(*names, default=0):
    try:
        return int(_get(*names, default=str(default)))
    except ValueError:
        return default
def _get_bool(*names, default=False):
    v = _get(*names, default=str(default)).lower()
    return v in ('1','true','yes','on')

CONFIG = Config()

# Re-export module-level constants (transitional; prefer CONFIG)
META_ACCESS_TOKEN = CONFIG.access_token
PAGE_ACCESS_TOKEN = CONFIG.fb_page_access_token
AD_ACCOUNT_ID = CONFIG.fb_ad_account_id
AD_ACCOUNT_IDS = CONFIG.ad_account_ids
PAGE_ID = CONFIG.page_id
INSTAGRAM_BUSINESS_ID = CONFIG.instagram_business_id
BUSINESS_ID = CONFIG.business_id
COMMERCE_ACCOUNT_ID = CONFIG.fb_commerce_account_id
APP_ID = CONFIG.fb_app_id
APP_SECRET = CONFIG.fb_app_secret
WABA_ID = CONFIG.fb_waba_id
WHATSAPP_PHONE_NUMBER_ID = CONFIG.fb_whatsapp_phone_number_id
GRAPH_VERSION = CONFIG.graph_version
SUPPORTED_API_VERSIONS = ["v24.0", "v25.0", "v26.0", "v27.0"]
DEPRECATED_API_VERSIONS = ["v18.0", "v19.0", "v20.0", "v21.0", "v22.0", "v23.0"]

BASE_DIR = CONFIG.base_dir
REPORT_DIR = CONFIG.report_dir if CONFIG.report_dir else (CONFIG.base_dir / 'reports')

ENABLE_WRITES = CONFIG.enable_writes
DRY_RUN = CONFIG.dry_run
ADS_ALLOW_ACTIVATE = CONFIG.ads_allow_activate
MAX_DAILY_BUDGET = CONFIG.max_daily_budget
MAX_LIFETIME_BUDGET = CONFIG.max_lifetime_budget
MAX_SPEND_CAP = CONFIG.max_spend_cap
CONFIRM_WRITES = CONFIG.confirm_writes
MCP_HTTP_TOKEN = ""
MCP_ALLOWED_TASKS = CONFIG.allowed_tasks
AUDIT_LOG_FILE = REPORT_DIR / "audit.jsonl"

META_WEBHOOK_VERIFY_TOKEN = CONFIG.meta_webhook_verify_token
WEBHOOK_PORT = CONFIG.webhook_port

ADAPTIVE_THROTTLE = CONFIG.adaptive_throttle
AUTO_RUN_WEBHOOK_AUTOMATIONS = CONFIG.auto_run_webhook_automations

SCHEDULER_DB_URL = CONFIG.scheduler_db_url

CLOUDINARY_URL = CONFIG.cloudinary_url
CLOUDINARY_CLOUD_NAME = CONFIG.cloudinary_cloud_name
CLOUDINARY_API_KEY = CONFIG.cloudinary_api_key
CLOUDINARY_API_SECRET = CONFIG.cloudinary_api_secret
S3_BUCKET = CONFIG.s3_bucket
S3_REGION = CONFIG.s3_region

ANALYTICS_DB_URL = CONFIG.analytics_db_url
ANALYTICS_RETENTION_DAYS = CONFIG.analytics_retention_days
ANALYTICS_TZ = CONFIG.tz_name
FB_CURRENCY_DEFAULT = CONFIG.currency_default
FB_PHONE_COUNTRY_CODE = CONFIG.phone_country_code
FB_ENABLE_OCR = CONFIG.enable_ocr
FB_CROSS_PLATFORM_TIKTOK = CONFIG.cross_platform_tiktok
FB_CROSS_PLATFORM_WHATSAPP_SCRAPE = CONFIG.cross_platform_whatsapp_scrape
FB_ATTRIBUTION_WINDOW = CONFIG.attribution_window

REQUIRED_KEYS = {"FB_ACCESS_TOKEN": CONFIG.access_token}


def resolve_ad_account_id(override: str = "") -> str:
    return CONFIG.resolve_ad_account_id(override)


def validate_config() -> list:
    rk = globals().get("REQUIRED_KEYS", None)
    if isinstance(rk, dict):
        return [k for k, v in rk.items() if not v]
    return [] if CONFIG.access_token else ["FB_ACCESS_TOKEN"]


def ensure_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
