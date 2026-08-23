# Meta MCP Server

> **199 tools + 3 resources + 2 prompts** — local-first MCP for Meta Marketing (Facebook / Instagram / WhatsApp)

[English](#) | [العربية](#ar)

## Quick start

```bash
git clone https://github.com/anomalyco/opencode-meta-mcp && cd meta-mcp-server
cp .env.example .env  # fill FB_*
pip install -r requirements.txt
python scripts/validate_config.py
pytest -q
python server.py  # or mcp dev server.py
```

See [Getting Started](getting-started.md) for opencode / Claude Desktop wiring.

## Highlights — Phase 1-5

- **Safety 5-guard:** `FB_ENABLE_WRITES`, `FB_DRY_RUN` (diff preview), `FB_ADS_ALLOW_ACTIVATE`, budget caps, `FB_CONFIRM_WRITES`
- **Paginate uniformly:** `src/utils.paginate` for all `list_*`
- **Automation:** `webhook_automations` + `scheduler` (APScheduler cron) + creative assistant (`generate_ad_copy`, `generate_caption_from_image`)
- **Observability:** `/metrics` (Prometheus), `/dashboard` (HTML), `correlation_id` tracing, adaptive throttle (`FB_ADAPTIVE_THROTTLE`), `get_metrics` MCP tool
- **Distribution:** PyPI `pipx install meta-mcp-server`, Docker `ghcr.io/anomalyco/opencode-meta-mcp`, `mkdocs` site

## Architecture

```
server.py (FastMCP meta-marketing-pro)
  ├─ discovery / campaigns / adsets / ads / insights / breakdowns / reports
  ├─ audiences (SHA-256) / pages (page token) / instagram (32 tools) / leads / messenger / whatsapp
  ├─ automation (ad rules) / finance / catalog (25 tools) / business / creatives
  ├─ webhook_automations (5) / scheduler (5) / metrics (3) / events (3)
  └─ resources_prompts (3R + 2P)
webhook_server.py (FastAPI)  :8080  → reports/webhooks/event_*.json (500 rotation)
```

See [Tools Reference](tools.md) — auto-generated via `python scripts/generate_docs.py`.

## Links

- `README.md` for env table & limits
- `ROADMAP.md` for phases 0-5
- `CONTRIBUTING.md` / `SECURITY.md`
