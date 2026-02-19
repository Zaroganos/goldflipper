"""Strategy listing and status tools."""

import yaml

from goldflipper.mcp_server.context import ctx
from goldflipper.mcp_server.server import mcp

# Known strategy config keys in settings.yaml
_STRATEGY_KEYS = [
    "options_swings",
    "option_swings_auto",
    "momentum",
    "sell_puts",
    "spreads",
]


@mcp.tool
def list_strategies() -> dict:
    """List all registered strategies and their enabled/disabled status from config.

    Returns:
        Dict with orchestration mode and list of strategies with their
        enabled status and config key.
    """
    cfg = ctx.config

    # Orchestration settings
    orch = {
        "enabled": cfg.get("strategy_orchestration", "enabled", default=False),
        "mode": cfg.get("strategy_orchestration", "mode", default="sequential"),
        "max_parallel_workers": cfg.get("strategy_orchestration", "max_parallel_workers", default=3),
        "dry_run": cfg.get("strategy_orchestration", "dry_run", default=False),
    }

    strategies = []
    for key in _STRATEGY_KEYS:
        section = cfg.get(key, default={})
        if section:
            strategies.append(
                {
                    "config_key": key,
                    "enabled": section.get("enabled", False),
                }
            )
        else:
            strategies.append(
                {
                    "config_key": key,
                    "enabled": False,
                    "note": "No config section found",
                }
            )

    return {
        "orchestration": orch,
        "strategies": strategies,
    }


@mcp.tool
def toggle_strategy(strategy_key: str, enabled: bool, confirm: bool = False) -> dict:
    """Enable or disable a strategy in settings.yaml.

    Args:
        strategy_key: The strategy config key (e.g., 'options_swings', 'momentum',
                      'sell_puts', 'spreads', 'option_swings_auto').
        enabled: True to enable, False to disable.
        confirm: Set to True to actually save. Default False returns a preview.

    Returns:
        Preview or confirmation of the change.
    """
    if strategy_key not in _STRATEGY_KEYS:
        return {"error": f"Unknown strategy key '{strategy_key}'. Valid keys: {', '.join(_STRATEGY_KEYS)}"}

    cfg = ctx.config
    current_section = cfg.get(strategy_key, default={})
    current_enabled = current_section.get("enabled", False) if current_section else False

    if not confirm:
        return {
            "preview": True,
            "strategy_key": strategy_key,
            "current_enabled": current_enabled,
            "new_enabled": enabled,
            "message": f"Would {'enable' if enabled else 'disable'} strategy '{strategy_key}'. Set confirm=True to save.",
        }

    # Load and modify settings.yaml directly
    from goldflipper.utils.exe_utils import get_settings_path

    settings_path = str(get_settings_path())
    try:
        with open(settings_path) as f:
            settings = yaml.safe_load(f) or {}
    except Exception as e:
        return {"error": f"Failed to load settings.yaml: {e}"}

    if strategy_key not in settings:
        settings[strategy_key] = {}
    settings[strategy_key]["enabled"] = enabled

    try:
        with open(settings_path, "w") as f:
            yaml.dump(settings, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        return {"error": f"Failed to save settings.yaml: {e}"}

    # Reload config
    try:
        cfg.reload()
    except Exception:
        pass

    return {
        "strategy_key": strategy_key,
        "previous_enabled": current_enabled,
        "enabled": enabled,
        "saved": True,
    }
