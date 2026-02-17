"""
Goldflipper MCP Server

Exposes the Goldflipper trading system via the Model Context Protocol (MCP)
using Streamable HTTP transport. Run as a standalone service:

    uv run goldflipper-mcp
    uv run goldflipper-mcp --port 9000

Connect from any MCP client:
    claude mcp add --transport http goldflipper http://localhost:8787/mcp/
"""

from goldflipper.mcp_server.server import create_server

__all__ = ["create_server"]
