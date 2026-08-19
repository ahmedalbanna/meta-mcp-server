#!/usr/bin/env python3
"""Run MCP server via stdio (for testing without restarting opencode)."""
import sys
import os

# Load .env before importing server
from dotenv import load_dotenv
load_dotenv()

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
