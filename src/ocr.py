"""Optional OCR for competitor price extraction from images.

Gated by FB_ENABLE_OCR. Requires pytesseract + tesseract binary on PATH.
Falls back gracefully when unavailable.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_AVAILABLE: bool | None = None


def is_available() -> bool:
    global _AVAILABLE
    if _AVAILABLE is not None:
        return _AVAILABLE
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        # check binary
        pytesseract.get_tesseract_version()
        _AVAILABLE = True
    except Exception as e:
        logger.info("OCR unavailable: %s", e)
        _AVAILABLE = False
    return _AVAILABLE


def _enabled() -> bool:
    from src.config import FB_ENABLE_OCR
    return bool(FB_ENABLE_OCR) and is_available()


def extract_text_from_image(source: str) -> str:
    """Extract text from image URL or local path. Returns '' if disabled/unavailable."""
    if not _enabled():
        return ""
    try:
        import pytesseract
        from PIL import Image

        if source.startswith("http://") or source.startswith("https://"):
            import io
            import urllib.request
            with urllib.request.urlopen(source, timeout=30) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data))
        else:
            img = Image.open(source)
        return str(pytesseract.image_to_string(img, lang="ara+eng"))
    except Exception as e:
        logger.warning("OCR failed for %s: %s", source, e)
        return ""


def extract_prices(text: str) -> list[float]:
    """Extract prices (YER) from OCR text, handling Arabic digits and thousands."""
    if not text:
        return []
    t = text.translate(_DIGIT_MAP)
    out: list[float] = []
    # thousands: "12 الف"
    for m in re.finditer(r"(\d[\d.,]*)\s*(?:ألف|الف)", t):
        with contextlib.suppress(ValueError):
            out.append(round(float(m.group(1).replace(",", "")) * 1000, 2))
    # riyal markers
    for m in re.finditer(r"(\d[\d.,]*)\s*(?:ريال|ر\.ي|YER)", t):
        with contextlib.suppress(ValueError):
            out.append(round(float(m.group(1).replace(",", "")), 2))
    # bare numbers >= 1000 treated as prices
    for m in re.finditer(r"(?<!\d)(\d{4,})(?!\d)", t):
        with contextlib.suppress(ValueError):
            v = float(m.group(1))
            if v not in out:
                out.append(round(v, 2))
    # dedupe preserving order
    seen = set()
    uniq = []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def ocr_price_for_image(source: str) -> dict[str, Any]:
    """Convenience: OCR an image and return extracted prices + raw text."""
    if not _enabled():
        return {"ocr": "disabled_or_unavailable", "prices": [], "text": ""}
    text = extract_text_from_image(source)
    return {"ocr": "ok", "prices": extract_prices(text), "text": text[:500]}
