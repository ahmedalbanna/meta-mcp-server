"""Shared helpers: SDK init, object conversion, error handling, raw API calls."""

import inspect
import json
from functools import wraps
from typing import Any, Dict, List, Optional

from facebook_business.api import FacebookAdsApi

from src.config import (
    ADS_ALLOW_ACTIVATE,
    DRY_RUN,
    ENABLE_WRITES,
    GRAPH_VERSION,
    MAX_DAILY_BUDGET,
    MAX_LIFETIME_BUDGET,
    META_ACCESS_TOKEN,
    PAGE_ACCESS_TOKEN,
    PAGE_ID,
)


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
                return page["access_token"]
        raise RuntimeError(
            f"الصفحة {page_id} غير موجودة في me/accounts أو بدون توكن صفحة. "
            "تأكد من أن المستخدم يدير الصفحة."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"تعذّر اشتقاق توكن الصفحة من توكن النظام: {e}")


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


_page_api: Optional[FacebookAdsApi] = None


def get_page_api() -> FacebookAdsApi:
    """Return a cached page-scoped API instance (never overrides the default)."""
    global _page_api
    if _page_api is None:
        _page_api = init_page_api()
    return _page_api


def page_api_call(method: str, path: str, params: Optional[dict] = None) -> Any:
    """Perform a raw Graph API call using the page-scoped token."""
    api = get_page_api()
    return api.call(method, (path,), params=params or {}).json()


def to_dict(obj: Any) -> Dict[str, Any]:
    """Convert a Meta SDK object to a plain JSON-safe dict."""
    if obj is None:
        return {}
    try:
        data = obj.export_all_data()
    except Exception:
        data = obj
    return _json_safe(data)


def _json_safe(value: Any) -> Any:
    """Recursively convert values to JSON-safe primitives."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, bool) or isinstance(value, (int, float)) or value is None:
        return value
    return str(value)


def handle_error(e: Exception, context: str = "") -> Dict[str, str]:
    """Normalise an exception into an error dict with an Arabic-friendly message."""
    from facebook_business.exceptions import FacebookRequestError

    if isinstance(e, FacebookRequestError):
        msg = e.api_error_message() or str(e)
        code = e.api_error_code()
        return {
            "error": f"Meta API error ({code}): {msg}",
            "context": context,
        }
    return {"error": f"{context}: {e}".strip(": "), "context": context}


def paged(getter, fields: List[str], params: Optional[dict] = None, limit: int = 25) -> List[dict]:
    """Fetch a full page through the SDK's pagination helper."""
    params = dict(params or {})
    params["fields"] = fields
    params["limit"] = limit
    results = getter(params=params)
    out: List[dict] = []
    for item in results:
        out.append(to_dict(item))
    return out


def api_call(method: str, path: str, params: Optional[dict] = None) -> Any:
    """Perform a raw Graph API call and return parsed JSON.

    Pass path as a tuple so the SDK prepends the versioned Graph base URL.
    """
    api = FacebookAdsApi.get_default_api()
    return api.call(
        method,
        (path,),
        params=params or {},
    ).json()


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
        return False, "عمليات الكتابة معطلة (FB_ENABLE_WRITES=false). فعّلها في .env ثم أعد تشغيل الخادم."
    if status == "ACTIVE" and not ADS_ALLOW_ACTIVATE:
        return False, "تفعيل (ACTIVE) معطل (FB_ADS_ALLOW_ACTIVATE=false)."
    if MAX_DAILY_BUDGET and daily_budget and daily_budget > MAX_DAILY_BUDGET:
        return False, f"الميزانية اليومية ({daily_budget}) تتجاوز الحد المسموح ({MAX_DAILY_BUDGET})."
    if MAX_LIFETIME_BUDGET and lifetime_budget and lifetime_budget > MAX_LIFETIME_BUDGET:
        return False, f"الميزانية الإجمالية ({lifetime_budget}) تتجاوز الحد المسموح ({MAX_LIFETIME_BUDGET})."
    return True, ""


def write_guard(fn):
    """Guard mutating tools: enforce write enable, dry-run, activate & budget caps.

    Uses functools.wraps so FastMCP still sees the original typed signature.
    """
    sig = inspect.signature(fn)

    @wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind_partial(*args, **kwargs)
        status = bound.arguments.get("status", "")
        daily_budget = bound.arguments.get("daily_budget") or 0
        lifetime_budget = bound.arguments.get("lifetime_budget") or 0
        spend_cap = bound.arguments.get("spend_cap") or 0
        ok, msg = evaluate_guard(status, daily_budget, lifetime_budget, spend_cap)
        if not ok:
            return json_dumps({"error": msg, "guard": True})
        if DRY_RUN:
            return json_dumps(
                {
                    "dry_run": True,
                    "action": fn.__name__,
                    "params": {k: v for k, v in bound.arguments.items() if k != "self"},
                    "note": "محاكاة فقط — لم يتم تنفيذ أي عملية فعلية",
                }
            )
        return fn(*args, **kwargs)

    return wrapper
