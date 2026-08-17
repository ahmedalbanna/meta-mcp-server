"""Unit tests for src/utils.py — no network involved."""

import hashlib
import time
from unittest import mock

import pytest
from facebook_business.exceptions import FacebookRequestError

from src.utils import (
    cached,
    get_correlation_id,
    normalize_email,
    normalize_phone,
    normalize_pii,
    paginate,
    retry_on_rate_limit,
    set_correlation_id,
)


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
# paginate
# ---------------------------------------------------------------------------


def test_paginate_raw_dict_with_cursor():
    calls = []

    def getter(params):
        calls.append(dict(params))
        if params.get("after") == "c2":
            return {"data": [{"id": "3"}], "paging": {}}
        return {
            "data": [{"id": "1"}, {"id": "2"}],
            "paging": {"cursors": {"after": "c2", "before": "b0"}},
        }

    rows = paginate(getter, fields=["id"], limit=2)
    assert rows == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert len(calls) == 2
    assert "after" not in calls[0]
    assert calls[1]["after"] == "c2"


def test_paginate_stops_when_no_cursor():
    calls = []

    def getter(params):
        calls.append(params)
        return {"data": [{"id": "1"}], "paging": {}}

    rows = paginate(getter, fields=["id"], limit=25)
    assert rows == [{"id": "1"}]
    assert len(calls) == 1


def test_paginate_respects_max_pages():
    def getter(params):
        return {"data": [{"id": "x"}], "paging": {"cursors": {"after": "again"}}}

    rows = paginate(getter, fields=["id"], limit=1, max_pages=3)
    assert len(rows) == 3


def test_paginate_handles_sdk_collection():
    class FakeItem:
        def __init__(self, data):
            self._data = data

        def export_all_data(self):
            return self._data

    class FakeCollection:
        def __init__(self, items, after):
            self.items = items
            self.after = after

        def __iter__(self):
            return iter(self.items)

        def get_cursors(self):
            return {"after": self.after} if self.after else {}

    first = FakeCollection([FakeItem({"id": "1"})], after="c2")
    second = FakeCollection([FakeItem({"id": "2"})], after="")

    def getter(params):
        return first if not params.get("after") else second

    rows = paginate(getter, fields=["id"])
    assert rows == [{"id": "1"}, {"id": "2"}]


# ---------------------------------------------------------------------------
# retry_on_rate_limit
# ---------------------------------------------------------------------------


def test_retry_succeeds_after_rate_limits():
    fn = mock.Mock(side_effect=[_rate_limit_error(), _rate_limit_error(), {"ok": True}])
    wrapped = retry_on_rate_limit(retries=3, base_delay=0.01)(fn)
    with mock.patch("src.utils.time.sleep"):
        result = wrapped()
    assert result == {"ok": True}
    assert fn.call_count == 3


def test_retry_gives_up_after_retries():
    fn = mock.Mock(side_effect=_rate_limit_error())
    wrapped = retry_on_rate_limit(retries=2, base_delay=0.01)(fn)
    with mock.patch("src.utils.time.sleep"):
        with pytest.raises(FacebookRequestError):
            wrapped()
    assert fn.call_count == 3  # initial + 2 retries


def test_non_rate_limit_error_propagates_immediately():
    fn = mock.Mock(side_effect=_other_error())
    wrapped = retry_on_rate_limit(retries=3, base_delay=0.01)(fn)
    with pytest.raises(FacebookRequestError):
        wrapped()
    assert fn.call_count == 1


# ---------------------------------------------------------------------------
# PII normalisation
# ---------------------------------------------------------------------------


def test_normalize_email_lowercases_and_hashes():
    assert normalize_email("  Foo@BAR.COM ") == hashlib.sha256(b"foo@bar.com").hexdigest()


def test_normalize_phone_strips_formatting():
    expected = hashlib.sha256(b"+15551234567").hexdigest()
    assert normalize_phone("+1 (555) 123-4567") == expected
    assert normalize_phone("15551234567") == hashlib.sha256(b"15551234567").hexdigest()


def test_normalize_pii_drops_empty_entries():
    out = normalize_pii(["a@b.com", " ", ""], pii_type="email")
    assert out == [hashlib.sha256(b"a@b.com").hexdigest()]


def test_normalize_pii_phone_mode():
    out = normalize_pii(["+966 5 0000 0000"], pii_type="phone")
    assert out == [hashlib.sha256(b"+966500000000").hexdigest()]


# ---------------------------------------------------------------------------
# cached
# ---------------------------------------------------------------------------


def test_cached_memoizes():
    calls = []

    @cached(ttl=60)
    def double(x):
        calls.append(x)
        return x * 2

    assert double(2) == 4
    assert double(2) == 4
    assert calls == [2]


def test_cached_expires_after_ttl():
    calls = []

    @cached(ttl=0.05)
    def stamp(x):
        calls.append(x)
        return time.monotonic()

    first = stamp(1)
    assert stamp(1) == first
    time.sleep(0.08)
    assert stamp(1) != first
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# correlation id
# ---------------------------------------------------------------------------


def test_correlation_id_roundtrip():
    set_correlation_id("req")
    assert get_correlation_id().startswith("req-")
