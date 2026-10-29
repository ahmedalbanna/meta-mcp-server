"""Tests for src.analytics pure helpers and tools."""

from datetime import date

import pytest

from src import analytics as a


def test_normalize_date_range_today():
    s, e = a.normalize_date_range("today", "Asia/Aden")
    assert s == e


def test_normalize_date_range_last_month():
    s, e = a.normalize_date_range("last_month", "Asia/Aden")
    assert s.endswith("-01")
    assert e > s


def test_zero_fill_daily():
    series = {"2026-10-02": 5.0}
    out = a.zero_fill_daily(series, date(2026, 10, 1), date(2026, 10, 3))
    assert len(out) == 3
    assert out[0]["value"] == 0.0
    assert out[1]["value"] == 5.0
    assert out[2]["value"] == 0.0


def test_invalid_preset_raises():
    with pytest.raises(ValueError):
        a.normalize_date_range("nope", "Asia/Aden")


def test_build_monthly_report_empty(mock_meta_sdk):
    from tests.conftest import TEST_SERVICES, Recorder

    rec = Recorder()
    a.register(rec, TEST_SERVICES)
    fn = rec.tools["build_monthly_report"]
    res = fn(year=2026, month=10, account_id="act_empty_xyz")
    import json

    data = json.loads(res)
    assert "entities" in data
    assert data["count"] == 0


def test_zero_fill_check_tool(mock_meta_sdk):
    from tests.conftest import TEST_SERVICES, Recorder

    rec = Recorder()
    a.register(rec, TEST_SERVICES)
    fn = rec.tools["zero_fill_check"]
    res = fn(start_date="2026-10-01", end_date="2026-10-03", account_id="act_empty_xyz")
    import json

    data = json.loads(res)
    assert data["days"] == 3
