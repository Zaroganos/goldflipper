"""Play file tools — list, get, count, create, modify, move, delete, validate."""

import json
import os
from datetime import datetime

from goldflipper.mcp_server.context import ctx
from goldflipper.mcp_server.server import mcp
from goldflipper.strategy.shared.play_manager import PlayStatus

# Map user-friendly status names to PlayStatus enum
_STATUS_MAP = {
    "new": PlayStatus.NEW,
    "pending-opening": PlayStatus.PENDING_OPENING,
    "pending_opening": PlayStatus.PENDING_OPENING,
    "open": PlayStatus.OPEN,
    "pending-closing": PlayStatus.PENDING_CLOSING,
    "pending_closing": PlayStatus.PENDING_CLOSING,
    "closed": PlayStatus.CLOSED,
    "expired": PlayStatus.EXPIRED,
    "temp": PlayStatus.TEMP,
}


def _resolve_status(status: str) -> PlayStatus:
    """Resolve a user-provided status string to a PlayStatus enum."""
    key = status.strip().lower()
    if key not in _STATUS_MAP:
        valid = ", ".join(sorted(_STATUS_MAP.keys()))
        raise ValueError(f"Unknown status '{status}'. Valid statuses: {valid}")
    return _STATUS_MAP[key]


@mcp.tool
def list_plays(status: str, strategy: str | None = None) -> dict:
    """List play files with a given status.

    Args:
        status: Play status to filter by. One of: new, open, closed, expired,
                pending-opening, pending-closing, temp.
        strategy: Optional strategy name to filter by (e.g., 'option_swings').

    Returns:
        Dict with status, play count, and list of play summaries.
    """
    try:
        play_status = _resolve_status(status)
    except ValueError as e:
        return {"error": str(e)}

    plays = ctx.play_manager.load_plays_by_status(play_status, strategy_name=strategy)

    summaries = []
    for p in plays:
        summaries.append(
            {
                "play_name": p.get("play_name", "unknown"),
                "symbol": p.get("symbol", "?"),
                "strategy": p.get("strategy", "?"),
                "trade_type": p.get("trade_type", "?"),
                "action": p.get("action", "?"),
                "play_status": p.get("status", {}).get("play_status", "?"),
                "file": os.path.basename(p.get("_play_file", "")),
            }
        )

    return {"status": status, "count": len(summaries), "plays": summaries}


@mcp.tool
def get_play(play_name: str) -> dict:
    """Load and return the full JSON data for a specific play file.

    Searches across all status folders for a play matching the given name.

    Args:
        play_name: The play name or filename (with or without .json extension).

    Returns:
        The complete play data dictionary, or an error.
    """
    filename = play_name if play_name.endswith(".json") else f"{play_name}.json"

    # Search all status folders
    for status in PlayStatus:
        play_files = ctx.play_manager.list_plays(status)
        for pf in play_files:
            if os.path.basename(pf) == filename:
                data = ctx.play_manager.load_play(pf)
                if data is not None:
                    data["_source_folder"] = PlayStatus.to_folder_name(status)
                    data["_file_path"] = pf
                    return data

    return {"error": f"Play '{play_name}' not found in any status folder"}


@mcp.tool
def count_plays_by_status() -> dict:
    """Count the number of play files in each status folder.

    Returns:
        Dict mapping each status to its play count, plus a total.
    """
    counts = {}
    total = 0
    for status in PlayStatus:
        play_files = ctx.play_manager.list_plays(status)
        name = PlayStatus.to_folder_name(status)
        counts[name] = len(play_files)
        total += len(play_files)

    counts["total"] = total
    return counts


# =========================================================================
# Phase 2: Write Operations
# =========================================================================


def _find_play_file(play_name: str) -> tuple[str | None, PlayStatus | None]:
    """Find a play file across all status folders. Returns (path, status) or (None, None)."""
    filename = play_name if play_name.endswith(".json") else f"{play_name}.json"
    for status in PlayStatus:
        for pf in ctx.play_manager.list_plays(status):
            if os.path.basename(pf) == filename:
                return pf, status
    return None, None


