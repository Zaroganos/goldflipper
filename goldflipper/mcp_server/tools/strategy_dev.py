"""Strategy development tools — playbooks, strategy code, scaffolding."""

import os

import yaml

from goldflipper.mcp_server.server import mcp


def _get_playbooks_dir() -> str:
    """Get the base playbooks directory path."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "strategy", "playbooks")


def _get_runners_dir() -> str:
    """Get the strategy runners directory path."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "strategy", "runners")


@mcp.tool
def list_playbooks(strategy: str | None = None) -> dict:
    """List available playbook YAML files, optionally filtered by strategy.

    Args:
        strategy: Optional strategy name (e.g., 'option_swings', 'momentum').
                  If omitted, lists playbooks for all strategies.

    Returns:
        Dict with list of playbooks grouped by strategy.
    """
    playbooks_dir = _get_playbooks_dir()

    if not os.path.isdir(playbooks_dir):
        return {"error": f"Playbooks directory not found: {playbooks_dir}"}

    result = {}

    if strategy:
        strategy_dir = os.path.join(playbooks_dir, strategy)
        if not os.path.isdir(strategy_dir):
            return {"error": f"No playbooks directory for strategy '{strategy}'"}
        dirs_to_scan = [(strategy, strategy_dir)]
    else:
        dirs_to_scan = []
        for name in sorted(os.listdir(playbooks_dir)):
            path = os.path.join(playbooks_dir, name)
            if os.path.isdir(path):
                dirs_to_scan.append((name, path))

    for strat_name, strat_dir in dirs_to_scan:
        playbooks = []
        for filename in sorted(os.listdir(strat_dir)):
            if filename.endswith((".yaml", ".yml")):
                filepath = os.path.join(strat_dir, filename)
                try:
                    with open(filepath) as f:
                        data = yaml.safe_load(f) or {}
                    playbooks.append(
                        {
                            "filename": filename,
                            "name": data.get("name", filename),
                            "status": data.get("status", "unknown"),
                            "description": (data.get("description", "") or "")[:200],
                        }
                    )
                except Exception:
                    playbooks.append({"filename": filename, "name": filename, "status": "error", "description": "Failed to parse"})
        result[strat_name] = playbooks

    total = sum(len(v) for v in result.values())
    return {"strategies": result, "total_playbooks": total}


@mcp.tool
def get_playbook(strategy: str, name: str) -> dict:
    """Get the full contents of a playbook YAML file.

    Args:
        strategy: Strategy name (e.g., 'option_swings').
        name: Playbook filename (with or without .yaml extension).

    Returns:
        Dict with the parsed playbook data, or error.
    """
    filename = name if name.endswith((".yaml", ".yml")) else f"{name}.yaml"
    filepath = os.path.join(_get_playbooks_dir(), strategy, filename)

    if not os.path.isfile(filepath):
        return {"error": f"Playbook not found: {strategy}/{filename}"}

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {"error": f"Failed to parse playbook: {e}"}

    data["_file_path"] = filepath
    data["_strategy"] = strategy
    return data


@mcp.tool
def create_playbook(strategy: str, name: str, playbook_yaml: str) -> dict:
    """Create a new playbook YAML file for a strategy.

    Args:
        strategy: Strategy name (e.g., 'option_swings', 'momentum', 'sell_puts').
        name: Playbook name (used as filename, without extension).
        playbook_yaml: Full YAML content for the playbook.

    Returns:
        Dict with created file path, or error.
    """
    strategy_dir = os.path.join(_get_playbooks_dir(), strategy)

    if not os.path.isdir(strategy_dir):
        try:
            os.makedirs(strategy_dir, exist_ok=True)
        except Exception as e:
            return {"error": f"Failed to create strategy playbook directory: {e}"}

    filename = name if name.endswith((".yaml", ".yml")) else f"{name}.yaml"
    filepath = os.path.join(strategy_dir, filename)

    if os.path.exists(filepath):
        return {"error": f"Playbook already exists: {strategy}/{filename}. Use modify_playbook to update it."}

    # Validate the YAML
    try:
        yaml.safe_load(playbook_yaml)
    except yaml.YAMLError as e:
        return {"error": f"Invalid YAML: {e}"}

    try:
        with open(filepath, "w") as f:
            f.write(playbook_yaml)
    except Exception as e:
        return {"error": f"Failed to write playbook: {e}"}

    return {"created": True, "strategy": strategy, "filename": filename, "file_path": filepath}


