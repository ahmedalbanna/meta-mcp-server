# OCR — `src/ocr.py`

> Optional OCR for competitor price extraction from images. Gated by
> `FB_ENABLE_OCR`. Requires `pytesseract` + the `tesseract` binary on PATH. Falls back
> gracefully when unavailable (returns empty results).

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `FB_ENABLE_OCR` | `false` | Enable OCR. Also requires `pytesseract` + `tesseract` binary. |

## Functions

| Function | Description |
|---|---|
| `is_available()` | Check whether `pytesseract` + `tesseract` binary are installed. |
| `extract_text_from_image(source)` | Extract text from an image URL or local path. Returns `""` if disabled/unavailable. |
| `extract_prices(text)` | Extract YER prices from OCR text (handles Arabic digits, "الف" thousands marker, "ريال"/"ر.ي"/"YER" markers, and bare numbers ≥1000). |
| `ocr_price_for_image(source)` | Convenience: OCR an image and return `{"ocr", "prices", "text"}`. |

## Price extraction rules

The extractor handles three price formats in Arabic/English text:

1. **Thousands**: `"12 ألف"` → `12000.0`, `"١٢ ألف"` → `12000.0` (Arabic digits translated).
2. **Riyal markers**: `"12000 ريال"`, `"ر.ي 500"`, `"500 YER"`.
3. **Bare numbers ≥1000**: `"السعر 25000"` → `25000.0`.

Arabic numerals (`٠١٢٣٤٥٦٧٨٩`) are translated to ASCII digits before parsing.

## Example

```python
from src.ocr import ocr_price_for_image

result = ocr_price_for_image("http://example.com/product.jpg")
# {"ocr": "ok", "prices": [12000.0], "text": "السعر ١٢٠٠٠ ريال ..."}
```

If OCR is disabled or the `tesseract` binary is missing, `ocr_price_for_image` returns
`{"ocr": "disabled_or_unavailable", "prices": [], "text": ""}`.