@mcp.tool
def create_play(
    symbol: str,
    trade_type: str,
    strike_price: float,
    expiration_date: str,
    contracts: int,
    entry_order_type: str = "limit at bid",
    entry_stock_price: float = 0.0,
    take_profit_premium_pct: float = 50.0,
    stop_loss_premium_pct: float = 25.0,
    stop_loss_type: str = "STOP",
    strategy: str = "option_swings",
    action: str = "BTO",
) -> dict:
    """Create a new play JSON file in the plays/new/ folder.

    Args:
        symbol: Stock ticker (e.g., 'AAPL', 'SPY').
        trade_type: 'CALL' or 'PUT'.
        strike_price: Option strike price.
        expiration_date: Option expiration in MM/DD/YYYY format.
        contracts: Number of contracts.
        entry_order_type: Order type for entry. One of: market, limit at bid,
                          limit at ask, limit at mid, limit at last.
        entry_stock_price: Target stock price for entry trigger (0 = any).
        take_profit_premium_pct: Take profit as % of entry premium (e.g., 50 = +50%).
        stop_loss_premium_pct: Stop loss as % of entry premium (e.g., 25 = -25%).
        stop_loss_type: 'STOP', 'LIMIT', or 'CONTINGENCY'.
        strategy: Strategy name (e.g., 'option_swings', 'momentum').
        action: Order action: 'BTO', 'STC', 'STO', 'BTC'.

    Returns:
        Dict with play_name and file_path of the created play, or error.
    """
    trade_type = trade_type.upper()
    if trade_type not in ("CALL", "PUT"):
        return {"error": "trade_type must be 'CALL' or 'PUT'"}

    valid_order_types = ["market", "limit at bid", "limit at ask", "limit at mid", "limit at last"]
    if entry_order_type not in valid_order_types:
        return {"error": f"entry_order_type must be one of: {', '.join(valid_order_types)}"}

    if stop_loss_type not in ("STOP", "LIMIT", "CONTINGENCY"):
        return {"error": "stop_loss_type must be 'STOP', 'LIMIT', or 'CONTINGENCY'"}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    play_name = f"{symbol}{expiration_date.replace('/', '')}{'C' if trade_type == 'CALL' else 'P'}{int(strike_price * 1000):08d}_{timestamp}"

    play_data = {
        "creator": "mcp",
        "play_name": play_name,
        "symbol": symbol.upper(),
        "trade_type": trade_type,
        "strike_price": str(strike_price),
        "expiration_date": expiration_date,
        "contracts": contracts,
        "strategy": strategy,
        "action": action.upper(),
        "creation_date": datetime.now().strftime("%m/%d/%Y"),
        "play_class": "SIMPLE",
        "entry_point": {
            "stock_price": entry_stock_price,
            "order_type": entry_order_type,
            "entry_premium": 0.0,
            "entry_stock_price": 0.0,
        },
        "take_profit": {
            "TP_type": "Single",
            "premium_pct": take_profit_premium_pct,
            "order_type": "limit at bid",
            "TP_option_prem": 0.0,
        },
        "stop_loss": {
            "SL_type": stop_loss_type,
            "premium_pct": stop_loss_premium_pct,
            "order_type": "market",
            "SL_option_prem": 0.0,
        },
        "status": {
            "play_status": "NEW",
            "order_id": None,
            "order_status": None,
            "position_exists": False,
        },
        "logging": {},
    }

    # Write to new/ folder
    new_dir = ctx.play_manager.get_plays_dir(PlayStatus.NEW)
    file_path = os.path.join(new_dir, f"{play_name}.json")

    try:
        from goldflipper.utils.atomic_io import atomic_write_json

        atomic_write_json(file_path, play_data, indent=4)
    except Exception as e:
        return {"error": f"Failed to write play file: {e}"}

    return {"play_name": play_name, "file_path": file_path, "status": "created in plays/new/"}


