"""Central configuration: loads .env and provides shared constants + guardrails.

Supports both FB_* (primary, matching env.md) and META_* (legacy alias) names.
"""

from __future__ import annotations

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
# Multi-account (Phase 8.1): FB_AD_ACCOUNT_IDS=act_1,act_2  — per-tool ad_account_id override
_raw_ids = _get("FB_AD_ACCOUNT_IDS", default="")
if _raw_ids:
    AD_ACCOUNT_IDS: list[str] = [s.strip() for s in _raw_ids.split(",") if s.strip()]
    if AD_ACCOUNT_ID and AD_ACCOUNT_ID not in AD_ACCOUNT_IDS:
        AD_ACCOUNT_IDS.insert(0, AD_ACCOUNT_ID)
else:
    AD_ACCOUNT_IDS = [AD_ACCOUNT_ID] if AD_ACCOUNT_ID else []


def resolve_ad_account_id(override: str = "") -> str:
    """Resolve effective ad account id: override > first of AD_ACCOUNT_IDS > AD_ACCOUNT_ID."""
    if override and override.strip():
        return override.strip()
    if AD_ACCOUNT_IDS:
        return AD_ACCOUNT_IDS[0]
    return AD_ACCOUNT_ID


PAGE_ID = _get("FB_PAGE_ID", "PAGE_ID")
INSTAGRAM_BUSINESS_ID = _get("FB_IG_USER_ID", "INSTAGRAM_BUSINESS_ID")
BUSINESS_ID = _get("FB_BUSINESS_ID", "BUSINESS_ID")
COMMERCE_ACCOUNT_ID = _get("FB_COMMERCE_ACCOUNT_ID", "COMMERCE_ACCOUNT_ID")
APP_ID = _get("FB_APP_ID", "APP_ID")
APP_SECRET = _get("FB_APP_SECRET", "APP_SECRET")
WABA_ID = _get("FB_WABA_ID", "WABA_ID")
WHATSAPP_PHONE_NUMBER_ID = _get("FB_WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_PHONE_NUMBER_ID")

GRAPH_VERSION = _get("FB_API_VERSION", default="v27.0")
# Supported Graph API versions (Phase 5.6 v27 smoke — SDK 27 prepared, PyPI latest 26.0.0 as of 2026-09-18)
SUPPORTED_API_VERSIONS = ["v24.0", "v25.0", "v26.0", "v27.0"]
DEPRECATED_API_VERSIONS = ["v18.0", "v19.0", "v20.0", "v21.0", "v22.0", "v23.0"]
if GRAPH_VERSION not in SUPPORTED_API_VERSIONS and GRAPH_VERSION not in DEPRECATED_API_VERSIONS:
    import logging as _log

    _log.getLogger(__name__).warning(
        "FB_API_VERSION %s غير مدعومة. المدعومة: %s — قد تحتاج لتحديث facebook-business SDK",
        GRAPH_VERSION,
        ", ".join(SUPPORTED_API_VERSIONS),
    )
if GRAPH_VERSION in DEPRECATED_API_VERSIONS:
    import logging as _log2

    _log2.getLogger(__name__).warning(
        "FB_API_VERSION %s deprecated — حدّث إلى %s", GRAPH_VERSION, SUPPORTED_API_VERSIONS[-1]
    )

REPORT_DIR = BASE_DIR / "reports"

# Write gating & ad-spend guardrails (safe defaults: writes OFF)
ENABLE_WRITES = _get_bool("FB_ENABLE_WRITES", default=False)
DRY_RUN = _get_bool("FB_DRY_RUN", default=False)
ADS_ALLOW_ACTIVATE = _get_bool("FB_ADS_ALLOW_ACTIVATE", default=False)
MAX_DAILY_BUDGET = _get_int("FB_ADS_MAX_DAILY_BUDGET")
MAX_LIFETIME_BUDGET = _get_int("FB_ADS_MAX_LIFETIME_BUDGET")
CONFIRM_WRITES = _get_bool("FB_CONFIRM_WRITES", default=False)

MCP_HTTP_TOKEN = _get("FB_MCP_TOKEN")
# RBAC (Phase 8.2): tasks allowed for this token — ADVERTISE, ANALYZE, MANAGE, DRAFT
MCP_ALLOWED_TASKS: list[str] = [
    s.strip().upper()
    for s in _get("FB_MCP_ALLOWED_TASKS", default="ADVERTISE,ANALYZE,MANAGE,DRAFT").split(",")
    if s.strip()
]
AUDIT_LOG_FILE = REPORT_DIR / "audit.jsonl"

# Webhook receiver (webhook_server.py)
META_WEBHOOK_VERIFY_TOKEN = _get("FB_META_WEBHOOK_VERIFY_TOKEN", "META_WEBHOOK_VERIFY_TOKEN")
WEBHOOK_PORT = _get_int("FB_WEBHOOK_PORT", default=8080)

# Observability & scale (Phase 4)
ADAPTIVE_THROTTLE = _get_bool("FB_ADAPTIVE_THROTTLE", default=True)
AUTO_RUN_WEBHOOK_AUTOMATIONS = _get_bool("FB_AUTO_RUN_WEBHOOK_AUTOMATIONS", default=False)

# Scheduler persistence (Phase 8.3): APScheduler with SQLAlchemy at reports/scheduler.db
SCHEDULER_DB_URL = _get("FB_SCHEDULER_DB_URL", default="")  # e.g. sqlite:///reports/scheduler.db
if not SCHEDULER_DB_URL:
    SCHEDULER_DB_URL = f"sqlite:///{(REPORT_DIR / 'scheduler.db').as_posix()}"

# Permanent media hosting (Phase 10) — Cloudinary/S3 for years, fallback uguu.se 72h
CLOUDINARY_URL = _get("CLOUDINARY_URL", "CLOUDINARY_URL")
# Format: cloudinary://api_key:api_secret@cloud_name  (also supports CLOUDINARY_CLOUD_NAME etc.)
CLOUDINARY_CLOUD_NAME = _get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = _get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = _get("CLOUDINARY_API_SECRET")
# S3 alternative
S3_BUCKET = _get("S3_BUCKET", "AWS_S3_BUCKET")
S3_REGION = _get("S3_REGION", default="us-east-1")

REQUIRED_KEYS = {
    "FB_ACCESS_TOKEN": META_ACCESS_TOKEN,
}


def validate_config() -> list:
    """Return a list of missing required environment variables."""
    return [k for k, v in REQUIRED_KEYS.items() if not v]


def ensure_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
