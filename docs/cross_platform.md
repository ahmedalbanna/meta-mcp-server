# Cross-Platform — `src/cross_platform.py`

> Cross-platform competitor intelligence (Phase 4). Best-effort, feature-gated scrapers
> for platforms Meta does not cover (TikTok) plus unified 360° views. TikTok scraping is
> fragile and gated behind `FB_CROSS_PLATFORM_TIKTOK`; treat results as indicative only.

## Tools

| Tool | Description |
|---|---|
| `tiktok_profile` | (Experimental) Fetch a public TikTok profile (name, bio, followers) via scraping. Requires `FB_CROSS_PLATFORM_TIKTOK=true`. |
| `whatsapp_business_link` | Generate a WhatsApp Click-to-Chat (`wa.me`) link for a number (Yemen `+967` default). |
| `competitor_360` | 360° view of a competitor across platforms: Instagram (Meta) + Facebook page + TikTok (if enabled) + WhatsApp link. |

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `FB_CROSS_PLATFORM_TIKTOK` | `false` | Enable TikTok scraping (fragile, results indicative only). |
| `FB_CROSS_PLATFORM_WHATSAPP_SCRAPE` | `false` | Enable WhatsApp scraping. |
| `FB_PHONE_COUNTRY_CODE` | `+967` | Default phone country code for WhatsApp links. |
| `FB_PAGE_ID` | — | Default page id (used by `competitor_360`). |

## Example

```python
from src.cross_platform_service import CrossPlatformService

svc = CrossPlatformService(services)
result = svc.competitor_360("competitor_handle", page_id="123456789", phone="+967777000111")
# Returns combined data from Instagram, Facebook, TikTok (if enabled), and WhatsApp link.
```
