"""Unit tests for src/throttle.py — concurrency limiting + rate-limit retry.

No network involved; the FacebookRequestError objects are constructed locally.
"""

import inspect
import threading
import time
from unittest import mock

import pytest
from facebook_business.exceptions import FacebookRequestError

from src.throttle import MAX_CONCURRENT, concurrency_limit, concurrent_count


def _rate_limit_error():
    return FacebookRequestError(
        message="rate limited",
        request_context={},
        http_status=400,
        http_headers={},
        body='{"error": {"code": 4, "message": "Application request limit reached"}}',
    )


def _other_error():
    return FacebookRequestError(
        message="bad request",
        request_context={},
        http_status=400,
        http_headers={},
        body='{"error": {"code": 100, "message": "Invalid parameter"}}',
    )


# ---------------------------------------------------------------------------
# Decorator mechanics
# ---------------------------------------------------------------------------


def test_concurrency_limit_preserves_signature():
    @concurrency_limit()
    def target(a, b: int = 2):
        return a + b

    assert target(3) == 5
    params = inspect.signature(target).parameters
    assert "a" in params and "b" in params


def test_concurrency_limit_returns_underlying_result():
    @concurrency_limit()
    def target(x):
        return {"ok": x}

    assert target(7) == {"ok": 7}


def test_concurrent_count_returns_to_zero():
    assert concurrent_count() == 0

    @concurrency_limit()
    def target():
        assert concurrent_count() == 1
        return 1

    target()
    assert concurrent_count() == 0


# ---------------------------------------------------------------------------
# Retry behaviour (rate-limit codes are retried, others propagate)
# ---------------------------------------------------------------------------


def test_retries_only_on_rate_limit():
    calls = []

    @concurrency_limit(retries=3, base_delay=0.01)
    def target():
        calls.append(1)
        if len(calls) < 3:
            raise _rate_limit_error()
        return "ok"

    with mock.patch("src.throttle.time.sleep"):
        assert target() == "ok"
    assert len(calls) == 3


def test_gives_up_after_retries():
    calls = []

    @concurrency_limit(retries=1, base_delay=0.01)
    def target():
        calls.append(1)
        raise _rate_limit_error()

    with mock.patch("src.throttle.time.sleep"):
        with pytest.raises(FacebookRequestError):
            target()
    assert len(calls) == 2  # initial + 1 retry


def test_non_rate_limit_propagates_immediately():
    calls = []

    @concurrency_limit(retries=3, base_delay=0.01)
    def target():
        calls.append(1)
        raise _other_error()

    with pytest.raises(FacebookRequestError):
        target()
    assert len(calls) == 1


def test_generic_exception_propagates_immediately():
    @concurrency_limit(retries=3, base_delay=0.01)
    def target():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        target()


# ---------------------------------------------------------------------------
# Concurrency cap (uses the shared global semaphore)
# ---------------------------------------------------------------------------


def test_parallel_calls_respect_global_cap():
    peak = 0
    lock = threading.Lock()
    results = []

    @concurrency_limit()
    def work(i):
        nonlocal peak
        with lock:
            peak = max(peak, concurrent_count())
        time.sleep(0.02)
        return i

    threads = [
        threading.Thread(target=lambda: results.append(work(i)))
        for i in range(MAX_CONCURRENT + 4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == MAX_CONCURRENT + 4
    assert peak <= MAX_CONCURRENT
    assert concurrent_count() == 0
