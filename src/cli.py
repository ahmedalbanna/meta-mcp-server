"""CLI for meta-mcp-server — Phase 9.2.

Provides:
- meta-mcp --help
- meta-mcp doctor (env + SDK + tools smoke)
- meta-mcp count-tools (wrapper for scripts/count_tools.py)
- meta-mcp generate-docs
- meta-mcp run (stdio) / meta-mcp run --transport sse|streamable-http
"""

import argparse
import sys


def cmd_doctor(_args) -> int:
    """Check env, SDK, and tool registration."""
    print("== meta-mcp doctor ==")
    from src.core.config import BASE_DIR, GRAPH_VERSION, REPORT_DIR

    print(f"BASE_DIR: {BASE_DIR}")
    print(f"REPORT_DIR: {REPORT_DIR} exists={REPORT_DIR.exists()}")
    print(f"GRAPH_VERSION: {GRAPH_VERSION}")
    # Config
    try:
        from scripts.validate_config import main as validate_main

        # Don't fail, just info
        validate_main()
    except SystemExit as e:
        print(f"validate_config exit: {e.code}")
    except Exception as e:
        print(f"validate_config error: {e}")

    # SDK
    try:
        import facebook_business

        print(
            f"facebook-business: {facebook_business.__version__ if hasattr(facebook_business, '__version__') else 'unknown'}"
        )
    except Exception as e:
        print(f"facebook-business missing: {e}")

    try:
        import mcp

        print(f"mcp: {mcp.__version__ if hasattr(mcp, '__version__') else 'unknown'}")
    except Exception as e:
        print(f"mcp missing: {e}")

    # Tools smoke
    try:
        from tests.conftest import Recorder, register_all

        r = Recorder()
        register_all(r)
        print(f"tools: {len(r.tools)} resources: {len(r.resources)} prompts: {len(r.prompts)}")
        # Quick JSON check
        import json

        for _, fn in list(r.tools.items())[:3]:
            out = fn(
                **{
                    k: "test" if p.annotation is str else 1
                    for k, p in __import__("inspect").signature(fn).parameters.items()
                    if p.default == __import__("inspect").Parameter.empty
                }
            )
            json.loads(out)
        print("smoke: ok (3 tools JSON-valid)")
    except Exception as e:
        print(f"smoke failed: {e}")
        return 1

    print("doctor: ok")
    return 0


def cmd_count_tools(_args) -> int:
    import subprocess

    return subprocess.call([sys.executable, "scripts/count_tools.py"])


def cmd_generate_docs(_args) -> int:
    import subprocess

    return subprocess.call([sys.executable, "scripts/generate_docs.py"])


def cmd_run(args) -> int:
    """Run MCP server (stdio/sse/streamable-http)."""
    import os

    if args.transport:
        os.environ["MCP_TRANSPORT"] = args.transport
    if args.host:
        os.environ["MCP_HOST"] = args.host
    if args.port:
        os.environ["MCP_PORT"] = str(args.port)
    from server import main as server_main

    server_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="meta-mcp", description="Meta Marketing MCP Server — 201 tools")
    p.add_argument("--version", action="version", version="%(prog)s 2.0.0")
    sub = p.add_subparsers(dest="cmd", required=False)

    # Default: help if no subcommand, but also allow `meta-mcp` to run doctor
    d = sub.add_parser("doctor", help="Check env, SDK, tools")
    d.set_defaults(func=cmd_doctor)

    c = sub.add_parser("count-tools", help="Count tools/resources/prompts")
    c.set_defaults(func=cmd_count_tools)

    g = sub.add_parser("generate-docs", help="Generate docs/tools.md")
    g.set_defaults(func=cmd_generate_docs)

    r = sub.add_parser("run", help="Run MCP server")
    r.add_argument(
        "--transport", choices=["stdio", "sse", "streamable-http"], default=None, help="Transport (env MCP_TRANSPORT)"
    )
    r.add_argument("--host", default=None, help="Host for http transports")
    r.add_argument("--port", type=int, default=None, help="Port for http transports")
    r.set_defaults(func=cmd_run)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
