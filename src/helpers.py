"""Shared helpers: SDK init, object conversion, error handling, raw API calls."""

from __future__ import annotations

import inspect
import json
import logging
import re
from functools import wraps
from pathlib import Path
from typing import Any

from facebook_business.api import FacebookAdsApi

from src.config import (
    ADS_ALLOW_ACTIVATE,
    CONFIRM_WRITES,
    DRY_RUN,
    ENABLE_WRITES,
    GRAPH_VERSION,
    MAX_DAILY_BUDGET,
    MAX_LIFETIME_BUDGET,
    META_ACCESS_TOKEN,
    PAGE_ACCESS_TOKEN,
    PAGE_ID,
)

_FILENAME_RE = re.compile(r'^[^/\\:<>"|?*\x00]+$')


def sanitize_filename(name: str) -> str:
    """Strip path components and dangerous characters from a filename.

    Raises ValueError if the result is empty or still contains path separators.
    """
    name = name.strip().lstrip("./\\")
    name = name.split("/")[-1].split("\\")[-1]
    if not name or not _FILENAME_RE.match(name):
        raise ValueError(f"Invalid filename: {name!r}")
    return name


def sanitize_path(path_str: str, allowed_root: Path) -> Path:
    """Resolve *path_str* relative to *allowed_root* and ensure it stays inside.

    Raises ValueError if the resolved path escapes allowed_root.
    """
    resolved = (Path(allowed_root) / path_str).resolve()
    root_resolved = Path(allowed_root).resolve()
    if not str(resolved).startswith(str(root_resolved) + "/") and resolved != root_resolved:
        raise ValueError(f"Path escapes allowed directory: {path_str!r}")
    return resolved


from src.throttle import (  # noqa: E402
    RATE_LIMIT_CODES,
    RATE_LIMIT_SUBCODES,
    async_concurrency_limit,
    concurrency_limit,
)

logger = logging.getLogger(__name__)


def init_meta_api() -> None:
    """Initialise the Facebook Ads SDK once."""
    FacebookAdsApi.init(
        access_token=META_ACCESS_TOKEN,
        api_version=GRAPH_VERSION,
    )


def _fetch_page_access_token() -> str:
    """Derive the page-scoped access token from the system token via me/accounts."""
    try:
        api = FacebookAdsApi.get_default_api()
        data = api.call(
            "GET",
            ("me/accounts",),
            params={"fields": "name,id,access_token", "limit": 100},
        ).json()
        page_id = str(PAGE_ID)
        for page in data.get("data", []):
            if str(page.get("id")) == page_id and page.get("access_token"):
                return str(page["access_token"])
        raise RuntimeError(
            f"الصفحة {page_id} غير موجودة في me/accounts أو بدون توكن صفحة. " "تأكد من أن المستخدم يدير الصفحة."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"تعذّر اشتقاق توكن الصفحة من توكن النظام: {e}") from e


def get_page_access_token() -> str:
    """Return the page-scoped access token (explicit .env value or auto-derived)."""
    if PAGE_ACCESS_TOKEN:
        return PAGE_ACCESS_TOKEN
    return _fetch_page_access_token()


def init_page_api() -> FacebookAdsApi:
    """Create a FacebookAdsApi bound to the page-scoped token (cached)."""
    from facebook_business.session import FacebookSession

    token = get_page_access_token()
    session = FacebookSession(None, None, token)
    return FacebookAdsApi(session, api_version=GRAPH_VERSION)


_page_api: FacebookAdsApi | None = None


def get_page_api() -> FacebookAdsApi:
    """Return a cached page-scoped API instance (never overrides the default)."""
    global _page_api
    if _page_api is None:
        _page_api = init_page_api()
    return _page_api


@concurrency_limit()
def page_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Perform a raw Graph API call using the page-scoped token."""
    api = get_page_api()
    resp = api.call(method, (path,), params=params or {})
    return resp.json()


@async_concurrency_limit()
def async_page_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Async version: perform a raw Graph API call using the page-scoped token."""
    api = get_page_api()
    resp = api.call(method, (path,), params=params or {})
    return resp.json()


def to_dict(obj: Any) -> dict[str, Any]:
    """Convert a Meta SDK object to a plain JSON-safe dict."""
    if obj is None:
        return {}
    try:
        data = obj.export_all_data()  # type: ignore[no-any-return, attr-defined]
    except Exception:
        data = obj
    return _json_safe(data)  # type: ignore[no-any-return]


def _json_safe(value: Any) -> Any:
    """Recursively convert values to JSON-safe primitives."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, bool | int | float) or value is None:
        return value
    return str(value)


def handle_error(e: Exception, context: str = "") -> dict[str, Any]:
    """Normalise an exception into an error dict with an Arabic-friendly message.

    Returns a consistent contract: {error, context, code?, subcode?, retry_after?}.
    Handles FacebookRequestError (including rate-limit without exception),
    generic exceptions, and empty/invalid API responses.
    """
    from facebook_business.exceptions import FacebookRequestError

    if isinstance(e, FacebookRequestError):
        msg = e.api_error_message() or str(e)
        code = e.api_error_code()
        subcode = e.api_error_subcode()
        # Rate-limit without raising — surface it clearly
        if code in RATE_LIMIT_CODES or subcode in RATE_LIMIT_SUBCODES:
            logger.warning("Rate limit hit in %s: code=%s subcode=%s", context, code, subcode)
            return {
                "error": f"تم تقييد الوصول من Meta (rate limit). كود: {code}/{subcode}",
                "context": context,
                "code": code,
                "subcode": subcode,
                "retry_after": "إعادة المحاولة بعد 30-60 ثانية",
            }
        return {
            "error": f"Meta API error ({code}): {msg}",
            "context": context,
            "code": code,
            "subcode": subcode,
        }
    logger.exception("Unexpected error in %s", context)
    return {"error": f"{context}: {e}".strip(": "), "context": context, "code": None, "subcode": None}


@concurrency_limit()
def api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Perform a raw Graph API call and return parsed JSON.

    Pass path as a tuple so the SDK prepends the versioned Graph base URL.
    Wrapped with a global concurrency limit and rate-limit retry so parallel
    tool invocations cannot overwhelm the Meta Graph API and stall the server.
    """
    api = FacebookAdsApi.get_default_api()
    resp = api.call(method, (path,), params=params or {})
    data = resp.json()
    if not data:
        logger.warning("Empty response from Graph API: %s %s", method, path)
    return data


