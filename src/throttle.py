"""Concurrency limiting + rate-limit retry for Graph API traffic.

Standalone module with no project imports, so both `src.helpers` and `src.utils`
can depend on it without creating an import cycle.

Meta throttling surfaces as FacebookRequestError with rate-limit codes; those are
retried with exponential backoff. A shared global semaphore bounds the number of
in-flight requests across the whole server, preventing a burst of parallel tool
invocations from overwhelming the Meta Graph API and stalling the stdio pipe.

Supports both sync (threading.Semaphore) and async (asyncio.Semaphore) modes.
"""

import asyncio
import os
import threading
import time
from collections.abc import Callable
from functools import wraps

from facebook_business.exceptions import FacebookRequestError

# Max concurrent Graph API requests across all in-flight tool invocations.
MAX_CONCURRENT = max(1, int(os.getenv("FB_MAX_CONCURRENT", "4")))

# Sync semaphore (for legacy sync tools)
_API_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT)
_COUNT_LOCK = threading.Lock()
_ACTIVE = 0

# Async semaphore (for async tools and resources)
_ASYNC_SEMAPHORE: asyncio.Semaphore | None = None
_ASYNC_ACTIVE = 0
_ASYNC_COUNT_LOCK = threading.Lock()

# Meta rate-limit + transient error codes/subcodes worth retrying.
RATE_LIMIT_CODES = {4, 17, 32, 613, 80004}
RATE_LIMIT_SUBCODES = {1487003, 1487048, 1487123, 1487182, 1639242}


def _get_async_semaphore() -> asyncio.Semaphore:
    """Lazy-init the async semaphore (must be called from running event loop)."""
    global _ASYNC_SEMAPHORE
    if _ASYNC_SEMAPHORE is None:
        _ASYNC_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT)
    return _ASYNC_SEMAPHORE


def concurrent_count() -> int:
    """Return the number of currently in-flight API calls (for health checks)."""
    with _COUNT_LOCK:
        sync = _ACTIVE
    with _ASYNC_COUNT_LOCK:
        async_count = _ASYNC_ACTIVE
    return sync + async_count


def _acquire_slot() -> None:
    global _ACTIVE
    _API_SEMAPHORE.acquire()
    with _COUNT_LOCK:
        _ACTIVE += 1


def _release_slot() -> None:
    global _ACTIVE
    with _COUNT_LOCK:
        _ACTIVE -= 1
    _API_SEMAPHORE.release()


def _acquire_async_slot() -> None:
    global _ASYNC_ACTIVE
    with _ASYNC_COUNT_LOCK:
        _ASYNC_ACTIVE += 1


def _release_async_slot() -> None:
    global _ASYNC_ACTIVE
    with _ASYNC_COUNT_LOCK:
        _ASYNC_ACTIVE -= 1


def _is_rate_limit(e: FacebookRequestError) -> bool:
    try:
        code = e.api_error_code() or 0
        subcode = e.api_error_subcode() or 0
    except Exception:
        return False
    return code in RATE_LIMIT_CODES or subcode in RATE_LIMIT_SUBCODES


_COOLDOWN_UNTIL = 0.0
# Use config ADAPTIVE_THROTTLE if available, else env
try:
    from src.core.config import ADAPTIVE_THROTTLE as _ADAPTIVE_CFG

    _ADAPTIVE = bool(_ADAPTIVE_CFG)
except Exception:
    _ADAPTIVE = os.getenv("FB_ADAPTIVE_THROTTLE", "true").lower() in ("1", "true", "yes", "on")


def _retry_on_error(fn: Callable, args, kwargs, retries, base_delay, backoff):
    """Invoke fn, retrying only on explicit Facebook rate-limit errors.

    Any non-rate-limit exception propagates immediately so callers keep their
    existing error-handling behaviour. Adaptive throttling (Phase 4.4) adds
    cooldown after rate-limit bursts.
    """
    global _COOLDOWN_UNTIL
    attempt = 0
    while True:
        # Adaptive: if in cooldown, extra sleep
        if _ADAPTIVE and time.time() < _COOLDOWN_UNTIL:
            time.sleep(0.5)
        try:
            return fn(*args, **kwargs)
        except FacebookRequestError as e:
            if not _is_rate_limit(e) or attempt >= retries:
                raise
            attempt += 1
            # Metrics + adaptive cooldown
            try:
                from src.metrics import inc_rate_limit

                inc_rate_limit(e.api_error_code() or 0)
            except Exception:
                pass
            if _ADAPTIVE:
                _COOLDOWN_UNTIL = time.time() + 5 * attempt  # exponential cooldown
            delay = base_delay * (backoff ** (attempt - 1))
            # Respect Retry-After if present (Meta sends via header, not body)
            try:
                retry_after = e._error.get("error", {}).get("retry_after") if hasattr(e, "_error") else None  # type: ignore
                if retry_after and int(retry_after) > 0:
                    delay = max(delay, float(retry_after))
            except Exception:
                pass
            time.sleep(delay)
        except Exception:
            raise


