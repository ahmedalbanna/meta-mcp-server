"""Meta Marketing MCP server - comprehensive Facebook/Instagram marketing assistant.

Run locally (stdio transport) and connect from Claude Desktop / Cursor / any MCP client.
"""

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from src import (
    ads,
    adsets,
    analytics,
    audiences,
    automation,
    breakdowns,
    business,
    campaigns,
    catalog,
    competitor_catalog,
    competitor_content,
    competitors,
    content_tools,
    creatives,
    cross_platform,
    discovery,
    events,
    finance,
    insights,
    instagram,
    leads,
    media_tools,
    messenger,
    metrics,
    page_builder,
    pages,
    reports,
    scheduler,
    webhook_automations,
    whatsapp,
    yemen_bundle,
)
from src.config import validate_config
from src.core.services import Services
from src.helpers import init_meta_api
from src.throttle import MAX_CONCURRENT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("meta-mcp")

mcp = FastMCP(
    "meta-marketing-pro",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", os.getenv("PORT", "8000"))),
)


# Log + swallow unhandled tool exceptions so a single bad request can never take
# down the stdio transport (a crash here previously dropped the whole session).
def _install_exception_hook() -> None:
    def hook(etype, value, tb):
        log.error("استثناء غير معالج داخل خادم MCP: %s: %s", etype.__name__, value)
        log.debug("traceback:", exc_info=(etype, value, tb))

    sys.excepthook = hook


def main() -> None:
    missing = validate_config()
    if missing:
        log.error("متغيرات بيئية ناقصة في ملف .env: %s", ", ".join(missing))
        log.error("انسخ .env.example إلى .env وعبّئ القيم، ثم أعد التشغيل.")
        sys.exit(1)

    init_meta_api()
    log.info("تم تهيئة Facebook Ads API")
    _install_exception_hook()
    log.info("حد التوازي لطلبات Graph API: %d", MAX_CONCURRENT)

    services = Services.default()
    # Register all tool modules (Phase 5 distributed resources/prompts per module)
    for module in (
        discovery,
        campaigns,
        adsets,
        ads,
        insights,
        analytics,
        breakdowns,
        reports,
        audiences,
        pages,
        page_builder,
        instagram,
        media_tools,
        leads,
        messenger,
        automation,
        finance,
        catalog,
        business,
        creatives,
        content_tools,
        cross_platform,
        competitor_content,
        competitors,
        competitor_catalog,
        whatsapp,
        events,
        webhook_automations,
        scheduler,
        metrics,
        yemen_bundle,
    ):
        module.register(mcp, services)
        log.info("تم تسجيل وحدة %s", module.__name__.split(".")[-1])

    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("MCP_PORT", os.getenv("PORT", "8000")))
    log.info(f"تشغيل خادم MCP: meta-marketing-pro (النقل: {mcp_transport} host={mcp_host}:{mcp_port})")
    # Phase 9.1: Support sse / streamable-http for mcp-remote and HTTP clients
    if mcp_transport in ("sse", "streamable-http", "http"):
        try:
            # FastMCP 1.29+ supports host/port kwargs for HTTP transports
            mcp.run(transport=mcp_transport, host=mcp_host, port=mcp_port)  # type: ignore[call-arg,arg-type]
        except TypeError:
            # Fallback for older FastMCP that only accepts transport
            mcp.run(transport=mcp_transport)  # type: ignore[arg-type]  # type: ignore[arg-type]
    else:
        mcp.run(transport=mcp_transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
