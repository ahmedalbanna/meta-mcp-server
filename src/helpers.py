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


from src.throttle import (
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
    import time

    from src.utils import get_correlation_id

    cid = get_correlation_id()
    if cid:
        params = dict(params or {})
        # Propagate correlation via custom header emulation (added to params for tracing)
        params["_cid"] = cid
    t0 = time.monotonic()
    try:
        from src.metrics import inc_api_call

        inc_api_call(method)
    except Exception:
        pass
    api = get_page_api()
    resp = api.call(method, (path,), params=params or {})
    try:
        from src.metrics import observe_tool_duration

        observe_tool_duration(f"page_api:{method}", time.monotonic() - t0)
    except Exception:
        pass
    return resp.json()


@async_concurrency_limit()
def async_page_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Async version: perform a raw Graph API call using the page-scoped token."""
    import time

    from src.utils import get_correlation_id

    cid = get_correlation_id()
    if cid:
        params = dict(params or {})
        params["_cid"] = cid
    t0 = time.monotonic()
    try:
        from src.metrics import inc_api_call

        inc_api_call(method)
    except Exception:
        pass
    api = get_page_api()
    resp = api.call(method, (path,), params=params or {})
    try:
        from src.metrics import observe_tool_duration

        observe_tool_duration(f"page_api:{method}", time.monotonic() - t0)
    except Exception:
        pass
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

    Returns a consistent contract: {error, context, code?, subcode?, retry_after?, correlation_id?}.
    Handles FacebookRequestError (including rate-limit without exception),
    generic exceptions, and empty/invalid API responses.
    """
    from facebook_business.exceptions import FacebookRequestError

    # Include correlation_id for tracing (Phase 4.2)
    try:
        from src.utils import get_correlation_id

        cid = get_correlation_id() or ""
    except Exception:
        cid = ""

    if isinstance(e, FacebookRequestError):
        msg = e.api_error_message() or str(e)
        code = e.api_error_code()
        subcode = e.api_error_subcode()
        # metrics
        try:
            from src.metrics import inc_api_error, inc_rate_limit

            inc_api_error(str(code))
            if code in RATE_LIMIT_CODES or subcode in RATE_LIMIT_SUBCODES:
                inc_rate_limit(code or 0)
        except Exception:
            pass
        # Rate-limit without raising — surface it clearly
        if code in RATE_LIMIT_CODES or subcode in RATE_LIMIT_SUBCODES:
            logger.warning(
                "Rate limit hit in %s: code=%s subcode=%s correlation_id=%s",
                context,
                code,
                subcode,
                cid or "-",
            )
            return {
                "error": f"تم تقييد الوصول من Meta (rate limit). كود: {code}/{subcode}",
                "context": context,
                "code": code,
                "subcode": subcode,
                "correlation_id": cid or None,
                "retry_after": "إعادة المحاولة بعد 30-60 ثانية",
            }
        return {
            "error": f"Meta API error ({code}): {msg}",
            "context": context,
            "code": code,
            "subcode": subcode,
            "correlation_id": cid or None,
        }
    logger.exception("Unexpected error in %s correlation_id=%s", context, cid or "-")
    return {
        "error": f"{context}: {e}".strip(": "),
        "context": context,
        "code": None,
        "subcode": None,
        "correlation_id": cid or None,
    }


@concurrency_limit()
def api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Perform a raw Graph API call and return parsed JSON.

    Pass path as a tuple so the SDK prepends the versioned Graph base URL.
    Wrapped with a global concurrency limit and rate-limit retry so parallel
    tool invocations cannot overwhelm the Meta Graph API and stall the server.
    Propagates X-Correlation-ID via params for tracing (Phase 4.2).
    """
    import time

    from src.utils import get_correlation_id

    cid = get_correlation_id()
    if cid:
        params = dict(params or {})
        # Add correlation header emulation (Meta ignores unknown params but we log it)
        # SDK doesn't expose headers, so we inject as param for traceability
        params["_cid"] = cid
    t0 = time.monotonic()
    try:
        from src.metrics import inc_api_call

        inc_api_call(method)
    except Exception:
        pass
    api = FacebookAdsApi.get_default_api()
    # Add correlation header to underlying session if possible
    try:
        if cid and hasattr(api, "_session") and hasattr(api._session, "headers"):
            api._session.headers["X-Correlation-ID"] = cid  # type: ignore
    except Exception:
        pass
    resp = api.call(method, (path,), params=params or {})
    data = resp.json()
    if not data:
        logger.warning("Empty response from Graph API: %s %s correlation_id=%s", method, path, cid or "-")
    try:
        from src.metrics import observe_tool_duration

        observe_tool_duration(f"api:{method}", time.monotonic() - t0)
    except Exception:
        pass
    return data


@async_concurrency_limit()
def async_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Async version: perform a raw Graph API call and return parsed JSON."""
    import time

    from src.utils import get_correlation_id

    cid = get_correlation_id()
    if cid:
        params = dict(params or {})
        params["_cid"] = cid
    t0 = time.monotonic()
    try:
        from src.metrics import inc_api_call

        inc_api_call(method)
    except Exception:
        pass
    api = FacebookAdsApi.get_default_api()
    try:
        if cid and hasattr(api, "_session") and hasattr(api._session, "headers"):
            api._session.headers["X-Correlation-ID"] = cid  # type: ignore
    except Exception:
        pass
    resp = api.call(method, (path,), params=params or {})
    data = resp.json()
    if not data:
        logger.warning("Empty response from Graph API: %s %s correlation_id=%s", method, path, cid or "-")
    try:
        from src.metrics import observe_tool_duration

        observe_tool_duration(f"api:{method}", time.monotonic() - t0)
    except Exception:
        pass
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


def _audit_log(tool: str, params: dict, correlation_id: str = "") -> None:
    """Append audit entry to REPORT_DIR/audit.jsonl (Phase 8.2)."""
    try:
        from src.config import AUDIT_LOG_FILE, REPORT_DIR

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "tool": tool,
            "params": {k: v for k, v in params.items() if "token" not in k.lower()},
            "correlation_id": correlation_id or None,
        }
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _check_rbac(tool: str) -> tuple[bool, str]:
    """Check if current MCP_ALLOWED_TASKS allows this tool (Phase 8.2)."""
    try:
        from src.config import MCP_ALLOWED_TASKS

        # Map tool to required task
        required = "ANALYZE"
        if any(
            x in tool for x in ("create", "update", "delete", "remove", "add_", "ban", "publish", "upload", "send_")
        ):
            required = "ADVERTISE"
        elif "lead" in tool or "audience" in tool:
            required = "MANAGE"
        if required not in MCP_ALLOWED_TASKS and "ADMIN" not in MCP_ALLOWED_TASKS:
            # Allow if wildcard
            if "*" not in MCP_ALLOWED_TASKS:
                return False, f"مهمة {tool} تتطلب صلاحية {required}. المسموح: {', '.join(MCP_ALLOWED_TASKS)}"
        return True, ""
    except Exception:
        return True, ""


