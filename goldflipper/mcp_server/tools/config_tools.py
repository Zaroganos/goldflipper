"""Configuration read/write tools for settings.yaml."""

import yaml

from goldflipper.mcp_server.context import ctx
from goldflipper.mcp_server.server import mcp


def _get_settings_path() -> str:
    """Get the path to settings.yaml."""
    from goldflipper.utils.exe_utils import get_settings_path

    return str(get_settings_path())


def _load_settings() -> dict:
    """Load settings.yaml as a dict."""
    path = _get_settings_path()
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_settings(data: dict) -> None:
    """Save settings dict back to settings.yaml."""
    path = _get_settings_path()
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


@mcp.tool
def get_config_value(key_path: str) -> dict:
    """Read a value from settings.yaml using dot-notation path.

    Args:
        key_path: Dot-separated path to the config value
                  (e.g., 'alpaca.active_account', 'monitoring.polling_interval',
                  'options_swings.enabled').

    Returns:
        Dict with the key path and its current value, or error.
    """
    try:
        settings = _load_settings()
    except FileNotFoundError:
        return {"error": "settings.yaml not found"}
    except Exception as e:
        return {"error": f"Failed to load settings: {e}"}

    keys = key_path.split(".")
    value = settings
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return {"error": f"Key '{key_path}' not found in settings (failed at '{key}')"}

    return {"key": key_path, "value": value}


@mcp.tool
def set_config_value(key_path: str, value: str, confirm: bool = False) -> dict:
    """Set a value in settings.yaml using dot-notation path.

    The value is parsed as YAML, so you can set strings, numbers, booleans, lists, etc.

    Args:
        key_path: Dot-separated path (e.g., 'monitoring.polling_interval').
        value: New value as a YAML-parseable string (e.g., '30', 'true', '"my string"').
        confirm: Set to True to actually save. Default False returns a preview.

    Returns:
        Preview or confirmation of the change.
    """
    # Parse the value as YAML
    try:
        parsed_value = yaml.safe_load(value)
    except yaml.YAMLError as e:
        return {"error": f"Could not parse value as YAML: {e}"}

    try:
        settings = _load_settings()
    except Exception as e:
        return {"error": f"Failed to load settings: {e}"}

    # Navigate to the parent key
    keys = key_path.split(".")
    current = settings
    for key in keys[:-1]:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, dict):
            # Key doesn't exist — will create it
            current[key] = {}
            current = current[key]
        else:
            return {"error": f"Cannot navigate path: '{key}' is not a dict"}

    final_key = keys[-1]
    old_value = current.get(final_key, "<not set>") if isinstance(current, dict) else "<not set>"

    if not confirm:
        return {
            "preview": True,
            "key": key_path,
            "old_value": old_value,
            "new_value": parsed_value,
            "message": "Set confirm=True to save this change.",
        }

    if isinstance(current, dict):
        current[final_key] = parsed_value
    else:
        return {"error": f"Cannot set '{final_key}' — parent is not a dict"}

    try:
        _save_settings(settings)
    except Exception as e:
        return {"error": f"Failed to save settings: {e}"}

    # Reload the config singleton so changes take effect
    try:
        ctx.config.reload()
    except Exception:
        pass  # Non-critical — config will reload on next access

    return {"key": key_path, "old_value": old_value, "new_value": parsed_value, "saved": True}


@mcp.tool
def list_config_sections() -> dict:
    """List all top-level sections in settings.yaml.

    Returns:
        Dict with section names and a brief summary of each.
    """
    try:
        settings = _load_settings()
    except Exception as e:
        return {"error": f"Failed to load settings: {e}"}

    sections = []
    for key, value in settings.items():
        summary = {}
        if isinstance(value, dict):
            summary["type"] = "section"
            summary["keys"] = list(value.keys())[:10]  # First 10 keys
            if len(value.keys()) > 10:
                summary["total_keys"] = len(value.keys())
        elif isinstance(value, list):
            summary["type"] = "list"
            summary["length"] = len(value)
        else:
            summary["type"] = type(value).__name__
            summary["value"] = value
        sections.append({"section": key, **summary})

    return {"sections": sections, "count": len(sections)}
