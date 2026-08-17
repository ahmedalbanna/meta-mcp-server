"""Meta Marketing MCP server - comprehensive Facebook/Instagram marketing assistant.

Run locally (stdio transport) and connect from Claude Desktop / Cursor / any MCP client.
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from src import (
    ads,
    adsets,
    audiences,
    automation,
    campaigns,
    discovery,
    finance,
    insights,
    instagram,
    pages,
    reports,
    resources_prompts,
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
        reports,
        audiences,
        pages,
        instagram,
        automation,
        finance,
        resources_prompts,
    ):
        module.register(mcp)
        log.info("تم تسجيل وحدة %s", module.__name__.split(".")[-1])

    log.info("تشغيل خادم MCP: meta-marketing-pro")
    mcp.run()


if __name__ == "__main__":
    main()
