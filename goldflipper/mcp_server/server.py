"""
FastMCP server instance and tool registration for Goldflipper.

Creates the FastMCP server and registers all tool modules.
"""

from fastmcp import FastMCP

# The FastMCP instance — tool modules import this to register via @mcp.tool
mcp = FastMCP(
    name="Goldflipper Trading System",
    instructions=(
        "You are connected to the Goldflipper options trading system. "
        "You can query market data, manage plays (trade files), view portfolio positions, "
        "and monitor strategy execution. "
        "Start with get_system_health to verify the system is operational, "
        "then get_active_account to see which trading account is active."
    ),
)


def _register_tools():
    """Import all tool modules to trigger their @mcp.tool registrations."""
    # Phase 1: Read-only tools
    # Phase 2: Orders & trading
    # Phase 3: Strategy development & config
    # Phase 4: Analytics
    from goldflipper.mcp_server.tools import (
        analytics,  # noqa: F401
        config_tools,  # noqa: F401
        market_data,  # noqa: F401
        orders,  # noqa: F401
        plays,  # noqa: F401
        portfolio,  # noqa: F401
        strategies,  # noqa: F401
        strategy_dev,  # noqa: F401
        system,  # noqa: F401
    )


def create_server() -> FastMCP:
    """Create and return the fully configured MCP server."""
    _register_tools()
    return mcp