def write_guard(fn):
    """Guard mutating tools: enforce write enable, dry-run, activate & budget caps.

    Uses functools.wraps so FastMCP still sees the original typed signature.
    Rejections include a machine-readable guard code for clients.
    FB_CONFIRM_WRITES: when true, DELETE/remove tools require confirm="yes".
    DRY_RUN: when true, shows diff preview instead of executing.
    RBAC (Phase 8.2): checks MCP_ALLOWED_TASKS.
    Audit (Phase 8.2): logs to audit.jsonl.
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
        # RBAC (Phase 8.2)
        ok_rbac, rbac_msg = _check_rbac(fn.__name__)
        if not ok_rbac:
            return json_dumps({"error": rbac_msg, "guard": True, "code": "GUARD_RBAC_DENIED"})
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
        # Audit log (Phase 8.2) — before execution
        try:
            from src.utils import get_correlation_id

            cid = get_correlation_id()
        except Exception:
            cid = ""
        _audit_log(fn.__name__, {k: v for k, v in bound.arguments.items() if k != "self"}, cid)
        # Strip confirm before dispatching to functions that don't expect it
        if "confirm" in kwargs:
            kwargs.pop("confirm")
        # Also handle confirm passed positionally? not needed
        return fn(*args, **kwargs)

    return wrapper
