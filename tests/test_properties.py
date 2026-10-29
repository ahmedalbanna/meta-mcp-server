"""Property-based tests (hypothesis) for pure business logic."""

from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.analytics import normalize_date_range, zero_fill_daily
from src.competitor_catalog import _extract_price
from src.ocr import extract_prices
from src.services.page_builder_service import normalize_phone

# --- phone normalization ------------------------------------------------

_phone_chars = st.sampled_from("0123456789 +-")
_phones = st.text(alphabet=_phone_chars, min_size=1, max_size=18)


@given(phone=_phones)
@settings(max_examples=200)
def test_normalize_phone_e164_or_none(phone):
    result = normalize_phone(phone, "+967")
    if result is not None:
        assert result.startswith("+967")
        digits = result.lstrip("+")
        assert digits.isdigit()
        assert 8 <= len(digits) <= 15


@given(
    national=st.text(alphabet="0123456789", min_size=7, max_size=9),
    sep=st.sampled_from(["", " ", "-"]),
)
@settings(max_examples=150)
def test_normalize_phone_idempotent(national, sep):
    raw = sep.join(national) if sep else national
    first = normalize_phone(raw, "+967")
    if first is None:
        return
    # feeding the E.164 back must be a no-op (already normalized)
    second = normalize_phone(first, "+967")
    assert second == first


# --- price extraction ---------------------------------------------------

@given(
    num=st.integers(min_value=1, max_value=999999),
    marker=st.sampled_from(["ريال", "YER", "ر.ي"]),
)
@settings(max_examples=150)
def test_extract_prices_riyal(num, marker):
    text = f"السعر {num} {marker}"
    prices = extract_prices(text)
    assert float(num) in prices


@given(thousands=st.integers(min_value=1, max_value=999))
@settings(max_examples=100)
def test_extract_prices_thousands(thousands):
    prices = extract_prices(f"سعرها {thousands} ألف")
    assert round(thousands * 1000, 2) in prices


@given(text=st.text(max_size=40))
@settings(max_examples=100)
def test_extract_prices_never_crashes(text):
    # pure function: must return a list of floats
    prices = extract_prices(text)
    assert isinstance(prices, list)
    assert all(isinstance(p, float) for p in prices)


@given(num=st.integers(min_value=100, max_value=10_000))
@settings(max_examples=100)
def test_extract_price_caption_riyal(num):
    assert _extract_price(f"الحلق بسعر {num} ريال") == float(num)


# --- date range + zero-fill ---------------------------------------------

@given(preset=st.sampled_from(["today", "yesterday", "last_7d", "last_30d", "this_month", "last_month"]))
@settings(max_examples=60)
def test_normalize_date_range_ordering(preset):
    s, e = normalize_date_range(preset, "Asia/Aden")
    assert s <= e  # start <= end


@given(preset=st.sampled_from(["invalid_preset", "nope", ""]))
def test_normalize_date_range_invalid_raises(preset):
    with pytest.raises(ValueError):
        normalize_date_range(preset, "Asia/Aden")


@given(days=st.integers(min_value=1, max_value=15))
@settings(max_examples=60)
def test_zero_fill_contiguous(days):
    start = date(2026, 10, 1)
    end = start + timedelta(days=days - 1)
    series = {}
    out = zero_fill_daily(series, start, end)
    assert len(out) == days
    # contiguous ascending dates
    dates = [date.fromisoformat(r["date"]) for r in out]
    assert dates == sorted(dates)
    for i in range(1, len(dates)):
        assert (dates[i] - dates[i - 1]).days == 1


@given(
    values=st.dictionaries(
        keys=st.dates(min_value=date(2026, 10, 1), max_value=date(2026, 10, 15)).map(lambda d: d.isoformat()),
        values=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        max_size=15,
    )
)
@settings(max_examples=60)
def test_zero_fill_preserves_values(values):
    start = date(2026, 10, 1)
    end = date(2026, 10, 15)
    out = zero_fill_daily(values, start, end)
    by_date = {r["date"]: r["value"] for r in out}
    for d, v in values.items():
        assert by_date[d] == pytest.approx(v)
