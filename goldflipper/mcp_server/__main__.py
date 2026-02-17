"""
Entry point for the Goldflipper MCP Server.

Usage:
    uv run goldflipper-mcp                    # Default: localhost:8787
    uv run goldflipper-mcp --port 9000        # Custom port
    python -m goldflipper.mcp_server          # Alternative invocation
"""

import argparse

from goldflipper.mcp_server.server import create_server


def main():
    parser = argparse.ArgumentParser(description="Goldflipper MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="Port number (default: 8787)")
    args = parser.parse_args()

    mcp = create_server()
    mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
