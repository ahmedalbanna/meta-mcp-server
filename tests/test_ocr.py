"""Tests for src.ocr helpers."""

from src import ocr


def test_extract_prices_arabic_digits():
    text = "السعر ١٢٠٠٠ ريال"
    prices = ocr.extract_prices(text)
    assert 12000.0 in prices


def test_extract_prices_thousands_marker():
    prices = ocr.extract_prices("12 الف")
    assert 12000.0 in prices


def test_extract_prices_disabled(monkeypatch):
    monkeypatch.setenv("FB_ENABLE_OCR", "false")
    import importlib

    import src.core.config as cfg
    importlib.reload(cfg)
    assert ocr.extract_text_from_image("http://example.com/x.jpg") == ""
    res = ocr.ocr_price_for_image("http://example.com/x.jpg")
    assert res["prices"] == []


def test_is_available_returns_bool():
    assert isinstance(ocr.is_available(), bool)
