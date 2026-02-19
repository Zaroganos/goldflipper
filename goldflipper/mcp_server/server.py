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
    from goldflipper.mcp_server.tools import analytics, config_tools, market_data, orders, plays, portfolio, strategies, strategy_dev, system

    _ = (analytics, config_tools, market_data, orders, plays, portfolio, strategies, strategy_dev, system)


def create_server() -> FastMCP:
    """Create and return the fully configured MCP server."""
    _register_tools()
    return mcp