@mcp.tool
def modify_playbook(strategy: str, name: str, updates_yaml: str) -> dict:
    """Modify an existing playbook by merging YAML updates into it.

    Args:
        strategy: Strategy name (e.g., 'option_swings').
        name: Playbook filename (with or without .yaml extension).
        updates_yaml: YAML string of fields to update. These are merged into the
                      existing playbook (top-level keys are replaced).

    Returns:
        Dict with modified fields, or error.
    """
    filename = name if name.endswith((".yaml", ".yml")) else f"{name}.yaml"
    filepath = os.path.join(_get_playbooks_dir(), strategy, filename)

    if not os.path.isfile(filepath):
        return {"error": f"Playbook not found: {strategy}/{filename}"}

    # Load existing
    try:
        with open(filepath) as f:
            existing = yaml.safe_load(f) or {}
    except Exception as e:
        return {"error": f"Failed to load playbook: {e}"}

    # Parse updates
    try:
        updates = yaml.safe_load(updates_yaml) or {}
    except yaml.YAMLError as e:
        return {"error": f"Invalid YAML in updates: {e}"}

    if not isinstance(updates, dict):
        return {"error": "Updates must be a YAML mapping (key-value pairs)"}

    # Deep merge: for top-level dict values, merge; otherwise replace
    def deep_merge(base, overlay):
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value

    deep_merge(existing, updates)

    try:
        with open(filepath, "w") as f:
            yaml.dump(existing, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        return {"error": f"Failed to save playbook: {e}"}

    return {"modified": True, "strategy": strategy, "filename": filename, "updated_keys": list(updates.keys())}


@mcp.tool
def get_strategy_code(strategy_name: str) -> dict:
    """Get the source code of a strategy runner module.

    Args:
        strategy_name: Strategy module name (e.g., 'option_swings', 'momentum', 'sell_puts').

    Returns:
        Dict with the strategy source code, or error.
    """
    runners_dir = _get_runners_dir()
    filepath = os.path.join(runners_dir, f"{strategy_name}.py")

    if not os.path.isfile(filepath):
        return {"error": f"Strategy runner not found: {strategy_name}.py"}

    try:
        with open(filepath) as f:
            source = f.read()
    except Exception as e:
        return {"error": f"Failed to read strategy file: {e}"}

    return {
        "strategy_name": strategy_name,
        "file_path": filepath,
        "line_count": source.count("\n") + 1,
        "source": source,
    }


@mcp.tool
def get_strategy_template() -> dict:
    """Get a template for creating a new strategy runner.

    Returns the BaseStrategy interface and a skeleton implementation
    that can be used as a starting point for a new strategy.

    Returns:
        Dict with template code and instructions.
    """
    template = '''"""
{StrategyName} Strategy Runner for Goldflipper

Implements the BaseStrategy interface for {description}.
"""

import logging
from typing import Dict, Any, List, Optional

from goldflipper.strategy.base import BaseStrategy, OrderAction
from goldflipper.strategy.registry import register_strategy


@register_strategy('{strategy_key}')
class {ClassName}(BaseStrategy):
    """
    {description}
    """

    def get_name(self) -> str:
        return "{strategy_key}"

    def is_enabled(self) -> bool:
        return self.config.get('{config_key}', 'enabled', default=False)

    def get_playbook_dir(self) -> str:
        import os
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "playbooks", "{strategy_key}"
        )

    def on_cycle_start(self) -> None:
        """Called at the start of each evaluation cycle."""
        pass

    def evaluate_new_plays(self, plays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate new plays for entry conditions.

        Args:
            plays: List of play dicts from plays/new/ folder.

        Returns:
            List of plays that should be opened (entry order placed).
        """
        entries = []
        for play in plays:
            # TODO: Implement entry evaluation logic
            pass
        return entries

    def evaluate_open_plays(self, plays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate open plays for exit conditions (TP/SL).

        Args:
            plays: List of play dicts from plays/open/ folder.

        Returns:
            List of plays that should be closed (exit order placed).
        """
        exits = []
        for play in plays:
            # TODO: Implement exit evaluation logic
            pass
        return exits

    def on_cycle_end(self) -> None:
        """Called at the end of each evaluation cycle."""
        pass
'''

    instructions = (
        "To create a new strategy:\n"
        "1. Replace placeholders ({StrategyName}, {strategy_key}, {ClassName}, etc.)\n"
        "2. Save to goldflipper/strategy/runners/{strategy_key}.py\n"
        "3. Add '{strategy_key}' to runner_modules list in strategy/registry.py\n"
        "4. Add config section to config/settings.yaml\n"
        "5. Create a playbooks directory at strategy/playbooks/{strategy_key}/\n"
        "6. Add a default.yaml playbook"
    )

    return {"template": template, "instructions": instructions}


@mcp.tool
def list_runner_modules() -> dict:
    """List all registered strategy runner modules and their files.

    Returns:
        Dict with known runner modules, which exist on disk, and which are registered.
    """
    from goldflipper.strategy.registry import StrategyRegistry

    runners_dir = _get_runners_dir()

    # Known modules from registry.py
    known_modules = ["option_swings", "option_swings_auto", "momentum", "sell_puts", "spreads"]

    modules = []
    for mod_name in known_modules:
        filepath = os.path.join(runners_dir, f"{mod_name}.py")
        modules.append(
            {
                "module": mod_name,
                "file_exists": os.path.isfile(filepath),
                "registered": StrategyRegistry.is_registered(mod_name),
            }
        )

    # Also check for any .py files in runners/ not in the known list
    if os.path.isdir(runners_dir):
        for filename in sorted(os.listdir(runners_dir)):
            if filename.endswith(".py") and filename != "__init__.py":
                mod_name = filename[:-3]
                if mod_name not in known_modules:
                    modules.append(
                        {
                            "module": mod_name,
                            "file_exists": True,
                            "registered": StrategyRegistry.is_registered(mod_name),
                            "note": "Not in known runner_modules list",
                        }
                    )

    return {"runner_modules": modules, "count": len(modules)}
