"""Central configuration: loads .env and provides shared constants + guardrails.

Supports both FB_* (primary, matching env.md) and META_* (legacy alias) names.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(*names: str, default: str = "") -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    return default


def _get_int(*names: str, default: int = 0) -> int:
    try:
        return int(_get(*names, default=str(default)))
    except ValueError:
        return default


def _get_bool(*names: str, default: bool = False) -> bool:
    v = _get(*names, default=str(default)).lower()
    return v in ("1", "true", "yes", "on")


# Credentials (FB_* primary, META_* fallback)
META_ACCESS_TOKEN = _get("FB_ACCESS_TOKEN", "META_ACCESS_TOKEN")
# Optional explicit page-scoped token (usually auto-derived from META_ACCESS_TOKEN via me/accounts)
PAGE_ACCESS_TOKEN = _get("FB_PAGE_ACCESS_TOKEN", "PAGE_ACCESS_TOKEN")
AD_ACCOUNT_ID = _get("FB_AD_ACCOUNT_ID", "AD_ACCOUNT_ID")
PAGE_ID = _get("FB_PAGE_ID", "PAGE_ID")
INSTAGRAM_BUSINESS_ID = _get("FB_IG_USER_ID", "INSTAGRAM_BUSINESS_ID")
BUSINESS_ID = _get("FB_BUSINESS_ID", "BUSINESS_ID")
COMMERCE_ACCOUNT_ID = _get("FB_COMMERCE_ACCOUNT_ID", "COMMERCE_ACCOUNT_ID")
APP_ID = _get("FB_APP_ID", "APP_ID")
APP_SECRET = _get("FB_APP_SECRET", "APP_SECRET")
WABA_ID = _get("FB_WABA_ID", "WABA_ID")
WHATSAPP_PHONE_NUMBER_ID = _get("FB_WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_PHONE_NUMBER_ID")

GRAPH_VERSION = _get("FB_API_VERSION", default="v26.0")
REPORT_DIR = BASE_DIR / "reports"

# Write gating & ad-spend guardrails (safe defaults: writes OFF)
ENABLE_WRITES = _get_bool("FB_ENABLE_WRITES", default=False)
DRY_RUN = _get_bool("FB_DRY_RUN", default=False)
ADS_ALLOW_ACTIVATE = _get_bool("FB_ADS_ALLOW_ACTIVATE", default=False)
MAX_DAILY_BUDGET = _get_int("FB_ADS_MAX_DAILY_BUDGET")
MAX_LIFETIME_BUDGET = _get_int("FB_ADS_MAX_LIFETIME_BUDGET")

MCP_HTTP_TOKEN = _get("FB_MCP_TOKEN")

# Webhook receiver (webhook_server.py)
META_WEBHOOK_VERIFY_TOKEN = _get("FB_META_WEBHOOK_VERIFY_TOKEN", "META_WEBHOOK_VERIFY_TOKEN")
WEBHOOK_PORT = _get_int("FB_WEBHOOK_PORT", default=8080)

REQUIRED_KEYS = {
    "FB_ACCESS_TOKEN": META_ACCESS_TOKEN,
}


def validate_config() -> list:
    """Return a list of missing required environment variables."""
    return [k for k, v in REQUIRED_KEYS.items() if not v]


def ensure_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