@async_concurrency_limit()
def async_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Async version: perform a raw Graph API call and return parsed JSON."""
    api = FacebookAdsApi.get_default_api()
    resp = api.call(method, (path,), params=params or {})
    data = resp.json()
    if not data:
        logger.warning("Empty response from Graph API: %s %s", method, path)
    return data


def json_dumps(data: Any) -> str:
    """JSON-encode data with Arabic-safe output."""
    return json.dumps(data, ensure_ascii=False)


def evaluate_guard(
    status: str = "",
    daily_budget: int = 0,
    lifetime_budget: int = 0,
    spend_cap: int = 0,
) -> tuple:
    """Evaluate write-guardrails. Returns (ok, message)."""
    if not ENABLE_WRITES:
        return (
            False,
            "عمليات الكتابة معطلة (FB_ENABLE_WRITES=false). فعّلها في .env ثم أعد تشغيل الخادم.",
        )
    if status == "ACTIVE" and not ADS_ALLOW_ACTIVATE:
        return False, "تفعيل (ACTIVE) معطل (FB_ADS_ALLOW_ACTIVATE=false)."
    if MAX_DAILY_BUDGET and daily_budget and daily_budget > MAX_DAILY_BUDGET:
        return (
            False,
            f"الميزانية اليومية ({daily_budget}) تتجاوز الحد المسموح ({MAX_DAILY_BUDGET}).",
        )
    if MAX_LIFETIME_BUDGET and lifetime_budget and lifetime_budget > MAX_LIFETIME_BUDGET:
        return (
            False,
            f"الميزانية الإجمالية ({lifetime_budget}) تتجاوز الحد المسموح ({MAX_LIFETIME_BUDGET}).",
        )
    return True, ""


def write_guard(fn):
    """Guard mutating tools: enforce write enable, dry-run, activate & budget caps.

    Uses functools.wraps so FastMCP still sees the original typed signature.
    Rejections include a machine-readable guard code for clients.
    FB_CONFIRM_WRITES: when true, DELETE/remove tools require confirm="yes".
    DRY_RUN: when true, shows diff preview instead of executing.
    """
    sig = inspect.signature(fn)
    is_destructive = "delete" in fn.__name__.lower() or "remove" in fn.__name__.lower() or "ban" in fn.__name__.lower()

    @wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind_partial(*args, **kwargs)
        status = bound.arguments.get("status", "")
        daily_budget = bound.arguments.get("daily_budget") or 0
        lifetime_budget = bound.arguments.get("lifetime_budget") or 0
        spend_cap = bound.arguments.get("spend_cap") or 0
        ok, msg = evaluate_guard(status, daily_budget, lifetime_budget, spend_cap)
        if not ok:
            # Derive a short guard code from the message for programmatic handling
            code = "GUARD_WRITES_DISABLED"
            if "تفعيل" in msg:
                code = "GUARD_ACTIVATE_DISABLED"
            elif "الميزانية اليومية" in msg:
                code = "GUARD_DAILY_BUDGET_EXCEEDED"
            elif "الميزانية الإجمالية" in msg:
                code = "GUARD_LIFETIME_BUDGET_EXCEEDED"
            return json_dumps({"error": msg, "guard": True, "code": code, "subcode": None})
        # Safety rails v2: confirm required for destructive ops when FB_CONFIRM_WRITES=true
        if CONFIRM_WRITES and is_destructive:
            confirm = bound.arguments.get("confirm", "")
            # Also check kwargs directly for confirm
            if not confirm:
                confirm = kwargs.get("confirm", "")
            if str(confirm).lower() not in ("yes", "true", "confirm", "1"):
                return json_dumps(
                    {
                        "error": "تأكيد مطلوب للعمليات الحذفية (FB_CONFIRM_WRITES=true). مرّر confirm='yes'",
                        "guard": True,
                        "code": "GUARD_CONFIRM_REQUIRED",
                        "action": fn.__name__,
                    }
                )
        if DRY_RUN:
            params = {k: v for k, v in bound.arguments.items() if k not in ("self", "confirm")}
            # Diff preview: show what would be created/updated/deleted
            diff_hint = (
                "إنشاء"
                if "create" in fn.__name__
                else "تحديث"
                if "update" in fn.__name__
                else "حذف"
                if is_destructive
                else "تنفيذ"
            )
            return json_dumps(
                {
                    "dry_run": True,
                    "action": fn.__name__,
                    "diff": f"{diff_hint} {fn.__name__} بالبراميترات: {json.dumps(params, ensure_ascii=False)}",
                    "params": params,
                    "note": "محاكاة فقط — لم يتم تنفيذ أي عملية فعلية (FB_DRY_RUN=true)",
                }
            )
        # Strip confirm before dispatching to functions that don't expect it
        if "confirm" in kwargs:
            kwargs.pop("confirm")
        # Also handle confirm passed positionally? not needed
        return fn(*args, **kwargs)

    return wrapper
