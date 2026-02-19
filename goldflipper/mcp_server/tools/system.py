"""System health and diagnostics tools."""

from goldflipper.mcp_server.context import ctx
from goldflipper.mcp_server.server import mcp


@mcp.tool
def get_system_health() -> dict:
    """Check Goldflipper system health: config loaded, providers available, active account.

    Call this first to verify the system is operational before using other tools.
    """
    health = {
        "config_loaded": False,
        "active_account": None,
        "market_data_providers": [],
        "plays_directory": None,
        "errors": [],
    }

    # Check config
    try:
        cfg = ctx.config
        if cfg._config:
            health["config_loaded"] = True
            health["active_account"] = cfg.get("alpaca", "active_account", default="unknown")
        else:
            health["errors"].append("Config is empty — settings.yaml may not exist")
    except Exception as e:
        health["errors"].append(f"Config load failed: {e}")

    # Check market data providers
    try:
        mdm = ctx.market_data
        health["market_data_providers"] = list(mdm.providers.keys())
    except Exception as e:
        health["errors"].append(f"MarketDataManager init failed: {e}")

    # Check plays directory
    try:
        pm = ctx.play_manager
        health["plays_directory"] = pm.plays_base_dir
    except Exception as e:
        health["errors"].append(f"PlayManager init failed: {e}")

    health["status"] = "healthy" if not health["errors"] else "degraded"
    return health
