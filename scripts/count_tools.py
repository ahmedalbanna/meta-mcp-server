#!/usr/bin/env python3
"""Count MCP tools/resources/prompts and sync README + pyproject.

Scans src/*.py for @mcp.tool / @mcp.resource / @mcp.prompt decorators,
updates:
- README.md first header line: ## المزايا (X أداة + Y موارد + Z مطالبات)
- pyproject.toml description field
- Optionally prints a detailed per-module table for copy-paste into README.
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "src"
README = BASE / "README.md"
PYPROJECT = BASE / "pyproject.toml"

TOOL_RE = re.compile(r"@mcp\.tool\(\)")
RES_RE = re.compile(r"@mcp\.resource\(")
PROMPT_RE = re.compile(r"@mcp\.prompt\(\)")


def count_in_file(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8")
    return len(TOOL_RE.findall(text)), len(RES_RE.findall(text)), len(PROMPT_RE.findall(text))


def main(update: bool = True) -> int:
    total_tools = total_res = total_prompts = 0
    per_module = {}
    for py in sorted(SRC.glob("*.py")):
        t, r, p = count_in_file(py)
        if t or r or p:
            per_module[py.stem] = (t, r, p)
            total_tools += t
            total_res += r
            total_prompts += p

    print(f"Tools: {total_tools}, Resources: {total_res}, Prompts: {total_prompts}")
    for mod, (t, r, p) in per_module.items():
        print(f"  {mod:20} tools={t:3} resources={r} prompts={p}")

    if not update:
        return 0

    # --- Update README.md ---
    if README.exists():
        text = README.read_text(encoding="utf-8")
        # Match pattern like "## المزايا (155 أداة + 3 موارد + 2 مطالبات)"
        new_header = f"## المزايا ({total_tools} أداة + {total_res} موارد + {total_prompts} مطالبات)"
        # Replace header line
        updated = re.sub(r"## المزايا \([^)]+\)", new_header, text)
        if updated != text:
            README.write_text(updated, encoding="utf-8")
            print(f"Updated {README} header -> {new_header}")
        else:
            print("README header already up to date")

        # Update description-like comment if present? We also update pyproject below.

    # --- Update pyproject.toml ---
    if PYPROJECT.exists():
        text = PYPROJECT.read_text(encoding="utf-8")
        # Update description field: description = "Meta Marketing MCP Server — 155+ tools ..."
        new_desc = f'description = "Meta Marketing MCP Server — {total_tools} tools for Facebook/Instagram/WhatsApp advertising"'
        updated = re.sub(r'description = "Meta Marketing MCP Server — [^"]+"', new_desc, text)
        if updated != text:
            PYPROJECT.write_text(updated, encoding="utf-8")
            print(f"Updated {PYPROJECT} description -> {new_desc}")
        else:
            print("pyproject description already up to date")

    return 0


if __name__ == "__main__":
    sys.exit(main(update="--no-update" not in sys.argv))
