"""Shared utilities: pagination, rate-limit retries, PII hashing, TTL cache, structured logging.

Reusable across all modules and safe to import without network access.
"""

import contextvars
import hashlib
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from facebook_business.exceptions import FacebookRequestError

from src.helpers import to_dict
from src.throttle import _is_rate_limit

# ---------------------------------------------------------------------------
# Structured logging with correlation id
# ---------------------------------------------------------------------------

_correlation_id: contextvars.ContextVar = contextvars.ContextVar("correlation_id", default="")


def set_correlation_id(prefix: str = "req") -> str:
    """Assign a new correlation id for the current context and return it."""
    cid = f"{prefix}-{uuid.uuid4().hex[:12]}"
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Return the current correlation id (empty when unset)."""
    return str(_correlation_id.get() or "")


class CorrelationFormatter(logging.Formatter):
    """Appends correlation_id=... to every log record when set."""

    def format(self, record: logging.LogRecord) -> str:
        cid = get_correlation_id()
        line = super().format(record)
        if cid:
            return f"{line} correlation_id={cid}"
        return line


def make_logger(name: str) -> logging.Logger:
    """Return a logger with the correlation-aware formatter (idempotent)."""
    logger = logging.getLogger(name)
    if not any(isinstance(h.formatter, CorrelationFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(CorrelationFormatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


log = make_logger("meta-mcp.utils")

# ---------------------------------------------------------------------------
# Cursor-based pagination
# ---------------------------------------------------------------------------


def _extract_batch(result: Any) -> tuple:
    """Split a Graph API response into (items, next_after_cursor).

    Accepts either a raw dict (from helpers.api_call) or an SDK edge collection.
    """
    if isinstance(result, dict):
        data = result.get("data", [])
        paging = result.get("paging", {}) or {}
        cursors = paging.get("cursors", {}) or {}
        after = cursors.get("after") or ""
        return list(data), after
    items = [to_dict(item) for item in result]
    try:
        cursors = result.get_cursors() or {}
        after = cursors.get("after") or ""
    except Exception:
        after = ""
    return items, after


def paginate(
    getter: Callable[..., Any],
    fields: list[str] | None = None,
    params: dict | None = None,
    limit: int = 25,
    max_pages: int | None = 10,
) -> list[dict]:
    """Walk an entire edge via cursor-based pagination (adaptive).

    - max_pages=None → paginate until no `after` cursor (adaptive, capped at 100 pages for safety)
    - max_pages=int → bounded paginate (Phase 6.1)
    getter is called as getter(params={...}) and must return either a raw dict
    with a "data"/"paging" shape or an SDK collection exposing get_cursors().
    """
    batch = dict(params or {})
    if fields:
        batch["fields"] = fields
    batch["limit"] = limit

    # Adaptive: None = unlimited until cursor exhausted, capped at 100
    effective_max = 100 if max_pages is None else max_pages
    out: list[dict] = []
    for _ in range(effective_max):
        try:
            result = getter(params=batch)
        except Exception:
            raise
        items, after = _extract_batch(result)
        out.extend(items)
        if not after:
            break
        # Stop early if API returned fewer than limit (last page) and no cursor
        if len(items) < limit and not after:
            break
        batch["after"] = after
    return out


# ---------------------------------------------------------------------------
# Rate-limit retry with exponential backoff
# ---------------------------------------------------------------------------

# Meta rate-limit + transient error codes worth retrying (from src.throttle)


def retry_on_rate_limit(retries: int = 3, base_delay: float = 2.0, backoff: float = 2.0):
    """Retry a call with exponential backoff when Meta throttles the request.

    Non-rate-limit errors propagate immediately.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except FacebookRequestError as e:
                    if not _is_rate_limit(e) or attempt >= retries:
                        raise
                    attempt += 1
                    delay = base_delay * (backoff ** (attempt - 1))
                    log.warning(
                        "تم بلوغ حد الطلبات، إعادة المحاولة %d بعد %ss (%s)",
                        attempt,
                        delay,
                        get_correlation_id() or "-",
                    )
                    time.sleep(delay)
                except Exception:
                    raise

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# PII normalisation (SHA-256 per Meta Customer List spec)
# ---------------------------------------------------------------------------


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    """Lowercase + trim an email, then return its SHA-256 hex digest."""
    email = (email or "").strip().lower()
    return _sha256_hex(email) if email else email


def normalize_phone(phone: str) -> str:
    """Normalise a phone number (digits, optional leading +) then SHA-256 it."""
    phone = (phone or "").strip()
    if phone.startswith("+"):
        digits = "+" + "".join(ch for ch in phone[1:] if ch.isdigit())
    else:
        digits = "".join(ch for ch in phone if ch.isdigit())
    return _sha256_hex(digits) if digits else phone


def normalize_pii(items: list[str], pii_type: str = "email") -> list[str]:
    """Hash a batch of emails or phones for the Customer List API.

    pii_type: "email" | "phone". Non-hashable/empty entries are dropped.
    """
    normalizer = normalize_phone if pii_type == "phone" else normalize_email
    out = []
    for item in items or []:
        value = str(item).strip()
        if not value:
            continue
        out.append(normalizer(value))
    return out


# ---------------------------------------------------------------------------
# TTL cache for read-only lookups
# ---------------------------------------------------------------------------


def cached(ttl: float = 60.0):
    """Memoise a function result for `ttl` seconds (thread-safe).

    Designed for read-only lookups; never wrap mutating tools with it.
    """

    def decorator(fn: Callable) -> Callable:
        cache: dict[Any, tuple] = {}
        lock = threading.Lock()

        def _key(args, kwargs) -> str:
            try:
                return json.dumps([args, kwargs], sort_keys=True, default=str)
            except Exception:
                return repr((args, kwargs))

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = _key(args, kwargs)
            now = time.monotonic()
            with lock:
                entry = cache.get(key)
                if entry and now - entry[1] < ttl:
                    return entry[0]
            result = fn(*args, **kwargs)
            with lock:
                cache[key] = (result, time.monotonic())
            return result

        return wrapper

    return decorator
