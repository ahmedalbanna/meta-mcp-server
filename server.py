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
    audiences,
    automation,
    breakdowns,
    business,
    campaigns,
    catalog,
    creatives,
    discovery,
    finance,
    insights,
    instagram,
    leads,
    messenger,
    pages,
    reports,
    resources_prompts,
    whatsapp,
)
from src.config import validate_config
from src.helpers import init_meta_api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("meta-mcp")

mcp = FastMCP("meta-marketing-pro")


def main() -> None:
    missing = validate_config()
    if missing:
        log.error("متغيرات بيئية ناقصة في ملف .env: %s", ", ".join(missing))
        log.error("انسخ .env.example إلى .env وعبّئ القيم، ثم أعد التشغيل.")
        sys.exit(1)

    init_meta_api()
    log.info("تم تهيئة Facebook Ads API")

    # Register all tool modules
    for module in (
        discovery,
        campaigns,
        adsets,
        ads,
        insights,
        breakdowns,
        reports,
        audiences,
        pages,
        instagram,
        leads,
        messenger,
        automation,
        finance,
        catalog,
        business,
        creatives,
        whatsapp,
        resources_prompts,
    ):
        module.register(mcp)
        log.info("تم تسجيل وحدة %s", module.__name__.split(".")[-1])

    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio")
    log.info(f"تشغيل خادم MCP: meta-marketing-pro (النقل: {mcp_transport})")
    mcp.run(transport=mcp_transport)


if __name__ == "__main__":
    main()
