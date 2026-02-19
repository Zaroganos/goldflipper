"""
Play Manager Module for Goldflipper Multi-Strategy System

This module provides centralized play file management including:
- Moving plays between status folders (new, open, closed, etc.)
- Saving and loading play data
- Account-aware directory routing for multi-account support

The module extracts and consolidates play file operations from core.py,
maintaining backward compatibility while enabling strategy-specific handling.

Usage:
    from goldflipper.strategy.shared.play_manager import PlayManager, save_play, move_play_to_open

    # Using class-based interface
    manager = PlayManager()
    manager.move_to_open(play_file)

    # Using standalone functions (backward compatible)
    move_play_to_open(play_file)
    save_play(play, play_file)
"""

import json
import logging
import os
from enum import Enum
from typing import Any
from uuid import UUID

from goldflipper.utils.atomic_io import atomic_write_json
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.utils.exe_utils import get_plays_dir as exe_get_plays_dir

# ==================================================
# JSON Encoder for Play Data
# ==================================================


class UUIDEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle UUID objects and pandas Series.

    Supports serialization of:
    - UUID objects -> string
    - Pandas Series/numpy values -> native Python types
    """

    def default(self, o):
        if isinstance(o, UUID):
            return str(o)
        if hasattr(o, "item"):  # Handle pandas Series/numpy values
            return o.item()
        return json.JSONEncoder.default(self, o)


# ==================================================
# Play Status Enum
# ==================================================


class PlayStatus(Enum):
    """
    Standard play status values used across all strategies.
    Maps to folder structure in plays/ directory.
    """

    NEW = "NEW"
    PENDING_OPENING = "PENDING-OPENING"
    OPEN = "OPEN"
    PENDING_CLOSING = "PENDING-CLOSING"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    TEMP = "TEMP"

    @classmethod
    def to_folder_name(cls, status: "PlayStatus") -> str:
        """Convert status enum to folder name."""
        folder_map = {
            cls.NEW: "new",
            cls.PENDING_OPENING: "pending-opening",
            cls.OPEN: "open",
            cls.PENDING_CLOSING: "pending-closing",
            cls.CLOSED: "closed",
            cls.EXPIRED: "expired",
            cls.TEMP: "temp",
        }
        return folder_map.get(status, status.value.lower())


# ==================================================
# Play Manager Class
# ==================================================


class PlayManager:
    """
    Centralized manager for play file operations.

    Handles moving plays between folders, saving/loading play data,
    and provides account-aware routing for multi-account setups.

    Directory Structure:
        plays/
        ├── account_1/                    # Live account
        │   ├── shared/                   # Shared pool (legacy/cross-strategy)
        │   │   ├── new/
        │   │   ├── open/
        │   │   └── ...
        │   ├── option_swings/            # Strategy-specific (future)
        │   └── ...
        ├── account_2/                    # Paper account 1
        │   └── ...
        └── ...

    Attributes:
        logger: Logger instance for this module
        _account_name: Account name for this manager instance
        _strategy: Strategy name for directory routing
    """

    def __init__(self, account_name: str | None = None, strategy: str = "shared", plays_base_dir: str | None = None):
        """
        Initialize the PlayManager.

        Args:
            account_name: Account name for routing (e.g., 'live', 'paper_1').
                          If None, uses the active account from config.
            strategy: Strategy name for directory routing. Default is "shared".
            plays_base_dir: Override for plays directory. If None, uses default.
        """
        self.logger = logging.getLogger(__name__)
        self._account_name = account_name  # None means use active account
        self._strategy = strategy

        if plays_base_dir:
            self._plays_base_dir = plays_base_dir
        else:
            # Use exe-aware path for plays directory (persists next to exe in frozen mode)
            self._plays_base_dir = str(exe_get_plays_dir(account_name=account_name, strategy=strategy))

    @property
    def plays_base_dir(self) -> str:
        """Get the base directory for plays."""
        return self._plays_base_dir

    # =========================================================================
    # Play File Operations
    # =========================================================================

    def save_play(self, play: dict[str, Any], play_file: str, atomic: bool = False) -> bool:
        """
        Save play data to the specified file.

        Args:
            play: Play data dictionary
            play_file: Path to the play file
            atomic: If True, use atomic write (safer but slightly slower)

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            if atomic:
                atomic_write_json(play_file, play, indent=4, encoder=UUIDEncoder)
            else:
                with open(play_file, "w") as f:
                    json.dump(play, f, indent=4, cls=UUIDEncoder)

            self.logger.info(f"Play data saved to {play_file}")
            display.success(f"Play data saved to {play_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving play data to {play_file}: {e}")
            display.error(f"Error saving play data to {play_file}: {e}")
            return False

    def load_play(self, play_file: str) -> dict[str, Any] | None:
        """
        Load play data from file.

        Args:
            play_file: Path to the play file

        Returns:
            Play data dictionary or None if load failed
        """
        try:
            with open(play_file) as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading play from {play_file}: {e}")
            return None

    def move_play(self, play_file: str, target_status: PlayStatus, status_updates: dict[str, Any] | None = None) -> str | None:
        """
        Move a play file to the target status folder and update its status.

        This is the core move operation used by all status-specific move functions.

        Args:
            play_file: Current path to the play file
            target_status: Target PlayStatus enum value
            status_updates: Optional additional status fields to update

        Returns:
            New file path if move successful, None otherwise

        Raises:
            Exception: If file operations fail (re-raised for caller handling)
        """
        try:
            # Load current play data
            with open(play_file) as f:
                play_data = json.load(f)

            # Ensure status object exists
            if "status" not in play_data:
                play_data["status"] = {}

            # Update play status
            play_data["status"]["play_status"] = target_status.value

            # Apply additional status updates if provided
            if status_updates:
                play_data["status"].update(status_updates)

            # Calculate new path
            target_folder = PlayStatus.to_folder_name(target_status)
            target_dir = os.path.join(os.path.dirname(os.path.dirname(play_file)), target_folder)
            os.makedirs(target_dir, exist_ok=True)
            new_path = os.path.join(target_dir, os.path.basename(play_file))

            # Save updated status to original location first
            with open(play_file, "w") as f:
                json.dump(play_data, f, indent=4, cls=UUIDEncoder)

            # Move file only if it's not already in the target directory
            if os.path.dirname(play_file) != target_dir:
                if os.path.exists(new_path):
                    os.remove(new_path)  # Remove any existing file at destination
                os.rename(play_file, new_path)
                self.logger.info(f"Moved play to {target_status.value} folder: {new_path}")

            return new_path

        except Exception as e:
            self.logger.error(f"Error moving play to {target_status.value}: {str(e)}")
            display.error(f"Error designating play as {target_status.value}: {str(e)}")
            raise

    # =========================================================================
    # Status-Specific Move Operations
    # =========================================================================

    def move_to_new(self, play_file: str) -> str | None:
        """
        Move play to NEW folder (for OTO triggered plays).

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(play_file, PlayStatus.NEW)

    def move_to_pending_opening(self, play_file: str) -> str | None:
        """
        Move play to PENDING-OPENING folder.
        (For plays whose BUY condition has hit but limit order has not yet been filled)

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(play_file, PlayStatus.PENDING_OPENING)

    def move_to_open(self, play_file: str) -> str | None:
        """
        Move play to OPEN folder.

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(play_file, PlayStatus.OPEN)

    def move_to_pending_closing(self, play_file: str) -> str | None:
        """
        Move play to PENDING-CLOSING folder.
        (For plays whose SELL condition has hit but limit order has not yet been filled)

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(play_file, PlayStatus.PENDING_CLOSING)

    def move_to_closed(self, play_file: str) -> str | None:
        """
        Move play to CLOSED folder (for plays whose TP or SL condition has hit).

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(play_file, PlayStatus.CLOSED, status_updates={"position_exists": False})

    def move_to_expired(self, play_file: str) -> str | None:
        """
        Move play to EXPIRED folder (for plays which have expired, and OCO triggered plays).

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(
            play_file,
            PlayStatus.EXPIRED,
            status_updates={
                "position_exists": False,
                "order_id": None,
                "order_status": None,
                "closing_order_id": None,
                "closing_order_status": None,
            },
        )

    def move_to_temp(self, play_file: str) -> str | None:
        """
        Move play to TEMP folder (for plays recycled by OCO or held for later activation).

        Args:
            play_file: Path to the play file

        Returns:
            New file path if successful
        """
        return self.move_play(
            play_file,
            PlayStatus.TEMP,
            status_updates={
                "position_exists": False,
                "order_id": None,
                "order_status": None,
                "closing_order_id": None,
                "closing_order_status": None,
            },
        )

    # =========================================================================
    # Play Directory Operations
    # =========================================================================

    def get_plays_dir(self, status: PlayStatus, strategy_name: str | None = None, account_name: str | None = None) -> str:
        """
        Get the directory path for plays with the given status.

        Args:
            status: PlayStatus enum value
            strategy_name: Optional strategy name override for strategy-specific dirs
            account_name: Optional account name override for account-based routing

        Returns:
            Full path to the plays directory:
            plays/{account_dir}/{strategy}/{status_folder}/
        """
        folder = PlayStatus.to_folder_name(status)

        # Use provided overrides or fall back to instance defaults
        strategy = strategy_name if strategy_name else self._strategy
        account = account_name if account_name else self._account_name

        # Get the base plays directory for this account/strategy
        base_dir = str(exe_get_plays_dir(account_name=account, strategy=strategy))

        # Build full path with status folder
        full_path = os.path.join(base_dir, folder)
        os.makedirs(full_path, exist_ok=True)

        return full_path

    def list_plays(self, status: PlayStatus, strategy_name: str | None = None) -> list[str]:
        """
        List all play files with the given status.

        Args:
            status: PlayStatus enum value to filter by
            strategy_name: Optional strategy filter

        Returns:
            List of play file paths
        """
        plays_dir = self.get_plays_dir(status, strategy_name)

        if not os.path.exists(plays_dir):
            return []

        return [os.path.join(plays_dir, f) for f in os.listdir(plays_dir) if f.endswith(".json")]

    def load_plays_by_status(self, status: PlayStatus, strategy_name: str | None = None) -> list[dict[str, Any]]:
        """
        Load all plays with the given status.

        Args:
            status: PlayStatus enum value to filter by
            strategy_name: Optional strategy filter

        Returns:
            List of play data dictionaries (with '_play_file' key added)
        """
        plays = []

        for play_file in self.list_plays(status, strategy_name):
            play_data = self.load_play(play_file)
            if play_data:
                play_data["_play_file"] = play_file
                plays.append(play_data)

        return plays


