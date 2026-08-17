"""Concurrency limiting + rate-limit retry for Graph API traffic.

Standalone module with no project imports, so both `src.helpers` and `src.utils`
can depend on it without creating an import cycle.

Meta throttling surfaces as FacebookRequestError with rate-limit codes; those are
retried with exponential backoff. A shared global semaphore bounds the number of
in-flight requests across the whole server, preventing a burst of parallel tool
invocations from overwhelming the Meta Graph API and stalling the stdio pipe.
"""

import os
import threading
import time
from functools import wraps
from typing import Callable

from facebook_business.exceptions import FacebookRequestError

# Max concurrent Graph API requests across all in-flight tool invocations.
MAX_CONCURRENT = max(1, int(os.getenv("FB_MAX_CONCURRENT", "4")))

_API_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT)
_COUNT_LOCK = threading.Lock()
_ACTIVE = 0

# Meta rate-limit + transient error codes/subcodes worth retrying.
RATE_LIMIT_CODES = {4, 17, 32, 613, 80004}
RATE_LIMIT_SUBCODES = {1487003, 1487048, 1487123, 1487182, 1639242}


def concurrent_count() -> int:
    """Return the number of currently in-flight API calls (for health checks)."""
    global _ACTIVE
    with _COUNT_LOCK:
        return _ACTIVE


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


def _is_rate_limit(e: FacebookRequestError) -> bool:
    try:
        code = e.api_error_code() or 0
        subcode = e.api_error_subcode() or 0
    except Exception:
        return False
    return code in RATE_LIMIT_CODES or subcode in RATE_LIMIT_SUBCODES


def _retry_on_error(fn: Callable, args, kwargs, retries, base_delay, backoff):
    """Invoke fn, retrying only on explicit Facebook rate-limit errors.

    Any non-rate-limit exception propagates immediately so callers keep their
    existing error-handling behaviour.
    """
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except FacebookRequestError as e:
            if not _is_rate_limit(e) or attempt >= retries:
                raise
            attempt += 1
            delay = base_delay * (backoff ** (attempt - 1))
            time.sleep(delay)
        except Exception:
            raise


def concurrency_limit(
    max_concurrent: int = MAX_CONCURRENT,
    retries: int = 3,
    base_delay: float = 0.5,
    backoff: float = 2.0,
):
    """Bound concurrent Graph API traffic and retry transient rate-limit errors.

    Uses a shared global semaphore so every wrapped callable contributes to one
    account-wide cap. Preserves the wrapped callable's signature (via
    functools.wraps) so FastMCP and the test suite still see the original typed
    parameters.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _acquire_slot()
            try:
                return _retry_on_error(fn, args, kwargs, retries, base_delay, backoff)
            finally:
                _release_slot()

        return wrapper

    return decorator
