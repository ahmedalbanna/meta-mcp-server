"""Live integration tests (Meta Graph API).

Gated by ``FB_LIVE_TESTS=true``. These tests hit the real Graph API and require
valid ``FB_ACCESS_TOKEN`` / ``FB_AD_ACCOUNT_ID`` / ``FB_PAGE_ID`` in the environment.

Run with::

    FB_LIVE_TESTS=true pytest tests/test_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from src.core.services import Services

pytestmark = pytest.mark.skipif(
    os.getenv("FB_LIVE_TESTS") != "true",
    reason="live integration tests require FB_LIVE_TESTS=true",
)


@pytest.fixture(scope="module")
def services():
    return Services.default()


# ---------------------------------------------------------------------------
# analytics
# ---------------------------------------------------------------------------


def test_analytics_zero_fill_check_live(services):
    from src import analytics

    rec = type("R", (), {"tools": {}})()

    class Recorder:
        def __init__(self):
            self.tools = {}
            self.resources = []
            self.prompts = []

        def tool(self, *a, **k):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn

            return deco

        def resource(self, *a, **k):
            return lambda fn: fn

        def prompt(self, *a, **k):
            return lambda fn: fn

    rec = Recorder()
    analytics.register(rec, services)
    fn = rec.tools["zero_fill_check"]
    import json

    res = fn(start_date="2026-10-01", end_date="2026-10-02")
    data = json.loads(res)
    assert "days" in data
    assert data["days"] == 2


# ---------------------------------------------------------------------------
# page_builder
# ---------------------------------------------------------------------------


def test_page_builder_validate_phone_live(services):
    from src import page_builder

    class Recorder:
        def __init__(self):
            self.tools = {}

        def tool(self, *a, **k):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn

            return deco

    rec = Recorder()
    page_builder.register(rec, services)
    fn = rec.tools["validate_phone_number"]
    import json

    # Yemeni number without country code -> should be normalized to +967...
    res = fn(phone="777000111")
    data = json.loads(res)
    assert "phone" in data


# ---------------------------------------------------------------------------
# ocr (pure helper, no network)
# ---------------------------------------------------------------------------


def test_ocr_extract_prices_live():
    from src import ocr

    prices = ocr.extract_prices("السعر ١٢٠٠٠ ريال")
    assert 12000.0 in prices


# ---------------------------------------------------------------------------
# cross_platform (whatsApp link, pure helper)
# ---------------------------------------------------------------------------


def test_cross_platform_whatsapp_link_live(services):
    from src import cross_platform

    class Recorder:
        def __init__(self):
            self.tools = {}

        def tool(self, *a, **k):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn

            return deco

    rec = Recorder()
    cross_platform.register(rec, services)
    fn = rec.tools["whatsapp_business_link"]
    import json

    res = fn(phone="777000111")
    data = json.loads(res)
    assert "wa.me" in res or "wa_link" in data or "link" in data