@mcp.tool
def modify_play(play_name: str, updates: str) -> dict:
    """Modify fields in an existing play file.

    Args:
        play_name: The play name or filename.
        updates: JSON string of fields to update. Supports dot-notation for nested
                 fields (e.g., '{"take_profit.premium_pct": 60, "contracts": 2}').

    Returns:
        Dict with updated fields or error.
    """
    file_path, status = _find_play_file(play_name)
    if file_path is None:
        return {"error": f"Play '{play_name}' not found"}

    try:
        update_dict = json.loads(updates)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in updates: {e}"}

    data = ctx.play_manager.load_play(file_path)
    if data is None:
        return {"error": "Failed to load play file"}

    changed = []
    for key, value in update_dict.items():
        parts = key.split(".")
        target = data
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        changed.append(key)

    ok = ctx.play_manager.save_play(data, file_path, atomic=True)
    if not ok:
        return {"error": "Failed to save play file"}

    return {"play_name": play_name, "modified_fields": changed}


@mcp.tool
def move_play(play_name: str, target_status: str, confirm: bool = False) -> dict:
    """Move a play to a different status folder.

    This is a Tier 3 operation. With confirm=False (default), returns a preview.
    With confirm=True, executes the move.

    Args:
        play_name: The play name or filename.
        target_status: Target status (new, open, closed, expired, pending-opening,
                       pending-closing, temp).
        confirm: Set to True to actually execute the move.

    Returns:
        Preview of the move (confirm=False) or result of the move (confirm=True).
    """
    file_path, current_status = _find_play_file(play_name)
    if file_path is None:
        return {"error": f"Play '{play_name}' not found"}

    try:
        new_status = _resolve_status(target_status)
    except ValueError as e:
        return {"error": str(e)}

    current_name = PlayStatus.to_folder_name(current_status) if current_status else "unknown"
    target_name = PlayStatus.to_folder_name(new_status)

    if not confirm:
        return {
            "preview": True,
            "play_name": play_name,
            "current_status": current_name,
            "target_status": target_name,
            "message": f"Would move play from '{current_name}' to '{target_name}'. Set confirm=True to execute.",
        }

    try:
        new_path = ctx.play_manager.move_play(file_path, new_status)
    except Exception as e:
        return {"error": f"Move failed: {e}"}

    return {"play_name": play_name, "moved_from": current_name, "moved_to": target_name, "new_path": new_path}


@mcp.tool
def delete_play(play_name: str, confirm: bool = False) -> dict:
    """Delete a play file permanently.

    Args:
        play_name: The play name or filename.
        confirm: Set to True to actually delete. Default False returns a preview.

    Returns:
        Preview or confirmation of deletion.
    """
    file_path, status = _find_play_file(play_name)
    if file_path is None:
        return {"error": f"Play '{play_name}' not found"}

    status_name = PlayStatus.to_folder_name(status) if status else "unknown"

    if not confirm:
        return {
            "preview": True,
            "play_name": play_name,
            "status": status_name,
            "file_path": file_path,
            "message": "Would permanently delete this play file. Set confirm=True to execute.",
        }

    try:
        os.remove(file_path)
    except Exception as e:
        return {"error": f"Delete failed: {e}"}

    return {"play_name": play_name, "deleted": True, "was_in": status_name}


@mcp.tool
def validate_play(play_data: str) -> dict:
    """Validate a play's JSON structure without saving it.

    Args:
        play_data: JSON string of the play data to validate.

    Returns:
        Dict with valid=True/False and any validation errors.
    """
    try:
        data = json.loads(play_data)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"]}

    errors = []
    required = ["symbol", "trade_type", "strike_price", "expiration_date", "contracts"]
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if data.get("trade_type", "").upper() not in ("CALL", "PUT", ""):
        errors.append("trade_type must be 'CALL' or 'PUT'")

    if "entry_point" not in data:
        errors.append("Missing 'entry_point' section")
    elif "order_type" not in data.get("entry_point", {}):
        errors.append("Missing 'entry_point.order_type'")
    else:
        valid_types = ["market", "limit at bid", "limit at ask", "limit at mid", "limit at last"]
        if data["entry_point"]["order_type"] not in valid_types:
            errors.append(f"entry_point.order_type must be one of: {', '.join(valid_types)}")

    if "take_profit" not in data:
        errors.append("Missing 'take_profit' section")
    if "stop_loss" not in data:
        errors.append("Missing 'stop_loss' section")

    return {"valid": len(errors) == 0, "errors": errors}
