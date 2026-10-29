# Page Builder — `src/page_builder.py`

> Page & store builder for our own account, inspired by competitor analysis. Phase 3:
> improve/develop OUR page/store using competitor insights, with Yemen defaults
> (YER, +967, Asia/Aden) and WhatsApp CTA validation.

## Tools

| Tool | Description |
|---|---|
| `validate_phone_number` | Validate a phone number and convert to E.164 (default `+967` Yemen). |
| `generate_whatsapp_cta_link` | Generate a `wa.me` Click-to-Chat link for use in CTA. |
| `page_building_checklist` | Checklist for building/improving a page: cover, profile photo, CTA, about, hours, location, pinned post, description. |
| `update_page_about` | Update page "about" text (write-guarded). |
| `update_page_cta_whatsapp` | Set page CTA to WhatsApp (Click-to-Chat) with `+967` phone validation (write-guarded). |
| `build_page_from_competitor` | Build/improve our page inspired by a competitor: pull their data (followers, cadence, hashtags, prices) and generate recommendations + apply changes (dry-run unless `FB_ENABLE_WRITES`). |

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `FB_PHONE_COUNTRY_CODE` | `+967` | Default phone country code (Yemen). |
| `FB_PAGE_ID` | — | Default page id. |
| `FB_ENABLE_WRITES` | `false` | Required for write operations (`update_page_about`, `update_page_cta_whatsapp`). |

## Example

```python
from src.page_builder_service import PageBuilderService

svc = PageBuilderService(services)
result = svc.validate_phone("777000111", "+967")
# {"phone": "+967777000111", "valid": True, "country_code": "+967"}
```