# ==================================================
# Standalone Functions (Backward Compatibility)
# ==================================================
# These functions provide backward compatibility with existing core.py usage.
# They delegate to a shared PlayManager instance.

# Shared manager instance for standalone functions
_default_manager: PlayManager | None = None


def _get_default_manager() -> PlayManager:
    """Get or create the default PlayManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = PlayManager()
    return _default_manager


def save_play(play: dict[str, Any], play_file: str) -> None:
    """
    Save the updated play data to the specified file.

    Backward-compatible function wrapping PlayManager.save_play().

    Args:
        play: Play data dictionary
        play_file: Path to the play file
    """
    manager = _get_default_manager()
    manager.save_play(play, play_file, atomic=False)


def save_play_improved(play: dict[str, Any], play_file: str) -> bool:
    """
    Improved atomic save for play data.

    Backward-compatible function wrapping PlayManager.save_play() with atomic=True.

    Args:
        play: Play data dictionary
        play_file: Path to the play file

    Returns:
        bool: True if save successful, False otherwise
    """
    manager = _get_default_manager()
    return manager.save_play(play, play_file, atomic=True)


def move_play_to_new(play_file: str) -> str | None:
    """
    Move play to NEW folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_new().
    """
    return _get_default_manager().move_to_new(play_file)


def move_play_to_pending_opening(play_file: str) -> str | None:
    """
    Move play to PENDING-OPENING folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_pending_opening().
    """
    return _get_default_manager().move_to_pending_opening(play_file)


def move_play_to_open(play_file: str) -> str | None:
    """
    Move play to OPEN folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_open().
    """
    return _get_default_manager().move_to_open(play_file)


def move_play_to_pending_closing(play_file: str) -> str | None:
    """
    Move play to PENDING-CLOSING folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_pending_closing().
    """
    return _get_default_manager().move_to_pending_closing(play_file)


def move_play_to_closed(play_file: str) -> str | None:
    """
    Move play to CLOSED folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_closed().
    """
    return _get_default_manager().move_to_closed(play_file)


def move_play_to_expired(play_file: str) -> str | None:
    """
    Move play to EXPIRED folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_expired().
    """
    return _get_default_manager().move_to_expired(play_file)


def move_play_to_temp(play_file: str) -> str | None:
    """
    Move play to TEMP folder and update status.

    Backward-compatible function wrapping PlayManager.move_to_temp().
    """
    return _get_default_manager().move_to_temp(play_file)