def concurrency_limit(
    max_concurrent: int = MAX_CONCURRENT,
    retries: int = 3,
    base_delay: float = 0.5,
    backoff: float = 2.0,
):
    """Bound concurrent Graph API traffic and retry transient rate-limit errors (SYNC).

    Uses a shared global semaphore so every wrapped callable contributes to one
    account-wide cap. Preserves the wrapped callable's signature (via
    functools.wraps) so FastMCP and the test suite still see the original typed
    parameters.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _acquire_slot()
            t0 = time.monotonic()
            status = "ok"
            # Ensure correlation_id for tracing (Phase 4.2)
            try:
                from src.utils import get_correlation_id, set_correlation_id

                if not get_correlation_id():
                    set_correlation_id(fn.__name__[:6])
            except Exception:
                pass
            try:
                result = _retry_on_error(fn, args, kwargs, retries, base_delay, backoff)
                # Heuristic error detection: if result is JSON string containing "error"
                try:
                    if isinstance(result, str) and '"error"' in result:
                        status = "error"
                except Exception:
                    pass
                return result
            except Exception:
                status = "exception"
                raise
            finally:
                try:
                    from src.metrics import inc_tool_call, observe_tool_duration

                    inc_tool_call(fn.__name__, status)
                    observe_tool_duration(fn.__name__, time.monotonic() - t0)
                except Exception:
                    pass
                _release_slot()

        return wrapper

    return decorator


async def _async_retry_on_error(fn: Callable, args, kwargs, retries, base_delay, backoff):
    """Async version of retry — calls sync fn in thread executor, retries on rate-limit."""
    attempt = 0
    while True:
        if _ADAPTIVE and time.time() < _COOLDOWN_UNTIL:
            await asyncio.sleep(0.5)
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except FacebookRequestError as e:
            if not _is_rate_limit(e) or attempt >= retries:
                raise
            attempt += 1
            try:
                from src.metrics import inc_rate_limit

                inc_rate_limit(e.api_error_code() or 0)
            except Exception:
                pass
            if _ADAPTIVE:
                globals()["_COOLDOWN_UNTIL"] = time.time() + 5 * attempt
            delay = base_delay * (backoff ** (attempt - 1))
            await asyncio.sleep(delay)
        except Exception:
            raise


def async_concurrency_limit(
    max_concurrent: int = MAX_CONCURRENT,
    retries: int = 3,
    base_delay: float = 0.5,
    backoff: float = 2.0,
):
    """Bound concurrent Graph API traffic and retry transient rate-limit errors (ASYNC).

    Wraps a sync callable and runs it via asyncio.to_thread with an async semaphore.
    Use this for tool functions that need to call blocking Facebook SDK methods.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            sem = _get_async_semaphore()
            async with sem:
                _acquire_async_slot()
                t0 = time.monotonic()
                status = "ok"
                try:
                    from src.utils import get_correlation_id, set_correlation_id

                    if not get_correlation_id():
                        set_correlation_id(fn.__name__[:6])
                except Exception:
                    pass
                try:
                    result = await _async_retry_on_error(fn, args, kwargs, retries, base_delay, backoff)
                    try:
                        if isinstance(result, str) and '"error"' in result:
                            status = "error"
                    except Exception:
                        pass
                    return result
                except Exception:
                    status = "exception"
                    raise
                finally:
                    try:
                        from src.metrics import inc_tool_call, observe_tool_duration

                        inc_tool_call(fn.__name__, status)
                        observe_tool_duration(fn.__name__, time.monotonic() - t0)
                    except Exception:
                        pass
                    _release_async_slot()

        return wrapper

    return decorator
